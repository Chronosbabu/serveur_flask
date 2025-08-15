from flask import Flask, request, jsonify
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

# 🔹 Initialisation Firebase
cred_info = json.loads(os.environ["FIREBASE_CREDENTIALS"])
cred = credentials.Certificate(cred_info)
firebase_admin.initialize_app(cred, {
    "databaseURL": os.environ.get("FIREBASE_URL", "")
})

# Références Firebase
eleves_ref = db.reference("eleves")
messages_ref = db.reference("messages")
ecoles_ref = db.reference("ecoles")
parents_ref = db.reference("parents")

def charger_json(ref):
    data = ref.get()
    return data if data else {}

def sauvegarder_json(ref, data):
    ref.set(data)

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
            "text": texte,
            "parse_mode": "HTML"
        })
    except Exception as e:
        print(f"Erreur envoi Telegram à {chat_id}: {e}")

@app.route("/exporter_jsons", methods=["GET"])
def exporter_jsons():
    return jsonify({
        "eleves": charger_json(eleves_ref),
        "messages": charger_json(messages_ref),
        "ecoles": charger_json(ecoles_ref),
        "telegram_ids": charger_json(parents_ref)
    })

@socketio.on("envoyer_message")
def envoyer_message(data):
    ecole_id = data["ecole_id"]
    eleves = data["eleves"]
    message = data["message"]
    timestamp = datetime.now().isoformat()

    # Sauvegarde dans Firebase
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

    # Envoi Telegram
    parents = charger_json(parents_ref)
    eleves_data = charger_json(eleves_ref)
    for eleve_id in eleves:
        eleve_info = None
        for ec_id, e_dict in eleves_data.items():
            if eleve_id in e_dict:
                if isinstance(e_dict[eleve_id], str):
                    e_dict[eleve_id] = {"nom": e_dict[eleve_id], "telegram_id": None}
                eleve_info = e_dict[eleve_id]
                break
        if eleve_info and eleve_info.get("telegram_id"):
            titre = f"📢 <b>Message pour {eleve_info['nom']}</b>\n\n"
            envoyer_message_telegram(eleve_info["telegram_id"], titre + message)
        if eleve_id in parents and parents[eleve_id]:
            titre = f"📢 <b>Message pour votre enfant {eleve_info['nom']}</b>\n\n"
            envoyer_message_telegram(parents[eleve_id], titre + message)

@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.json
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        texte = data["message"].get("text", "").strip()

        eleves = charger_json(eleves_ref)
        parents = charger_json(parents_ref)
        messages = charger_json(messages_ref)
        ecoles = charger_json(ecoles_ref)
        trouve = False

        for ecole_id, eleves_ecole in eleves.items():
            if texte in eleves_ecole:
                # Sauvegarde telegram_id
                if isinstance(eleves_ecole[texte], str):
                    eleves_ecole[texte] = {"nom": eleves_ecole[texte], "telegram_id": chat_id}
                else:
                    eleves_ecole[texte]["telegram_id"] = chat_id
                sauvegarder_json(eleves_ref, eleves)
                parents[texte] = chat_id
                sauvegarder_json(parents_ref, parents)

                nom_ecole = ecoles.get(ecole_id, "École inconnue")
                confirmation = f"✅ <b>Élève trouvé :</b> {eleves_ecole[texte]['nom']} ({nom_ecole})"
                envoyer_message_telegram(chat_id, confirmation)

                # Envoi des anciens messages
                if ecole_id in messages:
                    msgs_a_envoyer = [m for m in messages[ecole_id] if texte in m["eleves"]]
                    messages[ecole_id] = [m for m in messages[ecole_id] if texte not in m["eleves"]]
                    sauvegarder_json(messages_ref, messages)
                    for m in msgs_a_envoyer:
                        titre = f"📢 <b>Message pour {eleves_ecole[texte]['nom']}</b>\n\n"
                        envoyer_message_telegram(chat_id, titre + m["contenu"])
                trouve = True
                break
        if not trouve:
            envoyer_message_telegram(chat_id, "❌ Aucun élève trouvé avec cet ID.")

    return jsonify({"ok": True})

if __name__ == "__main__":
    set_telegram_webhook()
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port)
