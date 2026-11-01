"""
Main Flask application for Hollywood Moguls
"""
import os
import sys

# Windows consoles may not be able to print the emoji in our log output
for stream in (sys.stdout, sys.stderr):
    if stream and hasattr(stream, 'reconfigure'):
        stream.reconfigure(errors='replace')

from flask import Flask, render_template, send_file, jsonify
from flask_socketio import SocketIO
from game_logic import GameState
import socket_handlers
import socket
import qrcode
import io
import webbrowser
import threading

# When packaged with PyInstaller, bundled files live in a temp dir (sys._MEIPASS)
BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
PORT = int(os.environ.get('SHOWBIZ_PORT', 8080))

app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))
app.config['SECRET_KEY'] = 'hollywood-game-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

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
    player_url = f"http://{local_ip}:{PORT}/player"

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
    return jsonify({'url': f'http://{local_ip}:{PORT}/player'})

def open_browser():
    """Open browser to host page after server starts"""
    webbrowser.open(f'http://localhost:{PORT}')

def port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

if __name__ == '__main__':
    local_ip = get_local_ip()

    if port_in_use(PORT):
        print(f"\nPort {PORT} is already in use - is Hollywood Moguls already running?")
        print(f"Open http://localhost:{PORT} in your browser, or set SHOWBIZ_PORT to use another port.")
        if getattr(sys, 'frozen', False):
            input("\nPress Enter to exit...")
        sys.exit(1)

    print("\n" + "="*50)
    print("🎬 HOLLYWOOD MOGULS SERVER")
    print("="*50)
    print(f"\nHost view: http://localhost:{PORT}")
    print(f"Players connect to: http://{local_ip}:{PORT}/player")
    print("\nQR code will be available on host screen")
    if not os.environ.get('SHOWBIZ_NO_BROWSER'):
        print("Opening browser automatically...")
    print("Close this window (or press Ctrl+C) to stop the server.")
    print("="*50 + "\n")

    # Start browser in background thread (SHOWBIZ_NO_BROWSER=1 for headless servers)
    if not os.environ.get('SHOWBIZ_NO_BROWSER'):
        threading.Timer(1.5, open_browser).start()

    # debug=False: the debug reloader re-runs this script (opening two browser tabs)
    # and doesn't work in a packaged build
    socketio.run(app, host='0.0.0.0', port=PORT, debug=False,
                 allow_unsafe_werkzeug=True)
