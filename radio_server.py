import os
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO

# Initialize Flask and SocketIO
app = Flask(__name__)
# Allow cross-origin for the audio endpoint if needed
socketio = SocketIO(app, cors_allowed_origins="*")

# Serve the minimal frontend HTML page for the phone
@app.route('/radio')
def radio():
    return render_template('radio.html')

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "service": "radio_server"})

# Endpoint where the telegram_bot will send the raw .ogg/.wav data
@app.route('/broadcast', methods=['POST'])
def broadcast():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    
    audio_file = request.files['audio']
    audio_data = audio_file.read()
    
    if not audio_data:
        return jsonify({"error": "Empty audio data"}), 400
        
    print(f"📻 Broadcasting audio ({len(audio_data)} bytes) to all connected listeners...")
    
    # Broadcast the binary audio payload to all clients connected to the 'radio_stream' socket namespace/event
    # We will send it as a raw byte array
    socketio.emit('audio_stream', {'data': audio_data})
    
    return jsonify({"status": "broadcasted", "bytes": len(audio_data)})

@socketio.on('connect')
def handle_connect():
    print("🎧 New listener connected to the radio station.")

@socketio.on('disconnect')
def handle_disconnect():
    print("👋 Listener disconnected.")

if __name__ == '__main__':
    print("📡 Starting Live Police Radio Server on port 5002...")
    socketio.run(app, host='0.0.0.0', port=5002)
