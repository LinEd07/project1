import os
import requests
from helpers import login_required
from flask import Flask, session, render_template, request, redirect,jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/", methods=["GET", "POST"])
@login_required
def index():

    # Check for method
    if request.method == "POST":

        # Make a db select query with like and %
        query = "%" + request.form.get("query") + "%"
        titles = db.execute("SELECT title, isbn FROM books WHERE isbn LIKE :query OR author LIKE :query OR title LIKE :query",
                           {"query": query}).fetchall()
        # render a template and transmit the titles in a variable
        return render_template("results.html", titles=titles)
    else:
        return render_template("index.html")

@app.route("/books/<string:isbn>", methods=["GET", "POST"])
@login_required
def books(isbn):
    # Check for method
    if request.method == "POST":

        # Insert new review into db
        bookid = db.execute("SELECT id FROM books WHERE isbn=:isbn",
                           {"isbn": isbn}).fetchall()

        db.execute("INSERT INTO reviews (users_id, books_id, review) VALUES (:users_id, :books_id, :review)",
                  {"users_id": session["user_id"], "books_id": bookid[0]["id"], "review": request.form.get("rev")})

        db.commit()

        return redirect("books/"+ isbn )
        # Safe the new review in review db
    else:
        # Get all of the books information
        info = db.execute("SELECT * FROM books WHERE isbn=:isbn",
                         {"isbn":isbn}).fetchall()

        # Ask goodread api for book review
        res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "7amUvEcijRuxfjtX4Y6FTw", "isbns": isbn})
        resjson = res.json()

        # Get the reviews that exist about the book
        reviews=db.execute("SELECT review, username FROM reviews JOIN users ON reviews.users_id=users.id WHERE books_id IN \
                          (SELECT id FROM books WHERE isbn=:isbn)",
                          {"isbn": isbn}).fetchall()

        # Check if current user has already revied the book
        switch = 0
        if db.execute("SELECT review FROM reviews WHERE users_id=:users_id AND books_id IN \
                     (SELECT id FROM books WHERE isbn=:isbn)",
                     {"users_id": session["user_id"], "isbn": isbn}).rowcount != 0:
            switch = 1
        # Render a template with two variables
        return render_template("bookpage.html", info=info[0], resjson=resjson["books"][0], reviews=reviews, switch=switch)
@app.route("/login", methods=["GET", "POST"])
def login():

    # Delete cookies
    session.clear()

    if request.method == "POST":

        # Check if inputs are missing
        code=400
        if request.form.get("username") == "":
            return render_template("error.html", message="No username", code=code), code
        elif request.form.get("password") == "":
            return render_template("error.html", message="No password", code=code), code
        else:

            # Check if username exists and password fits
            user = db.execute("SELECT * from users WHERE username=:username",
                             {"username":request.form.get("username")}).fetchall()

            if len(user) != 1 or user[0]["password"] != request.form.get("password"):
                return render_template("error.html", message="Username and/or password incorrect", code=code), code
            else:
                # Fetch the id and assign as user_id
                session["user_id"] = user[0]["id"]
                print(session["user_id"])
                return redirect("/")

    else:
        return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    # Delete cookies
    session.clear()

    # Check for method
    if request.method== "POST":

        # Check if any of the imputs are missing and if password matches confirmation
        code = 400
        if request.form.get("username") == "":
            return render_template("error.html", message="No username", code=code), code
        elif request.form.get("password") == "":
            return render_template("error.html", message="No password", code=code), code
        elif request.form.get("confirmation") == "":
            return render_template("error.html", message="Enter password again", code=code), code
        elif request.form.get("password") != request.form.get("confirmation"):
            return render_template("error.html", message="Passwords do not match", code=code), code
        else:

            # Check if username is available
            if db.execute("SELECT * FROM users WHERE username=:username",
                         {"username": request.form.get("username")}).rowcount != 0:
                return render_template("error.html", message="Username is not available", code=code), code
            else:

                # Insert new user into db
                db.execute("INSERT INTO users (username, password) VALUES (:username, :password)",
                          {"username":request.form.get("username"), "password":request.form.get("password")})
                db.commit()

                # Fetch the id and assign as user_id
                row = db.execute("SELECT id FROM users WHERE username=:username",
                                {"username": request.form.get("username")}).fetchall()
                session["user_id"] = row[0]["id"]
                print(session["user_id"])
                return redirect("/")
    else:
        return render_template("register.html")


@app.route("/api/<string:isbn>")
def api(isbn):

    info = db.execute("SELECT * FROM books WHERE isbn=:isbn", {"isbn":isbn}).fetchall()

    if len(info) == 0:
        return jsonify({"error":"No book found with that isbn"}), 404
    else:

        res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "7amUvEcijRuxfjtX4Y6FTw", "isbns": isbn})
        resjson = res.json()

        print(resjson)
        return jsonify({"title": info[0]["title"],
                        "author": info[0]["author"],
                        "year": info[0]["year"],
                        "isbn": info[0]["isbn"],
                        "review_count": resjson["books"][0]["work_ratings_count"],
                        "average_score": resjson["books"][0]["average_rating"]})
