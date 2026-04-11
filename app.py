import os
import uuid
import datetime
from flask import Flask, jsonify, request, send_file, render_template, session
from models import (
    db, ADUser, Ticket, TicketNote, Computer, Department,
    seed_environment, generate_tickets as generate_ticket_objects,
    create_ticket, add_ticket_note,
    manual_password_reset, manual_account_unlock, manual_new_hire,
    fix_hardware, fix_network, install_software,
    export_users_to_csv,
)
import io

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
app.permanent_session_lifetime = datetime.timedelta(days=90)
app.instance_path = os.path.join(os.path.dirname(__file__), 'instance')
os.makedirs(app.instance_path, exist_ok=True)

database_url = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(app.instance_path, 'it_helpdesk.db'))
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()


def get_session_id():
    """Return the visitor's session UUID, seeding the environment if it doesn't exist yet."""
    session.permanent = True
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    sid = session['sid']
    # Seed if missing — handles new visitors and database wipes (e.g. Render redeploys)
    if Department.query.filter_by(session_id=sid).count() == 0:
        seed_environment(sid)
    return sid


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    get_session_id()   # ensure cookie + environment exist on first load
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    return jsonify({'status': 'OK'})


@app.route('/api/users')
def get_users():
    sid = get_session_id()
    users = ADUser.query.filter_by(session_id=sid).all()
    return jsonify([u.to_dict() for u in users])


