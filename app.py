from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import json
import os
from threading import Lock
from datetime import datetime
import requests
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")
verrou = Lock()

BOT_TOKEN = "8251629643:AAH1K4X-bjNQUOk_ym5p4BLVWLh3Ad6NF8M"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# 🔹 INITIALISATION FIREBASE
cred_info = json.loads(os.environ["FIREBASE_CREDENTIALS"])
cred = credentials.Certificate(cred_info)
firebase_admin.initialize_app(cred, {
    "databaseURL": os.environ.get("FIREBASE_URL", "https://mon-serveur-flask-default-rtdb.firebaseio.com/")
})

# 🔹 Références "fichiers" sur Firebase
eleves_ref = db.reference("eleves")
messages_ref = db.reference("messages")
ecoles_ref = db.reference("ecoles")
parents_ref = db.reference("parents")  # stocke les telegram_id parents

# 🔹 Fonctions pour lire/écrire sur Firebase
def charger_json(ref):
    data = ref.get()
    if not data:
        return {}
    return data

def sauvegarder_json(ref, data):
    ref.set(data)

def set_telegram_webhook():
    url_webhook = f"https://serveur-flask.onrender.com/webhook/{BOT_TOKEN}"
    try:
        resp = requests.get(f"{TELEGRAM_API_URL}/setWebhook", params={"url": url_webhook})
        print("Webhook Telegram set:", resp.json())
    except Exception as e:
        print("Erreur setWebhook Telegram:", e)

# 🔹 Modification ici pour envoyer un message formaté
def envoyer_message_telegram(chat_id, texte):
    try:
        requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": texte,
            "parse_mode": "HTML"  # permet gras, italique, etc.
        })
    except Exception as e:
        print(f"Erreur envoi Telegram à {chat_id}: {e}")

# 🔹 ENDPOINTS
@app.route("/exporter_jsons", methods=["GET"])
def exporter_jsons():
    data = {
        "eleves": charger_json(eleves_ref),
        "messages": charger_json(messages_ref),
        "ecoles": charger_json(ecoles_ref),
        "telegram_ids": charger_json(parents_ref)
    }
    return jsonify(data)

@app.route("/verifier_ecole", methods=["POST"])
def verifier_ecole():
    data = request.get_json()
    ecole_id = data.get("id")
    ecoles = charger_json(ecoles_ref)
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
        eleves = charger_json(eleves_ref)
        if ecole_id not in eleves:
            eleves[ecole_id] = {}
        telegram_id = eleves[ecole_id].get(eleve_id, {}).get("telegram_id")
        eleves[ecole_id][eleve_id] = {
            "nom": nom,
            "telegram_id": telegram_id
        }
        sauvegarder_json(eleves_ref, eleves)
    return jsonify({"success": True})

@app.route("/liste_eleves", methods=["POST"])
def liste_eleves():
    data = request.get_json()
    ecole_id = data.get("ecole_id")
    eleves = charger_json(eleves_ref)
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
            sauvegarder_json(eleves_ref, eleves)
    return jsonify(corrected)

@app.route("/supprimer_eleve", methods=["POST"])
def supprimer_eleve():
    data = request.get_json()
    ecole_id = data["ecole_id"]
    eleve_id = data["eleve_id"]
    with verrou:
        eleves = charger_json(eleves_ref)
        if ecole_id in eleves and eleve_id in eleves[ecole_id]:
            del eleves[ecole_id][eleve_id]
            sauvegarder_json(eleves_ref, eleves)
    return jsonify({"success": True})

@app.route("/supprimer_message", methods=["POST"])
def supprimer_message():
    data = request.get_json()
    ecole_id = data.get("ecole_id")
    timestamp = data.get("timestamp")
    if not ecole_id or not timestamp:
        return jsonify({"success": False, "error": "Paramètres manquants"}), 400
    with verrou:
        messages = charger_json(messages_ref)
        if ecole_id in messages:
            avant = len(messages[ecole_id])
            messages[ecole_id] = [m for m in messages[ecole_id] if m.get("timestamp") != timestamp]
            sauvegarder_json(messages_ref, messages)
            if len(messages[ecole_id]) == avant - 1:
                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "error": "Message non trouvé"}), 404
        return jsonify({"success": False, "error": "École non trouvée"}), 404

