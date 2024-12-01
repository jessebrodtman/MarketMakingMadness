import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_socketio import SocketIO, emit
import uuid
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from markets import get_random_market, get_market_answer, get_all_markets, add_market
from bots import Bot, BOTS, create_bot, remove_bot, get_bots_in_lobby
import random
from datetime import datetime, timedelta

# Configure application
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app)

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

@app.route("/")
def index():
    if "user_id" not in session:
        flash("You must log in to access the homepage", "warning")
        return redirect("/login")

    try:
        # Fetch user data if logged in
        user_id = session["user_id"]
        print(f"User ID from session: {user_id}")

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
    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash("Username and password are required", "danger")
            return render_template("login.html")

        rows = db.execute("SELECT * FROM users WHERE username = :username", username=username)

        if len(rows) != 1 or not check_password_hash(rows[0]["password"], password):
            flash("Invalid username or password", "danger")
            return render_template("login.html")

        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]
        flash(f"Welcome back, {rows[0]['username']}!", "success")
        return redirect("/")

    return render_template("login.html")

    
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username or not password or not confirmation:
            flash("All fields are required", "danger")
            return render_template("register.html")

        if password != confirmation:
            flash("Passwords do not match", "danger")
            return render_template("register.html")

        hashed_password = generate_password_hash(password)

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
        FROM game_results 
        WHERE user_id = :user_id
    """, user_id=user_id)[0]

    # Calculate winning percentage
    total_games = stats["total_games"]
    total_wins = db.execute("SELECT COUNT(id) FROM game_results WHERE user_id = :user_id AND pnl > 0", user_id=user_id)[0]["COUNT(id)"]
    winning_percentage = (total_wins / total_games * 100) if total_games > 0 else 0

    # Fetch detailed game history
    games = db.execute("""
        SELECT date(created_at) AS date, scenario, pnl, accuracy, time_taken
        FROM game_results
        WHERE user_id = :user_id
        ORDER BY created_at DESC
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

# Helper Functions for Databases and Lobbies
def is_lobby_full(lobby):
    """
    Check if a lobby is full, considering both humans and bots.

    Args:
        lobby (dict): The lobby object.

    Returns:
        bool: True if the lobby is full, False otherwise.
    """
    return len(lobby["players"]) >= int(lobby["max_players"])

def create_game(lobby_id, scenario, lobby_name):
    """
    Create a new game in the `games` table.
    """
    db.execute("""
        INSERT INTO games (id, scenario, lobby_name, status)
        VALUES (:id, :scenario, :lobby_name, :status)
    """, id=lobby_id, scenario=scenario, lobby_name=lobby_name, status="waiting")


def finalize_game_results(game_id, lobby):
    """
    Populate the `game_results` table by aggregating data from the `transactions` table
    and calculating P&L based on the fair market value.

    Args:
        game_id (str): The ID of the game to finalize results for.
        lobby (dict): The lobby object containing information about the game's state.
    """
    # Retrieve the scenario and fair value from the `lobby` dictionary
    scenario = lobby.get("market_question")
    lobby_id = lobby.get("id")

    fair_value = get_fair_value(lobby_id)

    # Aggregate performance data for each user based on the fair market value
    db.execute("""
        INSERT INTO game_results (user_id, game_id, scenario, pnl, trades_completed)
        SELECT
            t.buyer_id AS user_id,
            t.game_id,
            :scenario AS scenario,
            SUM(
                CASE
                    WHEN t.buyer_id IS NOT NULL THEN :fair_value - t.price  -- Profit for buyers
                    WHEN t.seller_id IS NOT NULL THEN t.price - :fair_value -- Profit for sellers
                END
            ) AS pnl,
            COUNT(t.id) AS trades_completed
        FROM transactions t
        WHERE t.game_id = :game_id
        GROUP BY t.buyer_id
    """, game_id=game_id, scenario=scenario, fair_value=fair_value)



