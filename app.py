# server.py
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import json
import os
from threading import Lock

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")
verrou = Lock()

# Fichiers JSON
eleves_file = "eleves.json"
messages_file = "messages.json"
ecoles_file = "ecoles.json"

# Fonctions utilitaires
def charger_json(fichier):
    if not os.path.exists(fichier):
        with open(fichier, "w") as f:
            json.dump({}, f)
    with open(fichier, "r") as f:
        return json.load(f)

def sauvegarder_json(fichier, data):
    with open(fichier, "w") as f:
        json.dump(data, f, indent=2)

# Routes HTTP
@app.route("/verifier_ecole", methods=["POST"])
def verifier_ecole():
    data = request.get_json()
    ecole_id = data.get("id")
    ecoles = charger_json(ecoles_file)
    if ecole_id in ecoles:
        return jsonify({"success": True, "nom": ecoles[ecole_id]})
    return jsonify({"success": False})

@app.route("/ajouter_eleve", methods=["POST"])
def ajouter_eleve():
    data = request.get_json()
    ecole_id = data["ecole_id"]
    eleve_id = data["eleve_id"]
    nom = data["nom"]
    with verrou:
        eleves = charger_json(eleves_file)
        if ecole_id not in eleves:
            eleves[ecole_id] = {}
        eleves[ecole_id][eleve_id] = nom
        sauvegarder_json(eleves_file, eleves)
    return jsonify({"success": True})

@app.route("/liste_eleves", methods=["POST"])
def liste_eleves():
    data = request.get_json()
    ecole_id = data.get("ecole_id")
    eleves = charger_json(eleves_file)
    return jsonify(eleves.get(ecole_id, {}))

@app.route("/supprimer_eleve", methods=["POST"])
def supprimer_eleve():
    data = request.get_json()
    ecole_id = data["ecole_id"]
    eleve_id = data["eleve_id"]
    with verrou:
        eleves = charger_json(eleves_file)
        if ecole_id in eleves and eleve_id in eleves[ecole_id]:
            del eleves[ecole_id][eleve_id]
            sauvegarder_json(eleves_file, eleves)
    return jsonify({"success": True})

# Événement WebSocket
@socketio.on("envoyer_message")
def envoyer_message(data):
    ecole_id = data["ecole_id"]
    eleves = data["eleves"]
    message = data["message"]
    with verrou:
        messages = charger_json(messages_file)
        if ecole_id not in messages:
            messages[ecole_id] = []
        messages[ecole_id].append({
            "eleves": eleves,
            "contenu": message
        })
        sauvegarder_json(messages_file, messages)
    emit("confirmation", {"statut": "envoyé"}, broadcast=True)

# Démarrage du serveur avec port dynamique
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port)
