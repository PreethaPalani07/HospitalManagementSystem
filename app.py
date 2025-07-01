import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from models import db, Patient, Doctor, Admin, Appointment, Medicine, Bill
from datetime import datetime
from functools import wraps # For creating decorators

# --- App Configuration ---
app = Flask(__name__)
# IMPORTANT: Generate a real secret key for production!
# Use: python -c 'import os; print(os.urandom(24))'
app.config['SECRET_KEY'] = b'\xe2\x19\xc9\x87\xc5\xd2<d\x0fp\xcf\xcb\xd8\xdaz8^s(#7\xc3\x18i' # !!! REPLACE THIS !!!
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'hospital.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Initialize Extensions ---
db.init_app(app)

# --- Helper Function to Create Initial Data ---
def create_initial_data():
    """Creates tables and initial Admin/Doctor if they don't exist."""
    with app.app_context():
        db.create_all()

        if not Admin.query.filter_by(username='admin').first():
            admin = Admin(username='admin')
            admin.set_password('adminpass123') # !!! CHANGE THIS DEFAULT PASSWORD !!!
            db.session.add(admin)
            print("Default admin user created (username='admin', password='adminpass123'). PLEASE CHANGE PASSWORD.")

        if Doctor.query.count() == 0:
             dr_jones = Doctor(doctor_name="Dr. Alice Jones", department_id="Cardiology", email="ajones@hospital.com")
             dr_jones.set_password('doctorpass1') # !!! CHANGE THIS !!!
             dr_smith = Doctor(doctor_name="Dr. Bob Smith", department_id="Pediatrics", email="bsmith@hospital.com")
             dr_smith.set_password('doctorpass2') # !!! CHANGE THIS !!!
             db.session.add_all([dr_jones, dr_smith])
             print("Sample doctors created with emails and default passwords. PLEASE CHANGE PASSWORDS.")
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error during initial data creation commit: {e}")

# --- Context Processor ---
@app.context_processor
def inject_now_and_role():
    """Injects current datetime and user role into template context."""
    return {
        'now': datetime.utcnow(),
        'user_role': session.get('user_role'), # Make role easily available in templates
        'user_name': session.get('user_name')  # Make user_name available
    }

# --- Decorators for Access Control ---
def login_required(role="ANY"):
    """Decorator to require login and optionally a specific role."""
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if 'user_id' not in session or 'user_role' not in session:
                flash("Please log in to access this page.", "warning")
                return redirect(url_for('login'))
            if role != "ANY" and session['user_role'] != role:
                flash(f"Access denied. This page requires '{role.capitalize()}' privileges.", "danger")
                # Redirect to appropriate dashboard based on current user's role
                current_role = session.get('user_role')
                if current_role == 'admin': return redirect(url_for('admin_dashboard'))
                elif current_role == 'doctor': return redirect(url_for('doctor_dashboard'))
                elif current_role == 'patient': return redirect(url_for('patient_dashboard'))
                else: return redirect(url_for('index')) # Fallback if role is unexpected
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper

