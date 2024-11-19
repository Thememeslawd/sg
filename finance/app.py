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
app.config['DEBUG'] = True

if __name__ == "__main__":
    app.run(debug=True)


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
    user_id = session["user_id"]

    # Query for the user's stock holdings
    holdings = db.execute(
        "SELECT DISTINCT symbol, SUM(shares) AS total_shares FROM purchases WHERE user_id = ? GROUP BY symbol", user_id)

    total_value = 0
    stocks = []

    # Loop through each holding and retrieve the live price and value
    for holding in holdings:
        symbol = holding["symbol"]
        total_shares = holding["total_shares"]
        stock = lookup(symbol)

        # Initialize live_price and value with defaults to prevent errors
        live_price = 0
        value = 0

        # Calculate live price and value if the stock lookup is successful
        if stock:
            live_price = stock["price"]
            value = total_shares * live_price
            total_value += value

        stocks.append({
            "user_id": user_id,
            "symbol": symbol,
            "total_shares": total_shares,
            "live_price": live_price,
            "value": value,
        })

    # Retrieve the user's current cash balance
    user_balance = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    balance = user_balance[0]["cash"] if user_balance else 0

    # Calculate the grand total (stocks' total value + cash balance)
    grand_total = total_value + balance

    # Render the index.html template with the stocks, balance, and grand total
    return render_template("index.html", stocks=stocks, balance=balance, grand_total=grand_total)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")

        # Validate inputs
        if not symbol:
            return render_template("error.html", message="Please provide a stock symbol.")
        if not shares.isdigit() or int(shares) <= 0:
            return render_template("error.html", message="Please provide a positive number of shares.")

        shares = int(shares)
        stock = lookup(symbol)

        if stock is None:
            return render_template("error.html", message="Invalid stock symbol.")

        cost = round(shares * stock["price"], 2)

        # Fetch user's balance and existing shares
        user_id = session["user_id"]
        user_data = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        if not user_data:
            return render_template("error.html", message="User not found.")

        balance = round(user_data[0]["cash"], 2)
        if cost > balance:
            return render_template("error.html", message="Insufficient funds.")

        # Update database
        db.execute("UPDATE users SET cash = ? WHERE id = ?", balance - cost, user_id)
        db.execute("INSERT INTO purchases (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)",
                   user_id, symbol, shares, stock["price"])
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, transaction_type) VALUES (?, ?, ?, ?, ?)",
                   user_id, symbol, shares, stock["price"], "Buy")

        return render_template("buy_confirmation.html", symbol=symbol, shares=shares, cost=cost)

    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]

    transactions = db.execute(
        "SELECT * FROM transactions WHERE user_id =? ORDER BY timestamp DESC", user_id)
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
        symbol = request.form.get("symbol")

        if not symbol:
            return apology("Please provide stock symbol", 400)
        stock = lookup(symbol)
        print(stock)

        if stock is None:
            return apology("invalid stock symbol", 400)
        return render_template("quoted.html", name=stock["name"], symbol=stock["symbol"], price=stock["price"])
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == ("POST"):
        try:

            # Get the username from form input
            username = request.form.get("username")
            if not username:
                return apology("Must Provide Username", 400)
             # Check if the username already exists
            rows = db.execute("SELECT * FROM users  WHERE username = ?", username)
            if rows:
                return apology("Username Already Exists", 400)

            password = request.form.get("password")
            confirmation = request.form.get("confirmation")
            if (not password or not confirmation):
                return apology("Must Provide Password", 400)

            if password != confirmation:
                return apology("Passwords Do Not Match", 400)

            # Hash the password before storing
            hashed_password = generate_password_hash(password)

            db.execute("INSERT INTO users (username , hash) VALUES(?, ?)",
                       username,  hashed_password)
            return redirect("/")

        except ValueError:
            return apology("Username Already Exists", 400)

    else:
        return render_template("register.html")


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
    user_id = session["user_id"]

    # Query for the user's stock holdings
    holdings = db.execute(
        "SELECT DISTINCT symbol, SUM(shares) AS total_shares FROM purchases WHERE user_id = ? GROUP BY symbol", user_id)

    total_value = 0
    stocks = []

    # Loop through each holding and retrieve the live price and value
    for holding in holdings:
        symbol = holding["symbol"]
        total_shares = holding["total_shares"]
        stock = lookup(symbol)

        # Initialize live_price and value with defaults to prevent errors
        live_price = 0
        value = 0

        # Calculate live price and value if the stock lookup is successful
        if stock:
            live_price = stock["price"]
            value = total_shares * live_price
            total_value += value

        stocks.append({
            "user_id": user_id,
            "symbol": symbol,
            "total_shares": total_shares,
            "live_price": live_price,
            "value": value,
        })

    # Retrieve the user's current cash balance
    user_balance = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    balance = user_balance[0]["cash"] if user_balance else 0

    # Calculate the grand total (stocks' total value + cash balance)
    grand_total = total_value + balance

    # Render the index.html template with the stocks, balance, and grand total
    return render_template("index.html", stocks=stocks, balance=balance, grand_total=grand_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Validate symbol input
        if not symbol:
            return apology("Please provide a stock symbol", 400)

        # Validate shares input and ensure it's a positive integer
        if not shares.isdigit() or int(shares) <= 0:
            return apology("Please provide a positive number of shares", 400)

        shares = int(shares)
        stock = lookup(symbol)

        # Check if the stock symbol is valid
        if stock is None:
            return apology("Invalid stock symbol", 400)

        # Calculate the cost of the shares after validation
        cost = round(shares * stock["price"], 2)  # Rounding to 2 decimal places for accuracy

        # Query user's current cash balance
        user_id = session["user_id"]
        user_balance = db.execute("SELECT cash FROM users WHERE id = ?", user_id)

        # Ensure user_balance is properly retrieved
        if not user_balance:
            return apology("User balance not found", 400)

        balance = user_balance[0]["cash"]

        # Check if the user can afford the shares
        if cost > balance:
            return apology("Not enough cash in balance", 400)

        # Update user's cash balance after the purchase
        new_balance = round(balance - cost, 2)  # Ensure new balance is rounded correctly
        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_balance, user_id)

        # Check if the user already owns shares of this stock
        existing_shares = db.execute(
            "SELECT shares FROM purchases WHERE user_id = ? AND symbol = ?", user_id, symbol)

        if existing_shares:
            # If the user already has shares, update the number of shares
            db.execute("UPDATE purchases SET shares = shares + ? WHERE user_id = ? AND symbol = ?",
                       shares, user_id, symbol)
        else:
            # If the user doesn't have shares, insert a new record
            db.execute("INSERT INTO purchases (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)",
                       user_id, symbol, shares, stock["price"])

        # Record the purchase in transactions table
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, transaction_type) VALUES (?, ?, ?, ?, ?)",
                   user_id, symbol, shares, stock["price"], "Buy")

        # Redirect to the home page
        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]

    transactions = db.execute(
        "SELECT * FROM transactions WHERE user_id =? ORDER BY timestamp DESC", user_id)
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
    if request.method == ("POST"):
        symbol = request.form.get("symbol")

        if not symbol:
            return apology("Please provide stock symbol", 400)
        stock = lookup(symbol)

        if stock is None:
            return apology("invalid stock symbol", 400)
        return render_template("quoted.html", name=stock["name"], symbol=stock["symbol"], price=stock["price"])
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == ("POST"):
        try:
            # Get the username from form input
            username = request.form.get("username")
            if not username:
                return apology("Must Provide Username", 400)
             # Check if the username already exists
            rows = db.execute("SELECT * FROM users  WHERE username = ?", username)
            if rows:
                return apology("Username Already Exists", 400)

            password = request.form.get("password")
            confirmation = request.form.get("confirmation")
            if (not password or not confirmation):
                return apology("Must Provide Password", 400)

            if password != confirmation:
                return apology("Passwords Do Not Match", 400)

            # Hash the password before storing
            hashed_password = generate_password_hash(password)

            db.execute("INSERT INTO users (username , hash) VALUES(?, ?)",
                       username,  hashed_password)
            return redirect("/")

        except ValueError:
            return apology("Username Already Exists", 400)

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]

    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Validate symbol input
        if not symbol:
            return apology("Must provide symbol", 400)

         # Validate shares input to ensure it is a positive integer
        if not shares.isdigit() or int(shares) <= 0:
            return apology("Must provide positive shares number", 400)

        # Convert shares to an integer after validation

        shares = int(shares)

        # Retrieve the user's holding of the specified stock
        holding = db.execute(
            "SELECT shares FROM purchases WHERE user_id = ? AND symbol = ?", user_id, symbol)

        # Check if the user owns enough shares to sell
        if not holding or holding[0]["shares"] < shares:
            return apology("You don't have enough shares", 400)

        # Look up the current stock price
        stock = lookup(symbol)

        # Check if the stock symbol is valid

        if not stock:
            return apology("Invalid stock symbol", 400)

          # Calculate the sale value
        sale_value = shares * stock["price"]

        # Update the user's cash balance
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", sale_value, user_id)

        # Check if the user is selling all shares or only some
        if holding[0]["shares"] == shares:
            # If all shares are sold, delete the stock from the user's portfolio
            db.execute("DELETE FROM purchases WHERE user_id = ? AND symbol = ?", user_id, symbol)
        else:
            # If only some shares are sold, update the shares count in the portfolio
            db.execute(
                "UPDATE purchases SET shares = shares - ? WHERE user_id = ? AND symbol = ?", shares, user_id, symbol)

        # Record the transaction in transactions table
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, transaction_type) VALUES (?, ?, ?, ?,?)",
                   user_id, symbol, shares, stock["price"], 'Sell')

        # Redirect to the homepage after the sale
        return redirect("/")
    else:
       # Fetch the user's stocks to populate the dropdown menu in the sell form
        stocks = db.execute("SELECT DISTINCT symbol FROM purchases WHERE user_id = ?", user_id)
    return render_template("sell.html", stocks=stocks)


@app.route("/delete", methods=["GET", "POST"])
@login_required
def delete():
    """Delete the user's account"""
    user_id = session["user_id"]

    if request.method == "POST":
        # Delete user's stock purchases, transactions, and account
        db.execute("DELETE FROM purchases WHERE user_id = ?", user_id)
        db.execute("DELETE FROM transactions WHERE user_id = ?", user_id)

        # Log the user out by clearing the session
        session.clear()

        # Redirect to the home page (or you can direct to a confirmation page)
        return redirect("/")

    else:
        # Display a confirmation page for account deletion
        return render_template("delete.html")
