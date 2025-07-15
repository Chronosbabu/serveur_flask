import requests
import json
import os
import time

url = "https://serveur-flask.onrender.com/exporter_jsons"

def sauvegarder_donnees():
    try:
        reponse = requests.get(url)
        if reponse.status_code == 200:
            data = reponse.json()

            # Sauvegarde des élèves
            if data.get("eleves"):
                with open("eleves.json", "w") as f:
                    json.dump(data["eleves"], f, indent=2)
                print("✅ eleves.json mis à jour.")
            else:
                print("ℹ️ Aucun élève à sauvegarder.")

            # Sauvegarde des messages
            if data.get("messages"):
                with open("messages.json", "w") as f:
                    json.dump(data["messages"], f, indent=2)
                print("✅ messages.json mis à jour.")
            else:
                print("ℹ️ Aucun message à sauvegarder.")
        else:
            print("❌ Erreur du serveur :", reponse.status_code)
    except Exception as e:
        print("❌ Erreur de connexion :", e)

# ❗ Code lancé seulement si on exécute ce fichier manuellement
if __name__ == "__main__":
    while True:
        sauvegarder_donnees()
        time.sleep(10)  # Attente 10 secondes avant de recommencer