def mark_game_as_completed(game_id):
    """
    Mark the game as completed.
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
    Create a new game lobby, assign a random market, and add it to the list of lobbies.
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
        
        # Validate max_players input
        if not max_players.isdigit() or int(max_players) <= 0:
            flash("Max players must be a positive number", "danger")
            return redirect(url_for("play"))

        # Generate a unique lobby ID
        lobby_id = str(uuid.uuid4())

        # Assign a random market to the lobby
        market = get_random_market()
        markets[lobby_id] = market  # Store the market in the global markets dictionary

        # Add to `games` table
        create_game(lobby_id, market["question"], lobby_name)

        # Create the lobby object
        new_lobby = {
            "id": lobby_id,
            "name": lobby_name,
            "max_players": int(max_players),
            "current_players": 0,
            "status": "waiting",
            "players": [],
            "market_question": market["question"],  # Add the market question to the lobby object
        }
        lobbies.append(new_lobby)

        # Notify via SocketIO (if needed)
        socketio.emit("lobby_update", new_lobby)

        # Redirect to the lobby page
        return redirect(url_for("join_lobby", lobby_id=lobby_id))

    # Render the play page if the method is GET
    return render_template("play.html")




@app.route("/join_lobby/<lobby_id>", methods=["GET", "POST"])
@login_required
def join_lobby(lobby_id):
    """
    Handle a user joining a lobby.
    """
    player_name = session.get("username")

    # Check if the user is already in a lobby
    current_lobby_id = None
    for lobby in lobbies:
        for player in lobby["players"]:
            if player["name"] == player_name:
                current_lobby_id = lobby["id"]
                break

    # Prevent joining another lobby if already in one
    if current_lobby_id and current_lobby_id != lobby_id:
        flash("You are already in another lobby. Leave that lobby to join a new one.", "danger")
        return redirect(url_for("play"))

    # Find the lobby
    lobby = next((lobby for lobby in lobbies if lobby["id"] == lobby_id), None)
    if not lobby:
        flash("Lobby not found", "danger")
        return redirect(url_for("play"))

    # Prevent joining if the game has already started
    if lobby["status"] == "in_progress":
        flash("Game has already started", "danger")
        return redirect(url_for("play"))

    # Check if the user is already in the lobby
    existing_player = next((p for p in lobby["players"] if p["name"] == player_name), None)
    if existing_player:
        # Update their last active timestamp
        existing_player["last_active"] = datetime.now()
        flash("Welcome back! You have re-entered the lobby.", "success")
    else:
        # Prevent joining if the lobby is full
        if len(lobby["players"]) >= int(lobby["max_players"]):
            flash("Lobby is full", "danger")
            return redirect(url_for("play"))

        # Add the player to the lobby
        lobby["players"].append({"name": player_name, "ready": False, "is_bot": False, "last_active": datetime.now()})
        lobby["current_players"] += 1
        flash("You have joined the lobby", "success")

    return render_template("lobby.html", lobby=lobby)





@app.route("/toggle_ready/<lobby_id>", methods=["GET", "POST"])
@login_required
def toggle_ready(lobby_id):
    for lobby in lobbies:
        if lobby['id'] == lobby_id:
            player_name = session.get('username')
            player = next((player for player in lobby['players'] if player['name'] == player_name), None)
            if player:
                player['ready'] = not player['ready']
                socketio.emit('player_ready', {'player_name': player_name, 'lobby_id': lobby_id})
            return redirect(url_for('join_lobby', lobby_id=lobby_id))

if __name__ == "__main__":
    app.run(debug=True)
    socketio.run(app)



# Lobby and Game Logic Helper Funciton
def get_fair_value(lobby_id):
    """
    Retrieve the fair value of the market for a given lobby.

    Args:
        lobby_id (str): The ID of the lobby.

    Returns:
        float: The fair value of the market.
    """
    market = markets.get(lobby_id)
    if market:
        return market['fair_value']
    raise ValueError(f"No market found for lobby {lobby_id}")  # Error if lobby has no market

def execute_trade(game_id, user_id, trade_type, trade_price):
    """
    Execute a trade for a given user (bot or human).

    Args:
        game_id (int): The ID of the game/lobby.
        user_id (str): The unique ID of the user (bot or human).
        trade_type (str): "buy" or "sell".
        trade_price (float): The price at which the trade is executed.
    """
    if trade_type == "buy":
        # Match with the best ask
        best_ask = db.execute("""
            SELECT id, user_id, price, quantity FROM orders
            WHERE game_id = :game_id AND type = 'ask' AND price = :trade_price
            ORDER BY created_at ASC LIMIT 1
        """, game_id=game_id, trade_price=trade_price)

        if best_ask:
            ask = best_ask[0]
            quantity_to_trade = min(ask["quantity"], random.randint(1, 10))

            # Record the transaction
            db.execute("""
                INSERT INTO transactions (game_id, buyer_id, seller_id, price, quantity, created_at)
                VALUES (:game_id, :buyer_id, :seller_id, :price, :quantity, CURRENT_TIMESTAMP)
            """, game_id=game_id, buyer_id=user_id, seller_id=ask["user_id"], price=trade_price, quantity=quantity_to_trade)

            # Update the remaining quantity or delete the order if fulfilled
            if ask["quantity"] > quantity_to_trade:
                db.execute("""
                    UPDATE orders SET quantity = quantity - :quantity WHERE id = :id
                """, quantity=quantity_to_trade, id=ask["id"])
            else:
                db.execute("DELETE FROM orders WHERE id = :id", id=ask["id"])

    elif trade_type == "sell":
        # Match with the best bid
        best_bid = db.execute("""
            SELECT id, user_id, price, quantity FROM orders
            WHERE game_id = :game_id AND type = 'bid' AND price = :trade_price
            ORDER BY created_at DESC LIMIT 1
        """, game_id=game_id, trade_price=trade_price)

        if best_bid:
            bid = best_bid[0]
            quantity_to_trade = min(bid["quantity"], random.randint(1, 10))

            # Record the transaction
            db.execute("""
                INSERT INTO transactions (game_id, buyer_id, seller_id, price, quantity, created_at)
                VALUES (:game_id, :buyer_id, :seller_id, :price, :quantity, CURRENT_TIMESTAMP)
            """, game_id=game_id, buyer_id=bid["user_id"], seller_id=user_id, price=trade_price, quantity=quantity_to_trade)

            # Update the remaining quantity or delete the order if fulfilled
            if bid["quantity"] > quantity_to_trade:
                db.execute("""
                    UPDATE orders SET quantity = quantity - :quantity WHERE id = :id
                """, quantity=quantity_to_trade, id=bid["id"])
            else:
                db.execute("DELETE FROM orders WHERE id = :id", id=bid["id"])

@app.route("/execute_trade/<lobby_id>", methods=["POST"])
@login_required
def player_trade(lobby_id):
    """
    Handle a player's trade in the market.
    """
    user_id = session["user_id"]
    trade_type = request.form.get("type")  # "buy" or "sell"
    trade_price = float(request.form.get("price"))

    # Execute the trade using the generalized function
    execute_trade(lobby_id, user_id, trade_type, trade_price)

    return redirect(url_for("play", lobby_id=lobby_id))

# Lobby / Game Cleanup Functions
def cleanup_lobby(lobby_id):
    """
    Remove the lobby and associated data from memory.

    Args:
        lobby_id (str): The ID of the lobby to clean up.
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
    Perform database cleanup after a game ends.

    Args:
        game_id (int): The ID of the game to clean up.
        lobby (dict): The lobby object containing information about the game's state.
    """
    # Check the lobby status
    if lobby["status"] == "waiting":
        print(f"Skipping finalizing game results for game ID {game_id}. Game was never started.")
    else:
        # Finalize game results only if the game was started
        finalize_game_results(game_id, lobby)

    # Mark game as completed in the database
    mark_game_as_completed(game_id)

    # Delete old orders and transactions from the database
    db.execute("""
        DELETE FROM orders WHERE game_id = :game_id
    """, game_id=game_id)

    db.execute("""
        DELETE FROM transactions WHERE game_id = :game_id
    """, game_id=game_id)



def cleanup_all(lobby_id):
    """
    Perform a full cleanup for a given lobby, including both memory and database data.

    Args:
        lobby_id (str): The ID of the lobby to clean up.
    """
    try:
        # Find the lobby in the global `lobbies` list
        lobby = next((lobby for lobby in lobbies if lobby["id"] == lobby_id), None)
        if not lobby:
            print(f"No lobby found with ID {lobby_id}. Skipping cleanup.")
            return

        print(f"Starting full cleanup for lobby ID: {lobby_id}")

        # Perform memory cleanup
        cleanup_lobby(lobby_id)

        # Perform database cleanup
        cleanup_game_data(lobby_id, lobby)

        print(f"Full cleanup for lobby ID {lobby_id} completed successfully.")

    except Exception as e:
        print(f"Error during full cleanup for lobby ID {lobby_id}: {e}")
        raise


    
@app.route("/leave_lobby/<lobby_id>", methods=["POST"])
@login_required
def leave_lobby(lobby_id):
    """
    Handle a user leaving a lobby.

    Args:
        lobby_id (str): The ID of the lobby the user is leaving.
    """
    player_name = session.get("username")

    # Find the lobby
    lobby = next((lobby for lobby in lobbies if lobby["id"] == lobby_id), None)
    if not lobby:
        flash("Lobby not found", "danger")
        return redirect(url_for("play"))

    # Remove the player from the lobby
    lobby["players"] = [player for player in lobby["players"] if player["name"] != player_name]
    lobby["current_players"] = len(lobby["players"])

    # Check if the lobby is now empty
    if lobby["current_players"] == 0:
        # Automatically clean up the lobby
        end_game(lobby_id)  # Call the end_game function directly
    # Check if the lobby now only contains bots
    if all(player.get("is_bot", False) for player in lobby["players"]):
        print(f"Lobby {lobby['id']} has only bots. Ending game.")
        cleanup_all(lobby["id"])

    flash("You have left the lobby", "success")
    return redirect(url_for("play"))

@app.route("/start_game/<lobby_id>", methods=["POST"])
@login_required
def start_game(lobby_id):
    """
    Start the game for a given lobby.

    Args:
        lobby_id (str): The ID of the lobby to start the game for.
    """
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

    # Notify players via SocketIO
    socketio.emit("game_start", lobby_id)

    flash("Game has started", "success")
    return render_template("game.html", lobby=lobby)

@app.route("/end_game/<lobby_id>", methods=["POST"])
@login_required
def end_game(lobby_id):
    """
    Handle game and lobby cleanup when a game ends.

    Args:
        lobby_id (str): The ID of the lobby to clean up.
    """
    try:
        cleanup_all(lobby_id)  # Perform memory and database cleanup
        flash("Game has been ended and data cleaned up", "success")
    except Exception as e:
        flash("An error occurred while ending the game. Please try again.", "danger")
        print(e)
    return redirect(url_for("play"))

# Bot Helper Functions and Routes
def get_current_market_state(lobby_id):
    """
    Retrieve the current market state for a specific lobby.
    """
    # Best bid and ask
    best_bid = db.execute("""
        SELECT price, user_id, quantity FROM orders
        WHERE game_id = :game_id AND type = 'bid'
        ORDER BY price DESC, created_at ASC LIMIT 1
    """, game_id=lobby_id)

    best_ask = db.execute("""
        SELECT price, user_id, quantity FROM orders
        WHERE game_id = :game_id AND type = 'ask'
        ORDER BY price ASC, created_at ASC LIMIT 1
    """, game_id=lobby_id)

    # Full market depth
    all_bids = db.execute("""
        SELECT price, user_id, quantity FROM orders
        WHERE game_id = :game_id AND type = 'bid'
        ORDER BY price DESC, created_at ASC
    """, game_id=lobby_id)

    all_asks = db.execute("""
        SELECT price, user_id, quantity FROM orders
        WHERE game_id = :game_id AND type = 'ask'
        ORDER BY price ASC, created_at ASC
    """, game_id=lobby_id)

    # Recent trades
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
    Add a bot to a lobby, ensuring proper handling of player counts and status.
    """
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
    lobby["players"].append({"name": bot_name, "ready": True, "is_bot": True, "last_active": datetime.now()})  # Mark bot as ready

    flash(f"Bot '{bot_name}' added to the lobby", "success")
    return redirect(url_for("join_lobby", lobby_id=lobby_id))



