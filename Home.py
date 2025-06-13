import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import pyotp
from datetime import datetime
from contextlib import closing
from fpdf import FPDF
from sklearn.linear_model import LinearRegression

# Mobile-friendly page configuration
st.set_page_config(
    page_title="Student Report Card System",
    layout="centered",
    initial_sidebar_state="auto",
    page_icon="📚",
)

# Add mobile-friendly CSS
st.markdown("""
    <style>
        @media screen and (max-width: 768px) {
            h1 {
                font-size: 1.5rem !important;
            }
            h2 {
                font-size: 1.3rem !important;
            }
            h3 {
                font-size: 1.1rem !important;
            }
            .stTextInput input, .stTextArea textarea, .stSelectbox select {
                font-size: 1rem !important;
            }
            .stButton button {
                width: 100% !important;
                font-size: 1rem !important;
                margin: 0.25rem 0 !important;
            }
            .stDataFrame {
                font-size: 0.9rem !important;
            }
            .stMetric {
                padding: 0.5rem !important;
            }
            .stMetric label {
                font-size: 0.9rem !important;
            }
            .stMetric value {
                font-size: 1.1rem !important;
            }
        }
    </style>
""", unsafe_allow_html=True)

def upgrade_database():
    """Handle database schema upgrades"""
    with closing(sqlite3.connect("users.db")) as conn:
        cursor = conn.cursor()
        
        # Check if is_admin column exists in teachers table
        cursor.execute("PRAGMA table_info(teachers)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'is_admin' not in columns:
            # Add the column if it doesn't exist
            cursor.execute("ALTER TABLE teachers ADD COLUMN is_admin BOOLEAN DEFAULT 0")
            # Update existing admin account
            cursor.execute(
                "UPDATE teachers SET is_admin = 1 WHERE username = ?",
                ("Lam",)
            )
            conn.commit()

# Initialize databases
def init_db():
    with closing(sqlite3.connect("reports.db")) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll_no TEXT NOT NULL,
            class TEXT NOT NULL,
            section TEXT NOT NULL,
            tamil INTEGER NOT NULL,
            english INTEGER NOT NULL,
            maths INTEGER NOT NULL,
            science INTEGER NOT NULL,
            social INTEGER NOT NULL,
            computer INTEGER NOT NULL,
            total INTEGER NOT NULL,
            percentage REAL NOT NULL,
            grade TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
        """)
        conn.commit()
    
    with closing(sqlite3.connect("users.db")) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_no TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            class TEXT NOT NULL,
            section TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS parent_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_roll_no TEXT UNIQUE NOT NULL,
            parent_email TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(student_roll_no) REFERENCES students(roll_no)
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS meeting_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_no TEXT NOT NULL,
            meeting_date TEXT NOT NULL,
            requested_at TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            teacher_notes TEXT,
            approval_timestamp TEXT,
            teacher_username TEXT
        )
        """)
        cursor.execute("SELECT 1 FROM teachers WHERE username=?", ("Lam",))
        if not cursor.fetchone():
            hashed_password = hashlib.sha256("Lam123".encode()).hexdigest()
            cursor.execute(
                "INSERT INTO teachers (username, password, full_name, created_at, is_admin) VALUES (?, ?, ?, ?, ?)",
                ("Lam", hashed_password, "Admin Teacher", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 1)
            )
            conn.commit()

# Initialize database and handle upgrades
init_db()
upgrade_database()

# Helper functions
def validate_parent_email(roll_no, email):
    with closing(sqlite3.connect("users.db")) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM parent_accounts WHERE student_roll_no=? AND parent_email=?",
            (roll_no, email)
        )
        return cursor.fetchone() is not None

def get_student_info(roll_no):
    with closing(sqlite3.connect("users.db")) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT roll_no, full_name, class, section FROM students WHERE roll_no=?",
            (roll_no,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "roll_no": row[0],
                "full_name": row[1],
                "class": row[2],
                "section": row[3]
            }
        return {}

def update_meeting_request_status(request_id, status, teacher_notes=""):
    with closing(sqlite3.connect("users.db")) as conn:
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "UPDATE meeting_requests SET status=?, teacher_notes=?, approval_timestamp=? WHERE id=?",
            (status, teacher_notes, timestamp, request_id)
        )
        conn.commit()

