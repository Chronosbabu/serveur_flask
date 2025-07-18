from flask import Flask, request, jsonify, send_from_directory 
from flask_socketio import SocketIO, emit
import json
import os
from threading import Lock
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, messaging

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")
verrou = Lock()

# Initialiser Firebase Admin
firebase_key_json = os.environ.get('FIREBASE_KEY')
if not firebase_key_json:
    raise Exception("La variable d'environnement FIREBASE_KEY est manquante")
cred = credentials.Certificate(json.loads(firebase_key_json))
firebase_admin.initialize_app(cred)

# Fichiers
eleves_file = "eleves.json"
messages_file = "messages.json"
ecoles_file = "ecoles.json"
tokens_file = "tokens.json"

# Fonctions JSON
def charger_json(fichier):
    if not os.path.exists(fichier):
        with open(fichier, "w", encoding="utf-8") as f:
            json.dump({}, f)
    with open(fichier, "r", encoding="utf-8") as f:
        return json.load(f)

def sauvegarder_json(fichier, data):
    with open(fichier, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# Tokens
def charger_tokens():
    return charger_json(tokens_file)

def sauvegarder_tokens(data):
    sauvegarder_json(tokens_file, data)

@app.route("/register_token", methods=["POST"])
def register_token():
    data = request.get_json()
    token = data.get("token")
    parent_id = data.get("parent_id", "")
    if not token:
        return jsonify({"success": False, "error": "Token manquant"}), 400
    with verrou:
        tokens = charger_tokens()
        tokens[token] = parent_id
        sauvegarder_tokens(tokens)
    return jsonify({"success": True})

def envoyer_notification(token, titre, corps):
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=titre,
                body=corps,
            ),
            token=token
        )
        response = messaging.send(message)
        print("✅ Notification envoyée :", response)
    except Exception as e:
        print("❌ Erreur notification :", e)

def notifier_parents(titre, corps):
    with verrou:
        tokens = charger_tokens()
        for token in tokens.keys():
            envoyer_notification(token, titre, corps)

# Routes diverses (ajouter, supprimer élèves, etc.)...
# ... (conserve tout ce que tu as déjà)

@app.route("/eleves.json")
def get_eleves():
    return send_from_directory(".", "eleves.json")

@app.route("/messages.json")
def get_messages():
    return send_from_directory(".", "messages.json")

# Nouvelle route pour supprimer un message spécifique
@app.route("/supprimer_message", methods=["POST"])
def supprimer_message():
    data = request.get_json()
    ecole_id = data.get("ecole_id")
    timestamp = data.get("timestamp")

    if not ecole_id or not timestamp:
        return jsonify({"success": False, "error": "Paramètres manquants"}), 400

    with verrou:
        messages = charger_json(messages_file)
        if ecole_id in messages:
            avant = len(messages[ecole_id])
            messages[ecole_id] = [msg for msg in messages[ecole_id] if msg.get("timestamp") != timestamp]
            apres = len(messages[ecole_id])
            sauvegarder_json(messages_file, messages)

            if avant == apres + 1:
                return jsonify({"success": True, "message": "Message supprimé"})
            else:
                return jsonify({"success": False, "error": "Message non trouvé"}), 404
        else:
            return jsonify({"success": False, "error": "École non trouvée"}), 404

# WebSocket (conserve ton code pour envoyer message)

@socketio.on("envoyer_message")
def envoyer_message(data):
    ecole_id = data["ecole_id"]
    eleves = data["eleves"]
    message = data["message"]
    timestamp = datetime.now().isoformat()

    with verrou:
        messages = charger_json(messages_file)
        if ecole_id not in messages:
            messages[ecole_id] = []
        messages[ecole_id].append({
            "eleves": eleves,
            "contenu": message,
            "timestamp": timestamp
        })
        sauvegarder_json(messages_file, messages)

    emit("confirmation", {"statut": "envoyé"}, broadcast=True)

    emit("nouveau_message", {
        "ecole_id": ecole_id,
        "message": {
            "eleves": eleves,
            "contenu": message,
            "timestamp": timestamp
        }
    }, broadcast=True)

    ecoles = charger_json(ecoles_file)
    nom_ecole = ecoles.get(ecole_id, ecole_id)

    titre = f"Nouveau message de l'école"
    corps = nom_ecole
    notifier_parents(titre, corps)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port)