@app.route("/eleves.json")
def get_eleves():
    return jsonify(charger_json(eleves_ref))

@app.route("/messages.json")
def get_messages():
    return jsonify(charger_json(messages_ref))

@socketio.on("envoyer_message")
def envoyer_message(data):
    ecole_id = data["ecole_id"]
    eleves = data["eleves"]
    message = data["message"]
    timestamp = datetime.now().isoformat()
    with verrou:
        messages = charger_json(messages_ref)
        if ecole_id not in messages:
            messages[ecole_id] = []
        messages[ecole_id].append({
            "eleves": eleves,
            "contenu": message,
            "timestamp": timestamp
        })
        sauvegarder_json(messages_ref, messages)

    emit("confirmation", {"statut": "envoyé"}, room=request.sid)
    emit("nouveau_message", {
        "ecole_id": ecole_id,
        "message": {
            "eleves": eleves,
            "contenu": message,
            "timestamp": timestamp
        }
    }, broadcast=True)

    parents = charger_json(parents_ref)
    eleves_data = charger_json(eleves_ref)
    ecoles_data = charger_json(ecoles_ref)
    for eleve_id in eleves:
        eleve_info = None
        nom_ecole = ""
        for ec_id, e_dict in eleves_data.items():
            if eleve_id in e_dict:
                if isinstance(e_dict[eleve_id], str):
                    e_dict[eleve_id] = {"nom": e_dict[eleve_id], "telegram_id": None}
                eleve_info = e_dict[eleve_id]
                nom_ecole = ecoles_data.get(ec_id, "")
                break
        if eleve_info:
            texte_eleve = f"<b>Message pour {eleve_info['nom']}</b>\n{message}"
            if eleve_info.get("telegram_id"):
                envoyer_message_telegram(eleve_info["telegram_id"], texte_eleve)
            if eleve_id in parents and parents[eleve_id]:
                texte_parent = f"<b>Message pour {eleve_info['nom']}</b>\n{message}"
                envoyer_message_telegram(parents[eleve_id], texte_parent)

@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.json
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        texte = data["message"].get("text", "").strip()

        eleves = charger_json(eleves_ref)
        parents = charger_json(parents_ref)
        messages = charger_json(messages_ref)
        ecoles_data = charger_json(ecoles_ref)
        trouve = False

        for ecole_id, eleves_ecole in eleves.items():
            if texte in eleves_ecole:
                if isinstance(eleves_ecole[texte], str):
                    eleves_ecole[texte] = {"nom": eleves_ecole[texte], "telegram_id": chat_id}
                else:
                    eleves_ecole[texte]["telegram_id"] = chat_id
                sauvegarder_json(eleves_ref, eleves)
                parents[texte] = chat_id
                sauvegarder_json(parents_ref, parents)
                nom_eleve = eleves_ecole[texte]['nom']
                nom_ecole = ecoles_data.get(ecole_id, "")
                confirmation = f"✅ <b>Élève trouvé : {nom_eleve} ({nom_ecole})</b>"
                envoyer_message_telegram(chat_id, confirmation)

                msgs_a_envoyer = []
                if ecole_id in messages:
                    for m in messages[ecole_id]:
                        if texte in m["eleves"]:
                            msgs_a_envoyer.append(m)
                    if msgs_a_envoyer:
                        messages[ecole_id] = [m for m in messages[ecole_id] if texte not in m["eleves"]]
                        sauvegarder_json(messages_ref, messages)
                for m in msgs_a_envoyer:
                    envoyer_message_telegram(chat_id, f"<b>Message pour {nom_eleve}</b>\n{m['contenu']}")
                trouve = True
                break
        if not trouve:
            envoyer_message_telegram(chat_id, "❌ Aucun élève trouvé avec cet ID.")

    return jsonify({"ok": True})

if __name__ == "__main__":
    set_telegram_webhook()
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port)

