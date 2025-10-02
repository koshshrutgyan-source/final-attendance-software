import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime

# --- CONFIGURATION ---
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.secret_key = "supersecretkey"

# Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'attendance.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Uploads
UPLOAD_FOLDER = os.path.join(basedir, 'static/uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)

# --- MODELS ---
class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    emp_id = db.Column(db.String(20), unique=True, nullable=False)
    image = db.Column(db.String(200), nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    mobile_number = db.Column(db.String(20), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=True)
    password_hash = db.Column(db.String(200), nullable=False)
    unique_phrase = db.Column(db.String(100), nullable=True)  # For forgot password confirmation

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Employee {self.name}>'

class AttendanceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), nullable=False)
    check_in = db.Column(db.String(20), nullable=True)
    check_out = db.Column(db.String(20), nullable=True)

    employee = db.relationship('Employee', backref=db.backref('attendance', lazy=True))

    def __repr__(self):
        return f'<Attendance {self.employee_id} on {self.date}>'

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(500), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=True)  # Null means all employees
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class EmployeeRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    request_type = db.Column(db.String(100), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), default="Pending")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Add this line:
    employee = db.relationship('Employee', backref=db.backref('requests', lazy=True))

# --- DECORATORS ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('You must be logged in as admin', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def employee_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('employee_logged_in'):
            flash('You must be logged in as employee', 'warning')
            return redirect(url_for('employee_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- ROUTES ---
@app.route('/')
def index():
    employees = Employee.query.all()
    return render_template('index.html', employees=employees)

# --- ADMIN LOGIN ---
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_employees'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('admin_login'))

# --- ADMIN DASHBOARD ---
@app.route('/admin/employees')
@admin_required
def admin_employees():
    employees = Employee.query.all()
    return render_template('admin_employees.html', employees=employees)

# --- ADD EMPLOYEE ---
@app.route('/admin/add_employee', methods=['GET', 'POST'])
@admin_required
def add_employee():
    if request.method == 'POST':
        name = request.form.get('name')
        emp_id_str = request.form.get('emp_id')
        gender = request.form.get('gender')
        address = request.form.get('address')
        mobile_number = request.form.get('mobile_number')
        date_of_birth_str = request.form.get('date_of_birth')
        email = request.form.get('email')
        password = request.form.get('password')

        # Date conversion
        date_of_birth = None
        if date_of_birth_str:
            try:
                date_of_birth = datetime.strptime(date_of_birth_str, "%Y-%m-%d").date()
            except ValueError:
                flash("Invalid date format for Date of Birth", "danger")
                return redirect(url_for('add_employee'))

        # Image upload
        image_file = request.files.get('image')
        filename = None
        if image_file and image_file.filename != "":
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)

        # Validate numeric fields
        if not emp_id_str.isdigit():
            flash("Employee ID must be numeric", "danger")
            return redirect(url_for('add_employee'))
        if not mobile_number.isdigit():
            flash("Mobile Number must be numeric", "danger")
            return redirect(url_for('add_employee'))

        # Generate unique phrase
        import random, string
        unique_phrase = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

        # Create employee
        new_emp = Employee(
            name=name,
            emp_id=emp_id_str,
            gender=gender,
            address=address,
            mobile_number=mobile_number,
            date_of_birth=date_of_birth,
            email=email,
            image=filename,
            unique_phrase=unique_phrase
        )
        new_emp.set_password(password)
        db.session.add(new_emp)
        db.session.commit()

        flash(f"Employee added! Unique Phrase: {unique_phrase}", "success")
        return redirect(url_for('admin_employees'))

    return render_template('add_employee.html')
# --- EDIT EMPLOYEE ---
@app.route('/admin/edit/<int:emp_id>', methods=['GET', 'POST'])
@admin_required
def edit_employee(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    if request.method == 'POST':
        emp.name = request.form['name']
        emp.emp_id = request.form['emp_id']
        emp.gender = request.form['gender']
        emp.address = request.form['address']
        emp.mobile_number = request.form['mobile_number']
        emp.email = request.form['email']
        emp.date_of_birth = datetime.strptime(request.form['date_of_birth'], "%Y-%m-%d").date() if request.form['date_of_birth'] else None
        password = request.form.get('password')
        if password:
            emp.set_password(password)

        # Image upload
        image_file = request.files.get('image')
        if image_file and image_file.filename != "":
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)
            emp.image = filename

        # Optional: update unique phrase
        unique_phrase = request.form.get('unique_phrase')
        if unique_phrase:
            emp.unique_phrase = unique_phrase

        db.session.commit()
        flash("Employee updated successfully!", "success")
        return redirect(url_for('admin_employees'))

    return render_template('edit_employee.html', emp=emp)

# --- DELETE EMPLOYEE ---
@app.route('/admin/delete/<int:emp_id>', methods=['POST'])
@admin_required
def delete_employee(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    db.session.delete(emp)
    db.session.commit()
    flash("Employee deleted successfully!", "success")
    return redirect(url_for('admin_employees'))

# --- EMPLOYEE LOGIN ---
@app.route('/employee/login', methods=['GET', 'POST'])
def employee_login():
    if request.method == 'POST':
        emp_id = request.form['emp_id']
        password = request.form['password']
        emp = Employee.query.filter_by(emp_id=emp_id).first()
        if emp and emp.check_password(password):
            session['employee_logged_in'] = True
            session['employee_id'] = emp.id
            return redirect(url_for('employee_dashboard'))
        else:
            flash("Invalid Employee ID or password", "danger")
    return render_template('employee_login.html')

@app.route('/employee/logout')
def employee_logout():
    session.pop('employee_logged_in', None)
    session.pop('employee_id', None)
    flash("Logged out successfully", "success")
    return redirect(url_for('employee_login'))


@app.route('/admin/employee_requests/update/<int:request_id>/<string:new_status>', methods=['POST'])
@admin_required
def update_employee_request_status(request_id, new_status):
    req = EmployeeRequest.query.get_or_404(request_id)
    if new_status not in ['Approved', 'Declined']:
        flash('Invalid status', 'danger')
        return redirect(url_for('admin_employee_requests'))

    req.status = new_status
    db.session.commit()
    flash(f'Request {new_status.lower()} successfully!', 'success')
    return redirect(url_for('admin_employee_requests'))

# --- EMPLOYEE DASHBOARD ---
@app.route('/employee/dashboard', methods=['GET', 'POST'])
@employee_required
def employee_dashboard():
    emp_id = session.get('employee_id')
    emp = Employee.query.get_or_404(emp_id)
    attendance = AttendanceRecord.query.filter_by(employee_id=emp.id).order_by(AttendanceRecord.date.desc()).all()
    notifications = Notification.query.filter((Notification.employee_id==emp.id)|(Notification.employee_id==None)).order_by(Notification.timestamp.desc()).all()
    requests = EmployeeRequest.query.filter_by(employee_id=emp.id).order_by(EmployeeRequest.timestamp.desc()).all()

    # Check-in/out handling
    if request.method == 'POST':
        action = request.form.get('action')
        today = datetime.today().date()
        record = AttendanceRecord.query.filter_by(employee_id=emp.id, date=today).first()

        if action == "check_in":
            if not record:
                new_record = AttendanceRecord(employee_id=emp.id, date=today, status="Present", check_in=datetime.now().strftime("%H:%M:%S"))
                db.session.add(new_record)
                db.session.commit()
                flash("Checked in successfully!", "success")
            else:
                flash("Already checked in today!", "warning")

        elif action == "check_out":
            if record and not record.check_out:
                record.check_out = datetime.now().strftime("%H:%M:%S")
                db.session.commit()
                flash("Checked out successfully!", "success")
            else:
                flash("Cannot check out before checking in!", "danger")

    return render_template('employee_dashboard.html', emp=emp, attendance=attendance, notifications=notifications, requests=requests)

# --- CREATE EMPLOYEE REQUEST ---
@app.route('/employee/create_request', methods=['GET', 'POST'])
@employee_required
def employee_create_request():
    emp_id = session.get('employee_id')
    emp = Employee.query.get_or_404(emp_id)

    if request.method == 'POST':
        request_type = request.form.get('request_type')
        message = request.form.get('message')

        if not request_type or not message:
            flash("All fields are required!", "danger")
            return redirect(url_for('employee_create_request'))

        new_request = EmployeeRequest(
            employee_id=emp.id,
            request_type=request_type,
            message=message
        )
        db.session.add(new_request)
        db.session.commit()
        flash("Request submitted successfully!", "success")
        return redirect(url_for('employee_dashboard'))

    return render_template('employee_create_request.html')

# --- EDIT EMPLOYEE PROFILE ---
@app.route('/employee/edit_profile', methods=['GET', 'POST'])
@employee_required
def edit_employee_profile():
    emp_id = session.get('employee_id')
    emp = Employee.query.get_or_404(emp_id)

    if request.method == 'POST':
        emp.name = request.form['name']
        emp.gender = request.form['gender']
        emp.address = request.form['address']
        emp.mobile_number = request.form['mobile_number']
        emp.email = request.form['email']
        emp.date_of_birth = datetime.strptime(request.form['date_of_birth'], "%Y-%m-%d").date() if request.form['date_of_birth'] else None
        password = request.form.get('password')
        if password:
            emp.set_password(password)

        # Image upload
        image_file = request.files.get('image')
        if image_file and image_file.filename != "":
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)
            emp.image = filename

        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for('employee_dashboard'))

    return render_template('edit_employee_profile.html', emp=emp)

