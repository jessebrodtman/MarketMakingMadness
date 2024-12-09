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
Below explains some of the structuring choices

static/
- Purpose: Houses static files like CSS and images for the frontend.
- Structure:
- Images: Contains visual assets for branding and UI aesthetics.
- CSS Files: Separate CSS files for each page or component (game.css, login.css, etc.) to ensure modularity.
- static.css: Contains shared styles that are used across multiple pages.
- Design Choice: Organized by file type to streamline development. Modular CSS files prevent overlap and allow targeted styling changes.
