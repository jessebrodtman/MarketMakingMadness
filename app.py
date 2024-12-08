import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_socketio import SocketIO, join_room, leave_room
import uuid
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from markets import get_random_market
from bots import BOTS, create_bot, get_bots_in_lobby
import random
from datetime import datetime
import time, threading
from threading import Lock
import logging

# Configure application
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Configure bot lock
bot_lock = Lock()

# Lobby storage
lobbies = []
markets = {}

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

if __name__ == "__main__":
    app.run(debug=True, use_reloader=True)
    socketio.run(app)

# More Bot Helper Functions and Routes that cant be in bots.py 
def get_current_market_state(lobby_id):
    """
    Retrieve the current market state for a specific lobby.
    """
    # Get the best bid and ask
    best_bid = db.execute("""
        SELECT price, user_id, quantity FROM orders
        WHERE game_id = :game_id AND order_type = 'bid'
        ORDER BY price DESC, created_at ASC LIMIT 1
    """, game_id=lobby_id)

    best_ask = db.execute("""
        SELECT price, user_id, quantity FROM orders
        WHERE game_id = :game_id AND order_type = 'ask'
        ORDER BY price ASC, created_at ASC LIMIT 1
    """, game_id=lobby_id)

    # Get the full market depth
    all_bids = db.execute("""
        SELECT price, user_id, quantity FROM orders
        WHERE game_id = :game_id AND order_type = 'bid'
        ORDER BY price DESC, created_at ASC
    """, game_id=lobby_id)

    all_asks = db.execute("""
        SELECT price, user_id, quantity FROM orders
        WHERE game_id = :game_id AND order_type = 'ask'
        ORDER BY price ASC, created_at ASC
    """, game_id=lobby_id)

    # Find recent trades
    recent_trades = db.execute("""
        SELECT buyer_id, seller_id, price, quantity, created_at FROM transactions
        WHERE game_id = :game_id
        ORDER BY created_at DESC LIMIT 10
    """, game_id=lobby_id)

    return {
        "best_bid": best_bid[0] if best_bid else None,
        "best_ask": best_ask[0] if best_ask else None,
        "all_bids": all_bids,
        "all_asks": all_asks,
        "recent_trades": recent_trades,
    }

@app.route("/add_bot_to_lobby/<lobby_id>", methods=["POST"])
@login_required
def add_bot_to_lobby(lobby_id):
    """
    Add a bot to a lobby
    """
    # Get bots name and level
    bot_name = request.form.get("bot_name", "DefaultBot")
    bot_level = request.form.get("bot_level", "medium")
    bot_name = f"{bot_name} ({bot_level})"

    # Find the lobby
    lobby = next((lobby for lobby in lobbies if lobby["id"] == lobby_id), None)
    if not lobby:
        flash("Lobby not found", "danger")
        return redirect(url_for("play"))

    # Check if the lobby is full
    if is_lobby_full(lobby):
        flash("Cannot add bot: Lobby is full", "warning")
        return redirect(url_for("join_lobby", lobby_id=lobby_id))

    # Add bot to the lobby
    bot_id = str(uuid.uuid4())
    bot = create_bot(bot_id, bot_name, get_fair_value(lobby_id), lobby_id, bot_level)
    lobby["players"].append({"name": bot_name, "ready": True, "is_bot": True, "last_active": datetime.now(), "id": bot_id})  # Mark bot as ready
    db.execute("INSERT INTO game_participants (game_id, user_id, username) VALUES (:game_id, :user_id, :username)", game_id=lobby_id, user_id=bot_id, username=bot_name)

    flash(f"Bot '{bot_name}' added to the lobby", "success")

    # Update for other players
    socketio.emit("force_refresh", to=lobby_id)
    return redirect(url_for("join_lobby", lobby_id=lobby_id))

# @app.route("/bot_action/<lobby_id>", methods=["POST"])
def bot_action(lobby_id):
    """
    Perform trading actions for all bots in a lobby
    """

    # Get the bots in this lobby
    bots = get_bots_in_lobby(lobby_id) 
    
    while True:
        with bot_lock:
            print(f"Bot action running for lobby {lobby_id}")
            # Find the lobby to operate in, stop if needed
            lobby = next((lobby for lobby in lobbies if lobby["id"] == lobby_id), None)
            if not lobby or lobby["status"] != "in_progress":
                print(f"Stopping bot action for lobby {lobby_id} (lobby not found or game not in progress)")
                break
            
            # Update market state for each bot
            for bot in bots:
                market_state = get_current_market_state(lobby_id)
                bot.update_market_state(market_state)

                # Decide whether to post new bid/ask prices
                if bot.should_update_quotes():
                    # Get the new bid and ask prices and post orders
                    bid, ask = bot.generate_bid_ask()
                    for price, order_type in [(bid, "bid"), (ask, "ask")]:
                        order_quantity = random.randint(1, 10)
                        print(f"logging bot trade of lobby id: {lobby_id}, bot id: {bot.bot_id}, price: {price}, order_type: {order_type}, quantity: {random.randint(1, 10)}")
                        print(f"{type(lobby_id)}, {type(bot.bot_id)}, {type(price)}, {type(random.randint(1, 10))}, {type(order_type)}")
                        db.execute("""
                            INSERT INTO orders (game_id, user_id, price, quantity, order_type, created_at)
                            VALUES (:game_id, :user_id, :price, :quantity, :order_type, CURRENT_TIMESTAMP)
                        """, game_id=lobby_id, user_id=bot.bot_id, price=price, quantity=order_quantity, order_type=order_type)
                        
                        # Emit real-time market update
                        # Get market data
                        asks = db.execute("""
                            SELECT price, quantity FROM orders
                            WHERE game_id = :game_id AND order_type = 'ask'
                            ORDER BY price ASC, created_at ASC
                        """, game_id=lobby_id)
                        bids = db.execute("""
                            SELECT price, quantity FROM orders
                            WHERE game_id = :game_id AND order_type = 'bid'
                            ORDER BY price DESC, created_at ASC
                        """, game_id=lobby_id)
                        socketio.emit('market_update', {
                            'bids': bids,
                            'asks': asks,
                        }, room=lobby_id)
                        print(f"New order emitted for bot {bot.bot_id} in lobby {lobby_id}")

                # Decide to trade or not
                trade = bot.decide_to_trade()
                if trade:
                    execute_trade(lobby_id, bot.bot_id, trade["type"], trade["price"], random.randint(1, 10))
            
        time.sleep(5) # Sleep for 5 seconds between bot actions

