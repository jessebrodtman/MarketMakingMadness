# utilities.py contains helper functions and routes that are used in the main application file (app.py) but are not directly related to the main application logic. This file is used to keep the main application file clean and organized.
import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_socketio import SocketIO, join_room, leave_room
import uuid
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from markets import get_random_market
import bots
from bots import create_bot, get_bots_in_lobby
import random
from datetime import datetime
import time, threading
from threading import Lock
import logging

import globals
from globals import db, bot_lock
socketio = None  # Private variable to store the SocketIO instance

def set_socketio(socketio_instance):
    """Setter function to initialize the socketio instance."""
    global socketio
    socketio = socketio_instance


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
            lobby = next((lobby for lobby in globals.lobbies if lobby["id"] == lobby_id), None)
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

def countdown_timer(lobby_id, redirect_url):
    """
    Handle the countdown timer for the lobby
    """
    while True:
        # Find the lobby
        lobby = next((lobby for lobby in globals.lobbies if lobby["id"] == lobby_id), None)
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

# Helper Functions for Databases and globals.lobbies
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

# Lobby and Game Logic Helper Functions
def get_fair_value(lobby_id):
    """
    Retrieve the fair value of the market for a given lobby
    """
    # Find market and return fair value
    market = globals.markets.get(lobby_id)
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
            for lobby in globals.lobbies:
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
            for lobby in globals.lobbies:
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

# Lobby / Game Cleanup Functions
def cleanup_lobby(lobby_id):
    """
    Remove the lobby and associated data from memory
    """

    # Remove lobby from lobbies array
    globals.lobbies = [lobby for lobby in globals.lobbies if lobby['id'] != lobby_id]
    print(globals.lobbies)

    # Remove bots associated with the lobby
    bots.BOTS = {bot_id: bot for bot_id, bot in bots.BOTS.items() if bot.lobby_id != lobby_id}

    # Remove market associated with the lobby
    if lobby_id in globals.markets:
        del globals.markets[lobby_id]

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
        lobby = next((lobby for lobby in globals.lobbies if lobby["id"] == lobby_id), None)
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

def end_game_helper(lobby_id):
    """
    Handle game and lobby cleanup when a game ends
    """
    try:
        # Find the lobby
        print("finding lobby to end")
        lobby = next((lobby for lobby in globals.lobbies if lobby["id"] == lobby_id), None)
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
            """, game_id=lobby_id, fair_value=globals.markets[lobby_id]["fair_value"])
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
