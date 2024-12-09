# Market Making Madness
Welcome to Market Making Madness, an interactive web-based simulation designed to replicate a live trading market environment where players (and bots) can trade contracts based on fair value estimates of real-world questions. This documentation serves as a comprehensive guide to understanding, configuring, and running the project.

Note: Proclife, requirements.txt, and runtime.txt are used to host the website on render
Link: https://marketmakingmadness.onrender.com/login

## Overview
Market Making Madness is a multiplayer market simulation where users create or join lobbies, trade contracts, and compete to maximize profit and efficiency. The platform uses Python (Flask + Socket.IO) for the backend and JavaScript with Bootstrap for the frontend. A SQLite database is used for data persistence. The game integrates trading bots at different difficulty levels and includes features like:
- Live market depth visualization (bid/ask)
- Historical trade data and game P&L for each user
- Trading bots with dynamic fair value adjustment
- Competitive leaderboard displayed at game conclusion
- Ability to quote bids, asks, spreads, purchases, and sales live in the market game
- Multiplayer compatibility

## Features
Core Gameplay
- Create or join a trading lobby.
- Trade contracts using a live bid/ask interface.
- Trade contracts with an interactive button that speeds up the interface.
- Compete with other players (human and bot).

Bots: Bots participate in markets at various difficulty levels:
- Easy: High noise, larger spreads.
- Medium: Moderate noise, balanced spreads.
- Hard: Low noise, tighter spreads.
- Jane Street: Minimal noise, efficient market-making.

Dynamic Leaderboard: P&L (Profit and Loss) leaderboard shown at game conclusion. Metrics include:
- P&L.
- Trade count.
- Accuracy of trades.
  
WebSocket Live Updates
- Markets update in real-time as trades occur.
- Players see live changes in bid/ask depth, roster, and trade history without refreshing.

## Setup and Installation
Prerequisites
- Python 3.10+: Ensure you have Python 3.10+ installed to interpret and execute the Flask app.
- pip 
- Node.js and npm (for WebSocket dependencies)

Installation Steps
1. Clone the repository:
git clone https://github.com/your-repo/market-making-madness.git
cd market-making-madness

2. Install Python dependencies:
pip install -r requirements.txt

3. Install frontend dependencies with: npm install

4. Ensure the SQLite database is properly initialized. Run: flask db upgrade

5. flask run in terminal

6. For local running: Open your browser and navigate to: http://127.0.0.1:5000

Frontend Compilation: The frontend uses Bootstrap and JavaScript. JavaScript files are loaded directly in the browser and do not require manual compilation. However, WebSocket functionality relies on the socket.io library, which is installed via npm.

WebSocket Server: The WebSocket server is a Python script that integrates Socket.IO to handle real-time communication. This is executed directly with Python.


## Usage

### Creating and Joining Lobbies 
Navigate to the "Play" page. 
- To create a lobby, enter a lobby name, specify maximum players, and enter a time limit. Bots can be added in the lobby by name and difficulty level through textual inputs.
- Join a lobby: Select a lobby from the list. The roster and market question will be displayed. You cannot be in multiple lobbies at once, so make sure to leave your current lobby with the "leave lobby" button before joining a new lobby. If the lobby is full or a game is in progress, you will be restricted from joining.
- Once in the lobby, mark yourself as "Ready." All players must be ready for the game to start.
- The lobby creator or any designated player can start the game once all players are ready.

### Game
- The game interface contains 4 primary components: Market Depth, User Actions, Roster, Trading History
- Look at the market depth to see the current bids and asks, which is what other users or bots are willing to buy or sell for on the market
- Use the interactive market interface to place bids/asks or make purchases/sales. The upper interface is for purchases/sales, the bottom for quoting bids/asks.
- The roster shows all players in the current game.
- The trading history shows all the trades that have been made in this game.

### Ending the Game
- Any player can end the game via the "End Game" button, or you can leave the lobby individually with the "Leave Lobby" button. The game also ends when the time runs out; in this case, the leaderboard is displayed, summarizing players' performance and P&L.
- After viewing the leaderboard, players can return to the lobby or exit the game.

### Game Logic
Bots are critical for providing market depth and liquidity. Each bot starts with an initial estimation of the fair value. These estimations update dynamically based on trades and market activity. Noise is added to the bot's logic to prevent it from centering around the fair value.

Bid/Ask Placement: Bots generate bid/ask prices based on:
- Market conditions (spread, depth)
- Difficulty level
- Recent trades

Trading: Bots evaluate opportunities to trade based on 
- Favorable bids/asks compared to fair value.
- Spread and market maturity.

Market Participation
- Bots actively generate bids and asks at intervals of ~10 seconds.
- Dynamic Adjustments: Fair value adjusts based on trade history and activity levels. Difficulty level dictates noise and margin behavior. The bots are also reluctant to tighten the spread when other players are not doing so. Bots become less likely to place tighter bids/asks if they already dominate the market to balance out the trades.

## Technical Notes
WebSockets
- All live updates (e.g., bids, asks, trades) are transmitted using Socket.IO.
- <script> tags built into HTML pages for Javascript handle client-side Socket.IO logic.

Database
- SQLite is used for persistent storage of orders, transactions, and users.

Error Handling: We implemented extensive error handling for edge cases which will all be dealt with on the backend:
- Empty markets
- Self-trading by bots
- Disconnects
- Joining multiple lobbies






