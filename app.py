from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_bcrypt import Bcrypt
import re
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Secret key for login session
app.secret_key = os.environ.get("SECRET_KEY", "local-development-key")

bcrypt = Bcrypt(app)


# =========================================================
# MySQL Database Connection
# =========================================================
def get_db_connection():
    return mysql.connector.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        port=int(os.environ.get("DB_PORT", "3306"))
    )

# =========================================================
# HOME PAGE
# =========================================================
@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# LOGIN
# =========================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    # Show login page
    if request.method == "GET":
        return render_template("login.html")

    # Get form data
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    account_type = request.form.get("account_type", "")

    # Check empty fields
    if not email or not password or not account_type:
        return render_template(
            "login.html",
            error="Please fill in all fields."
        )

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Find user by email
        cursor.execute("""
            SELECT id, name, email, password, role
            FROM users
            WHERE email = %s
        """, (email,))

        user = cursor.fetchone()

        # Account not registered
        if user is None:
            return render_template(
                "login.html",
                error="Account not registered. Please register first."
            )

        # Check password using werkzeug / generate_password_hash check
        if not check_password_hash(user["password"], password):
            return render_template(
                "login.html",
                error="Incorrect email or password."
            )

        # Check selected account type
        if account_type == "admin" and user["role"] != "admin":
            return render_template(
                "login.html",
                error="You are not registered as an administrator."
            )
        elif account_type == "user" and user["role"] != "user":
            return render_template(
                "login.html",
                error="This account is registered as an administrator."
            )

        # Save session
        session["user_id"] = user["id"]
        session["email"] = user["email"]
        session["name"] = user["name"]
        session["role"] = user["role"]

        # Redirect according to role
        if user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        else:
            return redirect(url_for("user_dashboard"))

    except Exception as e:
        # Log error in production
        return render_template("login.html", error="An error occurred during login. Please try again.")

    finally:
        # Safe cleanup check to prevent UnboundLocalError
        if cursor:
            cursor.close()
        if connection:
            connection.close()
# Make sure this appears ONLY ONCE in your app.py file:

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        # Handle password reset logic here
        return render_template('forgot_password.html', success="Reset instructions sent to your email.")
        
    return render_template('forgot_password.html')
@app.route('/forgot-password', methods=['GET', 'POST'])
def reset_pass():
    return render_template('forgot_password.html')
# =========================================================
# REGISTER
# =========================================================
@app.route("/register", methods=["GET", "POST"])
def register():

    # Show registration page
    if request.method == "GET":
        return render_template("register.html")

    # Get form data
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()  # Normalize email to lowercase
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")
    account_type = request.form.get("account_type", "user")

    # Check required fields
    if not name or not email or not password or not confirm_password:
        return render_template(
            "register.html",
            error="Please fill in all required fields."
        )

    # Check strong password (at least 8 chars, uppercase, lowercase, digit, special character)
    if not re.match(
        r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&]).{8,}$",
        password
    ):
        return render_template(
            "register.html",
            error=(
                "Password must contain at least 8 characters, "
                "one uppercase letter, one lowercase letter, "
                "one number and one special character."
            )
        )

    # Check confirm password
    if password != confirm_password:
        return render_template(
            "register.html",
            error="Passwords do not match."
        )

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Check whether email already exists
        cursor.execute(
            "SELECT id FROM users WHERE email = %s",
            (email,)
        )
        existing_user = cursor.fetchone()

        if existing_user:
            return render_template(
                "register.html",
                error="This email is already registered."
            )

        # Hash password securely
        password_hash = generate_password_hash(password)

        # Insert new user
        cursor.execute(
            """
            INSERT INTO users
            (name, email, password, role)
            VALUES (%s, %s, %s, %s)
            """,
            (
                name,
                email,
                password_hash,
                account_type
            )
        )

        connection.commit()

        # Registration successful
        return redirect(
            url_for("login", registered="success")
        )

    except mysql.connector.Error as error:
        if connection:
            connection.rollback()
        return render_template(
            "register.html",
            error=f"Database error: {error}"
        )

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

