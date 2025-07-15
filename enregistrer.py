import json
import os
import subprocess

# Chemin du fichier JSON
fichier = "ecoles.json"

# Charger les données existantes ou créer un nouveau dictionnaire
if os.path.exists(fichier):
    with open(fichier, "r") as f:
        ecoles = json.load(f)
else:
    ecoles = {}

while True:
    nom = input("Nom de l'école : ").strip()
    identifiant = input("ID de l'école : ").strip()

    if identifiant in ecoles:
        print("⚠️ Cet ID existe déjà. Réessaie.")
    else:
        ecoles[identifiant] = nom
        with open(fichier, "w") as f:
            json.dump(ecoles, f, indent=2)
        print("✅ École enregistrée.")

        # Commandes Git
        subprocess.run(["git", "add", "ecoles.json"])
        subprocess.run(["git", "commit", "-m", f"Ajout de l'école {nom} (ID: {identifiant})"])
        subprocess.run(["git", "push"])

    autre = input("Voulez-vous ajouter une autre école ? (o/n) : ").lower()
    if autre != "o":
        break