@app.route("/start_bot_trading/<lobby_id>", methods=["POST"])
@login_required
def start_bot_trading(lobby_id):
    """
    Start automatic trading cycles for all bots in the lobby
    """
    # Find the lobby
    print("finding lobby for bots")
    lobby = next((lobby for lobby in lobbies if lobby['id'] == lobby_id), None)
    if not lobby:
        flash("Lobby not found. Cannot start trading.", "danger")
        return redirect(url_for('play'))

    # Retrieve all bots in the lobby
    print("retreiving bots in lobby")
    bots_in_lobby = get_bots_in_lobby(lobby_id)

    if not bots_in_lobby:
        flash("No bots found in the lobby to start trading.", "warning")
        return redirect(url_for('join_lobby', lobby_id=lobby_id))

    print("starting bot trading cycles")
    bot_thread = threading.Thread(target=bot_action, args=(lobby_id,)) # Use a separate thread for bot trading
    bot_thread.daemon = True  # Set as daemon so it stops when the main program stops
    bot_thread.start() # Start the bot trading thread

    flash("Bot trading cycles started.", "success")
    return redirect(url_for('join_lobby', lobby_id=lobby_id))



@app.route("/")
def index():
    if "user_id" not in session:
        flash("You must log in to access the homepage", "warning")
        return redirect("/login")

    try:
        # Get user data if logged in
        user_id = session["user_id"]
        print(f"User ID from session: {user_id}");

        # Get user stats
        stats = db.execute("""
            SELECT 
                IFNULL(SUM(pnl), 0) AS total_pnl,
                IFNULL(COUNT(id), 0) AS games_played
            FROM game_results 
            WHERE user_id = :user_id
        """, user_id=user_id)[0]
        print(f"Stats fetched: {stats}")

        username = db.execute("SELECT username FROM users WHERE id = :user_id", user_id=user_id)[0]["username"]
        print(f"Username fetched: {username}")

        visitors_online = 95774  # Placeholder for visitor count
        return render_template(
            "homepage.html",
            username=username,
            total_pnl=stats["total_pnl"],
            games_played=stats["games_played"],
            visitors_online=visitors_online
        )
    except Exception as e:
        print(f"Error occurred: {e}")
        return render_template("error.html", error_message="An unexpected error occurred"), 500


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Log in the user and redirect to the homepage
    """
    session.clear()

    if request.method == "POST":
        # Get username and password
        username = request.form.get("username")
        password = request.form.get("password")

        # Validate username and password
        if not username or not password:
            flash("Username and password are required", "danger")
            return render_template("login.html")

        # Check if the user exists and the password is correct
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=username)

        if len(rows) != 1 or not check_password_hash(rows[0]["password"], password):
            flash("Invalid username or password", "danger")
            return render_template("login.html")

        # Log user in
        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]
        flash(f"Welcome back, {rows[0]['username']}!", "success")
        return redirect("/")

    return render_template("login.html")

    
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Get username and password
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Validate username and password
        if not username or not password or not confirmation:
            flash("All fields are required", "danger")
            return render_template("register.html")

        if password != confirmation:
            flash("Passwords do not match", "danger")
            return render_template("register.html")

        hashed_password = generate_password_hash(password)

        # Insert the new user into the database if the username is unique
        try:
            result = db.execute(
                "INSERT INTO users (username, password) VALUES (:username, :password)",
                username=username,
                password=hashed_password,
            )
        except:
            flash("Username already exists", "danger")
            return render_template("register.html")

        session["user_id"] = result
        flash("Registration successful! Welcome to MarketMakingMadness!", "success")
        return redirect("/")
    return render_template("register.html")

    
@app.route("/play", methods=["GET", "POST"])
@login_required
def play():
    """
    Display the play page with lobbies and allow users to create or join a lobby
    """
    username = session.get("username")
    user_lobby_id = None

    # Check if the user is already in a lobby
    for lobby in lobbies:
        for player in lobby["players"]:
            if player["name"] == username:
                user_lobby_id = lobby["id"]
                break

    return render_template("play.html", lobbies=lobbies, user_lobby_id=user_lobby_id)


@app.route("/history")
@login_required
def history():
    """
    Display the user's game history and statistics
    """
    user_id = session["user_id"]

    # Find users statistics
    stats = db.execute("""
        SELECT 
            IFNULL(SUM(pnl), 0) AS total_pnl,
            IFNULL(COUNT(id), 0) AS total_games,
            IFNULL(MAX(pnl), 0) AS best_pnl
        FROM game_results 
        WHERE user_id = :user_id
    """, user_id=user_id)[0]

    # Calculate winning percentage
    total_games = stats["total_games"]
    total_wins = db.execute("SELECT COUNT(id) FROM game_results WHERE user_id = :user_id AND pnl > 0", user_id=user_id)[0]["COUNT(id)"]
    winning_percentage = (total_wins / total_games * 100) if total_games > 0 else 0

    # Get detailed game history
    games = db.execute("""
        SELECT scenario, pnl
        FROM game_results
        WHERE user_id = :user_id
        ORDER BY created_at DESC
