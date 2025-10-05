import streamlit as st
import pandas as pd
import sqlite3
import os
from dotenv import load_dotenv

# --- Config ---
load_dotenv(dotenv_path=".secret")
DB_PATH = os.getenv("DB_PATH")

if "message" not in st.session_state:
    st.session_state["message"] = None


# ============================================================
# 🧰 Helpers DB
# ============================================================

def get_adresses():
    """Récupère la liste des rendez-vous avec le nom du client."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT a.id, c.nom AS client, a.num, a.rue, a.ville, a.zip, a.type
        FROM appointments a
        JOIN clients c ON a.client_id = c.id
        ORDER BY c.nom
    """)
    rows = c.fetchall()
    conn.close()
    df = pd.DataFrame(rows, columns=["id", "Client", "Num", "Rue", "Ville", "Zip", "Type"])
    return df


def get_or_create_client(conn, name, address):
    """Vérifie si un client existe (nom + adresse). Sinon, le crée."""
    c = conn.cursor()
    c.execute("SELECT id FROM clients WHERE nom = ? AND address = ?", (name, address))
    result = c.fetchone()
    if result:
        return result[0]
    c.execute("INSERT INTO clients (nom, address) VALUES (?, ?)", (name, address))
    conn.commit()
    return c.lastrowid


def add_adresse(client_name, num, rue, ville, zip_code, type_):
    """Ajoute un rendez-vous et crée le client s’il n’existe pas."""
    conn = sqlite3.connect(DB_PATH)
    address = f"{num} {rue}, {ville} {zip_code}"
    client_id = get_or_create_client(conn, client_name, address)

    c = conn.cursor()
    c.execute("""
        INSERT INTO appointments (client_id, num, rue, ville, zip, type)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (client_id, num, rue, ville, zip_code, type_))
    conn.commit()
    conn.close()


def delete_adresses(ids):
    """Supprime des rendez-vous (les clients restent)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executemany("DELETE FROM appointments WHERE id=?", [(i,) for i in ids])
    conn.commit()
    conn.close()


# ============================================================
# 🖥️ Interface Streamlit
# ============================================================

st.title("🏠 Gestion des adresses et rendez-vous")

# --- Message persistant ---
if st.session_state["message"]:
    if st.session_state["message"][1] > 1:
        st.session_state["message"] = None
    else:
        st.session_state["message"] = (st.session_state["message"][0], 2)
        st.success(st.session_state["message"][0])

# --- Charger les données ---
if "adresses" not in st.session_state:
    st.session_state["adresses"] = get_adresses()

df = st.session_state["adresses"]

# ============================================================
# 📋 Liste des rendez-vous
# ============================================================

st.subheader("📋 Liste des rendez-vous")

edited_df = st.data_editor(
    df,
    num_rows="dynamic",
    width="stretch",
    disabled=["id"],
    key="table_editor"
)

if st.button("💾 Mettre à jour la base"):
    df = edited_df
    df_orig = st.session_state["adresses"]

    # --- 1️⃣ Suppression ---
    ids_suppr = df_orig[~df_orig["id"].isin(df["id"])]["id"].tolist()
    if ids_suppr:
        delete_adresses(ids_suppr)

    # --- 2️⃣ Modification ---
    cols_editables = ["Client", "Num", "Rue", "Ville", "Zip", "Type"]
    df_merge = df.merge(df_orig, on="id", suffixes=("_new", "_old"))
    for _, row in df_merge.iterrows():
        updates = {col: row[f"{col}_new"] for col in cols_editables if row[f"{col}_new"] != row[f"{col}_old"]}
        if updates:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()

            # Si le client change → recréer un client si besoin
            if "Client" in updates:
                full_address = f"{row['Num_new']} {row['Rue_new']}, {row['Ville_new']} {row['Zip_new']}"
                client_id = get_or_create_client(conn, updates["Client"], full_address)
                updates["client_id"] = client_id
                del updates["Client"]

            set_str = ", ".join([f"{col.lower()} = ?" for col in updates])
            values = list(updates.values()) + [row["id"]]
            c.execute(f"UPDATE appointments SET {set_str} WHERE id = ?", values)
            conn.commit()
            conn.close()

    # --- Rechargement ---
    st.session_state["adresses"] = get_adresses()
    st.session_state["message"] = ("✅ Base de données mise à jour !", 1)
    st.rerun()


# ============================================================
# ➕ Ajout d’un rendez-vous
# ============================================================

st.markdown("---")
st.subheader("➕ Ajouter un rendez-vous")

with st.form("add_adresse_form"):
    client = st.text_input("Nom du client")
    num = st.text_input("Numéro")
    rue = st.text_input("Rue")
    ville = st.text_input("Ville")
    zip_code = st.text_input("Code postal")
    type_ = st.text_input("Type de RDV")

    submitted = st.form_submit_button("Ajouter")
    if submitted:
        if not client or not rue or not ville:
            st.error("⚠️ Merci de remplir au minimum le nom, la rue et la ville.")
        else:
            add_adresse(client, num, rue, ville, zip_code, type_)
            st.success("✅ Rendez-vous ajouté !")
            st.session_state["adresses"] = get_adresses()
            st.rerun()


# ============================================================
# 📥 Import CSV
# ============================================================

st.markdown("---")
st.subheader("📥 Importer un fichier CSV")

uploaded_file = st.file_uploader("Choisissez un fichier CSV", type="csv")

if uploaded_file is not None:
    df_csv = pd.read_csv(uploaded_file)

    expected_cols = ["Client", "Num", "Rue", "Ville", "Zip", "Type"]
    if not all(col in df_csv.columns for col in expected_cols):
        st.error(f"Le CSV doit contenir les colonnes suivantes : {expected_cols}")
    else:
        conn = sqlite3.connect(DB_PATH)
        for _, row in df_csv.iterrows():
            address = f"{row['Num']} {row['Rue']}, {row['Ville']} {row['Zip']}"
            client_id = get_or_create_client(conn, row["Client"], address)
            c = conn.cursor()
            c.execute("""
                INSERT INTO appointments (client_id, num, rue, ville, zip, type)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (client_id, row["Num"], row["Rue"], row["Ville"], row["Zip"], row["Type"]))
        conn.commit()
        conn.close()
        st.success("✅ Fichier importé et rendez-vous ajoutés !")
        st.session_state["adresses"] = get_adresses()
        st.rerun()
