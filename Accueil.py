import streamlit as st
import sqlite3, os
from dotenv import load_dotenv
# from datetime import datetime, timedelta

# --- Imports internes ---
from func.geocode import geocode_appointments
from func.clustering import clustering
from func.tsr_plan import TSP
from func.use_tools import fmt_time
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

        st.info("🛣️ Ordonner les itinéraires...")
        TSP(DB_PATH, ORS_API_KEY)

        st.success("✅ Optimisation terminée !")
        st.rerun()

    except Exception as e:
        st.error(f"❌ Une erreur est survenue : {e}")

# --------------------------------------------------
# 3. Visualiser les clusters & itinéraires
# --------------------------------------------------
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM itineraries")
count_itin = c.fetchone()[0]

if count_itin > 0:
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
            SELECT appt_id, sequence, depart_time, arrive_time, duration_visit, travel_time_prev, distance_prev
            FROM itineraries
            WHERE cluster_id = ?
            ORDER BY sequence
        """, (cluster_id,))
        itin = c.fetchall()

        # On parcourt les trajets entre chaque point
        for i in range(1, len(itin)):
            prev_appt_id, _, _, prev_depart, _, _, _ = itin[i-1]
            appt_id, seq, arrive, depart, duration, ttime, dist = itin[i]

            # Label des points (RDV ou Dépôt)
            prev_label = f"RDV {prev_appt_id}" if prev_appt_id else traveler_choice
            curr_label = f"RDV {appt_id}" if appt_id else traveler_choice

            st.markdown(
                f"**{seq}.** {prev_label} → {curr_label}  "
                f"\nDépart : {fmt_time(prev_depart)} | Arrivée : {fmt_time(arrive)}  "
                f"| 🚗 {ttime} min / {dist:.1f} km"
            )

            # afficher les informations du rdv qui suit le trajet
            # recuperer les info grace à l'id
            # afficher le type de rdv et sa durer
            # afficher le nom du client l'adresse et la durer

            # ---- Infos RDV ----
            if appt_id:  # si ce n'est pas le dépôt
                c.execute("""
                    SELECT client, num, rue, ville, zip, type
                    FROM appointments
                    WHERE id = ?
                """, (appt_id,))
                rdv = c.fetchone()

                if rdv:
                    client, num, rue, ville, zip_code, type_ = rdv
                    adresse = f"{num} {rue}, {ville} {zip_code}"
                    st.markdown("---")
                    st.markdown(
                        f"🧑 Client : **{client}**  \n"
                        f"📍 Adresse : {adresse}  \n"
                        f"🏷️ Type : {type_ or 'N/A'}  \n"
                        f"⏱️ Durée prévue : {duration} min"
                    )
                    st.markdown("---")

    else:
        st.info("ℹ️ Aucun cluster n'a encore été généré.")

conn.close()

# voir pour construire le planning complet trajet -> rdv -> trajet -> ... 
# une ligne = une etape dans la table => "planning"