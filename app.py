import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
## from cs50 import SQL
from flask import Flask, render_template, request, redirect

app = Flask(__name__)



## Connect to SQLite database
## db = SQL("sqlite:///students.db")




# Connect to Neon PostgreSQL using Vercel's environment variable.
database_url = os.environ.get("STUDENTDB_URL")

if not database_url:
    raise RuntimeError("STUDENTDB_URL environment variable is not configured.")

# Support Neon connection strings that start with postgresql://
if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://", "postgresql://", 1
    )

db = create_engine(database_url, pool_pre_ping=True)



@app.route("/")
def index():
    ## students = db.execute("SELECT * FROM students ORDER BY name")
    with db.connect() as conn:
        students = conn.execute(text("SELECT * FROM students ORDER BY name")).mappings().all()

    return render_template("index.html", students=students)


@app.route("/add", methods=["GET", "POST"])
def add():

    if request.method == "POST":
    
        name = request.form.get("name").strip()
        matric_number = request.form.get("matric_number").strip().lower()
        department = request.form.get("department").strip()
        level = request.form.get("level")


        if not all([name, matric_number, department, level]):
            return render_template( "add.html", error="Please complete all fields.")

        
        # Check if matric number already exists
        # existing = db.execute( "SELECT * FROM students WHERE matric_number = ?", matric_number)

        with db.connect() as connection:
            existing = connection.execute(text("""SELECT id FROM students    WHERE matric_number = :matric_number"""),{"matric_number": matric_number}).first()

        if existing:
            return render_template("add.html", error="This matric number already exists. Update student instead.")

        try:   
        # db.execute(""" INSERT INTO students (name, matric_number, department, level) VALUES (?, ?, ?, ?)  RETURNING id""", name, matric_number,department,level)
            with db.begin() as connection:
                connection.execute(text(""" INSERT INTO students (name, matric_number, department, level) VALUES (:name, :matric_number, :department, :level)"""), {"name": name, "matric_number": matric_number, "department": department, "level": level})

        except IntegrityError:
            return render_template("add.html", error="This matric number already exists. Update student instead.")
        
        return redirect("/")
    
    return render_template("add.html")


@app.route("/search", methods=["GET", "POST"])
def search():

    student = None

    if request.method == "POST":

        matric_number = request.form.get("matric_number").strip().lower()

        # student = db.execute("SELECT * FROM students WHERE matric_number = ?",matric_number)
        with db.connect() as connection:
            student = connection.execute(text("""SELECT * FROM students WHERE matric_number = :matric_number"""), {"matric_number": matric_number}).mappings().first()

        # if student:
        #     student = student[0]

    return render_template("search.html", student=student)





@app.route("/update/<int:id>", methods=["GET", "POST"])
def update(id):

    # student = db.execute( "SELECT * FROM students WHERE id = ?", id )
    with db.connect() as connection:
        student = connection.execute(text("""SELECT * FROM students WHERE id = :id"""), {"id": id}).mappings().first()

    if not student:
        return "Student not found", 404

    # student = student[0]

    if request.method == "POST":

        name = request.form.get("name").strip()
        department = request.form.get("department").strip()
        level = request.form.get("level")

        # db.execute( """ UPDATE students SET name = ?, department = ?, level = ? WHERE id = ? """, name, department, level, id )
        with db.begin() as connection:
            connection.execute(text(""" UPDATE students SET name = :name, department = :department, level = :level WHERE id = :id """), {"name": name, "department": department, "level": level, "id": id})

        return redirect("/")

    return render_template(
        "update.html",
        student=student
    )


@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):

    # db.execute("DELETE FROM students WHERE id = ? RETURNING id",id)
    with db.begin() as connection:
        connection.execute(text("""DELETE FROM students WHERE id = :id"""), {"id": id})

    return redirect("/")