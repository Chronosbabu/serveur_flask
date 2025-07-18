import firebase_admin
from firebase_admin import credentials, messaging

# Initialiser Firebase avec la clé JSON (assure-toi que le fichier est dans le même dossier)
cred = credentials.Certificate("firebase-key.json")
firebase_admin.initialize_app(cred)

# Fonction pour envoyer une notification push
def envoyer_notification(token, titre, message):
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=titre,
                body=message
            ),
            token=token
        )

        response = messaging.send(message)
        print("✅ Notification envoyée :", response)
    except Exception as e:
        print("❌ Erreur lors de l'envoi :", e)
