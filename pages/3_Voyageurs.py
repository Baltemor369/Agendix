import streamlit as st
import sqlite3,requests

import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=".secret")
DB_PATH = os.getenv("DB_PATH")
ORS_API_KEY = os.getenv("ORS_API_KEY")

if "message" not in st.session_state:
    st.session_state["message"] = None

# --- Helpers DB ---
def get_depots():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, nom, num, rue, ville, zip, lat, lon FROM depots")
    depots = c.fetchall()
    conn.close()
    return depots

def add_depot(nom, num, rue, ville, zip, lat, lon):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO depots (nom, num, rue, ville, zip, lat, lon) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (nom, num, rue, ville, zip, lat, lon),
    )
    conn.commit()
    conn.close()

def update_depot(depot_id, nom, num, rue, ville, zip, lat, lon):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE depots SET nom=?, num=?, rue=?, ville=?, zip=?, lat=?, lon=? WHERE id=?",
        (nom, num, rue, ville, zip, lat, lon, depot_id),
    )
    conn.commit()
    conn.close()

def delete_depot(depot_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM depots WHERE id=?", (depot_id,))
    conn.commit()
    conn.close()

# --- Géocodage ORS ---
def geocode_address(num, rue, ville, zip):
    """Retourne (lat, lon) depuis une adresse en utilisant ORS."""
    address = f"{num} {rue}, {zip} {ville}"
    url = "https://api.openrouteservice.org/geocode/search"
    params = {"api_key": ORS_API_KEY, "text": address}
    resp = requests.get(url, params=params)
    if resp.status_code == 200:
        features = resp.json().get("features", [])
        if features:
            coords = features[0]["geometry"]["coordinates"]
            return coords[1], coords[0]  # (lat, lon)
    return None, None

if st.session_state["message"]:
    if st.session_state["message"][1] > 1:
        st.session_state["message"] = None
    else:
        st.session_state["message"] = (st.session_state["message"][0],2)
        st.success(st.session_state["message"][0])

# --- Interface Streamlit ---
st.title("🏢 Gestion des Voyageurs")

# Liste des dépôts
st.subheader("📋 Liste des Voyageurs")
depots = get_depots()
if depots:
    for depot in depots:
        st.write(
            f"Voyageur {depot[0]} : {depot[1]} - {depot[2]} {depot[3]}, {depot[4]} {depot[5]} "
            f"(lat: {depot[6]}, lon: {depot[7]})"
        )
else:
    st.info("Aucun Voyageur trouvé.")

st.markdown("---")

# Ajouter un dépôt
st.subheader("➕ Ajouter un Voyageur")
with st.form("add_depot_form"):
    nom = st.text_input("Nom")
    num = st.text_input("Numéro", "")
    rue = st.text_input("Rue")
    ville = st.text_input("Ville")
    zip_code = st.text_input("Code postal")

    submitted = st.form_submit_button("Ajouter")
    if submitted:
        lat, lon = geocode_address(num, rue, ville, zip_code)
        if lat and lon:
            add_depot(nom, num, rue, ville, zip_code, lat, lon)
            st.session_state["message"]=("✅ Voyageur ajouté avec succès !",1)
            st.rerun()
        else:
            st.error("❌ Impossible de géocoder l'adresse.")

# Modifier un dépôt
st.subheader("✏️ Modifier un Voyageur")
if depots:
    # Crée une liste des noms de dépôts
    nom_depots = [d[1] for d in depots]

    # Sélection par nom
    nom_selectionne = st.selectbox("Choisir un Voyageur à modifier", nom_depots)

    # Récupère le dépôt correspondant
    depot = next(d for d in depots if d[1] == nom_selectionne)
    depot_id = depot[0]


    with st.form("update_depot_form"):
        nom = st.text_input("Nom", depot[1])
        num = st.text_input("Numéro", depot[2] or "")
        rue = st.text_input("Rue", depot[3] or "")
        ville = st.text_input("Ville", depot[4] or "")
        zip_code = st.text_input("Code postal", depot[5] or "")

        submitted = st.form_submit_button("Modifier")
        if submitted:
            lat, lon = geocode_address(num, rue, ville, zip_code)
            if lat and lon:
                update_depot(depot_id, nom, num, rue, ville, zip_code, lat, lon)
                st.session_state["message"]=("✅ Voyageur modifié avec succès !",1)
                st.rerun()
            else:
                st.error("❌ Impossible de géocoder l'adresse.")

# Supprimer un dépôt
st.subheader("🗑️ Supprimer un Voyageur")
if depots:
    nom_depots = [d[1] for d in depots]
    nom_a_supprimer = st.selectbox("Choisir un Voyageur à supprimer", nom_depots, key="delete_select")

    depot_a_supprimer = next(d for d in depots if d[1] == nom_a_supprimer)
    depot_id_to_delete = depot_a_supprimer[0]

    if st.button("Supprimer"):
        delete_depot(depot_id_to_delete)
        st.session_state["message"]=(f"❌ Voyageur '{nom_a_supprimer}' supprimé.",1)
        st.rerun()
