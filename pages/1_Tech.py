import streamlit as st
import sqlite3
import os

import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=".secret")
DB_PATH = os.getenv("DB_PATH")

# --- SQL de création des tables ---
TABLES_SQL = {
    "depots": """
        CREATE TABLE depots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom   TEXT    NOT NULL,
            num   TEXT,
            rue   TEXT,
            ville TEXT,
            zip   TEXT,
            lat   REAL,
            lon   REAL
        )
    """,
    "appointments": """
        CREATE TABLE appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client TEXT NOT NULL,
            num TEXT,
            rue TEXT,
            ville TEXT,
            zip TEXT,
            type TEXT
        )
    """,
    "locations": """
        CREATE TABLE locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appt_id INTEGER NOT NULL,
            lat REAL,
            lon REAL,
            FOREIGN KEY(appt_id) REFERENCES appointments(id) ON DELETE CASCADE
        )
    """,
    "clusters": """
        CREATE TABLE clusters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cluster_name TEXT,
            appt_id INTEGER,
            FOREIGN KEY(appt_id) REFERENCES appointments(id)
        )
    """,
    "itineraries": """
        CREATE TABLE itineraries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cluster_id INTEGER NOT NULL,
            appt_id INTEGER,
            sequence INTEGER NOT NULL,
            depart_time TEXT,
            arrive_time TEXT,
            duration_visit INTEGER,
            travel_time_prev INTEGER,
            FOREIGN KEY(cluster_id) REFERENCES clusters(id),
            FOREIGN KEY(appt_id) REFERENCES appointments(id)
        )
    """
}

# --- Fonction d'initialisation ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for name, sql in TABLES_SQL.items():
        c.execute(sql)
    conn.commit()
    conn.close()

# --- Interface Streamlit ---
st.title("🛠️ Outils techniques")

# Initialiser la DB
st.subheader("📂 Initialiser la base de données")
if st.button("Init Tables"):
    init_db()
    st.success("✅ Les tables de la DB initialisée avec succès.")

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
