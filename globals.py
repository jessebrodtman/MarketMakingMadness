# globals.py
from cs50 import SQL
from threading import Lock

# Shared database connection
db = SQL("sqlite:///gamefiles.db")

# Shared state
lobbies = []
markets = {}

# Locks
bot_lock = Lock()