# =========================================================
# MEDICINE PAGE
# =========================================================
@app.route("/medicines")
def medicines():

    if "email" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, name, category, quantity,
               risk_level, last_updated
        FROM medicines
        ORDER BY id ASC
    """)

    medicines = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "medicines.html",
        medicines=medicines
    )
# =========================================================
# USER DASHBOARD
# =========================================================
@app.route("/user_dashboard")
def user_dashboard():

    if "email" not in session:
        return redirect(url_for("login"))
    if session.get("role") != "user":
        return redirect(url_for("admin_dashboard"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Get logged-in user
    cursor.execute("""
        SELECT id, name, email, role
        FROM users
        WHERE email = %s
    """, (session["email"],))

    user = cursor.fetchone()

    # Get medicines
    cursor.execute("""
        SELECT id, name, category, quantity,
               risk_level, last_updated
        FROM medicines
        ORDER BY id ASC
    """)

    medicines = cursor.fetchall()

    cursor.close()
    connection.close()

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    return render_template(
        "user_dashboard.html",
        user=user,
        medicines=medicines
    )
# =========================================================
# ADMIN DASHBOARD
# =========================================================
@app.route("/admin_dashboard")
def admin_dashboard():

    if "email" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return redirect(url_for("user_dashboard"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, name, category, quantity,
               risk_level, last_updated
        FROM medicines
        ORDER BY  id ASC
        
    """)

    medicines = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin_dashboard.html",
        medicines=medicines
    )

# =========================================================
# ADD MEDICINEs
# =========================================================
@app.route("/add_medicine", methods=["GET", "POST"])
def add_medicine():

    if "email" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return redirect(url_for("user_dashboard"))

    if request.method == "POST":

        name = request.form["name"].strip()
        category = request.form["category"].strip()
        quantity = request.form["quantity"].strip()

        if not name or not category or not quantity:
            return render_template(
                "add_medicine.html",
                error="All fields are required."
            )

        try:
            quantity = int(quantity)
        except ValueError:
            return render_template(
                "add_medicine.html",
                error="Quantity must be a valid number."
            )

        if quantity < 0:
            return render_template(
                "add_medicine.html",
                error="Quantity cannot be negative."
            )

        # Automatic risk calculation
        if quantity <= 100:
            risk_level = "High Risk"
        elif quantity < 500:
            risk_level = "Medium Risk"
        else:
            risk_level = "Low Risk"

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Check duplicate medicine name
        cursor.execute(
            "SELECT id FROM medicines WHERE LOWER(name) = LOWER(%s)",
            (name,)
        )

        existing_medicine = cursor.fetchone()

        if existing_medicine:
            cursor.close()
            connection.close()

            return render_template(
                "add_medicine.html",
                error="Medicine already exists."
            )

        # Insert medicines
        cursor.execute("""
            INSERT INTO medicines
            (name, category, quantity, risk_level)
            VALUES (%s, %s, %s, %s)
        """, (
            name,
            category,
            quantity,
            risk_level
        ))

        connection.commit()

        cursor.close()
        connection.close()

        return redirect(url_for("admin_dashboard"))

    return render_template("add_medicine.html")

# =========================================================
# LOGOUT
# =========================================================
@app.route("/logout")
def logout():

    # Clear login session
    session.clear()

    return redirect(url_for("home"))

@app.route("/shortage_risk")
def shortage_risk():
    if "email" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, name, category, quantity, risk_level, last_updated
        FROM medicines
        WHERE risk_level = 'High Risk'
        ORDER BY quantity ASC
    """)

    medicines = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "shortage_risk.html",
        medicines=medicines
    )


@app.route("/prediction")
def prediction():
    if "email" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, name, category, quantity,
                   risk_level, last_updated
            FROM medicines
            ORDER BY quantity ASC
        """)

        medicines = cursor.fetchall()

        high_count = 0
        medium_count = 0
        low_count = 0

        for medicine in medicines:
            quantity = medicine["quantity"]

            if quantity <= 100:
                medicine["prediction"] = "High Shortage Risk"
                medicine["prediction_icon"] = "🔴"
                medicine["prediction_message"] = "Stock is critically low."
                high_count += 1

            elif quantity < 500:
                medicine["prediction"] = "Medium Shortage Risk"
                medicine["prediction_icon"] = "🟡"
                medicine["prediction_message"] = "Monitor stock closely."
                medium_count += 1

            else:
                medicine["prediction"] = "Low Shortage Risk"
                medicine["prediction_icon"] = "🟢"
                medicine["prediction_message"] = "Current stock is sufficient according to the project threshold."
                low_count += 1

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "prediction.html",
        medicines=medicines,
        total_medicines=len(medicines),
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count
    )

    
