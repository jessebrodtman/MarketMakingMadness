import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Get stocks the user has a non-0 position in
    positions = db.execute(
        "SELECT symbol, SUM(quantity) AS sum FROM transactions WHERE personId = ? GROUP BY symbol HAVING sum != 0", session["user_id"])

    # Get stock symbols
    symbols = [stock["symbol"] for stock in positions]

    # Make dictionary of quantity of shares of each symbol
    shares = {}
    for stock in positions:
        shares[stock["symbol"]] = stock["sum"]

    # Make dictionary of price of shares of each symbol
    prices = {}
    for symbol in symbols:
        prices[symbol] = lookup(symbol)["price"]

    # Store cash and total value
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
    value = sum(shares[symbol]*prices[symbol] for symbol in symbols) + cash

    # Display table with the data
    return render_template("index.html", symbols=symbols, shares=shares, prices=prices, cash=cash, value=value)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        # Get the symbol
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Please enter a symbol")

        # Make sure its a valid symbol and get the stock info
        stockInfo = lookup(symbol)
        if not stockInfo:
            return apology("Invalid symbol")

        # Validate number of shares
        quantity = request.form.get("shares")
        if not quantity:
            return apology("Enter a quantity")
        try:
            quantity = int(quantity)
        except ValueError:
            return apology("Enter a positive integer number of shares")
        if quantity <= 0:
            return apology("Enter a positive integer number of shares")

        # Make sure they have enough money
        transactionCost = stockInfo["price"]*quantity
        currentBalance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        currentBalance = currentBalance[0]["cash"]
        if currentBalance < transactionCost:
            return apology("insufficient funds")

        # Execute the trade if possible
        db.execute("INSERT INTO transactions (symbol, quantity, personId, timeTransacted, price) VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)",
                   symbol.upper(), quantity, session["user_id"], stockInfo["price"])
        # Reduce persons balance
        db.execute("UPDATE users SET cash = cash - ? WHERE id = ?",
                   transactionCost, session["user_id"])

        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # Get all transactions
    transactions = db.execute(
        "SELECT * FROM transactions WHERE personId = ? ORDER BY timeTransacted", session["user_id"])
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        # Get desired symbol
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Please enter a symbol")

        # Make sure its a valid symbol and get the stock info
        stockInfo = lookup(symbol)
        if not stockInfo:
            return apology("Invalid symbol")

        # If valid, send the info to and display the quoted page
        return render_template("quoted.html", companyName=stockInfo["name"], symbol=stockInfo["symbol"], price=stockInfo["price"])
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        """Register user"""
        # get username and password to make sure they exist
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if not username or not password or not confirmation:
            return apology("Fill all fields")

        # make sure passwords match
        if confirmation != password:
            return apology("Passwords do not match")

        # make sure its a new username and add it if so
        try:
            db.execute("INSERT INTO users (username, hash) VALUES (?,?)",
                       username, generate_password_hash(password))
        except ValueError:
            return apology("Username taken")

        # Log user in
        session["user_id"] = db.execute("SELECT * FROM users WHERE username = ?", username)[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # if clicked navbar button, bring up registration form
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        # Get symbol
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Fill out all fields")

        # Get number of those shares owned
        numberOwned = db.execute(
            "SELECT SUM(quantity) AS sum FROM transactions WHERE personId = ? AND symbol = ?", session["user_id"], symbol)[0]["sum"]

        # Validate number of shares
        quantity = request.form.get("shares")
        if not quantity:
            return apology("Enter a quantity")
        try:
            quantity = int(quantity)
        except ValueError:
            return apology("Enter a positive integer number of shares")
        if quantity <= 0:
            return apology("Enter a positive integer number of shares")
        elif quantity > numberOwned:
            return apology("You don't own enough shares")

        # Sell shares
        stockPrice = lookup(symbol)["price"]
        # Execute the trade
        db.execute("INSERT INTO transactions (symbol, quantity, personId, timeTransacted, price) VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)",
                   symbol, 0-quantity, session["user_id"], stockPrice)
        # Increase persons balance
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?",
                   quantity * stockPrice, session["user_id"])

        # Redirect user to home page
        return redirect("/")
    else:
        # Get symbols the user has a non-0 position in
        position = db.execute(
            "SELECT symbol, SUM(quantity) AS sum FROM transactions WHERE personId = ? GROUP BY symbol HAVING sum != 0", session["user_id"])
        symbols = [stock["symbol"] for stock in position]

        return render_template("sell.html", symbols=symbols)


@app.route("/resetPassword", methods=["GET", "POST"])
def resetPassword():
    """Reset Password"""
    if request.method == "POST":
        # get username and password to make sure they exist
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if not username or not password or not confirmation:
            return apology("Fill all fields")

        # make sure passwords match
        if confirmation != password:
            return apology("Passwords do not match")

        # make sure its an existing username
        hashedPassword = generate_password_hash(password)
        user = db.execute("SELECT * FROM users WHERE username = ?", username)
        if not user:
            return apology("username not found")

        # log user in and change the password
        session["user_id"] = db.execute("SELECT * FROM users WHERE username = ?", username)[0]["id"]
        db.execute("UPDATE users SET hash = ? WHERE id = ?",
                   generate_password_hash(password), session["user_id"])

        # Redirect user to home page
        return redirect("/")

    else:
        return render_template("reset.html")


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """Reset Password"""
    if request.method == "POST":
        # Get amount
        amount = request.form.get("amount")

        # Validate amount
        if not amount:
            return apology("Enter amount to deposit")
        try:
            amount = int(amount)
        except ValueError:
            return apology("Enter a positive integer")
        if amount <= 0:
            return apology("Enter a positive integer")

        # Add amount to their cash
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", amount, session["user_id"])

        # Redirect to home page
        return redirect("/")

    else:
        return render_template("deposit.html")