def get_single_student_meeting_request(roll_no):
    with closing(sqlite3.connect("users.db")) as conn:
        df = pd.read_sql("""
        SELECT
            meeting_date as "Preferred Date",
            requested_at as "Requested At",
            status as "Status",
            teacher_notes as "Teacher Notes",
            approval_timestamp as "Response Date"
        FROM meeting_requests
        WHERE roll_no = ?
        ORDER BY requested_at DESC
        LIMIT 1
        """, conn, params=(roll_no,))
    return df

def get_meeting_requests(teacher_username=None):
    with closing(sqlite3.connect("users.db")) as conn:
        if teacher_username:
            df = pd.read_sql("""
                SELECT
                    mr.id,
                    mr.roll_no as "Student Roll No",
                    s.full_name as "Student Name",
                    mr.meeting_date as "Preferred Date",
                    mr.requested_at as "Requested At",
                    mr.status as "Status",
                    mr.teacher_notes as "Teacher Notes"
                FROM meeting_requests mr
                JOIN students s ON mr.roll_no = s.roll_no
                WHERE mr.teacher_username = ?
                ORDER BY mr.requested_at DESC
            """, conn, params=(teacher_username,))
        else:
            df = pd.read_sql("""
                SELECT
                    mr.id,
                    mr.roll_no as "Student Roll No",
                    s.full_name as "Student Name",
                    mr.meeting_date as "Preferred Date",
                    mr.requested_at as "Requested At",
                    mr.status as "Status",
                    mr.teacher_notes as "Teacher Notes"
                FROM meeting_requests mr
                JOIN students s ON mr.roll_no = s.roll_no
                ORDER BY mr.requested_at DESC
            """, conn)
    return df

