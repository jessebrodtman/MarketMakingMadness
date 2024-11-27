import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_socketio import SocketIO, emit
import uuid
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps

# Configure application
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app)

# Lobby storage
lobbies = []

# Configure cs50 to use SQLite database
db = SQL("sqlite:///gamefiles.db")

# Require login -- taken from Finance pset
def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function

@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.route("/")
def index():
    """
    Render the homepage. Redirect unauthenticated users to the login page.
    """
    if "user_id" not in session:
        # Redirect unauthenticated users to the login page
        flash("You must log in to access the homepage", "warning")
        return redirect("/login")

    # Fetch user data if logged in
    user_id = session["user_id"]
    stats = db.execute("""
        SELECT 
            IFNULL(SUM(pnl), 0) AS total_pnl,
            IFNULL(COUNT(id), 0) AS games_played
        FROM games 
        WHERE user_id = :user_id
    """, user_id=user_id)[0]

    visitors_online = 95774  # Placeholder for visitor count

    return render_template(
        "homepage.html",
        username=db.execute("SELECT username FROM users WHERE id = :user_id", user_id=user_id)[0]["username"],
        total_pnl=stats["total_pnl"],
        games_played=stats["games_played"],
        visitors_online=visitors_online
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Handle user login. Authenticate the email and password entered in the login form.
    """
    # Clear any existing session
    session.clear()

    if request.method == "POST":
        # Get form data
        email = request.form.get("email")
        password = request.form.get("password")

        # Ensure email and password were submitted
        if not email or not password:
            flash("Email and password are required", "danger")
            return render_template("login.html")

        # Query database for email
        rows = db.execute("SELECT * FROM users WHERE email = :email", email=email)

        # Check if email exists and password matches
        if len(rows) != 1 or not check_password_hash(rows[0]["password"], password):
            flash("Invalid email or password", "danger")
            return render_template("login.html")

        # Log in the user
        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]

        flash(f"Welcome back, {rows[0]['username']}!", "success")
        return redirect("/")

    # Render the login page for GET requests
    return render_template("login.html")

    
@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Handle user registration. Validate form inputs, check for unique usernames, and add the user to the database.
    """
    if request.method == "POST":
        # Get form data
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Ensure all fields are provided
        if not username or not password or not confirmation:
            flash("All fields are required", "danger")
            return render_template("register.html")

        # Ensure passwords match
        if password != confirmation:
            flash("Passwords do not match", "danger")
            return render_template("register.html")

        # Hash the password
        hashed_password = generate_password_hash(password)

        # Insert the user into the database
        try:
            result = db.execute(
                "INSERT INTO users (username, password) VALUES (:username, :password)",
                username=username,
                password=hashed_password,
            )
        except:
            flash("Username already exists", "danger")
            return render_template("register.html")

        # Log the user in (store user ID in session)
        session["user_id"] = result

        flash("Registration successful! Welcome to MarketMakingMadness!", "success")
        return redirect("/")
    else:
        # Render the registration page for GET requests
        return render_template("register.html")
@app.route("/settings", methods=["GET", "POST"])
def settings():
    """
    Handle account settings. Allow users to update their username or password.
    Redirect unauthenticated users to the login page.
    """
    # Ensure user is logged in
    if "user_id" not in session:
        flash("Please log in to access account settings", "warning")
        return redirect("/login")

    user_id = session["user_id"]

    if request.method == "POST":
        # Fetch form data
        new_username = request.form.get("username")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        # Validate username change
        if new_username:
            if db.execute("SELECT * FROM users WHERE username = :username", username=new_username):
                flash("Username already exists", "danger")
            else:
                db.execute(
                    "UPDATE users SET username = :username WHERE id = :user_id",
                    username=new_username,
                    user_id=user_id
                )
                flash("Username updated successfully", "success")

        # Validate password change
        if new_password or confirm_password:
            if new_password != confirm_password:
                flash("Passwords do not match", "danger")
            else:
                hashed_password = generate_password_hash(new_password)
                db.execute(
                    "UPDATE users SET password = :password WHERE id = :user_id",
                    password=hashed_password,
                    user_id=user_id
                )
                flash("Password updated successfully", "success")

        # Redirect back to the settings page after updates
        return redirect("/settings")

    # Fetch the current username for display
    user = db.execute("SELECT username FROM users WHERE id = :user_id", user_id=user_id)[0]

    # Render the settings page
    return render_template("settings.html", user=user)
    
@app.route("/play", methods=["GET", "POST"])
@login_required
def game():
    return render_template("play.html", lobbies = lobbies)

@app.route("/history")
def history():
    """
    Display the user's game history and statistics.
    Redirect unauthenticated users to the login page.
    """
    # Ensure user is logged in
    if "user_id" not in session:
        flash("Please log in to view your game history", "warning")
        return redirect("/login")

    user_id = session["user_id"]

    # Query total statistics
    stats = db.execute("""
        SELECT 
            IFNULL(SUM(pnl), 0) AS total_pnl,
            IFNULL(COUNT(id), 0) AS total_games,
            IFNULL(MAX(pnl), 0) AS best_pnl
        FROM games 
        WHERE user_id = :user_id
    """, user_id=user_id)[0]

    # Calculate winning percentage
    total_games = stats["total_games"]
    total_wins = db.execute("SELECT COUNT(id) FROM games WHERE user_id = :user_id AND pnl > 0", user_id=user_id)[0]["COUNT(id)"]
    winning_percentage = (total_wins / total_games * 100) if total_games > 0 else 0

    # Fetch detailed game history
    games = db.execute("""
        SELECT 
            date, scenario, pnl, accuracy, time_taken
        FROM games 
        WHERE user_id = :user_id
        ORDER BY date DESC
    """, user_id=user_id)

    # Render the history page with all data
    return render_template(
        "history.html",
        total_pnl=stats["total_pnl"],
        total_games=total_games,
        best_pnl=stats["best_pnl"],
        winning_percentage=round(winning_percentage, 2),
        games=games
    )


@app.route("/settings", methods=["GET", "POST"])
def settings():
    """
    Handle account settings. Allow users to update their username or password.
    Redirect unauthenticated users to the login page.
    """
    # Ensure user is logged in
    if "user_id" not in session:
        flash("Please log in to access account settings", "warning")
        return redirect("/login")

    user_id = session["user_id"]

    if request.method == "POST":
        # Fetch form data
        new_username = request.form.get("username")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        # Validate username change
        if new_username:
            if db.execute("SELECT * FROM users WHERE username = :username", username=new_username):
                flash("Username already exists", "danger")
            else:
                db.execute(
                    "UPDATE users SET username = :username WHERE id = :user_id",
                    username=new_username,
                    user_id=user_id
                )
                flash("Username updated successfully", "success")

        # Validate password change
        if new_password or confirm_password:
            if new_password != confirm_password:
                flash("Passwords do not match", "danger")
            else:
                hashed_password = generate_password_hash(new_password)
                db.execute(
                    "UPDATE users SET password = :password WHERE id = :user_id",
                    password=hashed_password,
                    user_id=user_id
                )
                flash("Password updated successfully", "success")

        # Redirect back to the settings page after updates
        return redirect("/settings")

    # Fetch the current username for display
    user = db.execute("SELECT username FROM users WHERE id = :user_id", user_id=user_id)[0]

    # Render the settings page
    return render_template("settings.html", user=user)

    
@app.route("/logout")
def logout():
    """
    Log out the current user and redirect to the login page.
    """
    session.clear()
    flash("You have been logged out successfully", "info")
    return redirect("/login")


@app.errorhandler(404)
def not_found_error(e):
    """
    Handle 404 Not Found errors.
    """
    return render_template("error.html", error_message="The page you are looking for does not exist."), 404

@app.errorhandler(500)
def internal_error(e):
    """
    Handle 500 Internal Server errors.
    """
    return render_template("error.html", error_message="An internal server error occurred. Please try again later."), 500

@app.errorhandler(Exception)
def handle_exception(e):
    """
    Handle all other exceptions with a generic error message.
    """
    return render_template("error.html", error_message="An unexpected error occurred. Please contact support."), 500

@app.route("/create_lobby", methods=["GET", "POST"])
@login_required
def create_lobby():
    if request.method == "POST":
        lobby_name = request.form['lobby_name']
        max_players = request.form['max_players']
        new_lobby = {
            'id': str(uuid.uuid4()),
            'name': lobby_name,
            'max_players': max_players,
            'current_players': 0,
            'status': 'waiting',
            'players': []
        }
        lobbies.append(new_lobby)
        socketio.emit('lobby_update', new_lobby)
        return redirect(url_for('join_lobby', lobby_id=new_lobby['id']))
    return render_template


@app.route("/join_lobby/<lobby_id>", methods=["GET", "POST"])
@login_required
def join_lobby(lobby_id):
    for lobby in lobbies:
        if lobby['id'] == lobby_id:
            # Check if the player is already in the lobby
            player_name = session.get('username')
            if not player_name:
                return redirect(url_for('login'))  # Redirect to login if no username is in session

            if not any(player['name'] == player_name for player in lobby['players']):
                # Add player to the lobby
                lobby['players'].append({'name': player_name, 'ready': False})
                lobby['current_players'] += 1
            
            # Update lobby status if it reaches max players
            if lobby['current_players'] == int(lobby['max_players']):
                lobby['status'] = 'full'
            
            # Emit an update about the lobby state
            socketio.emit('lobby_update', lobby, to='/', namespace='/')

            # Render the lobby waiting room page
            return render_template('lobby.html', lobby=lobby)

    # If no matching lobby is found, redirect back to lobby selection
    return redirect(url_for('play'))

@app.route("/mark_ready/<lobby_id>", methods=["GET", "POST"])
@login_required
def mark_ready(lobby_id):
    for lobby in lobbies:
        if lobby['id'] == lobby_id:
            player_name = session.get('username')
            player = next((player for player in lobby['players'] if player['name'] == player_name), None)
            if player:
                player['ready'] = True
                socketio.emit('player_ready', {'player_name': player_name, 'lobby_id': lobby_id})
            return redirect(url_for('join_lobby', lobby_id=lobby_id))

if __name__ == "__main__":
    app.run(debug=True)
    socketio.run(app)