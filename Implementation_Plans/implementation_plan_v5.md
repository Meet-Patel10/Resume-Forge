# User Authentication & Management Plan

## Overview
This document summarizes the implementation of the user authentication system (login/register) and provides a guide on how to manage users in the PostgreSQL database (Neon).

---

## ✅ What was implemented

### New files
| File | Purpose |
|------|---------|
| `app/routes/auth.py` | Login, register, logout routes + `login_required` decorator handling session logic. |
| `app/templates/auth/login.html` | Premium dark-mode login page with flash messages & "remember me" toggle. |
| `app/templates/auth/register.html` | Register page with live password strength meter and confirm-password validation. |

### Modified files
- `app/__init__.py` — Registered the `auth_bp` blueprint, and added a 30-day session lifetime configuration for the "remember me" functionality.
- `app/templates/base.html` — Added a dynamic user avatar and Sign Out button in the sidebar (only visible when logged in).
- `app/routes/main.py` — Protected the `/dashboard` route with the `@login_required` decorator.

---

## How to access

Once the Flask app is running, use these endpoints:
- Login: [http://localhost:5001/auth/login](http://localhost:5001/auth/login)
- Register: [http://localhost:5001/auth/register](http://localhost:5001/auth/register)
- Logout: `http://localhost:5001/auth/logout`

*(Note: Port 5001 is used based on our recent configuration updates, but adjust to 5000 if running locally without Docker mapping constraints).*

---

## Managing users in the database (Neon/PostgreSQL)

### View all users
To see all registered users, run this in the Neon SQL Editor:
```sql
SELECT id, username, email, full_name, is_active, created_at FROM users;
```

### Create a user
The recommended way is via the app's UI at `/auth/register` to ensure the password hash is correctly generated using Werkzeug.

### Manually reset a password 
Because passwords are hashed, you cannot update them via plain text SQL. Instead, use the Flask shell:
```bash
cd /Users/meetpatel/Resume_Builder_Application
source venv/bin/activate
python3 -c "
from app import create_app, db
from app.models.user import User
app = create_app()
with app.app_context():
    u = User.query.filter_by(username='meetpatel').first()
    if u:
        u.set_password('NewPassword123!')
        db.session.commit()
        print('Password reset successfully.')
    else:
        print('User not found.')
"
```

### Deactivate a user
Lock an account without deleting their data:
```sql
UPDATE users SET is_active = false WHERE username = 'someuser';
```

### Delete a user and all their data
```sql
DELETE FROM users WHERE username = 'someuser';
```
*Note: Due to the `cascade='all, delete-orphan'` setup in the SQLAlchemy models, deleting a user will automatically delete their associated `master_resume`, `applications`, and `resume_versions`.*
