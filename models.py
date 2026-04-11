from flask_sqlalchemy import SQLAlchemy
import random
import csv
import io
import datetime
import json

db = SQLAlchemy()

SLA_HOURS = {
    'Critical': 4,
    'High': 8,
    'Medium': 24,
    'Low': 72,
}

DEFAULT_SOFTWARE = ['Chrome', 'Office 365', 'Slack', 'Zoom', '7-Zip']

NEW_HIRE_NAMES = [
    ('Emily', 'Carter'),    ('Marcus', 'Rivera'),   ('Sofia', 'Patel'),
    ('Derek', 'Nguyen'),    ('Priya', 'Kapoor'),    ('Liam', 'O\'Brien'),
    ('Amara', 'Osei'),      ('Tyler', 'Novak'),     ('Keiko', 'Tanaka'),
    ('Rashida', 'Grant'),   ('Ethan', 'Kowalski'),  ('Fatima', 'Hassan'),
    ('Lucas', 'Fernandez'), ('Zoe', 'Marchetti'),   ('Omar', 'Al-Rashid'),
]
INSTALLABLE_SOFTWARE = [
    'Adobe Acrobat', 'AutoCAD', 'Visual Studio Code',
    'Python 3.11', 'Notepad++', 'VLC Media Player',
    'Teams', 'OneDrive', 'FileZilla',
]


class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    manager = db.Column(db.String(100), nullable=False)

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'manager': self.manager}


class Computer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    hostname = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(50), nullable=False)
    original_ip = db.Column(db.String(50), nullable=True)
    department = db.Column(db.String(80), nullable=False)
    user_assigned = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(20), default='Online')
    installed_software = db.Column(db.Text, default='[]')

    def to_dict(self):
        return {
            'id': self.id,
            'hostname': self.hostname,
            'ip_address': self.ip_address,
            'department': self.department,
            'user_assigned': self.user_assigned,
            'status': self.status,
            'installed_software': json.loads(self.installed_software or '[]'),
        }


class ADUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    username = db.Column(db.String(50), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    password = db.Column(db.String(100), nullable=False, default='Pass123!')
    is_locked = db.Column(db.Boolean, default=False)
    groups = db.Column(db.String(200), default='Domain Users')

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'full_name': self.full_name,
            'department': self.department,
            'email': self.email,
            'password': self.password,
            'is_locked': self.is_locked,
            'groups': self.groups,
        }


class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(80), nullable=False)
    priority = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), default='Open')
    user_affected = db.Column(db.String(80), nullable=False)
    assigned_to = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())
    sla_deadline = db.Column(db.DateTime, nullable=True)
    computer_id = db.Column(db.Integer, db.ForeignKey('computer.id'), nullable=True)
    software_needed = db.Column(db.String(200), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'priority': self.priority,
            'status': self.status,
            'user_affected': self.user_affected,
            'assigned_to': self.assigned_to,
            'created_at': str(self.created_at),
            'sla_deadline': str(self.sla_deadline) if self.sla_deadline else None,
            'computer_id': self.computer_id,
            'software_needed': self.software_needed,
        }


class TicketNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)
    author = db.Column(db.String(100), nullable=False, default='Technician')
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'ticket_id': self.ticket_id,
            'author': self.author,
            'body': self.body,
            'created_at': str(self.created_at),
        }


# ── Seeding & helpers ──────────────────────────────────────────────────────────