@app.route('/api/user/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    sid = get_session_id()
    user = ADUser.query.filter_by(id=user_id, session_id=sid).first_or_404()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    if 'full_name' in data and data['full_name'].strip():
        user.full_name = data['full_name'].strip()
    if 'department' in data:
        user.department = data['department']
    if 'email' in data and data['email'].strip():
        user.email = data['email'].strip()
    if 'password' in data and data['password'].strip():
        user.password = data['password'].strip()
    if 'is_locked' in data:
        user.is_locked = bool(data['is_locked'])
    if 'groups' in data:
        user.groups = data['groups'].strip()
    db.session.commit()
    return jsonify(user.to_dict())


@app.route('/api/tickets')
def get_tickets():
    sid = get_session_id()
    tickets = Ticket.query.filter_by(session_id=sid).order_by(Ticket.created_at.desc()).all()
    return jsonify([t.to_dict() for t in tickets])


@app.route('/api/tickets/generate', methods=['POST'])
def generate_tickets():
    sid = get_session_id()
    data = request.get_json(silent=True) or {}
    count = max(1, int(data.get('count', 5)))
    new_tickets = generate_ticket_objects(count, sid)
    return jsonify([t.to_dict() for t in new_tickets])


@app.route('/api/tickets/create', methods=['POST'])
def create_ticket_endpoint():
    sid = get_session_id()
    data = request.get_json()
    required = ('title', 'description', 'category', 'priority', 'user_affected')
    if not data or any(k not in data for k in required):
        return jsonify({'error': f'Required fields: {", ".join(required)}'}), 400
    ticket = create_ticket(
        title=data['title'], description=data['description'],
        category=data['category'], priority=data['priority'],
        user_affected=data['user_affected'], session_id=sid,
        assigned_to=data.get('assigned_to'),
    )
    return jsonify(ticket.to_dict()), 201


@app.route('/api/tickets/clear', methods=['DELETE'])
def clear_tickets():
    sid = get_session_id()
    ticket_ids = [t.id for t in Ticket.query.filter_by(session_id=sid).all()]
    if ticket_ids:
        TicketNote.query.filter(TicketNote.ticket_id.in_(ticket_ids)).delete(synchronize_session=False)
    Ticket.query.filter_by(session_id=sid).delete()
    for computer in Computer.query.filter_by(session_id=sid).all():
        computer.status = 'Online'
        if computer.original_ip:
            computer.ip_address = computer.original_ip
    for user in ADUser.query.filter_by(session_id=sid).all():
        user.is_locked = False
    db.session.commit()
    return jsonify({'message': 'All tickets cleared'})


@app.route('/api/ticket/<int:ticket_id>/notes', methods=['GET'])
def get_ticket_notes(ticket_id):
    sid = get_session_id()
    Ticket.query.filter_by(id=ticket_id, session_id=sid).first_or_404()
    notes = TicketNote.query.filter_by(ticket_id=ticket_id).order_by(TicketNote.created_at).all()
    return jsonify([n.to_dict() for n in notes])


@app.route('/api/ticket/<int:ticket_id>/note', methods=['POST'])
def add_note(ticket_id):
    sid = get_session_id()
    Ticket.query.filter_by(id=ticket_id, session_id=sid).first_or_404()
    data = request.get_json()
    if not data or 'body' not in data:
        return jsonify({'error': 'body required'}), 400
    note = add_ticket_note(ticket_id, data.get('author', 'Technician'), data['body'])
    return jsonify(note.to_dict()), 201


@app.route('/api/ticket/<int:ticket_id>/status', methods=['POST'])
def update_ticket_status(ticket_id):
    sid = get_session_id()
    ticket = Ticket.query.filter_by(id=ticket_id, session_id=sid).first_or_404()
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({'error': 'status required'}), 400
    allowed = {'Open', 'In Progress', 'Resolved'}
    if data['status'] not in allowed:
        return jsonify({'error': f'status must be one of {allowed}'}), 400
    ticket.status = data['status']
    db.session.commit()
    return jsonify(ticket.to_dict())


@app.route('/api/ticket/<int:ticket_id>/assign', methods=['POST'])
def assign_ticket(ticket_id):
    sid = get_session_id()
    ticket = Ticket.query.filter_by(id=ticket_id, session_id=sid).first_or_404()
    data = request.get_json()
    if not data or 'assignee' not in data:
        return jsonify({'error': 'assignee required'}), 400
    ticket.assigned_to = data['assignee'] or None
    db.session.commit()
    return jsonify(ticket.to_dict())


@app.route('/api/ticket/<int:ticket_id>/resolve', methods=['POST'])
def resolve_ticket(ticket_id):
    sid = get_session_id()
    ticket = Ticket.query.filter_by(id=ticket_id, session_id=sid).first_or_404()
    ticket.status = 'Resolved'
    db.session.commit()
    return jsonify({'message': 'Ticket resolved'})


@app.route('/api/ticket/<int:ticket_id>/manual_password_reset', methods=['POST'])
def manual_password_reset_endpoint(ticket_id):
    sid = get_session_id()
    data = request.get_json()
    if not data or 'new_password' not in data:
        return jsonify({'error': 'new_password required'}), 400
    ticket = Ticket.query.filter_by(id=ticket_id, session_id=sid).first_or_404()
    if ticket.category != 'Password Reset':
        return jsonify({'error': 'Not a password reset ticket'}), 400
    user = ADUser.query.filter_by(username=ticket.user_affected, session_id=sid).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    manual_password_reset(user, data['new_password'])
    ticket.status = 'Resolved'
    db.session.commit()
    return jsonify({'message': 'Password reset completed'})


@app.route('/api/ticket/<int:ticket_id>/manual_account_unlock', methods=['POST'])
def manual_account_unlock_endpoint(ticket_id):
    sid = get_session_id()
    ticket = Ticket.query.filter_by(id=ticket_id, session_id=sid).first_or_404()
    if ticket.category != 'Account Lockout':
        return jsonify({'error': 'Not an account lockout ticket'}), 400
    user = ADUser.query.filter_by(username=ticket.user_affected, session_id=sid).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    manual_account_unlock(user)
    ticket.status = 'Resolved'
    db.session.commit()
    return jsonify({'message': 'Account unlocked'})


@app.route('/api/ticket/<int:ticket_id>/manual_new_hire', methods=['POST'])
def manual_new_hire_endpoint(ticket_id):
    sid = get_session_id()
    ticket = Ticket.query.filter_by(id=ticket_id, session_id=sid).first_or_404()
    if ticket.category != 'New Hire Setup':
        return jsonify({'error': 'Not a new hire ticket'}), 400
    data = request.get_json(silent=True) or {}
    user = manual_new_hire(ticket, department=data.get('department', 'New Hire'), computer_id=data.get('computer_id'))
    ticket.status = 'Resolved'
    db.session.commit()
    return jsonify({'message': 'New hire setup completed', 'username': user.username})


@app.route('/api/ticket/<int:ticket_id>/fix_hardware', methods=['POST'])
def fix_hardware_endpoint(ticket_id):
    sid = get_session_id()
    ticket = Ticket.query.filter_by(id=ticket_id, session_id=sid).first_or_404()
    if ticket.category != 'Hardware Issue':
        return jsonify({'error': 'Not a hardware issue ticket'}), 400
    computer = fix_hardware(ticket)
    if not computer:
        return jsonify({'error': 'No linked computer found for this ticket'}), 400
    ticket.status = 'Resolved'
    db.session.commit()
    return jsonify({'message': f'{computer.hostname} is back online', 'computer': computer.to_dict()})


@app.route('/api/ticket/<int:ticket_id>/fix_network', methods=['POST'])
def fix_network_endpoint(ticket_id):
    sid = get_session_id()
    ticket = Ticket.query.filter_by(id=ticket_id, session_id=sid).first_or_404()
    if ticket.category != 'Network Issue':
        return jsonify({'error': 'Not a network issue ticket'}), 400
    computer = fix_network(ticket)
    if not computer:
        return jsonify({'error': 'No linked computer or original IP found'}), 400
    ticket.status = 'Resolved'
    db.session.commit()
    return jsonify({'message': f'Network restored on {computer.hostname}', 'computer': computer.to_dict()})


@app.route('/api/ticket/<int:ticket_id>/install_software', methods=['POST'])
def install_software_endpoint(ticket_id):
    sid = get_session_id()
    ticket = Ticket.query.filter_by(id=ticket_id, session_id=sid).first_or_404()
    if ticket.category != 'Software Installation':
        return jsonify({'error': 'Not a software installation ticket'}), 400
    computer = install_software(ticket)
    if not computer:
        return jsonify({'error': 'No linked computer or software target found'}), 400
    ticket.status = 'Resolved'
    db.session.commit()
    return jsonify({'message': f'{ticket.software_needed} installed on {computer.hostname}', 'computer': computer.to_dict()})


@app.route('/api/computers')
def get_computers():
    sid = get_session_id()
    computers = Computer.query.filter_by(session_id=sid).all()
    return jsonify([c.to_dict() for c in computers])


@app.route('/api/departments')
def get_departments():
    sid = get_session_id()
    departments = Department.query.filter_by(session_id=sid).all()
    return jsonify([d.to_dict() for d in departments])


@app.route('/api/export_users')
def export_users():
    sid = get_session_id()
    csv_data = export_users_to_csv(sid)
    return send_file(
        io.BytesIO(csv_data.encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='users.csv'
    )


if __name__ == '__main__':
    app.run(debug=True)
