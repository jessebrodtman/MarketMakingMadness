# Design Document

## Introduction
The purpose of this design document is to provide an in-depth technical overview of the project's architecture, implementation, and design decisions. It outlines the rationale for language and software choices, the structure of the codebase, and the logic behind significant implementation decisions. 

## Language and Software
1. Python for Backend
We chose Python for the backend because of its:
- Ease of Use: Python's syntax and readability accelerate development.
- Framework Support: Flask, a micro-framework, allows for rapid development with a simple and flexible architecture.
- Extensive Libraries: Python has libraries for handling database interactions (sqlite3), WebSockets (flask-socketio), and data processing, making it suitable for our use case.

2. JavaScript for Frontend
- Dynamic Interaction: Real-time updates on the game page (e.g., bid/ask updates and trade histories) require JavaScript for dynamic DOM manipulation.
- Socket.IO: JavaScript integrates seamlessly with Socket.IO to handle WebSocket-based real-time communication between the server and client.

3. Flask-SocketIO for Real-Time Communication
- Integration with Flask: It integrates natively with Flask, allowing us to use one framework for HTTP and WebSocket handling.
- Ease of Use: It simplifies the implementation of event-based communication, making features like real-time updates and notifications easy to implement.

4. SQLite for Database
- Simplicity: It is serverless and lightweight, making it ideal for this project’s scale.
- Rapid Prototyping: SQLite requires minimal setup, which aligns with the project’s iterative development.

5. HTML + Jinja with Bootstrap and Custom CSS for Styling
HTML for Structure: Provides the semantic foundation for the web pages, enabling modular templating with Jinja2. Jinja integrates seamlessly with Flask and is a significant time saver with templates.
Bootstrap was used for:
- Responsive Design: Ensures the project looks good on various devices with minimal custom CSS.
- Consistency: Provides a clean and professional UI with minimal effort.
Custom CSS was applied
- For specific pages that required unqiue or tailored styling choices

## Structure and Design Choices
```
project/
├── __pycache__/                # Cached Python files (auto-generated) 
├── flask_session/              # Flask session data (auto-generated during runtime)
├── static/                     # Static files for frontend (CSS, images)
│   ├── images/                 # Images used across the application
│   │   ├── connor.jpg
│   │   ├── homepage-illustration.jpg
│   │   ├── jesse.jpg
│   ├── game.css                # Styling for the game page
│   ├── history.css             # Styling for the history page
│   ├── homepage.css            # Styling for the homepage
│   ├── login.css               # Styling for the login page
│   ├── settings.css            # Styling for the settings page
│   ├── static.css              # Shared global styles
├── templates/                  # Jinja2 HTML templates
│   ├── error.html              # Error page for handling invalid requests
│   ├── game.html               # Game interface
│   ├── history.html            # User's trade history page
│   ├── homepage.html           # Landing page for the application
│   ├── layout.html             # Base layout for templates (includes header/footer)
│   ├── lobby.html              # Lobby interface for creating/joining games
│   ├── login.html              # User login page
│   ├── play.html               # Page listing all available lobbies
│   ├── register.html           # User registration page
│   ├── settings.html           # User settings page
├── venv/                       # Virtual environment files
├── app.py                      # Main application entry point
├── bots.py                     # Bot logic and algorithms
├── gamefiles.db                # SQLite database for persistent data storage
├── markets.py                  # Market-related logic (e.g., fair value, trade matching)
├── Procfile                    # Deployment instructions for platforms like Heroku
├── README.md                   # User documentation
├── requirements.txt            # Python dependencies for the project
├── runtime.txt                 # Specifies Python runtime version
├── utilities.py                # Helper functions and shared logic
```
Below are some of our structuring choices for our Python, HTML, and CSS files. We tried our best to modulate files such that each one had a specific purpose, with app.py being the central file that each one connected to. 

static/
- Purpose: Houses static files like CSS and images for the frontend.
- Structure:
- Images: Contains visual assets for branding and UI aesthetics.
- CSS Files: Separate CSS files for each page or component (game.css, login.css, etc.) to ensure modularity.
- static.css: Contains shared styles that are used across multiple pages.
- Design Choice: Organized by file type to streamline development. Modular CSS files prevent overlap and allow targeted styling changes.

templates/
- Purpose: Contains Jinja2 templates for rendering dynamic HTML pages.
- Structure: layout.html: Acts as the base template, including shared elements like headers, footers, and navigation bars. Other templates extend this layout to maintain consistency.
- Page-Specific Templates: Each page (e.g., game.html, lobby.html) has its own template to decouple logic and ensure clarity.
- Error Handling: error.html provides user-friendly feedback for invalid requests.
- Design Choice: Separating templates by page improves maintainability and makes it easier to update individual components without affecting others.

Game
- We used play.html to list the potential lobbies to join and allow the user to create a lobby
- We used lobby.html to host a specific lobby with a specific lobby-id
- game.html hosts the actual trading game and is also connected to the specific lobby-id resulting from that lobby.

app.py
- Purpose: Acts as the main entry point for the application.
- Key Responsibilities include:
  - Routing and endpoint definitions.
  - Initialization of Flask-SocketIO for real-time communication.
  - Database setup and connections.
- Design Choice: Centralizing the application logic simplifies deployment and debugging. Modular imports from other files (bots.py, utilities.py) prevent app.py from becoming monolithic. app.py imports helper functions, global variables, and other logic from other files that will be explained below.

