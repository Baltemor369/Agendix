import streamlit as st
import pandas as pd
import sqlite3

import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=".secret")
DB_PATH = os.getenv("DB_PATH")

if "message" not in st.session_state:
    st.session_state["message"] = None

# --- Helpers DB ---
def get_adresses():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, client, num, rue, ville, zip, type FROM appointments")
    rows = c.fetchall()
    conn.close()
    df = pd.DataFrame(rows, columns=["id","Client","Num","Rue","Ville","Zip","Type"])
    return df

def add_adresse(client, num, rue, ville, zip_code, type_):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO appointments (client, num, rue, ville, zip, type) VALUES (?, ?, ?, ?, ?, ?)",
        (client, num, rue, ville, zip_code, type_),
    )
    conn.commit()
    conn.close()

def delete_adresses(ids):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executemany("DELETE FROM appointments WHERE id=?", [(i,) for i in ids])
    conn.commit()
    conn.close()

if st.session_state["message"]:
    if st.session_state["message"][1] > 1:
        st.session_state["message"] = None
    else:
        st.session_state["message"] = (st.session_state["message"][0],2)
        st.success(st.session_state["message"][0])

# --- Streamlit ---
st.title("🏠 Gestion des adresses")

# --- Session state ---
if "adresses" not in st.session_state:
    st.session_state["adresses"] = get_adresses()

df = st.session_state["adresses"]

st.subheader("📋 Liste des adresses")

# Affichage interactif du tableau avec sélection
edited_df = st.data_editor(
    df,
    num_rows="dynamic",
    width='stretch',
    # column_config={
        # "id": None,  # ID caché
    # },
    key="table_editor",
    disabled=["id"]
)

# sauvegarder le modification
if st.button("Mettre à jour la DB"):
    # Récupération du DataFrame édité
    df = edited_df

    # # Ancien DataFrame
    df_orig = st.session_state["adresses"]

    # # --- 1. Lignes supprimées ---
    ids_suppr = df_orig[~df_orig["id"].isin(df["id"])]["id"].tolist()
    if ids_suppr:
        delete_adresses(ids_suppr)

    # --- 2. Lignes modifiées ---
    # On compare uniquement les colonnes éditables
    cols_editables = ["Client", "Num", "Rue", "Ville", "Zip", "Type"]
    df_merge = df.merge(df_orig, on="id", suffixes=("_new", "_old"))
    for _, row in df_merge.iterrows():
        updates = {col: row[f"{col}_new"] for col in cols_editables if row[f"{col}_new"] != row[f"{col}_old"]}
        st.success(updates)
        
        if updates:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            set_str = ", ".join([f"{col.lower()} = ?" for col in updates])
            values = list(updates.values()) + [row["id"]]
            c.execute(f"UPDATE appointments SET {set_str} WHERE id = ?", values)
            conn.commit()
            conn.close()

    # # --- 3. Lignes ajoutées ---
    # df_added = df[df["id"].isna()]
    # for _, row in df_added.iterrows():
    #     add_adresse(row["Client"], row["Num"], row["Rue"], row["Ville"], row["Zip"], row["Type"])

    # --- Recharger la session ---
    st.session_state["adresses"] = get_adresses()
    st.session_state["message"]=("✅ Base de données mise à jour !",1)
    st.rerun()

st.markdown("---")
st.subheader("➕ Ajouter une adresse")

with st.form("add_adresse_form"):
    client = st.text_input("Client")
    num = st.text_input("Numéro")
    rue = st.text_input("Rue")
    ville = st.text_input("Ville")
    zip_code = st.text_input("Code postal")
    type_ = st.text_input("Type de rdv")

    submitted = st.form_submit_button("Ajouter")
    if submitted:
        add_adresse(client, num, rue, ville, zip_code, type_)
        st.success("✅ Adresse ajoutée !")
        st.session_state["adresses"] = get_adresses()  # met à jour la liste

st.markdown("---")

st.subheader("📥 Importer un listing")

uploaded_file = st.file_uploader("Choisissez un fichier CSV", type="csv")

if uploaded_file is not None:
    # Lire le CSV
    df_csv = pd.read_csv(uploaded_file)
    
    # Optionnel : vérifier que les colonnes correspondent à celles attendues
    expected_cols = ["Client","Num","Rue","Ville","Zip","Type"]
    if not all(col in df_csv.columns for col in expected_cols):
        st.error(f"Le CSV doit contenir ces colonnes : {expected_cols}")
    else:
        # Ajouter un ID temporaire pour les nouvelles lignes
        df_csv["id"] = None
        
        # Concaténer avec le DataFrame existant
        st.session_state["adresses"] = pd.concat(
            [st.session_state["adresses"], df_csv],
            ignore_index=True
        )
        st.success("✅ CSV ajouté au tableau")