# --- EMPLOYEE FORGOT PASSWORD ---
@app.route('/employee/forgot_password', methods=['GET', 'POST'])
def employee_forgot_password():
    if request.method == 'POST':
        emp_id = request.form['emp_id']
        email = request.form['email']
        unique_phrase = request.form['unique_phrase']
        emp = Employee.query.filter_by(emp_id=emp_id, email=email, unique_phrase=unique_phrase).first()
        if emp:
            flash(f"Your password is: {emp.password_hash}", "success")
            # In real app, send email instead of showing password
        else:
            flash("Invalid credentials or unique phrase", "danger")
    return render_template('employee_forgot_password.html')
# --- EMPLOYEE REQUESTS ---
@app.route('/employee/request', methods=['GET', 'POST'])
@employee_required
def employee_request():
    emp_id = session.get('employee_id')
    emp = Employee.query.get_or_404(emp_id)

    if request.method == 'POST':
        request_type = request.form['request_type']
        message = request.form['message']
        new_request = EmployeeRequest(employee_id=emp.id, request_type=request_type, message=message)
        db.session.add(new_request)
        db.session.commit()
        flash("Request submitted successfully!", "success")
        return redirect(url_for('employee_dashboard'))

    return render_template('employee_request.html', emp=emp)

# --- ADMIN NOTIFICATIONS ---
@app.route('/admin/notifications', methods=['GET', 'POST'])
@admin_required
def admin_notifications():
    employees = Employee.query.all()  # get all employees for dropdown

    if request.method == 'POST':
        message = request.form['message']
        recipient_type = request.form.get('recipient')  # 'all' or 'selected'
        selected_emp_id = request.form.get('employee_id')  # only if 'selected'

        if not message:
            flash("Message cannot be empty!", "danger")
            return redirect(url_for('admin_notifications'))

        # Determine recipient
        if recipient_type == 'all':
            notification = Notification(message=message, employee_id=None)
            db.session.add(notification)
            db.session.commit()
            flash("Notification sent to all employees!", "success")
        elif recipient_type == 'selected' and selected_emp_id:
            notification = Notification(message=message, employee_id=int(selected_emp_id))
            db.session.add(notification)
            db.session.commit()
            flash("Notification sent to selected employee!", "success")
        else:
            flash("Please select a valid employee!", "danger")
            return redirect(url_for('admin_notifications'))

        return redirect(url_for('admin_notifications'))

    notifications = Notification.query.order_by(Notification.timestamp.desc()).all()
    return render_template('admin_notifications.html', employees=employees, notifications=notifications)