def seed_environment(session_id):
    sw = json.dumps(DEFAULT_SOFTWARE)
    departments = [
        Department(session_id=session_id, name='IT',        manager='John Smith'),
        Department(session_id=session_id, name='HR',        manager='Jane Doe'),
        Department(session_id=session_id, name='Finance',   manager='Bob Johnson'),
        Department(session_id=session_id, name='Marketing', manager='Alice Brown'),
        Department(session_id=session_id, name='Sales',     manager='Charlie Wilson'),
    ]
    computers = [
        Computer(session_id=session_id, hostname='IT-WKS-001',  ip_address='192.168.1.10', original_ip='192.168.1.10', department='IT',        user_assigned='jsmith',   installed_software=sw),
        Computer(session_id=session_id, hostname='HR-WKS-001',  ip_address='192.168.1.11', original_ip='192.168.1.11', department='HR',        user_assigned='jdoe',     installed_software=sw),
        Computer(session_id=session_id, hostname='FIN-WKS-001', ip_address='192.168.1.12', original_ip='192.168.1.12', department='Finance',   user_assigned='bjohnson', installed_software=sw),
        Computer(session_id=session_id, hostname='MKT-WKS-001', ip_address='192.168.1.13', original_ip='192.168.1.13', department='Marketing', user_assigned='abrown',   installed_software=sw),
        Computer(session_id=session_id, hostname='SAL-WKS-001', ip_address='192.168.1.14', original_ip='192.168.1.14', department='Sales',     user_assigned='cwilson',  installed_software=sw),
    ]
    users = [
        ADUser(session_id=session_id, username='jsmith',   full_name='John Smith',     department='IT',        email='john.smith@company.com',     password='Pass123!'),
        ADUser(session_id=session_id, username='jdoe',     full_name='Jane Doe',       department='HR',        email='jane.doe@company.com',       password='Pass123!'),
        ADUser(session_id=session_id, username='bjohnson', full_name='Bob Johnson',    department='Finance',   email='bob.johnson@company.com',    password='Pass123!'),
        ADUser(session_id=session_id, username='abrown',   full_name='Alice Brown',    department='Marketing', email='alice.brown@company.com',    password='Pass123!'),
        ADUser(session_id=session_id, username='cwilson',  full_name='Charlie Wilson', department='Sales',     email='charlie.wilson@company.com', password='Pass123!'),
    ]
    db.session.add_all(departments + computers + users)
    db.session.commit()


def _sla_deadline(priority):
    hours = SLA_HOURS.get(priority, 24)
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours)


def _get_user_computer(username, session_id):
    return Computer.query.filter_by(user_assigned=username, session_id=session_id).first()


def generate_tickets(count, session_id):
    ticket_templates = {
        'Password Reset': [
            ('Password Reset Request', 'User cannot log in and needs their password reset.'),
            ('Expired Password', 'User password has expired and they are locked out.'),
        ],
        'Account Lockout': [
            ('Account Locked Out', 'User account has been locked after multiple failed login attempts.'),
            ('AD Account Lockout', 'Active Directory account is locked, user unable to access resources.'),
        ],
        'New Hire Setup': [
            ('New Employee Onboarding', '{name} needs account creation, email setup, and workstation provisioning.'),
            ('Contractor Access Setup', '{name} (new contractor) requires limited access credentials and system setup.'),
        ],
        'Software Installation': [
            ('Software Install Request', 'User requires a software package installed on their workstation.'),
            ('Application Upgrade Needed', 'User needs an application installed on their workstation.'),
        ],
        'Hardware Issue': [
            ('Workstation Not Powering On', 'User workstation is offline and fails to respond. Possible hardware fault.'),
            ('Monitor Display Problem', 'User workstation is offline. Monitor showing no signal.'),
            ('Keyboard/Mouse Unresponsive', 'Workstation not responding. Peripheral devices unresponsive.'),
        ],
        'Network Issue': [
            ('No Network Connectivity', 'User workstation has obtained an APIPA address and cannot reach the network.'),
            ('IP Address Conflict', 'Workstation is showing an IP conflict. Network adapter may need reset.'),
            ('Cannot Access Network Shares', 'User unable to map drives or access file shares due to network issue.'),
        ],
    }

    categories = list(ticket_templates.keys())
    priorities = ['Low', 'Medium', 'High', 'Critical']
    usernames = [u.username for u in ADUser.query.filter_by(session_id=session_id).all()]
    if not usernames:
        return []

    new_tickets = []
    for _ in range(count):
        category = random.choice(categories)
        priority = random.choice(priorities)
        title_tmpl, desc_tmpl = random.choice(ticket_templates[category])

        if category == 'New Hire Setup':
            first, last = random.choice(NEW_HIRE_NAMES)
            full_name = f'{first} {last}'
            ticket = Ticket(
                session_id=session_id,
                title=f'{title_tmpl} — {full_name}',
                description=f'[HR] {desc_tmpl.format(name=full_name)}',
                category=category, priority=priority,
                user_affected=full_name,
                sla_deadline=_sla_deadline(priority),
            )
        else:
            user = random.choice(usernames)
            ticket = Ticket(
                session_id=session_id,
                title=f'{title_tmpl} — {user}',
                description=f'[Reported by {user}] {desc_tmpl}',
                category=category, priority=priority,
                user_affected=user,
                sla_deadline=_sla_deadline(priority),
            )

            if category == 'Account Lockout':
                affected = ADUser.query.filter_by(username=user, session_id=session_id).first()
                if affected:
                    affected.is_locked = True

            elif category == 'Hardware Issue':
                computer = _get_user_computer(user, session_id)
                if computer and computer.status == 'Online':
                    computer.status = 'Offline'
                    ticket.computer_id = computer.id

            elif category == 'Network Issue':
                computer = _get_user_computer(user, session_id)
                if computer and not computer.ip_address.startswith('169.254'):
                    computer.original_ip = computer.ip_address
                    computer.ip_address = f'169.254.{random.randint(1,254)}.{random.randint(1,254)}'
                    ticket.computer_id = computer.id

            elif category == 'Software Installation':
                computer = _get_user_computer(user, session_id)
                if computer:
                    installed = json.loads(computer.installed_software or '[]')
                    available = [s for s in INSTALLABLE_SOFTWARE if s not in installed]
                    if available:
                        software = random.choice(available)
                        ticket.software_needed = software
                        ticket.computer_id = computer.id
                        ticket.title = f'Software Install Request — {user}'
                        ticket.description = f'[Reported by {user}] {user} requires {software} installed on {computer.hostname}.'

        db.session.add(ticket)
        new_tickets.append(ticket)

    db.session.commit()
    return new_tickets