# --- Routes ---
@app.route('/')
def index():
    if 'user_role' in session:
        role = session['user_role']
        if role == 'admin': return redirect(url_for('admin_dashboard'))
        elif role == 'doctor': return redirect(url_for('doctor_dashboard'))
        elif role == 'patient': return redirect(url_for('patient_dashboard'))
        else: session.clear() # Clear invalid session
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_role' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        identifier = request.form.get('identifier')
        password = request.form.get('password')

        if not identifier or not password:
            flash('Username/Email and Password are required.', 'warning')
            return redirect(url_for('login'))

        admin = Admin.query.filter_by(username=identifier).first()
        if admin and admin.check_password(password):
            session['user_id'] = admin.id
            session['user_role'] = 'admin'
            session['user_name'] = admin.username
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin_dashboard'))

        doctor = Doctor.query.filter_by(email=identifier).first()
        if doctor and doctor.check_password(password):
            session['user_id'] = doctor.id
            session['user_role'] = 'doctor'
            session['user_name'] = doctor.doctor_name
            flash('Doctor login successful!', 'success')
            return redirect(url_for('doctor_dashboard'))

        patient = Patient.query.filter_by(email=identifier).first()
        if patient and patient.check_password(password):
            session['user_id'] = patient.id
            session['user_role'] = 'patient'
            session['user_name'] = patient.patient_name
            flash('Patient login successful!', 'success')
            return redirect(url_for('patient_dashboard'))

        flash('Invalid username/email or password.', 'danger')
        return redirect(url_for('login'))

    return render_template('index.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_role', None)
    session.pop('user_name', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register_patient():
    if request.method == 'POST':
        name = request.form.get('patient_name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        age_str = request.form.get('age')
        phone = request.form.get('phone_number')
        address = request.form.get('address')

        errors = []
        if not name: errors.append('Patient Name is required.')
        if not email: errors.append('Email is required.')
        if not password: errors.append('Password is required.')
        if not confirm_password: errors.append('Confirm Password is required.')
        if not phone: errors.append('Phone Number is required.')

        if password and confirm_password and password != confirm_password:
             errors.append('Passwords do not match.')

        if email and (Patient.query.filter_by(email=email).first() or
                      Doctor.query.filter_by(email=email).first() or
                      Admin.query.filter_by(username=email).first()): # Check for email collision
            errors.append('Email address already registered.')

        age = None
        if age_str:
            if age_str.isdigit(): age = int(age_str)
            else: errors.append('Age must be a valid number.')
        
        if errors:
            for error in errors: flash(error, 'danger')
            return render_template('register_patient.html', name=name, email=email, age=age_str, phone=phone, address=address) # Pass back form data

        new_patient = Patient(patient_name=name, email=email, age=age, phone_number=phone, address=address)
        new_patient.set_password(password)
        try:
            db.session.add(new_patient)
            db.session.commit()
            flash(f'Patient {name} registered successfully! You can now log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error registering patient: {e}', 'danger')
            print(f"Error registering patient: {e}")
            return render_template('register_patient.html', name=name, email=email, age=age_str, phone=phone, address=address)
    return render_template('register_patient.html')

@app.route('/appointments/schedule', methods=['GET', 'POST'])
@login_required(role='admin')
def schedule_appointment():
    try:
        patients = Patient.query.order_by(Patient.patient_name).all()
        doctors = Doctor.query.order_by(Doctor.doctor_name).all()
    except Exception as e:
        flash("Error fetching patient or doctor list.", "danger")
        print(f"DB Error fetching lists: {e}")
        patients, doctors = [], []
        return render_template('schedule_appointment.html', patients=patients, doctors=doctors)

    if request.method == 'POST':
        try:
            patient_id = request.form.get('patient_id', type=int)
            doctor_id = request.form.get('doctor_id', type=int)
            date_str = request.form.get('appointment_date')
            reason = request.form.get('reason', '')

            if not patient_id or not doctor_id or not date_str:
                flash('Patient, Doctor, and Date/Time selection are required.', 'warning')
                return render_template('schedule_appointment.html', patients=patients, doctors=doctors)
            try:
                appointment_dt = datetime.fromisoformat(date_str)
            except ValueError:
                flash('Invalid Date/Time format submitted.', 'danger')
                return render_template('schedule_appointment.html', patients=patients, doctors=doctors)

            now = datetime.now()
            if appointment_dt < now:
                flash('Cannot schedule appointments in the past.', 'danger')
                return render_template('schedule_appointment.html', patients=patients, doctors=doctors)

            patient = Patient.query.get_or_404(patient_id)
            doctor = Doctor.query.get_or_404(doctor_id)
            new_appointment = Appointment(patient_id=patient.id, doctor_id=doctor.id, appointment_date=appointment_dt, reason=reason)
            db.session.add(new_appointment)
            db.session.commit()
            flash('Appointment scheduled successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error scheduling appointment: {e}', 'danger')
            print(f"Error scheduling appointment: {e}")
            return render_template('schedule_appointment.html', patients=patients, doctors=doctors)
    return render_template('schedule_appointment.html', patients=patients, doctors=doctors)

@app.route('/dashboard/admin')
@login_required(role='admin')
def admin_dashboard():
    try:
        appointments = Appointment.query.order_by(Appointment.appointment_date.desc()).all()
        patients = Patient.query.order_by(Patient.patient_name).all()
        doctors = Doctor.query.order_by(Doctor.doctor_name).all()
        medicines = Medicine.query.order_by(Medicine.name).all()
        bills = Bill.query.order_by(Bill.issued_date.desc()).all()
    except Exception as e:
        flash(f"Error fetching admin dashboard data: {e}", "danger")
        print(f"Error fetching admin dashboard data: {e}")
        appointments, patients, doctors, medicines, bills = [], [], [], [], []
    return render_template('admin_dashboard.html', appointments=appointments, patients=patients, doctors=doctors, medicines=medicines, bills=bills)

@app.route('/dashboard/doctor')
@login_required(role='doctor')
def doctor_dashboard():
    doctor_id = session['user_id']
    try:
        doctor = Doctor.query.get_or_404(doctor_id)
        appointments = Appointment.query.filter_by(doctor_id=doctor_id).order_by(Appointment.appointment_date.asc()).all()
    except Exception as e:
        flash(f"Error fetching doctor dashboard data: {e}", "danger")
        print(f"Error fetching doctor dashboard data: {e}")
        doctor, appointments = None, []
    return render_template('doctor_dashboard.html', doctor=doctor, appointments=appointments)

@app.route('/dashboard/patient')
@login_required(role='patient')
def patient_dashboard():
    patient_id = session['user_id']
    try:
        patient = Patient.query.get_or_404(patient_id)
        appointments = Appointment.query.filter_by(patient_id=patient_id).order_by(Appointment.appointment_date.desc()).all()
        bills = Bill.query.filter_by(patient_id=patient_id).order_by(Bill.issued_date.desc()).all()
    except Exception as e:
        flash(f"Error fetching patient dashboard data: {e}", "danger")
        print(f"Error fetching patient dashboard data: {e}")
        patient, appointments, bills = None, [], []
    return render_template('patient_dashboard.html', patient=patient, appointments=appointments, bills=bills)

@app.route('/medicines/add', methods=['POST'])
@login_required(role='admin')
def add_medicine():
    try:
        name = request.form.get('name')
        m_type = request.form.get('type', '')
        price = request.form.get('price', type=float)
        stock = request.form.get('stock', type=int, default=0)
        if not name or price is None or price < 0 or stock < 0:
             flash('Valid Medicine Name, positive Price, and non-negative Stock are required.', 'warning')
        else:
            new_med = Medicine(name=name, type=m_type, price=price, stock=stock)
            db.session.add(new_med)
            db.session.commit()
            flash(f'Medicine "{name}" added successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding medicine: {e}', 'danger')
        print(f"Error adding medicine: {e}")
    return redirect(url_for('admin_dashboard'))

@app.route('/bills/generate', methods=['POST'])
@login_required(role='admin')
def generate_bill():
    try:
        patient_id = request.form.get('patient_id_bill', type=int)
        amount = request.form.get('amount', type=float)
        appointment_id_str = request.form.get('appointment_id_bill')
        if not patient_id or amount is None or amount <= 0:
            flash('Patient selection and a valid positive Amount are required.', 'warning')
        else:
            appointment_id = None
            if appointment_id_str and appointment_id_str.isdigit(): appointment_id = int(appointment_id_str)
            patient = Patient.query.get_or_404(patient_id)
            appointment = None
            valid_appointment_link = False
            if appointment_id:
                appointment = Appointment.query.filter_by(id=appointment_id, patient_id=patient.id).first()
                if appointment: valid_appointment_link = True
                else: flash(f'Warning: Appt ID {appointment_id} not found for patient {patient.patient_name}. Bill generated without link.', 'warning')
            new_bill = Bill(patient_id=patient.id, amount=amount, appointment_id=appointment.id if valid_appointment_link else None)
            db.session.add(new_bill)
            db.session.commit()
            flash(f'Bill generated successfully for Patient {patient.patient_name}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error generating bill: {e}', 'danger')
        print(f"Error generating bill: {e}")
    return redirect(url_for('admin_dashboard'))

@app.route('/bills/mark_paid/<int:bill_id>', methods=['POST'])
@login_required(role='admin')
def mark_bill_paid(bill_id):
    try:
        bill = Bill.query.get_or_404(bill_id)
        if bill.payment_status == 'Pending':
            bill.payment_status = 'Paid'
            db.session.commit()
            flash(f'Bill #{bill.id} marked as Paid.', 'success')
        else: flash(f'Bill #{bill.id} was already {bill.payment_status}.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating bill status: {e}', 'danger')
        print(f"Error marking bill paid: {e}")
    return redirect(url_for('admin_dashboard'))

@app.route('/bills/delete/<int:bill_id>', methods=['POST'])
@login_required(role='admin')
def delete_bill(bill_id):
    try:
        bill = Bill.query.get_or_404(bill_id)
        db.session.delete(bill)
        db.session.commit()
        flash(f'Bill #{bill.id} deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting bill: {e}', 'danger')
        print(f"Error deleting bill: {e}")
    return redirect(url_for('admin_dashboard'))

# --- Main Execution ---
if __name__ == '__main__':
    create_initial_data()
    app.run(debug=True, host='0.0.0.0', port=5000) # Set debug=False for production
