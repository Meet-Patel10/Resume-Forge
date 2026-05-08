import functools
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from app.models.user import User

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    """Decorator to require login for protected routes."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page."""
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username_or_email = request.form.get('username_or_email', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        if not username_or_email or not password:
            flash('Please fill in all fields.', 'danger')
            return render_template('auth/login.html')

        # Look up by username or email
        user = User.query.filter(
            (User.username == username_or_email) |
            (User.email == username_or_email)
        ).first()

        if not user or not user.check_password(password):
            flash('Invalid username/email or password.', 'danger')
            return render_template('auth/login.html')

        if not user.is_active:
            flash('Your account has been deactivated. Contact support.', 'danger')
            return render_template('auth/login.html')

        # Set session
        session.permanent = remember
        session['user_id'] = user.id
        session['username'] = user.username
        session['full_name'] = user.full_name or user.username

        flash(f'Welcome back, {user.full_name or user.username}!', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Register page."""
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validation
        errors = []
        if not full_name:
            errors.append('Full name is required.')
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if not email or '@' not in email:
            errors.append('A valid email is required.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if password != confirm_password:
            errors.append('Passwords do not match.')

        if not errors:
            # Check uniqueness
            if User.query.filter_by(username=username).first():
                errors.append('Username is already taken.')
            if User.query.filter_by(email=email).first():
                errors.append('An account with this email already exists.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('auth/register.html',
                                   full_name=full_name, username=username, email=email)

        # Create user
        user = User(full_name=full_name, username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Auto-login after register
        session['user_id'] = user.id
        session['username'] = user.username
        session['full_name'] = user.full_name

        flash(f'Account created! Welcome to ResumeForge, {full_name}! 🎉', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('auth/register.html')


@auth_bp.route('/logout')
def logout():
    """Log out and clear session."""
    name = session.get('full_name', 'User')
    session.clear()
    flash(f'Goodbye, {name}! You have been logged out.', 'success')
    return redirect(url_for('auth.login'))
