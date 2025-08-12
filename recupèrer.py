import requests
import json
import time

# URL de ton serveur Flask
url = "https://serveur-flask.onrender.com/exporter_jsons"

def sauvegarder_donnees():
    try:
        reponse = requests.get(url)
        if reponse.status_code == 200:
            data = reponse.json()

            # Sauvegarde des élèves
            if data.get("eleves"):
                with open("eleves.json", "w", encoding="utf-8") as f:
                    json.dump(data["eleves"], f, indent=2, ensure_ascii=False)
                print("✅ eleves.json mis à jour.")
            else:
                print("ℹ️ Aucun élève à sauvegarder.")

            # Sauvegarde des messages
            if data.get("messages"):
                with open("messages.json", "w", encoding="utf-8") as f:
                    json.dump(data["messages"], f, indent=2, ensure_ascii=False)
                print("✅ messages.json mis à jour.")
            else:
                print("ℹ️ Aucun message à sauvegarder.")

            # Sauvegarde des Telegram IDs
            if data.get("telegram_ids"):
                with open("telegram_ids.json", "w", encoding="utf-8") as f:
                    json.dump(data["telegram_ids"], f, indent=2, ensure_ascii=False)
                print("✅ telegram_ids.json mis à jour.")
            else:
                print("ℹ️ Aucun Telegram ID à sauvegarder.")

        else:
            print("❌ Erreur du serveur :", reponse.status_code)

    except Exception as e:
        print("❌ Erreur de connexion :", e)

if __name__ == "__main__":
    while True:
        sauvegarder_donnees()
        time.sleep(10)  # Attente de 10 secondes

