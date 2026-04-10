# IT Help Desk Simulator

A simple Python-based IT help desk simulator that generates support tickets, simulates Active Directory tasks, and logs activity.

## Features

- Generates random IT tickets for password resets, locked accounts, software installs, printer issues, VPN/connectivity and more.
- Simulates Active Directory user state changes and group membership updates.
- Tracks ticket assignments and resolution history.
- Writes an activity log to `it_helpdesk_activity.csv`.

## Requirements

- Python 3.8+

## Run

Install dependencies and start the Flask app:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5000/` in your browser.


## Files

- `simulator.py` - main simulator script
- `README.md` - usage instructions
- `it_helpdesk_activity.csv` - generated activity log after running the simulator
 - `app.py` - Flask web application for browser-based simulation
 - `templates/index.html` - embedded web UI for the simulator
 - `requirements.txt` - Python packages required for the web app

## Version

This version uses Flask with SQLite to simulate:

- Active Directory users, departments, and computer inventory with password management
- Ticket queue with priority/SLA handling
- Dynamic outcomes for category-based resolution
- Password resets, account lockouts, and group membership changes
- **Manual ticket completion**: For Password Reset (with password change prompt) and New Hire Setup tickets, users can manually perform actions like resetting passwords or creating new users.
- **User export**: Download a CSV file containing all users and their passwords.


