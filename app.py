from flask import Flask, request, jsonify

app = Flask(__name__)
messages = []

@app.route('/')
def accueil():
    return "Serveur Flask avec ID client fonctionne !"

@app.route('/envoyer', methods=['POST'])
def envoyer():
    data = request.get_json()
    if "client" in data and "message" in data:
        messages.append(data)
        return jsonify({"status": "Message reçu"}), 200
    return jsonify({"error": "Données invalides"}), 400

@app.route('/recevoir', methods=['GET'])
def recevoir():
    return jsonify(messages)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)