""", user_id=user_id)

    # Render the history page with all data
    return render_template(
        "history.html",
        total_pnl=round(stats["total_pnl"], 2),
        total_games=total_games,
        best_pnl=stats["best_pnl"],
        winning_percentage=round(winning_percentage, 2),
        games=games
    )

def countdown_timer(lobby_id, redirect_url):
    """
    Handle the countdown timer for the lobby
    """
    while True:
        # Find the lobby
        lobby = next((lobby for lobby in lobbies if lobby["id"] == lobby_id), None)
        if not lobby:
            print("breaking out of timer")
            break

        # Countdown logic
        if lobby["game_length"] > 0:
            time.sleep(1)  # Wait for 1 second
            lobby["game_length"] -= 1
            # Emit timer update to all clients in the lobby
            socketio.emit('timer_update', {'game_length': lobby["game_length"]}, room=lobby_id)
        else:
            # Timer reaches zero
            socketio.emit('timer_ended', {'message': 'Time is up! Game over!', 'redirect_url': redirect_url}, room=lobby_id)

            # End the game
            end_game_helper(lobby_id)
            break

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    """
    Handle account settings
    Allow users to update their username or password
    """
    user_id = session["user_id"]

    if request.method == "POST":
        # Get form data
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
    Log out the current user and redirect to the login page
    """
    session.clear()
    flash("You have been logged out successfully", "info")
    return redirect("/login")

@app.errorhandler(404)
def not_found_error(e):
    """
    Handle 404 Not Found errors
    """
    return render_template("error.html", error_message="The page you are looking for does not exist."), 404

@app.errorhandler(500)
def internal_error(e):
    """
    Handle 500 Internal Server errors
    """
    return render_template("error.html", error_message="An internal server error occurred. Please try again later."), 500

@app.errorhandler(Exception)
def handle_exception(e):
    """
    Handle all other exceptions with a generic error message
    """
    return render_template("error.html", error_message="An unexpected error occurred. Please contact support."), 500

# Helper Functions for Databases and Lobbies
def is_lobby_full(lobby):
    """
    Check if a lobby is full, considering both players and bots
    """
    return len(lobby["players"]) >= int(lobby["max_players"])

def create_game(lobby_id, scenario, lobby_name, game_length):
    """
    Create a new game in the games database
    """
    db.execute("""
        INSERT INTO games (id, scenario, lobby_name, status, game_length)
        VALUES (:id, :scenario, :lobby_name, :status, :game_length)
    """, id=lobby_id, scenario=scenario, lobby_name=lobby_name, status="waiting", game_length=game_length)

def finalize_game_results(game_id, lobby):
    """
    Populate the game_results table with the final results of the game
    """
    # Get the scenario and fair value from the lobby dictionary
    print("retrieve scenario and fair value")
    scenario = lobby.get("market_question")
    lobby_id = lobby.get("id")
    fair_value = get_fair_value(lobby_id)

    # Aggregate performance data for each user based on the fair market value
    print("aggregating performance data")
    db.execute("""
        INSERT INTO game_results (user_id, game_id, scenario, pnl, accuracy, time_taken, created_at, trades_completed)
        SELECT
            user_id,
            :game_id AS game_id,
            :scenario AS scenario,
            SUM(pnl) AS pnl,
            COUNT(*) AS trades_completed,
            ROUND(CASE WHEN COUNT(*) > 0
                THEN SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
                ELSE 0
            END, 2) AS accuracy,
            g.game_length AS time_taken,
            g.created_at AS created_at
        FROM (
            -- Buyer Data
            SELECT
                t.buyer_id AS user_id,
                (:fair_value - t.price) AS pnl
            FROM transactions t
            WHERE t.game_id = :game_id
            UNION ALL
            -- Seller Data
            SELECT
                t.seller_id AS user_id,
                (t.price - :fair_value) AS pnl
            FROM transactions t
            WHERE t.game_id = :game_id
        ) AS combined
        JOIN games g ON g.id = :game_id
        GROUP BY user_id

    """, game_id=game_id, scenario=scenario, fair_value=fair_value)

