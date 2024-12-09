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
            "all_bids": [],
            "all_asks": [],
            "recent_trades": []
        }

        # Add noise to the bot's estimation of fair value based on bot level
        fair_value_noise_percentage = {
            "easy": random.uniform(-0.20, 0.20),  # +/-20% noise
            "medium": random.uniform(-0.10, 0.10),
            "hard": random.uniform(-0.05, 0.05),
            "Jane Street": random.uniform(-0.02, 0.02),
        }
        noise_percentage = fair_value_noise_percentage.get(
            self.level, random.uniform(-0.10, 0.10))
        self.estimated_fair_value = self.fair_value * (1 + noise_percentage)

    def update_market_state(self, market_state):
        """
        Update the bot's view of the market state, excluding its own orders
        """
        self.market_state = market_state

        # Exclude the bot's own orders from best bid and ask
        all_bids = [bid for bid in market_state.get("all_bids", [])
                    if bid["user_id"] != self.bot_id]
        all_asks = [ask for ask in market_state.get("all_asks", [])
                    if ask["user_id"] != self.bot_id]

        # Update best bid and ask excluding the bot's own orders
        self.market_state["best_bid"] = max(
            all_bids, key=lambda x: x["price"], default=None)
        self.market_state["best_ask"] = min(
            all_asks, key=lambda x: x["price"], default=None)

        self.market_state["all_bids"] = all_bids
        self.market_state["all_asks"] = all_asks

        # Update market maturity level (e.g., based on trades or time elapsed)
        self.market_maturity = len(self.market_state.get("recent_trades", []))

        # Adjust the bot's estimated fair value based on recent trades
        self.adjust_estimated_fair_value()

    def adjust_estimated_fair_value(self):
        """
        Adjust the bot's estimated fair value based on recent trades.
        """
        last_trades = self.market_state.get("recent_trades", [])
        if not last_trades:
            return

        # Calculate average trade price
        avg_trade_price = sum(
            trade["price"] for trade in last_trades) / len(last_trades)

        # Adjust estimated fair value towards avg_trade_price
        adjustment_factor = 0.1  # Bot adjusts 10% towards the average price
        new_fair_value = (
            (1 - adjustment_factor) * self.estimated_fair_value
            + adjustment_factor * avg_trade_price
        )

        # Add dynamic noise to prevent exact centering
        level_noise = {
            "easy": random.uniform(-0.05, 0.05),  # +/-5%
            "medium": random.uniform(-0.02, 0.02),
            "hard": random.uniform(-0.01, 0.01),
            "Jane Street": random.uniform(-0.005, 0.005),
        }
        noise = level_noise.get(self.level, random.uniform(-0.02, 0.02))
        self.estimated_fair_value = new_fair_value * (1 + noise)


    def generate_bid_ask(self):
        """
        Generate a bid/ask price based on the bot level, current market state, and market depth.
        """
        # Generate random noise based on bot level
        level_noise = {
            "easy": random.uniform(5, 10),
            "medium": random.uniform(2, 5),
            "hard": random.uniform(1, 2),
            "Jane Street": random.uniform(0.5, 1),
        }
        noise = level_noise.get(self.level, random.uniform(2, 5))

        # Calculate a margin based on the fair value
        margin_multiplier = {
            "easy": 0.1,
            "medium": 0.05,
            "hard": 0.02,
            "Jane Street": 0.01,
        }
        margin = margin_multiplier.get(self.level, 0.05) * self.fair_value

        # Weigh fair value vs. market state based on maturity
        maturity_factor = min(self.market_maturity / 20, 1)  # Gradually increases to 1
        weight_on_market = maturity_factor
        weight_on_fair_value = 1 - maturity_factor

        # Extract market depth and calculate weighted bid/ask
        best_bid = self.market_state.get("best_bid")
        best_ask = self.market_state.get("best_ask")

        # Fallback values for bid/ask if the market is empty
        best_bid_price = best_bid["price"] if best_bid else self.fair_value - noise
        best_ask_price = best_ask["price"] if best_ask else self.fair_value + noise

        all_bids = self.market_state.get("all_bids", [])
        all_asks = self.market_state.get("all_asks", [])
        avg_bid_depth = sum(bid["quantity"] for bid in all_bids) / len(all_bids) if all_bids else 1
        avg_ask_depth = sum(ask["quantity"] for ask in all_asks) / len(all_asks) if all_asks else 1

        # Adjust behavior if the bot holds the top bid/ask
        reluctant_to_tighten_spread = False
        if self.current_bid and best_bid and self.current_bid >= best_bid_price:
            reluctant_to_tighten_spread = True

        if self.current_ask and best_ask and self.current_ask <= best_ask_price:
            reluctant_to_tighten_spread = True

        # Generate bid/ask prices
        bid_price = (
            weight_on_market * (best_bid_price + random.uniform(-1, 0.5)) +
            weight_on_fair_value * (self.fair_value - margin - noise)
        ) + random.uniform(-avg_bid_depth / 10, avg_bid_depth / 10)

        ask_price = (
            weight_on_market * (best_ask_price + random.uniform(0.5, 1)) +
            weight_on_fair_value * (self.fair_value + margin + noise)
        ) + random.uniform(-avg_ask_depth / 10, avg_ask_depth / 10)

        # Adjust if the bot is reluctant to tighten the spread
        if reluctant_to_tighten_spread:
            bid_price -= random.uniform(0, noise / 2)
            ask_price += random.uniform(0, noise / 2)

        # Ensure valid spread
        if ask_price <= bid_price:
            ask_price = bid_price + random.uniform(0.5, 1)

        # Update bot's current bid and ask
        self.current_bid = max(0, bid_price)
        self.current_ask = max(0, ask_price)

        return round(self.current_bid, 2), round(self.current_ask, 2)




    def decide_to_trade(self):
        """
        Decide whether the bot will execute a trade based on market conditions,
        depth, and recent activity in the market.
        """
        best_ask = self.market_state.get("best_ask", None)
        best_bid = self.market_state.get("best_bid", None)
        last_trades = self.market_state.get("recent_trades", [])

        # Adjust trading probability based on market activity
        trade_frequency_modifier = self._get_trade_frequency_modifier(last_trades)

        # Trading margin logic
        trade_margin_multiplier = {
            "easy": 0.1,
            "medium": 0.05,
            "hard": 0.02,
            "Jane Street": 0.01,
        }
        trade_margin = trade_margin_multiplier.get(self.level, 0.05) * self.fair_value

        # Determine trade quantity with a preference for smaller trades
        trade_quantity = self._calculate_trade_quantity()

        # Decide to buy if the best ask is favorable
        if best_ask and best_ask["price"] <= self.fair_value - trade_margin:
            # Check the bot is not trading with its own ask
            if self.current_ask is None or best_ask["price"] < self.current_ask:
                return {"type": "buy", "price": best_ask["price"], "quantity": trade_quantity}

        # Decide to sell if the best bid is favorable
        if best_bid and best_bid["price"] >= self.fair_value + trade_margin:
            # Check the bot is not trading with its own bid
            if self.current_bid is None or best_bid["price"] > self.current_bid:
                return {"type": "sell", "price": best_bid["price"], "quantity": trade_quantity}

        # Adjust based on spread and activity
        spread = (best_ask["price"] - best_bid["price"]) if best_ask and best_bid else None
        if spread and spread > random.uniform(1, 5):  # Favor trading in wider spreads
            if random.random() < trade_frequency_modifier:
                if best_ask and random.random() < 0.6:
                    return {"type": "buy", "price": best_ask["price"], "quantity": trade_quantity}
                elif best_bid and random.random() < 0.4:
                    return {"type": "sell", "price": best_bid["price"], "quantity": trade_quantity}

        return None


    def _calculate_trade_quantity(self):
        """
        Determine the quantity for the bot's trades based on proportional likelihood.
        """
        # Higher probability for smaller quantities
        quantities = [1, 2, 3, 5, 8]  # Fibonacci-like for variability
        weights = [0.4, 0.3, 0.2, 0.07, 0.03]  # Higher weights for smaller quantities
        return random.choices(quantities, weights=weights, k=1)[0]


    def _get_trade_frequency_modifier(self, last_trades):
        """
        Determine how often the bot should trade based on market activity.
        """
        now = datetime.now()
        recent_trades = [
            trade for trade in last_trades if now - datetime.strptime(trade["created_at"], DATE_FORMAT) < timedelta(seconds=30)
        ]
        activity_level = len(recent_trades)

        # Increase trade frequency at the start
        if self.market_maturity < 5:  # Market is immature
            return 0.8  # High trade frequency in early stages

        # Adjust frequency based on activity level
        if activity_level > 5:
            return 0.6  # High activity, lower trade frequency
        elif activity_level > 2:
            return 0.4
        else:
            return 0.2  # Low activity, higher trade frequency


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
        Decide whether the bot should post new bid/ask prices based on market conditions and timing.
        """
        now = datetime.now()
        time_since_last_trade = (now - self.last_trade_time).total_seconds()

        # Probability-based update to reduce frequency
        update_probability = {
            "easy": 0.1,
            "medium": 0.25,
            "hard": 0.5,
            "Jane Street": 0.7,
        }
        should_update = random.random() < update_probability.get(self.level, 0.25)

        if not should_update:
            return False

        # Only update if sufficient time has passed since the last trade
        if time_since_last_trade < 40:  # Increase this threshold to further slow down
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
