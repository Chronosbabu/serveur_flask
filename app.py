from flask import Flask, render_template
from flask_socketio import SocketIO, send

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

@socketio.on('message')
def handle_message(msg):
    print('Message reçu:', msg)
    send(msg, broadcast=True)  # renvoie le message à tous les clients connectés

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)