@app.route("/bot_action/<lobby_id>", methods=["POST"])
def bot_action(lobby_id):
    bots = get_bots_in_lobby(lobby_id)

    for bot in bots:
        market_state = get_current_market_state(lobby_id)
        bot.update_market_state(market_state)

        # Decide whether to post new bid/ask prices
        if bot.should_update_quotes():
            bid, ask = bot.generate_bid_ask()
            for price, order_type in [(bid, "bid"), (ask, "ask")]:
                db.execute("""
                    INSERT INTO orders (game_id, user_id, price, quantity, type, created_at)
                    VALUES (:game_id, :user_id, :price, :quantity, :type, CURRENT_TIMESTAMP)
                """, game_id=lobby_id, user_id=bot.bot_id, price=price, quantity=random.randint(1, 10), type=order_type)

        # Decide to trade
        trade = bot.decide_to_trade()
        if trade:
            execute_trade(bot.bot_id, trade["type"], trade["price"])

@app.route("/start_bot_trading/<lobby_id>", methods=["POST"])
@login_required
def start_bot_trading(lobby_id):
    """
    Start automatic trading cycles for all bots in the lobby.
    """
    # Find the lobby
    lobby = next((lobby for lobby in lobbies if lobby['id'] == lobby_id), None)
    if not lobby:
        flash("Lobby not found. Cannot start trading.", "danger")
        return redirect(url_for('play'))

    # Retrieve all bots in the lobby
    bots_in_lobby = [bot for bot in BOTS if bot.lobby_id == lobby_id]

    if not bots_in_lobby:
        flash("No bots found in the lobby to start trading.", "warning")
        return redirect(url_for('join_lobby', lobby_id=lobby_id))

    
    bot_action(lobby_id)  # Use the existing bot_action function

    flash("Bot trading cycles started.", "success")
    return redirect(url_for('join_lobby', lobby_id=lobby_id))

