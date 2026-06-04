"""
Main Flask application for Hollywood Moguls
"""
from flask import Flask, render_template, send_file, jsonify
from flask_socketio import SocketIO
from game_logic import GameState
import socket_handlers
import socket
import qrcode
import io
import webbrowser
import threading

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

def get_local_ip():
    """Get the local network IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"

@app.route('/qr-code')
def generate_qr():
    """Generate QR code for player URL"""
    local_ip = get_local_ip()
    player_url = f"http://{local_ip}:8080/player"

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(player_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    return send_file(buf, mimetype='image/png')

@app.route('/api/player-url')
def player_url():
    """API endpoint to get player URL"""
    local_ip = get_local_ip()
    return jsonify({'url': f'http://{local_ip}:8080/player'})

def open_browser():
    """Open browser to host page after server starts"""
    import time
    time.sleep(1.5)  # Wait for server to start
    webbrowser.open('http://localhost:8080')

if __name__ == '__main__':
    local_ip = get_local_ip()

    print("\n" + "="*50)
    print("🎬 HOLLYWOOD MOGULS SERVER")
    print("="*50)
    print("\nHost view: http://localhost:8080")
    print(f"Players connect to: http://{local_ip}:8080/player")
    print("\nQR code will be available on host screen")
    print("Opening browser automatically...")
    print("="*50 + "\n")

    # Start browser in background thread
    threading.Timer(1.5, open_browser).start()

    socketio.run(app, host='0.0.0.0', port=8080, debug=True)