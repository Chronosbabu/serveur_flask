from flask import Flask, request, jsonify

app = Flask(__name__)
messages = []

@app.route('/')
def accueil():
    return "Serveur Flask sur Railway fonctionne !"

@app.route('/envoyer', methods=['POST'])
def envoyer():
    data = request.json
    messages.append(data)
    return jsonify({"status": "Message reçu"})

@app.route('/recevoir', methods=['GET'])
def recevoir():
    return jsonify(messages)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