'''
# Handling Inactive Users in a Lobby (Ones that leave, etc.)
def remove_inactive_users():
    """
    Periodically remove inactive users from all lobbies and clean up empty or bot-only lobbies.
    """
    # Update global lobbies list with active lobbies
    global lobbies
    lobbies = active_lobbies

    now = datetime.now()
    timeout = timedelta(seconds=30)  # Timeout duration for inactivity
    active_lobbies = []

    for lobby in lobbies:
        active_players = []
        for player in lobby["players"]:
            # Check if the player is a human and inactive
            if not player["is_bot"] and "last_active" in player and now - player["last_active"] > timeout:
                print(f"Removing inactive user: {player['name']} from lobby {lobby['id']}")
            else:
                # Keep the player (either active or a bot)
                active_players.append(player)

        # Update the lobby's player list
        lobby["players"] = active_players

        # Check if there are still humans in the lobby
        has_human_players = any(not player["is_bot"] for player in lobby["players"])

        # If the lobby contains only bots, initiate cleanup
        if has_human_players:
            active_lobbies.append(lobby)
        else:
            print(f"Cleaning up lobby with only bots: {lobby['id']}")
            cleanup_all(lobby["id"])

    
@app.route("/heartbeat/<lobby_id>", methods=["POST"])
@login_required
def heartbeat(lobby_id):
    """
    Handle heartbeat requests from the client to confirm their presence in the lobby.
    """
    username = session.get("username")
    if not username:
        return {"status": "error", "message": "User not logged in"}, 401

    # Update user's last active timestamp in the lobby
    lobby = next((lobby for lobby in lobbies if lobby["id"] == lobby_id), None)
    if not lobby:
        return {"status": "error", "message": "Lobby not found"}, 404

    # Find the user in the lobby and update their last active time
    for player in lobby["players"]:
        if player["name"] == username:
            player["last_active"] = datetime.now()

    # Perform cleanup for inactive users
    remove_inactive_users()

    return {"status": "success", "message": "Heartbeat received"}, 200




'''