def add_parent_account(student_roll_no, parent_email):
    try:
        with closing(sqlite3.connect("users.db", timeout=10)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM parent_accounts WHERE student_roll_no=?",
                (student_roll_no,)
            )
            cursor.execute(
                "INSERT INTO parent_accounts (student_roll_no, parent_email, created_at) VALUES (?, ?, ?)",
                (student_roll_no, parent_email, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False
    except sqlite3.OperationalError as e:
        st.error(f"Database operation failed: {str(e)}")
        return False

# Authentication functions
def authenticate_teacher(username, password):
    """Authenticate teacher and return (name, is_admin) tuple"""
    with closing(sqlite3.connect("users.db")) as conn:
        cursor = conn.cursor()
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        try:
            cursor.execute(
                "SELECT full_name, is_admin FROM teachers WHERE username=? AND password=?",
                (username, hashed_password)
            )
            result = cursor.fetchone()
            if result:
                return result[0], bool(result[1])
        except sqlite3.OperationalError:
            # Fallback if is_admin column doesn't exist (shouldn't happen after upgrade)
            cursor.execute(
                "SELECT full_name FROM teachers WHERE username=? AND password=?",
                (username, hashed_password)
            )
            result = cursor.fetchone()
            if result:
                return result[0], username == "Lam"  # Only "Lam" is admin in this case
        return None, False

def authenticate_student(roll_no, password):
    with closing(sqlite3.connect("users.db")) as conn:
        cursor = conn.cursor()
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute(
            "SELECT full_name FROM students WHERE roll_no=? AND password=?",
            (roll_no, hashed_password)
        )
        result = cursor.fetchone()
        return result[0] if result else None

# Teacher functions
def create_student(roll_no, password, full_name, class_name, section):
    with closing(sqlite3.connect("users.db")) as conn:
        cursor = conn.cursor()
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        try:
            cursor.execute(
                "INSERT INTO students (roll_no, password, full_name, class, section, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (roll_no, hashed_password, full_name, class_name, section, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

# Report functions
def save_report(report_data):
    with closing(sqlite3.connect("reports.db")) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT OR REPLACE INTO reports (
            name, roll_no, class, section,
            tamil, english, maths, science, social, computer,
            total, percentage, grade, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            report_data["Name"],
            report_data["Roll No"],
            report_data["Class"],
            report_data["Section"],
            report_data["Tamil"],
            report_data["English"],
            report_data["Maths"],
            report_data["Science"],
            report_data["Social"],
            report_data["Computer"],
            report_data["Total"],
            report_data["Percentage"],
            report_data["Grade"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()

def get_student_report(roll_no):
    with closing(sqlite3.connect("reports.db")) as conn:
        df = pd.read_sql("""
        SELECT 
            name as "Name",
            roll_no as "Roll No",
            class as "Class",
            section as "Section",
            tamil as "Tamil",
            english as "English",
            maths as "Maths",
            science as "Science",
            social as "Social",
            computer as "Computer",
            total as "Total",
            percentage as "Percentage",
            grade as "Grade",
            timestamp as "Date"
        FROM reports
        WHERE roll_no = ?
        ORDER BY timestamp DESC
        LIMIT 1
        """, conn, params=(roll_no,))
    return df

def get_all_students():
    with closing(sqlite3.connect("users.db")) as conn:
        df = pd.read_sql("""
        SELECT 
            roll_no as "Roll No",
            full_name as "Full Name",
            class as "Class",
            section as "Section"
        FROM students
        ORDER BY class, section, roll_no
        """, conn)
    return df

# AI Prediction function
def predict_student_performance(roll_no):
    try:
        history = pd.read_sql(
            "SELECT * FROM reports WHERE roll_no=? ORDER BY timestamp",
            sqlite3.connect("reports.db"),
            params=(roll_no,)
        )
        
        if len(history) >= 3:
            X = history[['tamil', 'english', 'maths', 'science', 'social', 'computer']].values[:-1]
            y = history['percentage'].values[1:]
            
            if len(X) == len(y):
                model = LinearRegression()
                model.fit(X, y)
                
                latest_scores = history[['tamil', 'english', 'maths', 'science', 'social', 'computer']].iloc[-1].values.reshape(1, -1)
                prediction = model.predict(latest_scores)[0]
                return max(0, min(100, prediction))
    except Exception as e:
        st.error(f"Prediction error: {str(e)}")
    return None

# PDF Generation
def generate_pdf_report(report_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Official Report Card", ln=1, align='C')
    
    if 'Date' not in report_data:
        report_data['Date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    pdf.cell(200, 10, txt=f"Name: {report_data['Name']}", ln=1)
    pdf.cell(200, 10, txt=f"Class: {report_data['Class']}-{report_data['Section']}", ln=1)
    pdf.cell(200, 10, txt=f"Roll No: {report_data['Roll No']}", ln=1)
    pdf.cell(200, 10, txt=f"Date: {report_data['Date']}", ln=1)
    
    pdf.cell(200, 10, txt="Subject Marks:", ln=1)
    subjects = ["Tamil", "English", "Maths", "Science", "Social", "Computer"]
    for subject in subjects:
        pdf.cell(200, 10, txt=f"{subject}: {report_data[subject]}/100", ln=1)
    
    pdf.cell(200, 10, txt=f"Total: {report_data['Total']}/600", ln=1)
    pdf.cell(200, 10, txt=f"Percentage: {report_data['Percentage']}%", ln=1)
    pdf.cell(200, 10, txt=f"Grade: {report_data['Grade']}", ln=1)
    
    temp_pdf_path = "report_card_temp.pdf"
    pdf.output(temp_pdf_path)
    
    with open(temp_pdf_path, "rb") as f:
        st.download_button(
            "📥 Download PDF Report", 
            f.read(), 
            file_name="report_card.pdf",
            mime="application/pdf",
            use_container_width=True
        )

def get_student_parent_email(roll_no):
    with closing(sqlite3.connect("users.db")) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT parent_email FROM parent_accounts WHERE student_roll_no=?",
            (roll_no,)
        )
        result = cursor.fetchone()
        return result[0] if result else None

# UI Components
def teacher_login():
    st.title("Teacher Login")
    with st.form("teacher_login"):
        username = st.text_input("Username", key="teacher_user")
        password = st.text_input("Password", type="password", key="teacher_pass")
        submit = st.form_submit_button("Login", use_container_width=True)
        
        if submit:
            teacher_name, is_admin = authenticate_teacher(username, password)
            if teacher_name:
                st.session_state.logged_in = True
                st.session_state.role = "teacher"
                st.session_state.username = username
                st.session_state.teacher_name = teacher_name
                st.session_state.is_admin = is_admin
                st.success(f"Welcome {teacher_name}!")
                st.rerun()
            else:
                st.error("Invalid username or password")

def student_login():
    st.title("Student Login")
    with st.form("student_login"):
        roll_no = st.text_input("Roll Number", key="student_roll")
        password = st.text_input("Password", type="password", key="student_pass")
        submit = st.form_submit_button("Login", use_container_width=True)
        
        if submit:
            student_name = authenticate_student(roll_no, password)
            if student_name:
                st.session_state.logged_in = True
                st.session_state.role = "student"
                st.session_state.roll_no = roll_no
                st.session_state.student_name = student_name
                st.success(f"Welcome {student_name}!")
                st.rerun()
            else:
                st.error("Invalid roll number or password")

def parent_login():
    st.title("Parent Portal Login")
    
    with st.form("parent_login"):
        student_roll_no = st.text_input("Student Roll Number", key="parent_roll")
        parent_email = st.text_input("Registered Parent Email", key="parent_email")
        
        totp_secret = "base32secret3232"

        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Generate OTP", use_container_width=True):
                if validate_parent_email(student_roll_no, parent_email):
                    totp = pyotp.TOTP(totp_secret)
                    otp = totp.now()
                    st.session_state.temp_otp = otp
                    st.session_state.temp_roll_no = student_roll_no
                    st.info(f"OTP generated: **{otp}**")
                else:
                    st.error("Invalid roll number/email combination.")
        
        entered_otp = st.text_input("Enter 6-digit OTP", key="parent_otp_input")

        if 'temp_otp' in st.session_state and st.session_state.temp_roll_no == student_roll_no:
            with col2:
                if st.form_submit_button("Verify OTP", use_container_width=True):
                    if entered_otp == st.session_state.temp_otp:
                        st.session_state.logged_in = True
                        st.session_state.role = "parent"
                        st.session_state.roll_no = st.session_state.temp_roll_no
                        del st.session_state.temp_otp
                        del st.session_state.temp_roll_no
                        st.success("OTP verified!")
                        st.rerun()
                    else:
                        st.error("Invalid OTP")
            
            if st.form_submit_button("Resend OTP", use_container_width=True):
                if validate_parent_email(student_roll_no, parent_email):
                    totp = pyotp.TOTP(totp_secret)
                    otp = totp.now()
                    st.session_state.temp_otp = otp
                    st.session_state.temp_roll_no = student_roll_no
                    st.info(f"New OTP generated: **{otp}**")
                else:
                    st.error("Cannot resend OTP.")

def teacher_portal():
    st.title(f"👩‍🏫 Teacher Portal")
    st.subheader(f"Welcome {st.session_state.teacher_name}")
    
    # Create tabs based on admin status
    if st.session_state.get('is_admin', False):
        tabs = ["📝 Enter Marks", "👥 Manage Students", "📊 View Reports", 
               "📅 Meetings", "📧 Parent Emails", "➕ Add Teacher"]
    else:
        tabs = ["📝 Enter Marks", "👥 Manage Students", "📊 View Reports", 
               "📅 Meetings", "📧 Parent Emails"]
    
    # Create tabs dynamically
    created_tabs = st.tabs(tabs)
    
    with created_tabs[0]:
        with st.form("student_marks", clear_on_submit=True):
            st.header("Enter Student Marks")
            
            students_df = get_all_students()
            if students_df.empty:
                st.warning("No students found. Please add students first.")
            else:
                selected_student = st.selectbox(
                    "Select Student",
                    students_df["Roll No"] + " - " + students_df["Full Name"],
                    key="mark_student_select"
                )
                roll_no = selected_student.split(" - ")[0]
                
                subjects = ["Tamil", "English", "Maths", "Science", "Social", "Computer"]
                marks = {}
                
                for subject in subjects:
                    marks[subject] = st.number_input(
                        f"{subject} Marks (0-100)",
                        min_value=0,
                        max_value=100,
                        step=1,
                        key=f"marks_{subject}"
                    )

                submitted = st.form_submit_button("Save Marks", use_container_width=True)
                
                if submitted:
                    student_info = students_df[students_df["Roll No"] == roll_no].iloc[0]
                    
                    total = sum(marks.values())
                    percentage = round((total / (len(subjects) * 100)) * 100, 2)
                    
                    if percentage >= 90:
                        grade = "O (Outstanding)"
                    elif percentage >= 75:
                        grade = "A (Very Good)"
                    elif percentage >= 60:
                        grade = "B (Good)"
                    elif percentage >= 50:
                        grade = "C (Average)"
                    elif percentage >= 40:
                        grade = "D (Needs Improvement)"
                    else:
                        grade = "F (Fail)"
                    
                    report_data = {
                        "Name": student_info["Full Name"],
                        "Roll No": roll_no,
                        "Class": student_info["Class"],
                        "Section": student_info["Section"],
                        **marks,
                        "Total": total,
                        "Percentage": percentage,
                        "Grade": grade
                    }
                    
                    save_report(report_data)
                    st.success("Marks saved successfully!")
    
    with created_tabs[1]:
        st.header("Manage Students")
        
        with st.expander("➕ Add New Student"):
            with st.form("add_student", clear_on_submit=True):
                roll_no = st.text_input("Roll Number", key="new_roll")
                full_name = st.text_input("Full Name", key="new_name")
                class_name = st.text_input("Class", key="new_class")
                section = st.text_input("Section", key="new_section")
                password = st.text_input("Password", type="password", key="new_pass")
                
                submitted = st.form_submit_button("Add Student", use_container_width=True)
                if submitted:
                    if create_student(roll_no, password, full_name, class_name, section):
                        st.success("Student added successfully!")
                    else:
                        st.error("Roll number already exists")
        
        st.header("Student List")
        students_df = get_all_students()
        if students_df.empty:
            st.info("No students found")
        else:
            st.dataframe(students_df, hide_index=True, use_container_width=True)
    
    with created_tabs[2]:
        st.header("View All Reports")
        reports = pd.read_sql("SELECT * FROM reports ORDER BY class, section, roll_no", sqlite3.connect("reports.db"))
        if reports.empty:
            st.info("No reports found")
        else:
            st.dataframe(reports, hide_index=True, use_container_width=True)
    
    with created_tabs[3]:
        st.header("Parent Meeting Requests")
        
        meeting_requests_df = get_meeting_requests(st.session_state.username)
        
        if meeting_requests_df.empty:
            st.info("No meeting requests pending.")
        else:
            pending_requests_df = meeting_requests_df[meeting_requests_df['Status'] == 'Pending']
            other_requests_df = meeting_requests_df[meeting_requests_df['Status'] != 'Pending']

            if not pending_requests_df.empty:
                st.write("### Pending Requests")
                for index, row in pending_requests_df.iterrows():
                    request_id = row['id']
                    with st.form(key=f"meeting_request_form_{request_id}"):
                        st.subheader(f"Request from {row['Student Name']}")
                        st.caption(f"Roll No: {row['Student Roll No']}")
                        st.write(f"**Preferred Date:** {row['Preferred Date']}")
                        st.write(f"**Requested On:** {row['Requested At']}")
                        
                        teacher_notes = st.text_area("Teacher Notes", key=f"notes_{request_id}")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("✅ Approve", use_container_width=True):
                                update_meeting_request_status(request_id, "Approved", teacher_notes)
                                st.success("Meeting approved!")
                                st.rerun()
                        with col2:
                            if st.form_submit_button("❌ Reject", use_container_width=True):
                                update_meeting_request_status(request_id, "Rejected", teacher_notes)
                                st.warning("Meeting rejected.")
                                st.rerun()
                        st.markdown("---")
                
            if not other_requests_df.empty:
                st.write("### Reviewed Requests")
                st.dataframe(
                    other_requests_df.drop(columns=['id']), 
                    hide_index=True, 
                    use_container_width=True
                )

    with created_tabs[4]:
        st.header("Manage Parent Email Addresses")
        
        students_df = get_all_students()
        if students_df.empty:
            st.warning("No students found. Please add students first.")
        else:
            selected_student = st.selectbox(
                "Select Student",
                students_df["Roll No"] + " - " + students_df["Full Name"],
                key="parent_email_student_select"
            )
            roll_no = selected_student.split(" - ")[0]
            
            current_email = get_student_parent_email(roll_no)
            
            with st.form("parent_email_form"):
                new_email = st.text_input(
                    "Parent Email",
                    value=current_email if current_email else "",
                    key="parent_email_input"
                )
                
                submitted = st.form_submit_button("Save Email", use_container_width=True)
                if submitted:
                    if new_email:
                        try:
                            with closing(sqlite3.connect("users.db", timeout=10)) as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    "DELETE FROM parent_accounts WHERE student_roll_no=?",
                                    (roll_no,)
                                )
                                cursor.execute(
                                    "INSERT INTO parent_accounts (student_roll_no, parent_email, created_at) VALUES (?, ?, ?)",
                                    (roll_no, new_email, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                )
                                conn.commit()
                                st.success("Parent email saved successfully!")
                        except sqlite3.Error as e:
                            st.error(f"Failed to save email: {str(e)}")
                    else:
                        try:
                            with closing(sqlite3.connect("users.db", timeout=10)) as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    "DELETE FROM parent_accounts WHERE student_roll_no=?",
                                    (roll_no,)
                                )
                                conn.commit()
                                st.success("Parent email removed.")
                        except sqlite3.Error as e:
                            st.error(f"Failed to remove email: {str(e)}")

    # Only show Add Teacher tab for admin users
    if st.session_state.get('is_admin', False) and len(created_tabs) > 5:
        with created_tabs[5]:
            st.header("Add New Teacher (Admin Only)")
            with st.form("add_teacher_form", clear_on_submit=True):
                new_username = st.text_input("Username*", key="new_teacher_user")
                new_full_name = st.text_input("Full Name*", key="new_teacher_name")
                new_password = st.text_input("Password*", type="password", key="new_teacher_pass")
                new_password_confirm = st.text_input("Confirm Password*", type="password", key="new_teacher_pass_confirm")
                make_admin = st.checkbox("Make this teacher an admin")
                
                submitted = st.form_submit_button("Add Teacher", use_container_width=True)
                if submitted:
                    if not all([new_username, new_full_name, new_password, new_password_confirm]):
                        st.error("Please fill all required fields (*)")
                    elif new_password != new_password_confirm:
                        st.error("Passwords don't match!")
                    else:
                        with closing(sqlite3.connect("users.db")) as conn:
                            cursor = conn.cursor()
                            hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
                            try:
                                cursor.execute(
                                    "INSERT INTO teachers (username, password, full_name, created_at, is_admin) VALUES (?, ?, ?, ?, ?)",
                                    (new_username, hashed_password, new_full_name, 
                                     datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                                     1 if make_admin else 0)
                                )
                                conn.commit()
                                st.success("Teacher added successfully!")
                                st.rerun()
                            except sqlite3.IntegrityError:
                                st.error("Username already exists.")

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear() or st.rerun(), use_container_width=True)

def student_portal():
    st.title(f"👨‍🎓 Student Portal")
    st.subheader(f"Welcome {st.session_state.student_name}")
    
    report = get_student_report(st.session_state.roll_no)
    if report.empty:
        st.warning("No report found for your roll number.")
        st.info("Please contact your teacher if you believe this is an error.")
    else:
        data = report.iloc[0].to_dict()
        
        st.subheader("Your Latest Report Card")
        st.markdown(f"**Name:** {data['Name']}")
        st.markdown(f"**Class:** {data['Class']}-{data['Section']}")
        st.markdown(f"**Roll No:** {data['Roll No']}")
        st.markdown(f"**Date:** {data['Date']}")
        
        st.divider()
        
        st.subheader("Subject-wise Marks")
        subjects = ["Tamil", "English", "Maths", "Science", "Social", "Computer"]
        for subject in subjects:
            score = data[subject]
            st.metric(label=f"{subject}", value=f"{score}/100", delta_color="off")
        
        st.divider()
        
        cols = st.columns(3)
        metrics = [
            ("Total", f"{data['Total']}/600"),
            ("Percentage", f"{data['Percentage']}%"),
            ("Grade", data['Grade'])
        ]
        for col, (label, value) in zip(cols, metrics):
            with col:
                st.metric(label, value)
        
        st.divider()
        
        st.subheader("Performance Prediction")
        prediction = predict_student_performance(st.session_state.roll_no)
        if prediction is not None:
            current_perc = data['Percentage']
            delta = prediction - current_perc
            
            st.metric(
                label="Next Term Prediction", 
                value=f"{prediction:.1f}%",
                delta=f"{delta:+.1f}%",
                delta_color="normal"
            )
            
            if delta > 5:
                st.success("📈 You're improving! Keep it up!")
            elif delta < -5:
                st.warning("📉 Focus on weaker subjects.")
            else:
                st.info("🔄 Your performance is stable.")
        else:
            st.info("Not enough data for prediction (need 3+ reports).")
        
        if st.button("Download PDF Report", use_container_width=True):
            generate_pdf_report(data)
            st.success("PDF ready for download.")

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear() or st.rerun(), use_container_width=True)

def parent_portal():
    st.title(f"👪 Parent Portal")
    st.subheader(f"Student: {st.session_state.roll_no}")
    
    student_info = get_student_info(st.session_state.roll_no)
    st.write(f"Viewing report for: **{student_info.get('full_name', 'Unknown')}**")
    
    report = get_student_report(st.session_state.roll_no)
    if not report.empty:
        data = report.iloc[0].to_dict()
        
        st.subheader("Student Report Card")
        st.markdown(f"**Name:** {data['Name']}")
        st.markdown(f"**Class:** {data['Class']}-{data['Section']}")
        st.markdown(f"**Roll No:** {data['Roll No']}")
        st.markdown(f"**Date:** {data['Date']}")
        
        st.divider()
        
        st.subheader("Subject Marks")
        subjects = ["Tamil", "English", "Maths", "Science", "Social", "Computer"]
        for subject in subjects:
            score = data[subject]
            color = "green" if score >= 75 else "orange" if score >= 45 else "red"
            st.markdown(f"<span style='color:{color}'>{subject}: {score}/100</span>", unsafe_allow_html=True)
        
        st.divider()
        
        cols = st.columns(3)
        metrics = [
            ("Total", f"{data['Total']}/600"),
            ("Percentage", f"{data['Percentage']}%"),
            ("Grade", data['Grade'])
        ]
        for col, (label, value) in zip(cols, metrics):
            with col:
                st.metric(label, value)
        
        st.divider()
        
        latest_request_df = get_single_student_meeting_request(st.session_state.roll_no)
        if not latest_request_df.empty:
            latest_request = latest_request_df.iloc[0]
            st.info("**Latest Meeting Request Status:**")
            st.write(f"- **Date:** {latest_request['Preferred Date']}")
            st.write(f"- **Status:** **{latest_request['Status']}**")
            if latest_request['Status'] != 'Pending':
                st.write(f"- **Notes:** {latest_request.get('Teacher Notes', 'N/A')}")
            st.markdown("---")
        
        with closing(sqlite3.connect("users.db")) as conn:
            teachers_df = pd.read_sql("SELECT username, full_name FROM teachers", conn)
        teacher_options = teachers_df["username"] + " - " + teachers_df["full_name"]
        selected_teacher = st.selectbox("Select Teacher", teacher_options)
        teacher_username = selected_teacher.split(" - ")[0]
        meeting_date = st.date_input("Preferred date")
        if st.button("Request Meeting", use_container_width=True):
            if meeting_date and teacher_username:
                with closing(sqlite3.connect("users.db")) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO meeting_requests (roll_no, meeting_date, requested_at, status, teacher_username) VALUES (?, ?, ?, ?, ?)",
                        (st.session_state.roll_no, str(meeting_date), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'Pending', teacher_username)
                    )
                    conn.commit()
                st.success("Meeting request submitted!")
                st.rerun()
            else:
                st.warning("Please select a date and teacher.")
        
        if st.button("Download Report", use_container_width=True):
            generate_pdf_report(data)
    
    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear() or st.rerun(), use_container_width=True)

# Main App
def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.role = None
        st.session_state.username = None
        st.session_state.teacher_name = None
        st.session_state.roll_no = None
        st.session_state.student_name = None

    if not st.session_state.logged_in:
        with st.sidebar:
            st.title("Login")
            choice = st.radio(
                "Select role:",
                ["Teacher", "Student", "Parent"],
                label_visibility="collapsed"
            )
        
        if choice == "Teacher":
            teacher_login()
        elif choice == "Student":
            student_login()
        elif choice == "Parent":
            parent_login()
    else:
        if st.session_state.role == "teacher":
            teacher_portal()
        elif st.session_state.role == "student":
            student_portal()
        elif st.session_state.role == "parent":
            parent_portal()

if __name__ == "__main__":
    main()