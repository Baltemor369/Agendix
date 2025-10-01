import streamlit as st
import sqlite3
from config import SAMPLES,DEPOT1, TABLES_SQL
from func.geocode import geocode_address

import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=".secret")
DB_PATH = os.getenv("DB_PATH")
ORS_API_KEY = os.getenv("ORS_API_KEY")
DEPOT = DEPOT1

# --- Fonction de création ---
def create_db(db_path=DB_PATH):
    # Vérifier si le fichier existe
    db_exists = os.path.exists(db_path)
    if not db_exists:
        # Création du fichier SQLite (il sera créé automatiquement lors de la connexion)
        conn = sqlite3.connect(db_path)
        conn.close()
        return True
    else:
        return False

# --- Fonction d'initialisation ---
def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        for name, sql in TABLES_SQL.items():
            c.execute(sql)
        conn.commit()
        conn.close()
        return True
    except:
        return False

def insert_data_test(db_path=DB_PATH, data=SAMPLES):
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        for client, num, rue, ville, zipc, typ in data:
            c.execute("""
                INSERT INTO appointments (client, num, rue, ville, zip, type)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (client, num, rue, ville, zipc, typ))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def insert_depot_test(db_path=DB_PATH):
    full = f"{DEPOT["num"]} {DEPOT["rue"]}, {DEPOT["ville"]} {DEPOT["zip_code"]}"
    conn = sqlite3.connect(db_path)
    lat, lon = geocode_address(full, ORS_API_KEY, conn)  # ta fonction existante

    c = conn.cursor()
    c.execute("""
      INSERT INTO depots (nom, num, rue, ville, zip, lat, lon)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (DEPOT["nom"], DEPOT["num"], DEPOT["rue"], DEPOT["ville"], DEPOT["zip_code"], lat, lon))
    conn.commit()
    conn.close()
    print(f"* Dépôt '{DEPOT["nom"]}' ajouté : {lat}, {lon}")
    return True

# --- Interface Streamlit ---
st.title("🛠️ Outils techniques")

# Initialiser la DB
st.subheader("📂 Initialiser la base de données")

if st.button("Créer Database"):
    if create_db():
        st.success("✅ Database créé avec succès.")
    else:
        st.error("❌ Impossible de créer la Database.")

if st.button("Init Tables"):
    if init_db():
        st.success("✅ Les tables de la DB initialisée avec succès.")
    else:
        st.error("❌ Impossible d'initialiser les tables de la base de données.")

if st.button("Inserer données test"):
    if insert_data_test():
        st.success("✅ Données insérées dans la Database.")
    else:
        st.error("❌ Impossible d'insérer les données dans la Database.")

if st.button("Inserer dépôt test"):
    if insert_depot_test():
        st.success("✅ Dépôt insérées dans la Database.")
    else:
        st.error("❌ Impossible d'insérer le dépôt dans la Database.")

st.markdown("---")

# Sauvegarde DB
st.subheader("💾 Sauvegarder la base de données")
if os.path.exists(DB_PATH):
    with open(DB_PATH, "rb") as f:
        st.download_button(
            label="⬇️ Télécharger",
            data=f,
            file_name=f"save_{DB_PATH}",
            mime="application/octet-stream"
        )
else:
    st.error("❌ Aucune base trouvée.")
