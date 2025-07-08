from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import json, os
from datetime import datetime
from threading import Lock

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")
verrou = Lock()

eleves_file = "eleves.json"
messages_file = "messages.json"
ecoles_file = "ecoles.json"
connexions_parents = {}

# Créer les fichiers JSON s'ils n'existent pas
for fichier in [eleves_file, messages_file, ecoles_file]:
    if not os.path.exists(fichier):
        with open(fichier, 'w') as f:
            json.dump([], f)

def charger_json(fichier):
    try:
        with open(fichier, 'r') as f:
            return json.load(f)
    except:
        return []

def sauvegarder_json(fichier, donnees):
    with open(fichier, 'w') as f:
        json.dump(donnees, f, indent=4)

@app.route('/')
def accueil():
    return "✅ Serveur Flask-SocketIO actif"

@app.route('/api', methods=['POST'])
def api():
    data = request.json
    if not data or "type" not in data:
        return jsonify({"status": "type_invalide"})

    type_requete = data["type"]
    eleves = charger_json(eleves_file)
    ecoles = charger_json(ecoles_file)

    if type_requete == "enregistrer_eleve":
        id_recu = data["id"].strip()
        if any(e["id"].strip() == id_recu for e in eleves):
            return "id_existe"

        eleves.append({
            "nom": data["nom"],
            "id": id_recu,
            "ecole": data["ecole"]
        })
        sauvegarder_json(eleves_file, eleves)
        return "enregistrement_reussi"

    elif type_requete == "connexion_ecole":
        id_ecole_recu = data["ecole"].strip()
        ecole_trouvee = next((e for e in ecoles if e["id"].strip() == id_ecole_recu), None)
        if not ecole_trouvee:
            return jsonify({"status": "invalide"})

        nom_ecole = ecole_trouvee["nom"]
        eleves_ecole = [e for e in eleves if e["ecole"].strip() == id_ecole_recu]
        return jsonify({
            "status": "ok",
            "nom_ecole": nom_ecole,
            "eleves": eleves_ecole
        })

    elif type_requete == "connexion_parent":
        id_parent = data["id"].strip()
        eleve = next((e for e in eleves if e["id"].strip() == id_parent), None)
        if not eleve:
            return jsonify({"status": "invalide"})

        with verrou:
            messages = charger_json(messages_file)
            mess = [m for m in messages if m["id"].strip() == id_parent]
            messages = [m for m in messages if m["id"].strip() != id_parent]
            sauvegarder_json(messages_file, messages)

        return jsonify({
            "status": "ok",
            "nom": eleve["nom"],
            "messages": mess
        })

    elif type_requete == "supprimer_eleve":
        id_eleve = data["id"].strip()
        ecole = data["ecole"].strip()
        eleves = [e for e in eleves if not (e["id"].strip() == id_eleve and e["ecole"].strip() == ecole)]
        sauvegarder_json(eleves_file, eleves)
        return "eleve_supprime"

    return jsonify({"status": "type_invalide"})

# Gestion WebSocket pour parent en temps réel
@socketio.on("connexion_parent_en_temps_reel")
def gerer_parent_temps_reel(data):
    id_parent = data.get("id", "").strip()
    if not id_parent:
        return

    eleves = charger_json(eleves_file)
    eleve = next((e for e in eleves if e["id"].strip() == id_parent), None)
    if not eleve:
        return

    connexions_parents[id_parent] = request.sid
    print(f"✅ Parent {id_parent} connecté en WebSocket")

@socketio.on("disconnect")
def deconnexion():
    id_deco = None
    for pid, sid in connexions_parents.items():
        if sid == request.sid:
            id_deco = pid
            break
    if id_deco:
        del connexions_parents[id_deco]
        print(f"❌ Parent {id_deco} déconnecté")

@socketio.on("envoyer_message")
def envoyer_message(data):
    liste_ids = []

    if "ids" in data:
        liste_ids = [i.strip() for i in data["ids"]]
    elif "id" in data:
        liste_ids = [data["id"].strip()]
    elif "id_eleve" in data:
        liste_ids = [data["id_eleve"].strip()]

    texte = data.get("message", "")
    date_heure = datetime.now().isoformat()

    for id_cible in liste_ids:
        message = {
            "id": id_cible,
            "message": texte,
            "heure": date_heure
        }

        with verrou:
            messages = charger_json(messages_file)
            messages.append(message)
            sauvegarder_json(messages_file, messages)

        sid = connexions_parents.get(id_cible)
        if sid:
            try:
                emit("nouveau_message", message, to=sid)
                print(f"📨 Message temps réel envoyé à {id_cible}")
            except:
                print(f"⚠️ Erreur d'envoi à {id_cible}, message stocké")
        else:
            print(f"📥 Parent {id_cible} non connecté, message stocké")

    emit("message_recu", {"status": "ok"})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=10000)