def mark_game_as_completed(game_id):
    """
    Mark the game as completed
    """
    db.execute("""
        UPDATE games
        SET status = 'completed'
        WHERE id = :game_id
    """, game_id=game_id)

@app.route("/create_lobby", methods=["GET", "POST"])
@login_required
def create_lobby():
    """
    Create a new game lobby, assign a random market, and add it to the list of lobbies
    """
    player_name = session.get("username")

    # Check if the user is already in a lobby
    current_lobby_id = None
    for lobby in lobbies:
        for player in lobby["players"]:
            if player["name"] == player_name:
                current_lobby_id = lobby["id"]
                break

    # Prevent creating a new lobby if the user is already in one
    if current_lobby_id:
        flash("You are already in a lobby. Leave the current lobby to create a new one.", "danger")
        return redirect(url_for("play"))

    if request.method == "POST":
        # Get lobby details from the form
        lobby_name = request.form.get("lobby_name")
        max_players = request.form.get("max_players")
        game_length = int(request.form.get("game_length"))
        
        # Validate max_players input
        if not max_players.isdigit() or int(max_players) <= 0:
            flash("Max players must be a positive number", "danger")
            return redirect(url_for("play"))

        # Generate a unique lobby ID
        lobby_id = str(uuid.uuid4())

        # Assign a random market to the lobby
        market = get_random_market()
        markets[lobby_id] = market  # Store the market in the global markets dictionary

        # Add to games table
        create_game(lobby_id, market["question"], lobby_name, game_length)

        # Create the lobby object
        new_lobby = {
            "id": lobby_id,
            "name": lobby_name,
            "max_players": int(max_players),
            "current_players": 0,
            "status": "waiting",
            "players": [],
            "market_question": market["question"], 
            "game_length": game_length,
        }
        lobbies.append(new_lobby)

        # Notify via SocketIO
        socketio.emit("lobby_update", new_lobby)
        socketio.emit("force_refresh", room="/play")

        # Redirect to the lobby page
        return redirect(url_for("join_lobby", lobby_id=lobby_id))

    # Render the play page if the method is GET
    return render_template("play.html")


@app.route("/join_lobby/<lobby_id>", methods=["GET", "POST"])
@login_required
def join_lobby(lobby_id):
    """
    Let a user join a lobby
    """
    player_name = session.get("username")

    # Check if the user is already in a lobby
    print("checking if in lobby")
    current_lobby_id = None
    for lobby in lobbies:
        for player in lobby["players"]:
            if player["name"] == player_name:
                print("found player in lobby")
                current_lobby_id = lobby["id"]
                break

    # Prevent joining another lobby if already in one
    if current_lobby_id and current_lobby_id != lobby_id:
        flash("You are already in another lobby. Leave that lobby to join a new one.", "danger")
        return redirect(url_for("play"))

    # Find the lobby
    print("finding lobby")
    lobby = next((lobby for lobby in lobbies if lobby["id"] == lobby_id), None)
    if not lobby:
        flash("Lobby not found", "danger")
        return redirect(url_for("play"))

    # Check if the user is already in the lobby
    print("checking if user is in lobby")
    existing_player = next((p for p in lobby["players"] if p["name"] == player_name), None)
    if existing_player:
        print("user is in lobby")
        # Update their last active timestamp
        existing_player["last_active"] = datetime.now()
        flash("Welcome back! You have re-entered the lobby.", "success")

        # Check if game has started
        if lobby["status"] == "in_progress":
            return redirect(url_for("game", lobby_id=lobby_id))
    else:
        print("checking if lobby is full")
        # Prevent joining if the lobby is full
        if len(lobby["players"]) >= int(lobby["max_players"]):
            flash("Lobby is full", "danger")
            return redirect(url_for("play"))
        
        print("checking if game has started")
        # Prevent joining if the game has already started
        if lobby["status"] == "in_progress":
            flash("Game has already started", "danger")
            return redirect(url_for("play"))

        print("adding player to lobby")
        # Add the player to the lobby
        lobby["players"].append({"name": player_name, "ready": False, "is_bot": False, "last_active": datetime.now(), "id": str(session["user_id"])})
        db.execute("INSERT INTO game_participants (game_id, user_id, username) VALUES (:game_id, :user_id, :username)", game_id=lobby_id, user_id=str(session["user_id"]), username=session.get("username"))
        lobby["current_players"] += 1

        print("emitting event")
        # Notify the lobby of the updated players list
        socketio.emit("force_refresh", to=lobby_id)

        #flash("You have joined the lobby", "success")

    print("rendering lobby")
    return render_template("lobby.html", lobby=lobby)

@socketio.on("join_room_event")
def join_room_event(data):
    """
    Handle a user joining a Socket.IO room for real-time updates
    """
    lobby_id = data.get("lobby_id")
    username = session.get("username")

    # Check if the user is logged in and the lobby exists
    if not username or not lobby_id:
        return {"status": "error", "message": "Invalid lobby or user"}, 400

    # Join the Socket.IO room
    join_room(lobby_id)
    print(f"{username} joined room {lobby_id}")

    # Notify others in the room
    socketio.emit("player_joined", {"player": username}, to=lobby_id)

