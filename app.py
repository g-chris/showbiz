"""
Main Flask application for Hollywood Moguls
"""
from flask import Flask, render_template
from flask_socketio import SocketIO
from game_logic import GameState
import socket_handlers

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hollywood-game-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize game state
game_state = GameState()

# Register socket handlers
socket_handlers.register_handlers(socketio, game_state)

@app.route('/')
def index():
    """Host view"""
    return render_template('host.html')

@app.route('/player')
def player():
    """Player view"""
    return render_template('player.html')

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🎬 HOLLYWOOD MOGULS SERVER")
    print("="*50)
    print("\nHost view: http://localhost:8080")
    print("Players connect to: http://YOUR_LOCAL_IP:8080/player")
    print("\nTo find your local IP:")
    print("  Mac/Linux: ifconfig | grep inet")
    print("  Windows: ipconfig")
    print("="*50 + "\n")
    socketio.run(app, host='0.0.0.0', port=8080, debug=True)