bots.py
- Purpose: Implements the bot behavior and trading logic with a Bot class.
- Key Responsibilities:
  - Generating realistic bids/asks.
  - Executing trades based on market conditions.
  - Adjusting behavior dynamically based on market maturity and activity.
Design Choice: Abstracting bot logic into its own file ensures modularity and makes the codebase extensible for future enhancements.

gamefiles.db: SQLite database to persist data such as transactions, orders, and user details. Lightweight and serverless, SQLite is perfect for this project’s scale. The single-file database simplifies deployment and avoids external dependencies.
markets.py: Handles market-related operations such as fair value calculations and trade matching; also stores a dictionary of all the market questions for the game.
utilities.py: Contains helper functions and shared utilities used across the project. Especially useful for handling lobby cleanup and starting logic, along with error handling.
globals.py: Centralizes variables used across files

## Front-End and Back-End Design
### Back-End
The backend is built using Flask, a lightweight Python web framework. The key components of the backend are:
- Flask Routing: Routes handle requests for specific pages (e.g., /play, /game/<lobby_id>). Each route processes incoming data, interacts with the database, and renders the appropriate template. The most important part of the backend was the lobby and game: we had to create variables to store lobby information as dictionaries and clean them up after the games were ended. Likewise, information from the games were connected to databases in real time, with live updates using Socket.IO
- Socket.IO Integration: Real-time updates (e.g., new bids/asks, trades, lobby status changes) are implemented using Flask-SocketIO. This allows seamless communication between users without requiring manual page refreshes.
- Database Design: SQLite is used as the database for persistent storage. Our primary ID was the game id for a specific game, from which we identified order, trading, and user data. Tables include:
  - users: Stores user credentials and preferences.
  - games: Stores active lobbies and their configurations.
  - orders: Tracks all bids and asks in the market.
  - transactions: Records completed trades, including price, quantity, and participants.

### Frontend Design
The frontend uses HTML, CSS, and JavaScript to provide an interactive interface for the application. Key design aspects include:

HTML Templates:
- Jinja2 templates are used to dynamically generate pages with Flask, such as game.html for the trading interface and lobby.html for game selection.
- The base layout.html ensures consistent headers, footers, and styles across all pages.
CSS Styling:
- Each page has its own dedicated CSS file (e.g., game.css, login.css) to ensure modular and maintainable styles.
- A global static.css provides shared styles for common elements. We went for a crimson, Harvard-based color palette.
JavaScript:
- Socket.IO is used to handle real-time updates (e.g., market depth changes or trade history updates).
Game:
- We wanted the game interface to look similar to a real-life trading platform, where you could see the depth of the market, current bids, and asks and make your own trades.

## Bot Design

### Bot Strategy
- Market-Making Logic: Bots contribute to market depth by placing bids and asks around their estimated fair value. The generate_bid_ask method incorporates noise and market maturity to calculate bid/ask prices, ensuring that bots provide liquidity without tightening spreads excessively.
- Trading Logic: Bots execute trades when they detect prices significantly deviating from their estimated fair value. To balance the market, bots also adjust their trading frequency based on recent activity, favoring wider spreads during early stages and gradually tightening as the market matures.

### Dynamic Behavior
- Noise and Estimation: Bots introduce randomness to their fair value estimations, making their behavior less predictable and preventing human players from deducing the actual fair value simply by analyzing the bot’s spread.
- Reluctance to Tighten Spread: If a bot already holds the best bid or ask, it reduces the likelihood of placing even tighter orders. This logic helps prevent unnecessary self-competition and avoids overly aggressive market convergence.

### Design Decisions for Bots
- Trading Margins: Bots use a margin-based system, scaled relative to the fair value of the market question. This ensures consistent depth across different market sizes.
- Proportional Trade Quantities: To simulate realistic behavior, bots prefer smaller trade quantities, with larger trades occurring less frequently.
- Adaptive Behavior: Bots dynamically adjust their estimated fair value based on recent trades, ensuring they remain active and relevant even if human players influence prices away from the initial fair value.
- By balancing market-making with dynamic trading behavior, the bots contribute to both liquidity and market efficiency while ensuring that the game remains competitive and engaging for human players.


## Challenges and Solutions

- Challenge: Unnatural Market Dynamics from Overactive Bots.
  - Initially, bots traded too frequently, causing erratic market behavior and diminishing the realism of market dynamics.
  - Solution: Introduced logic to slow down bot trades, emphasizing meaningful and well-timed transactions. Bots now prioritize favorable trades and maintain balance in market activity.
- Challenge: Maintaining Market Depth Without Convergence
  - Markets quickly converged as bots over-tightened spreads by repeatedly improving bids/asks.
  - Solution: Implemented trading margins and reluctance logic, where bots reduce aggressive spread tightening, especially if they already hold the best bid or ask.
- Challenge: Real-Time Synchronization Across Clients
  - Ensuring consistent market state and game updates for all participants was complex due to simultaneous actions by multiple users and bots.
  - Solution: Used Flask-SocketIO to broadcast updates in real-time, enabling synchronized views of bids, asks, and trade histories across all connected clients.

## Future Improvements
- Enhanced Bot Intelligence: Develop more advanced bot strategies, such as dynamic fair value estimation using machine learning, to adapt better to changing market conditions and player behavior.
- Expanded Trading Features: Introduce advanced trading options like batch order placements, market-making tools, and derivatives (e.g., options and futures) to add complexity and engagement.
- Multiplayer Improvment: Allow lobby hosts to customize game settings, such as trade limits, bot difficulty levels, and market dynamics, to tailor the experience to the preferences of players.