# --- ADMIN VIEW EMPLOYEE REQUESTS ---
@app.route('/admin/employee_requests')
@admin_required
def admin_employee_requests():
    # Only requests that have a valid employee
    requests = EmployeeRequest.query.join(Employee).order_by(EmployeeRequest.timestamp.desc()).all()
    return render_template('admin_employee_requests.html', requests=requests)


# --- ADMIN DASHBOARD: PROFILE EDIT (Optional) ---
@app.route('/admin/edit_profile/<int:admin_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_profile(admin_id):
    admin = Admin.query.get_or_404(admin_id)
    if request.method == 'POST':
        username = request.form['username']
        password = request.form.get('password')
        admin.username = username
        if password:
            admin.set_password(password)
        db.session.commit()
        flash("Admin profile updated!", "success")
        return redirect(url_for('admin_employees'))
    return render_template('admin_edit_profile.html', admin=admin)

@app.route('/test_hub')
def test_hub():
    return render_template('test_hub.html')

# --- DASHBOARD STATS AND PERFORMANCE (Optional) ---
def calculate_rating(emp_id):
    attendance = AttendanceRecord.query.filter_by(employee_id=emp_id).all()
    total_days = len(attendance)
    present_days = sum(1 for a in attendance if a.status == "Present")
    if total_days == 0:
        return 0
    return round((present_days / total_days) * 10, 2)

@app.context_processor
def inject_ratings():
    if 'employee_id' in session:
        emp_id = session['employee_id']
        return {'employee_rating': calculate_rating(emp_id)}
    return {}


from werkzeug.security import generate_password_hash

@app.cli.command("create-admin")
def create_admin():
    """One-time command to create a new admin"""
    username = input("Enter new admin username: ")
    password = input("Enter new admin password: ")

    # Hash the password
    hashed_pw = generate_password_hash(password)

    # Check if admin already exists
    existing = Admin.query.filter_by(username=username).first()
    if existing:
        print(f"⚠️ Admin with username '{username}' already exists.")
        return

    # Create new admin
    new_admin = Admin(username=username, password_hash=hashed_pw)
    db.session.add(new_admin)
    db.session.commit()

    print(f"✅ Admin '{username}' created successfully!")

# --- MAIN ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # create tables if they don't exist
    app.run(debug=True)