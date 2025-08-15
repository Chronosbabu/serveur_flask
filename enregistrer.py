import firebase_admin
from firebase_admin import credentials, db

# 🔹 Chemin vers ton fichier JSON Firebase (service account)
chemin_clef = r"C:\Users\Alfred M\Desktop\serviceAccountKey.json"

# 🔹 Initialisation Firebase
cred = credentials.Certificate(chemin_clef)
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://mon-serveur-flask-default-rtdb.firebaseio.com/"
})

# 🔹 Références Firebase
ecoles_ref = db.reference("ecoles")

print("=== Ajout d'écoles ===")

while True:
    # 🔹 Session Entry
    nom = input("Nom de l'école : ").strip()
    identifiant = input("ID de l'école : ").strip()

    # 🔹 Vérification si l'ID existe déjà
    ecoles = ecoles_ref.get() or {}
    if identifiant in ecoles:
        print("⚠️ Cet ID existe déjà. Réessaie.")
    else:
        # 🔹 Ajout dans Firebase
        ecoles_ref.update({identifiant: nom})
        print(f"✅ École '{nom}' (ID: {identifiant}) enregistrée.")

    # 🔹 Continuer ou arrêter
    autre = input("Voulez-vous ajouter une autre école ? (o/n) : ").strip().lower()
    if autre != "o":
        break

print("Fin de l'ajout des écoles.")