def create_ticket(title, description, category, priority, user_affected, session_id, assigned_to=None):
    ticket = Ticket(
        session_id=session_id,
        title=title, description=description,
        category=category, priority=priority,
        user_affected=user_affected,
        assigned_to=assigned_to or None,
        sla_deadline=_sla_deadline(priority),
    )
    db.session.add(ticket)
    db.session.commit()
    return ticket


def add_ticket_note(ticket_id, author, body):
    note = TicketNote(ticket_id=ticket_id, author=author, body=body)
    db.session.add(note)
    db.session.commit()
    return note


def manual_password_reset(user, new_password):
    user.password = new_password
    user.is_locked = False
    db.session.commit()


def manual_account_unlock(user):
    user.is_locked = False
    db.session.commit()


def manual_new_hire(ticket, department='New Hire', computer_id=None):
    full_name = ticket.user_affected
    sid = ticket.session_id
    parts = full_name.lower().split()
    base_username = (parts[0][0] + parts[-1]) if len(parts) >= 2 else parts[0]
    base_username = ''.join(c for c in base_username if c.isalnum())

    username = base_username
    counter = 2
    while ADUser.query.filter_by(username=username, session_id=sid).first():
        username = f'{base_username}{counter}'
        counter += 1

    new_user = ADUser(
        session_id=sid, username=username, full_name=full_name,
        department=department, email=f'{username}@company.com', password='TempPass123!',
    )
    db.session.add(new_user)

    if computer_id:
        computer = Computer.query.get(computer_id)
        if computer and computer.session_id == sid:
            computer.user_assigned = username

    db.session.commit()
    return new_user


def fix_hardware(ticket):
    if ticket.computer_id:
        computer = Computer.query.get(ticket.computer_id)
        if computer and computer.session_id == ticket.session_id:
            computer.status = 'Online'
            db.session.commit()
            return computer
    return None


def fix_network(ticket):
    if ticket.computer_id:
        computer = Computer.query.get(ticket.computer_id)
        if computer and computer.original_ip and computer.session_id == ticket.session_id:
            computer.ip_address = computer.original_ip
            db.session.commit()
            return computer
    return None


def install_software(ticket):
    if ticket.computer_id and ticket.software_needed:
        computer = Computer.query.get(ticket.computer_id)
        if computer and computer.session_id == ticket.session_id:
            installed = json.loads(computer.installed_software or '[]')
            if ticket.software_needed not in installed:
                installed.append(ticket.software_needed)
                computer.installed_software = json.dumps(installed)
                db.session.commit()
            return computer
    return None


def export_users_to_csv(session_id):
    users = ADUser.query.filter_by(session_id=session_id).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Username', 'Full Name', 'Department', 'Email', 'Password', 'Locked', 'Groups'])
    for user in users:
        writer.writerow([user.username, user.full_name, user.department, user.email, user.password, user.is_locked, user.groups])
    return output.getvalue()
