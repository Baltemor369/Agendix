import streamlit as st
import sqlite3, os
from dotenv import load_dotenv
# from datetime import datetime, timedelta

# --- Imports internes ---
from func.geocode import geocode_appointments
from func.clustering import clustering
from func.tsr_plan import plan_clusters
# from func.map_gen import plot_clusters_map_v2  # tu peux commenter si inutile

# --- Config ---
load_dotenv(dotenv_path=".secret")
DB_PATH = os.getenv("DB_PATH")
ORS_API_KEY = os.getenv("ORS_API_KEY")

st.title("📅 Agendix Routing - Optimisation des tournées")

# --- Connexion DB ---
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# --------------------------------------------------
# 1. Sélection du voyageur (dépôt)
# --------------------------------------------------
st.subheader("👤 Choix du Voyageur")
c.execute("SELECT id, nom, ville FROM depots")
depots = c.fetchall()

if not depots:
    st.warning("⚠️ Aucun dépôt trouvé dans la base. Veuillez en créer un dans la page Dépôts.")
    st.stop()

traveler_choice = st.selectbox(
    "Sélectionnez le voyageur :",
    options=[f"{nom} ({ville})" for _, nom, ville in depots]
)
depot_id = depots[[f"{nom} ({ville})" for _, nom, ville in depots].index(traveler_choice)][0]

# --------------------------------------------------
# 2. Bouton pour lancer l’optimisation
# --------------------------------------------------
st.subheader("⚙️ Optimisation")
if st.button("🚀 Lancer l'optimisation des RDV"):
    try:
        st.info("📍 Géocodage des adresses...")
        geocode_appointments(DB_PATH, ORS_API_KEY)

        st.info("🔗 Regroupement par proximité...")
        clustering(DB_PATH, capacity=6, max_distance_km=30, verbose=True)

        # st.info("🛣️ Ordonner les itinéraires...")
        # plan_clusters(DB_PATH, ORS_API_KEY)

        st.success("✅ Optimisation terminée !")
        # st.session_state["optim_done"] = True
        # st.rerun()

    except Exception as e:
        st.error(f"❌ Une erreur est survenue : {e}")

# --------------------------------------------------
# 3. Visualiser les clusters & itinéraires
# --------------------------------------------------
if "optim_done" in st.session_state:
    st.subheader("📊 Résultats des clusters")

    # Charger clusters disponibles
    c.execute("""
        SELECT DISTINCT i.cluster_id, c.cluster_name
        FROM itineraries i
        JOIN clusters c ON i.cluster_id = c.id
    """)
    clusters = c.fetchall()

    if clusters:
        cluster_choice = st.selectbox(
            "Choisir un cluster à afficher :",
            options=[name for _, name in clusters]
        )
        cluster_id = next(cid for cid, name in clusters if name == cluster_choice)

        # Récupérer itinéraire (séquence ordonnée)
        c.execute("""
            SELECT appt_id, sequence, arrive_time, depart_time, travel_time_prev, distance_prev
            FROM itineraries
            WHERE cluster_id = ?
            ORDER BY sequence
        """, (cluster_id,))
        itin = c.fetchall()

        st.subheader("🕒 Planning du cluster")

        # Récupération de l'itinéraire complet
        c.execute("""
            SELECT appt_id, sequence, depart_time, arrive_time, duration, travel_time_prev, distance_prev
            FROM itineraries
            WHERE cluster_id = ?
            ORDER BY sequence
        """, (cluster_id,))
        itin = c.fetchall()

        # On parcourt les trajets entre chaque point
        for i in range(1, len(itin)):
            prev_appt_id, _, _, prev_depart, _, _ = itin[i-1]
            appt_id, seq, arrive, depart, ttime, dist = itin[i]

            # Label des points (RDV ou Dépôt)
            prev_label = f"RDV {prev_appt_id}" if prev_appt_id else traveler_choice
            curr_label = f"RDV {appt_id}" if appt_id else traveler_choice

            st.markdown(
                f"**{seq}.** {prev_label} → {curr_label}  "
                f"| Départ : {prev_depart} | Arrivée : {arrive}  "
                f"| 🚗 {ttime} min / {dist:.1f} km"
            )

    else:
        st.info("ℹ️ Aucun cluster n’a encore été généré.")

conn.close()
