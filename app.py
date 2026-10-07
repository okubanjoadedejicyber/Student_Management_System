from cs50 import SQL
from flask import Flask, render_template, request, redirect

app = Flask(__name__)

# Connect to SQLite database
db = SQL("sqlite:///students.db")


@app.route("/")
def index():
    students = db.execute("SELECT * FROM students ORDER BY name")

    return render_template("index.html", students=students)


@app.route("/add", methods=["GET", "POST"])
def add():

    if request.method == "POST":
    
        name = request.form.get("name").lower()
        matric_number = request.form.get("matric_number").strip().lower()
        department = request.form.get("department").lower()
        level = request.form.get("level")

        # Check if matric number already exists
        existing = db.execute( "SELECT * FROM students WHERE matric_number = ?", matric_number)

        if existing:
            return render_template("add.html", error="This matric number already exists. Update student instead.")

        db.execute(""" INSERT INTO students (name, matric_number, department, level) VALUES (?, ?, ?, ?) """, name, matric_number,department,level)

        return redirect("/")

    return render_template("add.html")


@app.route("/search", methods=["GET", "POST"])
def search():

    student = None

    if request.method == "POST":

        matric_number = request.form.get("matric_number").strip().lower()

        student = db.execute(
            "SELECT * FROM students WHERE matric_number = ?",
            matric_number
        )

        if student:
            student = student[0]

    return render_template(
        "search.html",
        student=student
    )


@app.route("/update/<int:id>", methods=["GET", "POST"])
def update(id):

    student = db.execute( "SELECT * FROM students WHERE id = ?", id )

    if not student:
        return "Student not found", 404

    student = student[0]

    if request.method == "POST":

        name = request.form.get("name").lower()
        department = request.form.get("department").lower()
        level = request.form.get("level")

        db.execute( """ UPDATE students SET name = ?, department = ?, level = ? WHERE id = ? """, name, department, level, id )

        return redirect("/")

    return render_template(
        "update.html",
        student=student
    )


@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):

    db.execute(
        "DELETE FROM students WHERE id = ?",
        id
    )

    return redirect("/")