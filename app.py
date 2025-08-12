from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
import json
import os
from threading import Lock
from datetime import datetime
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")
verrou = Lock()

BOT_TOKEN = "8251629643:AAH1K4X-bjNQUOk_ym5p4BLVWLh3Ad6NF8M"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

eleves_file = "eleves.json"
messages_file = "messages.json"
ecoles_file = "ecoles.json"

clients_connectes = {}  # eleve_id -> sid socket

def charger_json(fichier):
    if not os.path.exists(fichier):
        with open(fichier, "w", encoding="utf-8") as f:
            json.dump({}, f)
    try:
        with open(fichier, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Erreur chargement {fichier}: {e}")
        return {}

def sauvegarder_json(fichier, data):
    try:
        with open(fichier, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Erreur sauvegarde {fichier}: {e}")

def set_telegram_webhook():
    url_webhook = f"https://serveur-flask.onrender.com/webhook/{BOT_TOKEN}"
    try:
        resp = requests.get(f"{TELEGRAM_API_URL}/setWebhook", params={"url": url_webhook})
        print("Webhook Telegram set:", resp.json())
    except Exception as e:
        print("Erreur setWebhook Telegram:", e)

def envoyer_message_telegram(chat_id, texte):
    try:
        requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": texte
        })
    except Exception as e:
        print(f"Erreur envoi Telegram à {chat_id}: {e}")

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
        telegram_id = eleves[ecole_id].get(eleve_id, {}).get("telegram_id")
        eleves[ecole_id][eleve_id] = {
            "nom": nom,
            "telegram_id": telegram_id
        }
        sauvegarder_json(eleves_file, eleves)
    return jsonify({"success": True})

@app.route("/liste_eleves", methods=["POST"])
def liste_eleves():
    data = request.get_json()
    ecole_id = data.get("ecole_id")
    eleves = charger_json(eleves_file)
    if ecole_id not in eleves:
        return jsonify({})
    corrected = {}
    for eid, val in eleves[ecole_id].items():
        if isinstance(val, str):
            corrected[eid] = {"nom": val, "telegram_id": None}
        else:
            corrected[eid] = val
    if corrected != eleves[ecole_id]:
        eleves[ecole_id] = corrected
        with verrou:
            sauvegarder_json(eleves_file, eleves)
    return jsonify(corrected)

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

# -- SOCKET.IO --

@socketio.on('connect')
def on_connect():
    print(f"Client connecté sid={request.sid}")

@socketio.on('identification')
def on_identification(data):
    eleve_id = data.get('eleve_id')
    if not eleve_id:
        return
    clients_connectes[eleve_id] = request.sid
    join_room(request.sid)
    print(f"Élève {eleve_id} identifié et connecté avec sid={request.sid}")

    # Envoi des messages non lus
    with verrou:
        messages = charger_json(messages_file)
    for ecole_id, msgs in messages.items():
        for m in msgs:
            if eleve_id in m.get('eleves', []):
                emit('nouveau_message', {
                    "ecole_id": ecole_id,
                    "message": m
                }, room=request.sid)

@socketio.on('confirmer_reception')
def confirmer_reception(data):
    ecole_id = data.get('ecole_id')
    timestamp = data.get('timestamp')
    eleve_id = data.get('eleve_id')
    if not all([ecole_id, timestamp, eleve_id]):
        return
    with verrou:
        messages = charger_json(messages_file)
        if ecole_id in messages:
            # Supprimer message reçu par cet élève
            new_messages = []
            for m in messages[ecole_id]:
                if m['timestamp'] == timestamp:
                    # Enlever cet élève de la liste destinataires
                    m['eleves'] = [e for e in m['eleves'] if e != eleve_id]
                    if m['eleves']:  # Si reste d'autres destinataires
                        new_messages.append(m)
                else:
                    new_messages.append(m)
            messages[ecole_id] = new_messages
            sauvegarder_json(messages_file, messages)
            print(f"Réception confirmée : élève {eleve_id} message {timestamp}")

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    for eleve_id, stored_sid in list(clients_connectes.items()):
        if stored_sid == sid:
            del clients_connectes[eleve_id]
            print(f"Élève {eleve_id} déconnecté sid={sid}")
            break

@socketio.on("envoyer_message")
def envoyer_message(data):
    ecole_id = data["ecole_id"]
    eleves = data["eleves"]
    message = data["message"]
    timestamp = datetime.now().isoformat()
    print(f"envoyer_message: école={ecole_id}, message='{message}' aux élèves={eleves}")

    with verrou:
        messages = charger_json(messages_file)
        if ecole_id not in messages:
            messages[ecole_id] = []
        messages[ecole_id].append({
            "eleves": eleves[:],  # copie liste destinataires
            "contenu": message,
            "timestamp": timestamp
        })
        sauvegarder_json(messages_file, messages)

    emit("confirmation", {"statut": "envoyé"}, broadcast=True)
    for eleve_id in eleves:
        sid = clients_connectes.get(eleve_id)
        if sid:
            # Envoyer directement via socket
            emit("nouveau_message", {
                "ecole_id": ecole_id,
                "message": {
                    "eleves": [eleve_id],
                    "contenu": message,
                    "timestamp": timestamp
                }
            }, room=sid)
        else:
            # Non connecté socket, envoyer par Telegram si possible
            eleves_data = charger_json(eleves_file)
            for ec_id, e_dict in eleves_data.items():
                if eleve_id in e_dict:
                    telegram_id = e_dict[eleve_id].get("telegram_id")
                    nom = e_dict[eleve_id].get("nom")
                    if telegram_id:
                        envoyer_message_telegram(telegram_id, f"Message pour {nom}: {message}")
                    break

@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.json
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        texte = data["message"].get("text", "").strip()

        eleves = charger_json(eleves_file)
        trouve = False
        for ecole_id, eleves_ecole in eleves.items():
            if texte in eleves_ecole:
                if isinstance(eleves_ecole[texte], str):
                    eleves_ecole[texte] = {
                        "nom": eleves_ecole[texte],
                        "telegram_id": chat_id
                    }
                else:
                    if eleves_ecole[texte].get("telegram_id") != chat_id:
                        eleves_ecole[texte]["telegram_id"] = chat_id

                sauvegarder_json(eleves_file, eleves)
                envoyer_message_telegram(chat_id, f"✅ Élève trouvé : {eleves_ecole[texte]['nom']} ({ecole_id})")
                trouve = True
                break
        if not trouve:
            envoyer_message_telegram(chat_id, "❌ Aucun élève trouvé avec cet ID.")

    return jsonify({"ok": True})

if __name__ == "__main__":
    set_telegram_webhook()
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port)


