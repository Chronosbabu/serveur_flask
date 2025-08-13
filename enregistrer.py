import json
import os
import subprocess

# Nom du fichier JSON
fichier = "ecoles.json"

# Charger les données existantes ou créer un dictionnaire vide
if os.path.exists(fichier):
    with open(fichier, "r") as f:
        try:
            ecoles = json.load(f)
        except json.JSONDecodeError:
            ecoles = {}
else:
    ecoles = {}

while True:
    nom = input("Nom de l'école : ").strip()
    identifiant = input("ID de l'école : ").strip()

    if identifiant in ecoles:
        print("⚠️ Cet ID existe déjà. Réessaie.")
    else:
        ecoles[identifiant] = nom

        # Sauvegarde dans le fichier JSON
        with open(fichier, "w") as f:
            json.dump(ecoles, f, indent=2, ensure_ascii=False)

        print(f"✅ École '{nom}' (ID: {identifiant}) enregistrée.")

        # Mise à jour sur Git
        subprocess.run(["git", "add", fichier])
        subprocess.run(["git", "commit", "-m", f"Ajout de l'école {nom} (ID: {identifiant})"])
        subprocess.run(["git", "push"])

    # Continuer ou arrêter
    autre = input("Voulez-vous ajouter une autre école ? (o/n) : ").strip().lower()
    if autre != "o":
        break