@app.route("/alerts")
def alerts():

    if "email" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, name, category, quantity,
               risk_level, last_updated
        FROM medicines
        ORDER BY quantity ASC
    """)

    medicines = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "alerts.html",
        medicines=medicines
    )
# -----------------------------
# My Medicine
# -----------------------------
@app.route("/my_medicines")
def my_medicines():

    if "email" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, name, category, quantity,
               risk_level, last_updated
        FROM medicines
        ORDER BY  id ASC
    """)

    medicines = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "my_medicines.html",
        medicines=medicines
    )
@app.route("/search")
def search():

    if "email" not in session:
        return redirect(url_for("login"))

    query = request.args.get("query", "").strip()

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, name, category, quantity,
               risk_level, last_updated
        FROM medicines
        WHERE name LIKE %s
           OR category LIKE %s
        ORDER BY id ASC
    """, (
        "%" + query + "%",
        "%" + query + "%"
    ))

    medicines = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "medicines.html",
        medicines=medicines,
        search_query=query
    )
@app.route("/medicine/<int:medicine_id>")
def medicine_detail(medicine_id):

    if "email" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, name, category, quantity,
               risk_level, last_updated
        FROM medicines
        WHERE id = %s
    """, (medicine_id,))

    medicine = cursor.fetchone()

    cursor.close()
    connection.close()

    if medicine is None:
        return "Medicine not found", 404

    return render_template(
        "medicine_detail.html",
        medicine=medicine
    )
@app.route("/edit_medicine/<int:medicine_id>", methods=["GET", "POST"])
def edit_medicine(medicine_id):

    if "email" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return redirect(url_for("user_dashboard"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Get existing medicine
    cursor.execute("""
        SELECT id, name, category, quantity, risk_level, last_updated
        FROM medicines
        WHERE id = %s
    """, (medicine_id,))

    medicine = cursor.fetchone()

    if medicine is None:
        cursor.close()
        connection.close()
        return "Medicine not found", 404

    # Update medicine
    if request.method == "POST":

        name = request.form["name"].strip()
        category = request.form["category"].strip()
        quantity = request.form["quantity"].strip()

        if not name or not category or not quantity:
            cursor.close()
            connection.close()

            return render_template(
                "edit_medicine.html",
                medicine=medicine,
                error="All fields are required."
            )

        try:
            quantity = int(quantity)
        except ValueError:
            cursor.close()
            connection.close()

            return render_template(
                "edit_medicine.html",
                medicine=medicine,
                error="Quantity must be a valid number."
            )

        if quantity < 0:
            cursor.close()
            connection.close()

            return render_template(
                "edit_medicine.html",
                medicine=medicine,
                error="Quantity cannot be negative."
            )

        # Calculate risk automatically
        if quantity <= 100:
            risk_level = "High Risk"
        elif quantity < 500:
            risk_level = "Medium Risk"
        else:
            risk_level = "Low Risk"

        cursor.execute("""
            UPDATE medicines
            SET name = %s,
                category = %s,
                quantity = %s,
                risk_level = %s,
                last_updated = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            name,
            category,
            quantity,
            risk_level,
            medicine_id
        ))

        connection.commit()

        cursor.close()
        connection.close()

        return redirect(url_for("admin_dashboard"))

    cursor.close()
    connection.close()

    return render_template(
        "edit_medicine.html",
        medicine=medicine
    )
@app.route("/delete_medicine/<int:medicine_id>", methods=["POST"])
def delete_medicine(medicine_id):

    if "email" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return redirect(url_for("user_dashboard"))

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM medicines WHERE id = %s",
        (medicine_id,)
    )

    connection.commit()

    cursor.close()
    connection.close()

    return redirect(url_for("admin_dashboard"))
@app.route("/profile")
def profile():

    if "email" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, name, email, role
        FROM users
        WHERE email = %s
    """, (session["email"],))

    user = cursor.fetchone()

    cursor.close()
    connection.close()

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    return render_template(
        "profile.html",
        user=user
    )
# =========================================================
# RUN FLASK APPLICATION
# =========================================================
if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        use_reloader=False
    )
