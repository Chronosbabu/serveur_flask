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

# Initialiser Firebase Admin avec la bonne variable d'environnement
firebase_key_json = os.environ.get('FIREBASE_KEY_PARENT')
if not firebase_key_json:
    raise Exception("La variable d'environnement FIREBASE_KEY_PARENT est manquante")
cred = credentials.Certificate(json.loads(firebase_key_json))
firebase_admin.initialize_app(cred)

# Fichiers JSON
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

# Gestion des tokens
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
            notification=messaging.Notification(title=titre, body=corps),
            token=token,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    channel_id='default_channel',
                    sound='default',
                    click_action='FLUTTER_NOTIFICATION_CLICK'
                )
            ),
            apns=messaging.APNSConfig(
                headers={'apns-priority': '10'},
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound='default',
                        category='NEW_MESSAGE_CATEGORY'
                    )
                )
            )
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

# Routes Flask

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
            messages[ecole_id] = [m for m in messages[ecole_id] if m.get("timestamp") != timestamp]
            sauvegarder_json(messages_file, messages)
            if len(messages[ecole_id]) == avant - 1:
                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "error": "Message non trouvé"}), 404
        return jsonify({"success": False, "error": "École non trouvée"}), 404

@app.route("/eleves.json")
def get_eleves():
    return send_from_directory(".", "eleves.json")

@app.route("/messages.json")
def get_messages():
    return send_from_directory(".", "messages.json")

# Socket.IO

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

    nom_ecole = charger_json(ecoles_file).get(ecole_id, ecole_id)
    notifier_parents("Nouveau message de l'école", nom_ecole)

# Lancement serveur

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port)
