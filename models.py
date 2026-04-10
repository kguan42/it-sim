from flask_sqlalchemy import SQLAlchemy
import random
import csv
import io
import datetime

db = SQLAlchemy()

SLA_HOURS = {
    'Critical': 4,
    'High': 8,
    'Medium': 24,
    'Low': 72,
}


class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    manager = db.Column(db.String(100), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'manager': self.manager,
        }


class Computer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(50), nullable=False)
    department = db.Column(db.String(80), nullable=False)
    user_assigned = db.Column(db.String(80), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'hostname': self.hostname,
            'ip_address': self.ip_address,
            'department': self.department,
            'user_assigned': self.user_assigned,
        }


class ADUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
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
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(80), nullable=False)
    priority = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), default='Open')
    user_affected = db.Column(db.String(80), nullable=False)
    assigned_to = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())
    sla_deadline = db.Column(db.DateTime, nullable=True)

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


def seed_environment():
    if Department.query.count() == 0:
        departments = [
            Department(name='IT', manager='John Smith'),
            Department(name='HR', manager='Jane Doe'),
            Department(name='Finance', manager='Bob Johnson'),
            Department(name='Marketing', manager='Alice Brown'),
            Department(name='Sales', manager='Charlie Wilson'),
        ]
        db.session.add_all(departments)

    if Computer.query.count() == 0:
        computers = [
            Computer(hostname='IT-WKS-001', ip_address='192.168.1.10', department='IT', user_assigned='jsmith'),
            Computer(hostname='HR-WKS-001', ip_address='192.168.1.11', department='HR', user_assigned='jdoe'),
            Computer(hostname='FIN-WKS-001', ip_address='192.168.1.12', department='Finance', user_assigned='bjohnson'),
            Computer(hostname='MKT-WKS-001', ip_address='192.168.1.13', department='Marketing', user_assigned='abrown'),
            Computer(hostname='SAL-WKS-001', ip_address='192.168.1.14', department='Sales', user_assigned='cwilson'),
        ]
        db.session.add_all(computers)

    if ADUser.query.count() == 0:
        users = [
            ADUser(username='jsmith', full_name='John Smith', department='IT', email='john.smith@company.com', password='Pass123!'),
            ADUser(username='jdoe', full_name='Jane Doe', department='HR', email='jane.doe@company.com', password='Pass123!'),
            ADUser(username='bjohnson', full_name='Bob Johnson', department='Finance', email='bob.johnson@company.com', password='Pass123!'),
            ADUser(username='abrown', full_name='Alice Brown', department='Marketing', email='alice.brown@company.com', password='Pass123!'),
            ADUser(username='cwilson', full_name='Charlie Wilson', department='Sales', email='charlie.wilson@company.com', password='Pass123!'),
        ]
        db.session.add_all(users)

    db.session.commit()


def _sla_deadline(priority):
    hours = SLA_HOURS.get(priority, 24)
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours)


def generate_tickets(count=5):
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
            ('New Employee Onboarding', 'New hire needs account creation, email setup, and workstation provisioning.'),
            ('Contractor Access Setup', 'New contractor requires limited access credentials and system setup.'),
        ],
        'Software Installation': [
            ('Software Install Request', 'User requires a software package installed on their workstation.'),
            ('Application Upgrade Needed', 'User needs an application upgraded to the latest approved version.'),
        ],
        'Hardware Issue': [
            ('Workstation Not Powering On', 'User workstation fails to boot, possible hardware fault.'),
            ('Monitor Display Problem', 'User monitor is flickering or showing no signal.'),
            ('Keyboard/Mouse Unresponsive', 'Peripheral devices not responding, possible driver or hardware issue.'),
        ],
    }

    categories = list(ticket_templates.keys())
    priorities = ['Low', 'Medium', 'High', 'Critical']
    usernames = [user.username for user in ADUser.query.all()]
    if not usernames:
        return []

    new_tickets = []
    for _ in range(count):
        category = random.choice(categories)
        priority = random.choice(priorities)
        user = random.choice(usernames)
        title_tmpl, desc_tmpl = random.choice(ticket_templates[category])
        ticket = Ticket(
            title=f'{title_tmpl} — {user}',
            description=f'[Reported by {user}] {desc_tmpl}',
            category=category,
            priority=priority,
            user_affected=user,
            sla_deadline=_sla_deadline(priority),
        )
        # Lock the user for Account Lockout tickets
        if category == 'Account Lockout':
            affected_user = ADUser.query.filter_by(username=user).first()
            if affected_user:
                affected_user.is_locked = True
        db.session.add(ticket)
        new_tickets.append(ticket)

    db.session.commit()
    return new_tickets


def create_ticket(title, description, category, priority, user_affected, assigned_to=None):
    ticket = Ticket(
        title=title,
        description=description,
        category=category,
        priority=priority,
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


def manual_new_hire(ticket):
    username = ticket.user_affected.lower().replace(' ', '.')
    full_name = ticket.user_affected
    department = 'New Department'
    new_user = ADUser(
        username=username,
        full_name=full_name,
        department=department,
        email=f'{username}@company.com',
        password='TempPass123!',
    )
    db.session.add(new_user)
    db.session.commit()


def export_users_to_csv():
    users = ADUser.query.all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Username', 'Full Name', 'Department', 'Email', 'Password', 'Locked', 'Groups'])
    for user in users:
        writer.writerow([user.username, user.full_name, user.department, user.email, user.password, user.is_locked, user.groups])
    return output.getvalue()
