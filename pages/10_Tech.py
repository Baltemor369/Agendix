import streamlit as st
import os
from mods.rebuild_db import rebuild_database


from dotenv import load_dotenv
load_dotenv(dotenv_path=".secret")
DB_PATH = os.getenv("DB_PATH")

# --- Interface Streamlit ---
st.title("🛠️ Outils techniques")

# Initialiser la DB
st.subheader("📂 Initialiser la base de données")

if st.button("Rebuild Database"):
    try:
        rebuild_database(DB_PATH)
        st.success("✅ Database successful rebuilt.")
    except Exception as e:
        st.error(f"❌ error while rebuilding : {e}")


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
