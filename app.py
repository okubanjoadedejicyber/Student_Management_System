
import os
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, abort
)
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import (
    check_password_hash, generate_password_hash
)


app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("Set the SECRET_KEY environment variable.")

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("VERCEL") == "1"
)

csrf = CSRFProtect(app)

database_url = os.environ.get("STUDENTDB_URL")
if not database_url:
    raise RuntimeError("Set the STUDENTDB_URL environment variable.")

# Support older PostgreSQL URL prefixes if present.
if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://", "postgresql+psycopg://", 1
    )
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace(
        "postgresql://", "postgresql+psycopg://", 1
    )

db = create_engine(database_url, pool_pre_ping=True)


def login_required(role=None):
    """Require a logged-in user, optionally of a specific role."""
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in first.", "error")
                if role == "student":
                    return redirect(url_for("student_login"))
                return redirect(url_for("staff_login"))

            if role and session.get("role") != role:
                abort(403)

            return view(*args, **kwargs)
        return wrapped_view
    return decorator


@app.route("/")
def landing():
    if session.get("role") == "staff":
        return redirect(url_for("staff_dashboard"))
    if session.get("role") == "student":
        return redirect(url_for("student_dashboard"))
    return render_template("landing.html")


@app.route("/staff/login", methods=["GET", "POST"])
def staff_login():
    if "user_id" in session:
        if session.get("role") == "staff":
            return redirect(url_for("staff_dashboard"))
        return redirect(url_for("student_dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        with db.connect() as connection:
            staff = connection.execute(
                text("""
                    SELECT id, username, password_hash
                    FROM staff_users
                    WHERE LOWER(username) = LOWER(:username)
                """),
                {"username": username}
            ).mappings().first()

        if staff and check_password_hash(
            staff["password_hash"], password
        ):
            session.clear()
            session["user_id"] = staff["id"]
            session["role"] = "staff"
            session["username"] = staff["username"]
            return redirect(url_for("staff_dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("staff_login.html")


@app.route("/student/register", methods=["GET", "POST"])
def student_register():
    if "user_id" in session:
        if session.get("role") == "student":
            return redirect(url_for("student_dashboard"))
        return redirect(url_for("staff_dashboard"))

    if request.method == "POST":
        surname = (request.form.get("surname") or "").strip()
        matric = (
            request.form.get("matric_number") or ""
        ).strip().lower()
        password = request.form.get("password") or ""
        confirmation = request.form.get("confirm_password") or ""

        if not all([surname, matric, password, confirmation]):
            flash("Complete all fields.", "error")
            return render_template("student_register.html")

        if len(password) < 12:
            flash("Use a password of at least 12 characters.", "error")
            return render_template("student_register.html")

        if password != confirmation:
            flash("The passwords do not match.", "error")
            return render_template("student_register.html")

        password_hash = generate_password_hash(password)

        try:
            with db.begin() as connection:
                student = connection.execute(
                    text("""
                        SELECT id, password_hash
                        FROM students
                        WHERE LOWER(TRIM(surname)) = LOWER(:surname)
                          AND LOWER(TRIM(matric_number)) = :matric
                        FOR UPDATE
                    """),
                    {"surname": surname, "matric": matric}
                ).mappings().first()

                if not student:
                    flash(
                        "We could not verify your student record. "
                        "Check your details or contact staff.",
                        "error"
                    )
                    return render_template("student_register.html")

                if student["password_hash"]:
                    flash(
                        "This student account is already registered. "
                        "Please log in.",
                        "error"
                    )
                    return render_template("student_register.html")

                connection.execute(
                    text("""
                        UPDATE students
                        SET password_hash = :password_hash
                        WHERE id = :id
                          AND password_hash IS NULL
                    """),
                    {
                        "password_hash": password_hash,
                        "id": student["id"]
                    }
                )

        except Exception:
            app.logger.exception("Student registration failed")
            flash(
                "Registration could not be completed. Please try again.",
                "error"
            )
            return render_template("student_register.html"), 500

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("student_login"))

    return render_template("student_register.html")


@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    if "user_id" in session:
        if session.get("role") == "student":
            return redirect(url_for("student_dashboard"))
        return redirect(url_for("staff_dashboard"))

    if request.method == "POST":
        matric = (
            request.form.get("matric_number") or ""
        ).strip().lower()
        password = request.form.get("password") or ""

        with db.connect() as connection:
            student = connection.execute(
                text("""
                    SELECT id, password_hash
                    FROM students
                    WHERE LOWER(TRIM(matric_number)) = :matric
                """),
                {"matric": matric}
            ).mappings().first()

        if (
            student
            and student["password_hash"]
            and check_password_hash(student["password_hash"], password)
        ):
            session.clear()
            session["user_id"] = student["id"]
            session["role"] = "student"
            return redirect(url_for("student_dashboard"))

        flash(
            "Invalid matric number or password. Register first if "
            "you have not created an account.",
            "error"
        )

    return render_template("student_login.html")


@app.route("/staff/dashboard")
@login_required("staff")
def staff_dashboard():
    with db.connect() as connection:
        students = connection.execute(
            text("""
                SELECT id, first_name, middle_name, surname,
                       matric_number, department, level
                FROM students
                ORDER BY surname, first_name
            """)
        ).mappings().all()

    return render_template(
        "staff_dashboard.html", students=students
    )


@app.route("/student/dashboard")
@login_required("student")
def student_dashboard():
    with db.connect() as connection:
        student = connection.execute(
            text("""
                SELECT id, first_name, middle_name, surname,
                       matric_number, department, level
                FROM students
                WHERE id = :id
            """),
            {"id": session["user_id"]}
        ).mappings().first()

    if not student:
        session.clear()
        flash("Your student record could not be found.", "error")
        return redirect(url_for("student_login"))

    return render_template(
        "student_dashboard.html", student=student
    )


@app.route("/add", methods=["GET", "POST"])
@login_required("staff")
def add():
    if request.method == "POST":
        first_name = (request.form.get("first_name") or "").strip()
        middle_name = (request.form.get("middle_name") or "").strip()
        surname = (request.form.get("surname") or "").strip()
        matric = (
            request.form.get("matric_number") or ""
        ).strip().lower()
        department = (request.form.get("department") or "").strip()
        level_text = (request.form.get("level") or "").strip()

        if not all([first_name, surname, matric, department, level_text]):
            flash(
                "First name, surname, matric number, department "
                "and level are required.",
                "error"
            )
            return render_template("add.html")

        try:
            level = int(level_text)
        except ValueError:
            flash("Level must be a number.", "error")
            return render_template("add.html")

        if level not in (100, 200, 300, 400, 500):
            flash("Choose a valid level.", "error")
            return render_template("add.html")

        try:
            with db.begin() as connection:
                connection.execute(
                    text("""
                        INSERT INTO students
                            (first_name, middle_name, surname,
                             matric_number, department, level)
                        VALUES
                            (:first_name, :middle_name, :surname,
                             :matric, :department, :level)
                    """),
                    {
                        "first_name": first_name,
                        "middle_name": middle_name or None,
                        "surname": surname,
                        "matric": matric,
                        "department": department,
                        "level": level
                    }
                )
        except IntegrityError as e:
            error_message = str(e.orig).lower()

            if (
                "students_matric_number_key" in error_message
                or "unique constraint" in error_message
                or "duplicate key" in error_message
            ):
                flash(
                    "That matric number already exists. "
                    "Search for the student and update their record instead.",
                    "error"
                )
            else:
                app.logger.exception(
                    "Database integrity error while adding student."
                )
                flash(
                    "The student could not be added because of a database "
                    "constraint. Check the Flask terminal for details.",
                    "error"
                )

            return render_template("add.html")

        flash("Student added successfully.", "success")
        return redirect(url_for("staff_dashboard"))

    return render_template("add.html")


@app.route("/search", methods=["GET", "POST"])
@login_required("staff")
def search():
    student = None

    if request.method == "POST":
        matric = (
            request.form.get("matric_number") or ""
        ).strip().lower()

        with db.connect() as connection:
            student = connection.execute(
                text("""
                    SELECT id, first_name, middle_name, surname,
                           matric_number, department, level
                    FROM students
                    WHERE LOWER(TRIM(matric_number)) = :matric
                """),
                {"matric": matric}
            ).mappings().first()

        if not student:
            flash("No student found with that matric number.", "error")

    return render_template("search.html", student=student)


@app.route("/update/<int:id>", methods=["GET", "POST"])
@login_required("staff")
def update(id):
    with db.connect() as connection:
        student = connection.execute(
            text("""
                SELECT id, first_name, middle_name, surname,
                       matric_number, department, level
                FROM students
                WHERE id = :id
            """),
            {"id": id}
        ).mappings().first()

    if not student:
        abort(404)

    if request.method == "POST":
        first_name = (request.form.get("first_name") or "").strip()
        middle_name = (request.form.get("middle_name") or "").strip()
        surname = (request.form.get("surname") or "").strip()
        department = (request.form.get("department") or "").strip()
        level_text = (request.form.get("level") or "").strip()

        if not all([first_name, surname, department, level_text]):
            flash("Complete all required fields.", "error")
            return render_template("update.html", student=student)

        try:
            level = int(level_text)
        except ValueError:
            flash("Level must be a number.", "error")
            return render_template("update.html", student=student)

        if level not in (100, 200, 300, 400, 500):
            flash("Choose a valid level.", "error")
            return render_template("update.html", student=student)

        with db.begin() as connection:
            connection.execute(
                text("""
                    UPDATE students
                    SET first_name = :first_name,
                        middle_name = :middle_name,
                        surname = :surname,
                        department = :department,
                        level = :level
                    WHERE id = :id
                """),
                {
                    "first_name": first_name,
                    "middle_name": middle_name or None,
                    "surname": surname,
                    "department": department,
                    "level": level,
                    "id": id
                }
            )

        flash("Student updated successfully.", "success")
        return redirect(url_for("staff_dashboard"))

    return render_template("update.html", student=student)


@app.route("/delete/<int:id>", methods=["POST"])
@login_required("staff")
def delete(id):
    with db.begin() as connection:
        result = connection.execute(
            text("DELETE FROM students WHERE id = :id"),
            {"id": id}
        )

    if result.rowcount == 0:
        abort(404)

    flash("Student deleted successfully.", "success")
    return redirect(url_for("staff_dashboard"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have logged out.", "success")
    return redirect(url_for("landing"))


@app.errorhandler(403)
def forbidden(error):
    return render_template(
        "error.html",
        code=403,
        message="You are not allowed to access this page."
    ), 403


@app.errorhandler(404)
def not_found(error):
    return render_template(
        "error.html",
        code=404,
        message="The page or student record was not found."
    ), 404