@app.route("/toggle_ready/<lobby_id>", methods=["GET", "POST"])
@login_required
def toggle_ready(lobby_id):
    # Find lobby
    for lobby in lobbies:
        if lobby['id'] == lobby_id:
            # Find user
            player_name = session.get('username')
            player = next((player for player in lobby['players'] if player['name'] == player_name), None)
            if player:
                # Update user's ready status
                player['ready'] = not player['ready']
                socketio.emit('force_refresh', to=lobby_id)
            return redirect(url_for('join_lobby', lobby_id=lobby_id))

# Lobby and Game Logic Helper Functions
def get_fair_value(lobby_id):
    """
    Retrieve the fair value of the market for a given lobby
    """
    # Find market and return fair value
    market = markets.get(lobby_id)
    if market:
        return market['fair_value']
    raise ValueError(f"No market found for lobby {lobby_id}")  # Error if lobby has no market

def execute_trade(game_id, user_id, trade_type, trade_price, trade_quantity):
    """
    Execute a trade for a given user and update the market in real-time
    """
    print(f"executing trade for {game_id}, {user_id}, {trade_type}, {trade_price}, {trade_quantity}")
    if trade_type == "buy":
        # Match with the best ask
        best_ask = db.execute("""
            SELECT id, user_id, price, quantity FROM orders
            WHERE game_id = :game_id AND order_type = 'ask' AND price <= :trade_price
            ORDER BY price ASC, created_at ASC LIMIT 1
        """, game_id=game_id, trade_price=trade_price)
        print("best ask: ", best_ask)

        # If a best ask exists
        if best_ask:
            ask = best_ask[0]
            print("ask: ", ask)
            quantity_to_trade = min(ask["quantity"], trade_quantity)

            print("trade is: ", user_id, ask['user_id'], ask["price"], quantity_to_trade)
            # Record the transaction
            db.execute("""
                INSERT INTO transactions (game_id, buyer_id, seller_id, price, quantity, created_at)
                VALUES (:game_id, :buyer_id, :seller_id, :price, :quantity, CURRENT_TIMESTAMP)
            """, game_id=game_id, buyer_id=user_id, seller_id=ask["user_id"], price=ask["price"], quantity=quantity_to_trade)

            # Update the remaining quantity or delete the order if fulfilled
            if ask["quantity"] > quantity_to_trade:
                db.execute("""
                    UPDATE orders SET quantity = quantity - :quantity WHERE id = :id
                """, quantity=quantity_to_trade, id=ask["id"])
            else:
                db.execute("DELETE FROM orders WHERE id = :id", id=ask["id"])

            # Get the buyer and seller names
            for lobby in lobbies:
                if lobby["id"] == game_id:
                    print("Players: ", lobby["players"])
                    buyer_name = next((player["name"] for player in lobby["players"] if player["id"] == str(user_id)), None)
                    seller_name = next((player["name"] for player in lobby["players"] if player["id"] == ask["user_id"]), None)
                    break
            # Emit real-time trade update
            print("completing trade with price: ", ask['price'], " quantity: ", quantity_to_trade, "buyer: ", buyer_name, str(user_id), " and seller: ", seller_name, ask["user_id"])
            print("types: ",type(seller_name), type(buyer_name))
            socketio.emit("trade_update", 
                {'price': ask['price'], 'quantity': quantity_to_trade, 'buyer_name': buyer_name, 'buyer_id': user_id, 'seller_name': seller_name, 'seller_id': ask["user_id"],'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }, room=game_id)
            # Emit real-time market update
            # Get market data
            asks = db.execute("""
                SELECT price, quantity FROM orders
                WHERE game_id = :game_id AND order_type = 'ask'
                ORDER BY price ASC, created_at ASC
            """, game_id=game_id)
            bids = db.execute("""
                SELECT price, quantity FROM orders
                WHERE game_id = :game_id AND order_type = 'bid'
                ORDER BY price DESC, created_at ASC
            """, game_id=game_id)
            socketio.emit('market_update', {
                'bids': bids,
                'asks': asks,
            }, room=game_id)
        else:
            flash("No matching ask found", "danger")

    elif trade_type == "sell":
        # Match with the best bid
        best_bid = db.execute("""
            SELECT id, user_id, price, quantity FROM orders
            WHERE game_id = :game_id AND order_type = 'bid' AND price >= :trade_price
            ORDER BY price DESC, created_at ASC LIMIT 1
        """, game_id=game_id, trade_price=trade_price)
        print("best bid: ", best_bid)

        # If a best bid exists
        if best_bid:
            bid = best_bid[0]
            quantity_to_trade = min(bid["quantity"], trade_quantity)

            # Record the transaction
            db.execute("""
                INSERT INTO transactions (game_id, buyer_id, seller_id, price, quantity, created_at)
                VALUES (:game_id, :buyer_id, :seller_id, :price, :quantity, CURRENT_TIMESTAMP)
            """, game_id=game_id, buyer_id=bid["user_id"], seller_id=user_id, price=bid["price"], quantity=quantity_to_trade)

            # Update the remaining quantity or delete the order if fulfilled
            if bid["quantity"] > quantity_to_trade:
                db.execute("""
                    UPDATE orders SET quantity = quantity - :quantity WHERE id = :id
                """, quantity=quantity_to_trade, id=bid["id"])
            else:
                db.execute("DELETE FROM orders WHERE id = :id", id=bid["id"])

            # Get the buyer and seller names
            for lobby in lobbies:
                if lobby["id"] == game_id:
                    print("Players: ", lobby["players"])
                    buyer_name = next((player["name"] for player in lobby["players"] if player["id"] == bid["user_id"]), None)
                    seller_name = next((player["name"] for player in lobby["players"] if player["id"] == str(user_id)), None)
                    break
            # Emit real-time trade update
            print("completing trade with price: ", bid['price'], " quantity: ", quantity_to_trade, "buyer: ", buyer_name, bid["user_id"], " and seller: ", seller_name, user_id)
            print("types: ",type(seller_name), type(buyer_name))
            socketio.emit("trade_update", 
                {'price': bid['price'], 'quantity': quantity_to_trade, 'buyer_name': buyer_name, 'buyer_id': bid["user_id"], 'seller_name': seller_name, 'seller_id': user_id, 'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }, room=game_id)
            # Emit real-time market update
            # Get market data
            asks = db.execute("""
                SELECT price, quantity FROM orders
                WHERE game_id = :game_id AND order_type = 'ask'
                ORDER BY price ASC, created_at ASC
            """, game_id=game_id)
            bids = db.execute("""
                SELECT price, quantity FROM orders
                WHERE game_id = :game_id AND order_type = 'bid'
                ORDER BY price DESC, created_at ASC
            """, game_id=game_id)
            socketio.emit('market_update', {
                'bids': bids,
                'asks': asks,
            }, room=game_id)
        else:
            flash("No matching bid found", "danger")

@app.route("/execute_trade/<lobby_id>", methods=["POST"])
@login_required
def player_trade(lobby_id):
    """
    Handle a player's trade in the market
    """
    # Get trade information
    user_id = session["user_id"]
    trade_type = request.form.get("type")  # "buy" or "sell"
    trade_price = float(request.form.get("price"))
    trade_quantity = float(request.form.get("quantity"))

    # Execute the trade using the main trading function
    execute_trade(lobby_id, user_id, trade_type, trade_price, trade_quantity)

    # Emit real-time player action update
    socketio.emit("player_action", {"lobby_id": lobby_id, "user_id": user_id, "action": trade_type, "price": trade_price, "quantity": trade_quantity}, room=lobby_id)
    #return ('', 204)
    return redirect(url_for("game", lobby_id=lobby_id))

@app.route("/set_order/<lobby_id>", methods=["POST"])
@login_required
def set_order(lobby_id):
    """
    Handle a player setting a bid or ask in the market
    """
    # Get order information
    user_id = session["user_id"]
    order_type = request.form.get("type")  # "bid" or "ask"
    order_price = float(request.form.get("price"))
    order_quantity = int(request.form.get("quantity"))

    # Insert the new order into the database
    print(f"inserting player trade of {lobby_id}, {user_id}, {order_type}, {order_price}, {order_quantity}")
    print(f"{type(lobby_id)}, {type(user_id)}, {type(order_type)}, {type(order_price)}, {type(order_quantity)}")
    db.execute("""
        INSERT INTO orders (game_id, user_id, order_type, price, quantity, created_at)
        VALUES (:game_id, :user_id, :type, :price, :quantity, CURRENT_TIMESTAMP)
    """, game_id=lobby_id, user_id=user_id, type=order_type, price=order_price, quantity=order_quantity)

    # Emit real-time market update
    # Get market data
    asks = db.execute("""
        SELECT price, quantity FROM orders
        WHERE game_id = :game_id AND order_type = 'ask'
        ORDER BY price ASC, created_at ASC
    """, game_id=lobby_id)
    bids = db.execute("""
        SELECT price, quantity FROM orders
        WHERE game_id = :game_id AND order_type = 'bid'
        ORDER BY price DESC, created_at ASC
    """, game_id=lobby_id)
    socketio.emit('market_update', {
        'bids': bids,
        'asks': asks,
    }, room=lobby_id)

    flash(f"Your {order_type} order has been placed.", "success")
    return redirect(url_for("game", lobby_id=lobby_id))

@app.route("/game/<lobby_id>", methods=["GET"])
@login_required
def game(lobby_id):
    """
    Render the game page for a specific lobby
    """
    # Find the lobby
    lobby = next((lobby for lobby in lobbies if lobby["id"] == lobby_id), None)
    if not lobby:
        flash("Lobby not found", "danger")
        return redirect(url_for("play"))

    # Get market data
    asks = db.execute("""
        SELECT price, quantity FROM orders
        WHERE game_id = :game_id AND order_type = 'ask'
        ORDER BY price ASC, created_at ASC
    """, game_id=lobby_id)

    bids = db.execute("""
        SELECT price, quantity FROM orders
        WHERE game_id = :game_id AND order_type = 'bid'
        ORDER BY price DESC, created_at ASC
    """, game_id=lobby_id)

    # Get trade history
    transactions = db.execute("""SELECT * FROM transactions t where t.game_id = :game_id""", game_id=lobby_id)
    print("transactions:", transactions)
    game_participants = db.execute("""SELECT * FROM game_participants gp where gp.game_id = :game_id""", game_id=lobby_id)
    print("game participants:", game_participants)

    trade_history = db.execute("""
        SELECT DISTINCT
            t.price, 
            t.quantity, 
            t.created_at,
            buyer.username AS buyer,
            seller.username AS seller
        FROM transactions t
        LEFT JOIN game_participants buyer ON t.buyer_id = buyer.user_id
        LEFT JOIN game_participants seller ON t.seller_id = seller.user_id
        WHERE t.game_id = :game_id
        ORDER BY t.created_at DESC
        LIMIT 10
    """, game_id=lobby_id)
    print("trade history:", trade_history)

    # Make trades into a portfolio
    user_portfolio = {"contracts": 0, "cash": 0}
    for trade in trade_history:
        if trade["buyer"] == session["username"]:
            user_portfolio["contracts"] += trade["quantity"]
            user_portfolio["cash"] -= trade["price"] * trade["quantity"]
        if trade["seller"] == session["username"]:
            user_portfolio["contracts"] -= trade["quantity"]
            user_portfolio["cash"] += trade["price"] * trade["quantity"]
    user_portfolio["cash"] = round(user_portfolio["cash"], 2)

    # Prepare data for rendering
    context = {
        "lobby": lobby,
        "asks": asks,
        "bids": bids,
        "trade_history": trade_history,
        "user_portfolio": user_portfolio,
    }

    return render_template("game.html", **context)


# Lobby / Game Cleanup Functions
def cleanup_lobby(lobby_id):
    """
    Remove the lobby and associated data from memory
    """
    global lobbies, BOTS, markets

    # Remove lobby from lobbies array
    lobbies = [lobby for lobby in lobbies if lobby['id'] != lobby_id]

    # Remove bots associated with the lobby
    BOTS = {bot_id: bot for bot_id, bot in BOTS.items() if bot.lobby_id != lobby_id}

    # Remove market associated with the lobby
    if lobby_id in markets:
        del markets[lobby_id]


def cleanup_game_data(game_id, lobby):
    """
    Perform database cleanup
    """
    # Check the lobby status
    if lobby["status"] == "waiting":
        print(f"Skipping finalizing game results for game ID {game_id}. Game was never started.")
    else:
        # Finalize game results only if the game was started
        print("finalizizing game results")
        finalize_game_results(game_id, lobby)

    # Mark game as completed in the database
    print("marking game as completed")
    mark_game_as_completed(game_id)

    # Delete old orders from the database
    print("deleting old orders")
    db.execute("""
        DELETE FROM orders WHERE game_id = :game_id
    """, game_id=game_id)

    # Delete old transactions from the database
    print("deleting old transactions")
    db.execute("""
        DELETE FROM transactions WHERE game_id = :game_id
    """, game_id=game_id)

    # Delete game participants from the database
    print("deleting game participants")
    db.execute("""
        DELETE FROM game_participants WHERE game_id = :game_id
    """, game_id=game_id)

def cleanup_all(lobby_id):
    """
    Perform a full cleanup for a given lobby
    """
    try:
        # Find the lobby in the global `lobbies` list
        lobby = next((lobby for lobby in lobbies if lobby["id"] == lobby_id), None)
        if not lobby:
            print(f"No lobby found with ID {lobby_id}. Skipping cleanup.")
            return

        print(f"Starting full cleanup for lobby ID: {lobby_id}")

        # Perform database cleanup
        print("cleaning database")
        cleanup_game_data(lobby_id, lobby)
        print("cleaned database successfully")

        # Perform memory cleanup
        print("cleaning memory")
        cleanup_lobby(lobby_id)
        print("cleaned memory successfully")

        print(f"Full cleanup for lobby ID {lobby_id} completed successfully.")

    except Exception as e:
        print(f"Error during full cleanup for lobby ID {lobby_id}: {e}")
        raise


@app.route("/leave_lobby/<lobby_id>", methods=["POST"])
@login_required
def leave_lobby(lobby_id):
    """
    Handle a user leaving a lobby
    """
    player_name = session.get("username")

    print("finding lobby")
    # Find the lobby
    lobby = next((lobby for lobby in lobbies if lobby["id"] == lobby_id), None)
    if not lobby:
        flash("Lobby not found", "danger")
        return redirect(url_for("play"))

    print("removing player from lobby")
    # Remove the player from the lobby
    lobby["players"] = [player for player in lobby["players"] if player["name"] != player_name]
    lobby["current_players"] = len(lobby["players"])

    # Notify the lobby of the updated players list
    #socketio.emit("lobby_update", {"lobby_id": lobby_id, "players": lobby["players"]}, to=lobby_id)

    print("checking if lobby is empty")
    # Check if the lobby is now empty
    if lobby["current_players"] == 0:
        # Automatically clean up the lobby
        end_game(lobby_id)  # Call the end_game function directly
        socketio.emit("force_refresh", to="/play")
    # Check if the lobby now only contains bots
    elif all(player.get("is_bot", False) for player in lobby["players"]):
        print(f"Lobby {lobby['id']} has only bots. Ending game.")
        cleanup_all(lobby["id"])
        socketio.emit("force_refresh", to="/play")

    #flash("You have left the lobby", "success")
    socketio.emit("force_refresh", to=lobby_id)
    return redirect(url_for("play"))

@socketio.on("leave_room_event")
def leave_room_event(data):
    """
    Handle a user leaving a Socket.IO room for real-time updates
    """
    lobby_id = data.get("lobby_id")
    username = session.get("username")

    # Check if the user is logged in and the lobby exists
    if not username or not lobby_id:
        return {"status": "error", "message": "Invalid lobby or user"}, 400

    # Leave the Socket.IO room
    leave_room(lobby_id)
    print(f"{username} left room {lobby_id}")

    # Notify others in the room
    socketio.emit("player_left", {"player": username}, to=lobby_id)

@app.route("/start_game/<lobby_id>", methods=["POST"])
@login_required
def start_game(lobby_id):
    """
    Start the game for a given lobby
    """
    print(f"starting game for lobby {lobby_id}")

    # Find the lobby
    lobby = next((lobby for lobby in lobbies if lobby["id"] == lobby_id), None)
    if not lobby:
        flash("Lobby not found", "danger")
        return redirect(url_for("play"))

    # Check if the lobby has enough players to start
    if len(lobby["players"]) < 2:
        flash("Lobby must have at least 2 players to start", "danger")
        return redirect(url_for("join_lobby", lobby_id=lobby_id))
    
    #make sure all players are ready
    for player in lobby["players"]:
        if not player["ready"]:
            flash("All players must be ready to start the game", "danger")
            return redirect(url_for("join_lobby", lobby_id=lobby_id))

    # Update the lobby status to "in_progress"
    lobby["status"] = "in_progress"

    # Start the timer in a new thread
    print(f"Starting timer for lobby {lobby_id}")
    redirect_url = url_for("play")
    timer_thread = threading.Thread(target=countdown_timer, args=(lobby_id, redirect_url))
    timer_thread.start()
    logging.debug(f"timer started for lobby {lobby_id}")

    # Start the bots
    print(f"starting bots in lobby {lobby_id}")
    start_bot_trading(lobby_id)

    flash("Game has started", "success")
    try:
        # Notify players via SocketIO
        game_url = url_for("game", lobby_id=lobby_id)
        socketio.emit("game_start", {"redirect_url": game_url}, to = lobby_id)
        socketio.emit("force_refresh", to=lobby_id)
        print("game start emitted")
        return redirect(url_for("game", lobby_id=lobby_id))
    except Exception as e:
        print(f"Error in start_game: {e}")
        return redirect(url_for("play"))

def end_game_helper(lobby_id):
    """
    Handle game and lobby cleanup when a game ends
    """
    try:
        # Find the lobby
        print("finding lobby to end")
        lobby = next((lobby for lobby in lobbies if lobby["id"] == lobby_id), None)
        if not lobby:
            print("Lobby not found. Unable to end the game.")
            return

        # If the game is in progress, generate the leaderboard
        if lobby["status"] == "in_progress":
            print("generating leaderboard")
            # Fetch P&L leaderboard from transactions
            leaderboard = db.execute("""
                SELECT
                    user_id,
                    SUM(pnl) AS pnl,
                    COUNT(*) AS trade_count,
                    ROUND(CASE WHEN COUNT(*) > 0
                        THEN SUM(CASE WHEN (pnl > 0) THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
                        ELSE 0
                    END, 2) AS accuracy
                FROM (
                    -- Buyer Data
                    SELECT
                        t.buyer_id AS user_id,
                        (:fair_value - t.price) AS pnl  -- PnL for buyers
                    FROM transactions t
                    WHERE t.game_id = :game_id

                    UNION ALL

                    -- Seller Data
                    SELECT
                        t.seller_id AS user_id,
                        (t.price - :fair_value) AS pnl  -- PnL for sellers
                    FROM transactions t
                    WHERE t.game_id = :game_id
                ) AS combined
                GROUP BY user_id
                ORDER BY pnl DESC
            """, game_id=lobby_id, fair_value=markets[lobby_id]["fair_value"])
            print("leaderboard generated")

            print("converting leaderboard")
            # Convert leaderboard to a list of dictionaries
            leaderboard_data = [
                {
                    "user_id": next((player["name"] for player in lobby["players"] if player["id"] == entry["user_id"]), None),
                    "pnl": round(entry["pnl"], 2),
                    "trade_count": entry["trade_count"],
                    "accuracy": entry["accuracy"],
                }
                for entry in leaderboard
            ]
            print("leaderboard converted")

            # Notify all players in the lobby about the leaderboard
            print("sending out leaderboard")
            socketio.emit("game_end_leaderboard", {"leaderboard": leaderboard_data}, room=lobby_id)

        # Notify all players in the lobby about the game ending
        print("send out game end")
        socketio.emit("lobby_ended", {"lobby_id": lobby_id}, room=lobby_id)

        # Perform memory and database cleanup
        print("Performing memory and database cleanup")
        cleanup_all(lobby_id)

        print("Game has been ended and data cleaned up successfully")

    except Exception as e:
        print(f"Error in end_game_helper: {e}")

@app.route("/end_game/<lobby_id>", methods=["POST"])
@login_required
def end_game(lobby_id):
    """
    Handle game and lobby cleanup when a game ends
    """
    try:
        end_game_helper(lobby_id)
        flash("Game has been ended and data cleaned up", "success")
    except Exception as e:
        flash("An error occurred while ending the game. Please try again.", "danger")
        print(f"Error in end_game: {e}")

    return redirect(url_for("play"))