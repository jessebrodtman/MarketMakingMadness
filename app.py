import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_socketio import SocketIO, emit
import uuid
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

# Configure application
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app)

# Lobby storage
lobbies = []

# Configure cs50 to use SQLite database
db = SQL("sqlite:///gamefiles.db")

@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.route("/")
def index():
    return render_template("homepage.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    #forget user_id
    session.clear()

    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("login.html", error="Must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template("login.html", error="Must provide password")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                  username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["password"], request.form.get("password")):
            return render_template("login.html", error="Invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")
    else:
        return render_template("login.html")
    
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("register.html", error="Must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template("register.html", error="Must provide password")

        # Ensure password was confirmed
        elif not request.form.get("confirmation"):
            return render_template("register.html", error="Must confirm password")

        # Ensure password and confirmation match
        elif request.form.get("password") != request.form.get("confirmation"):
            return render_template("register.html", error="Passwords do not match")

        # Insert new user into database
        result = db.execute("INSERT INTO users (username, password) VALUES(?, ?)", request.form.get("username"), generate_password_hash(request.form.get("password")))

        # Check if username is already taken
        if not result:
            return render_template("register.html", error="Username already taken")

        # Remember which user has logged in
        session["user_id"] = result

        # Redirect user to home page
        return redirect("/")
    else:
        return render_template("register.html")
    
@app.route("/play", methods=["GET", "POST"])
def game():
    return render_template("play.html", lobbies = lobbies)

@app.route("/history", methods=["GET", "POST"])
def history():
    if request.method == "POST":
        return render_template("history.html")
    else:
        return render_template("history.html")

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        return render_template("settings.html")
    else:
        return render_template("settings.html")
    
@app.route("/create_lobby", methods=["GET", "POST"])
def create_lobby():
    lobby_name = request.form['lobby_name']
    max_players = request.form['max_players']
    new_lobby = {
        'id': str(uuid.uuid4()),
        'name': lobby_name,
        'max_players': max_players,
        'current_players': 0,
        'status': 'waiting'
    }
    lobbies.append(new_lobby)
    print(lobbies)
    socketio.emit('lobby_update', new_lobby)
    return redirect(url_for('play'))

@app.route("/join_lobby/<lobby_id>", methods=["GET", "POST"])
def join_lobby(lobby_id):
    for lobby in lobbies:
        if lobby['id'] == lobby_id and lobby['status'] == 'waiting':
            lobby['current_players'] += 1
            if lobby['current_players'] == lobby['max_players']:
                lobby['status'] = 'full'
            socketio.emit('lobby_update', lobby, broadcast=True)
            return redirect(url_for('play'))
    return redirect(url_for('play'))

if __name__ == "__main__":
    app.run(debug=True)
    socketio.run(app)