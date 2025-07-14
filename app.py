from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import json
import os
from threading import Lock
from datetime import datetime
from supabase_client import supabase  # Import du client Supabase

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")
verrou = Lock()

# Fichiers JSON pour les autres données
eleves_file = "eleves.json"
messages_file = "messages.json"
# ecoles_file n'est plus utilisé pour Supabase

# Fonctions JSON inchangées pour les autres routes
def charger_json(fichier):
    if not os.path.exists(fichier):
        with open(fichier, "w") as f:
            json.dump({}, f)
    with open(fichier, "r") as f:
        return json.load(f)

def sauvegarder_json(fichier, data):
    with open(fichier, "w") as f:
        json.dump(data, f, indent=2)

# --- ROUTES HTTP ---

@app.route("/verifier_ecole", methods=["POST"])
def verifier_ecole():
    data = request.get_json()
    ecole_id = data.get("id")

    if not ecole_id:
        return jsonify({"success": False, "error": "ID manquant"}), 400

    try:
        ecole_id = int(ecole_id)
    except ValueError:
        return jsonify({"success": False, "error": "ID invalide"}), 400

    result = supabase.table("ecoles").select("*").eq("identifiant", ecole_id).execute()
    print(f"ID reçu: {ecole_id}, résultat Supabase: {result.data}")  # DEBUG

    if result.data:
        return jsonify({"success": True, "nom": result.data[0]["nom"]})
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

# --- FICHIERS JSON DISPONIBLES EN LECTURE POUR LES CLIENTS ---

@app.route("/eleves.json")
def get_eleves():
    return send_from_directory(".", "eleves.json")

@app.route("/messages.json")
def get_messages():
    return send_from_directory(".", "messages.json")

# --- WEBSOCKET : réception de messages de l'école ---

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

    # Réponse à l’école
    emit("confirmation", {"statut": "envoyé"}, broadcast=True)

    # Notification en temps réel pour les parents
    emit("nouveau_message", {
        "ecole_id": ecole_id,
        "message": {
            "eleves": eleves,
            "contenu": message,
            "timestamp": timestamp
        }
    }, broadcast=True)

# --- LANCEMENT DU SERVEUR ---

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port)

