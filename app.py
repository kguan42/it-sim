import os
from flask import Flask, jsonify, request, send_file, render_template
from models import (
    db, ADUser, Ticket, TicketNote, Computer, Department,
    seed_environment, generate_tickets as generate_ticket_objects,
    create_ticket, add_ticket_note,
    manual_password_reset, manual_account_unlock, manual_new_hire,
    export_users_to_csv,
)
import io

app = Flask(__name__)
app.instance_path = os.path.join(os.path.dirname(__file__), 'instance')
os.makedirs(app.instance_path, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'it_helpdesk.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


with app.app_context():
    db.drop_all()
    db.create_all()
    seed_environment()


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    return jsonify({'status': 'OK'})

@app.route('/api/users')
def get_users():
    users = ADUser.query.all()
    return jsonify([user.to_dict() for user in users])

@app.route('/api/tickets')
def get_tickets():
    tickets = Ticket.query.order_by(Ticket.created_at.desc()).all()
    return jsonify([ticket.to_dict() for ticket in tickets])

@app.route('/api/tickets/generate', methods=['POST'])
def generate_tickets():
    data = request.get_json(silent=True) or {}
    count = int(data.get('count', 5))
    if count <= 0:
        count = 5
    new_tickets = generate_ticket_objects(count)
    return jsonify([ticket.to_dict() for ticket in new_tickets])

@app.route('/api/tickets/create', methods=['POST'])
def create_ticket_endpoint():
    data = request.get_json()
    required = ('title', 'description', 'category', 'priority', 'user_affected')
    if not data or any(k not in data for k in required):
        return jsonify({'error': f'Required fields: {", ".join(required)}'}), 400
    ticket = create_ticket(
        title=data['title'],
        description=data['description'],
        category=data['category'],
        priority=data['priority'],
        user_affected=data['user_affected'],
        assigned_to=data.get('assigned_to'),
    )
    return jsonify(ticket.to_dict()), 201

@app.route('/api/tickets/clear', methods=['DELETE'])
def clear_tickets():
    TicketNote.query.delete()
    Ticket.query.delete()
    db.session.commit()
    return jsonify({'message': 'All tickets cleared'})

@app.route('/api/ticket/<int:ticket_id>/notes', methods=['GET'])
def get_ticket_notes(ticket_id):
    Ticket.query.get_or_404(ticket_id)
    notes = TicketNote.query.filter_by(ticket_id=ticket_id).order_by(TicketNote.created_at).all()
    return jsonify([n.to_dict() for n in notes])

@app.route('/api/ticket/<int:ticket_id>/note', methods=['POST'])
def add_note(ticket_id):
    Ticket.query.get_or_404(ticket_id)
    data = request.get_json()
    if not data or 'body' not in data:
        return jsonify({'error': 'body required'}), 400
    author = data.get('author', 'Technician')
    note = add_ticket_note(ticket_id, author, data['body'])
    return jsonify(note.to_dict()), 201

@app.route('/api/ticket/<int:ticket_id>/status', methods=['POST'])
def update_ticket_status(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
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
    ticket = Ticket.query.get_or_404(ticket_id)
    data = request.get_json()
    if not data or 'assignee' not in data:
        return jsonify({'error': 'assignee required'}), 400
    ticket.assigned_to = data['assignee'] or None
    db.session.commit()
    return jsonify(ticket.to_dict())

@app.route('/api/ticket/<int:ticket_id>/resolve', methods=['POST'])
def resolve_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    ticket.status = 'Resolved'
    db.session.commit()
    return jsonify({'message': 'Ticket resolved'})

@app.route('/api/ticket/<int:ticket_id>/manual_password_reset', methods=['POST'])
def manual_password_reset_endpoint(ticket_id):
    data = request.get_json()
    if not data or 'new_password' not in data:
        return jsonify({'error': 'new_password required'}), 400
    ticket = Ticket.query.get_or_404(ticket_id)
    if ticket.category != 'Password Reset':
        return jsonify({'error': 'Not a password reset ticket'}), 400
    user = ADUser.query.filter_by(username=ticket.user_affected).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    manual_password_reset(user, data['new_password'])
    ticket.status = 'Resolved'
    db.session.commit()
    return jsonify({'message': 'Password reset completed'})

@app.route('/api/ticket/<int:ticket_id>/manual_account_unlock', methods=['POST'])
def manual_account_unlock_endpoint(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if ticket.category != 'Account Lockout':
        return jsonify({'error': 'Not an account lockout ticket'}), 400
    user = ADUser.query.filter_by(username=ticket.user_affected).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    manual_account_unlock(user)
    ticket.status = 'Resolved'
    db.session.commit()
    return jsonify({'message': 'Account unlocked'})

@app.route('/api/ticket/<int:ticket_id>/manual_new_hire', methods=['POST'])
def manual_new_hire_endpoint(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if ticket.category != 'New Hire Setup':
        return jsonify({'error': 'Not a new hire ticket'}), 400
    manual_new_hire(ticket)
    ticket.status = 'Resolved'
    db.session.commit()
    return jsonify({'message': 'New hire setup completed'})

@app.route('/api/computers')
def get_computers():
    computers = Computer.query.all()
    return jsonify([computer.to_dict() for computer in computers])

@app.route('/api/departments')
def get_departments():
    departments = Department.query.all()
    return jsonify([dept.to_dict() for dept in departments])

@app.route('/api/export_users')
def export_users():
    csv_data = export_users_to_csv()
    return send_file(
        io.BytesIO(csv_data.encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='users.csv'
    )

if __name__ == '__main__':
    app.run(debug=True)
