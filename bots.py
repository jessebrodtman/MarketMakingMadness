import random
from datetime import datetime, timedelta
BOTS = {}  # Dictionary to track active bots in all lobbies
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

class Bot:
    def __init__(self, bot_id, name, fair_value, lobby_id, level="medium"):
        """
        Initialize the bot with its properties
        """
        self.bot_id = bot_id
        self.name = name
        self.fair_value = fair_value
        self.lobby_id = lobby_id
        self.level = level
        self.pnl = 0
        self.current_bid = None
        self.current_ask = None
        self.last_trade_time = datetime.now()
        self.market_maturity = 0 
        self.market_state = {
            "best_bid": None,
            "best_ask": None,
            "all_bids": {},
            "all_asks": {},
            "recent_trades": {}
        }

    def update_market_state(self, market_state):
        """
        Update the bot's view of the market state
        """
        self.market_state = market_state

        # Update market maturity level (e.g., based on trades or time elapsed)
        self.market_maturity = len(market_state.get("recent_trades", []))

    def generate_bid_ask(self):
        """
        Generate a bid/ask price based on the bot level, current market state, and market depth
        """
        # Generate random noise based on bot level
        level_noise = {
            "easy": random.uniform(5, 10),
            "medium": random.uniform(2, 5),
            "hard": random.uniform(1, 2),
            "Jane Street": random.uniform(0.5, 1),
        }
        noise = level_noise.get(self.level, random.uniform(2, 5))

        # Weigh fair value vs. market state based on maturity
        maturity_factor = min(self.market_maturity / 20, 1)  # Gradually increases to 1
        weight_on_market = maturity_factor
        weight_on_fair_value = 1 - maturity_factor

        # Extract market depth and calculate weighted bid/ask
        print(self.market_state)
        best_bid = self.market_state.get("best_bid", {"price": self.fair_value - noise})["price"] if self.market_state["best_bid"] else self.fair_value - noise
        best_ask = self.market_state.get("best_ask", {"price": self.fair_value + noise})["price"] if self.market_state["best_ask"] else self.fair_value + noise

        all_bids = self.market_state.get("all_bids", [])
        all_asks = self.market_state.get("all_asks", [])
        avg_bid_depth = sum(bid["quantity"] for bid in all_bids) / len(all_bids) if all_bids else 1
        avg_ask_depth = sum(ask["quantity"] for ask in all_asks) / len(all_asks) if all_asks else 1

        bid_price = (
            weight_on_market * (best_bid + random.uniform(-1, 0.5)) +
            weight_on_fair_value * (self.fair_value - noise)
        ) + random.uniform(-avg_bid_depth / 10, avg_bid_depth / 10)

        ask_price = (
            weight_on_market * (best_ask + random.uniform(0.5, 1)) +
            weight_on_fair_value * (self.fair_value + noise)
        ) + random.uniform(-avg_ask_depth / 10, avg_ask_depth / 10)

        # Ensure valid spread
        if ask_price <= bid_price:
            ask_price = bid_price + random.uniform(0.5, 1)

        self.current_bid = max(0, bid_price)
        self.current_ask = max(0, ask_price)

        return round(self.current_bid, 2), round(self.current_ask, 2)

    def decide_to_trade(self):
        """
        Decide whether the bot will execute a trade based on market conditions,
        depth, and recent activity in the market
        """
        best_ask = self.market_state.get("best_ask", None)
        best_bid = self.market_state.get("best_bid", None)
        last_trades = self.market_state.get("recent_trades", [])

        # Adjust trading probability based on market activity
        trade_frequency_modifier = self._get_trade_frequency_modifier(last_trades)

        # Adjust based on spread and depth
        spread = (best_ask["price"] - best_bid["price"]) if best_ask and best_bid else None
        if spread and spread > random.uniform(1, 5):  # Favor trading in wider spreads
            if random.random() < trade_frequency_modifier:
                if best_ask and random.random() < 0.6:
                    return {"type": "buy", "price": best_ask["price"]}
                elif best_bid and random.random() < 0.4:
                    return {"type": "sell", "price": best_bid["price"]}

        return None

    def _get_trade_frequency_modifier(self, last_trades):
        """
        Determine how often the bot should trade based on market activity
        """
        now = datetime.now()
        recent_trades = [
            trade for trade in last_trades if now - datetime.strptime(trade["created_at"], DATE_FORMAT) < timedelta(seconds=30)
        ]
        activity_level = len(recent_trades)

        if activity_level > 5:
            return 0.1  # Low activity, low trade frequency
        elif activity_level > 2:
            return 0.3
        else:
            return 0.6  # High activity, higher trade frequency

    def update_pnl(self, trade_price, trade_type):
        """
        Update the bot's P&L based on completed trades
        """
        if trade_type == "buy":
            self.pnl -= trade_price
        elif trade_type == "sell":
            self.pnl += trade_price

    def should_update_quotes(self):
        """
        Decide whether the bot should post new bid/ask prices based on market conditions
        """
        now = datetime.now()
        time_since_last_trade = (now - self.last_trade_time).total_seconds()

        # Only update if sufficient time has passed since the last trade
        if time_since_last_trade < 10:  # Adjust this threshold as needed
            return False

        # Check if the bot's current quotes are still competitive
        best_bid = self.market_state.get("best_bid", None)
        best_ask = self.market_state.get("best_ask", None)

        if self.current_bid and best_bid and self.current_bid >= best_bid["price"]:
            return False  # Current bid is still competitive

        if self.current_ask and best_ask and self.current_ask <= best_ask["price"]:
            return False  # Current ask is still competitive

        # Otherwise, allow the bot to update quotes
        return True



def create_bot(bot_id, name, fair_value, lobby_id, level="medium"):
    """
    Create a new bot and add it to the BOTS dictionary
    """
    new_bot = Bot(bot_id, name, fair_value, lobby_id, level)
    BOTS[bot_id] = new_bot
    return new_bot

def remove_bot(bot_id):
    """
    Remove a bot from the BOTS dictionary
    """
    if bot_id in BOTS:
        del BOTS[bot_id]

def get_bots_in_lobby(lobby_id):
    """
    Get all bots in a specific lobby
    """
    return [bot for bot in BOTS.values() if bot.lobby_id == lobby_id]
