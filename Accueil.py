import streamlit as st
import sqlite3, os
from dotenv import load_dotenv

# --- Imports internes ---
from mods.geocode import geocode_appointments
from mods.clustering import clustering
from mods.tsr_plan import TSP
from mods.models import Client, Appointment, Travel


# --- Config ---
load_dotenv(dotenv_path=".secret")
DB_PATH = os.getenv("DB_PATH")
ORS_API_KEY = os.getenv("ORS_API_KEY")

st.title("📅 Agendix Routing - Optimisation des tournées")

# --- Connexion DB ---
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row  # pour ORM
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
    print("\n##############\n")
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

        # Récupération itinéraire + RDV associés
        c.execute("""
            SELECT i.appt_id, i.sequence, i.depart_time, i.arrive_time,
                   i.duration_visit, i.travel_time_prev, i.distance_prev,
                   a.client_id, a.type, a.duration,
                   a.num, a.rue, a.ville, a.zip,
                   cl.nom as client_nom, cl.address as client_address
            FROM itineraries i
            LEFT JOIN appointments a ON i.appt_id = a.id
            LEFT JOIN clients cl ON a.client_id = cl.id
            WHERE i.cluster_id = ?
            ORDER BY i.sequence
        """, (cluster_id,))
        rows = c.fetchall()

        travels: list[Travel] = []
        prev_appt: Appointment | None = None

        for row in rows:
            appt_id = row["appt_id"]

            appt = None
            if appt_id:  # construire l’objet Appointment + Client
                client = Client(
                    id=row["client_id"],
                    nom=row["client_nom"],
                    address=row["client_address"]
                )
                adresse = f"{row['num']} {row['rue']}, {row['ville']} {row['zip']}"
                appt = Appointment(
                    id=appt_id,
                    client_id=client.id,
                    num=row["num"], rue=row["rue"], ville=row["ville"], zip=row["zip"],
                    type=row["type"], duration=row["duration"]
                )
                appt.client = client  # lien objet, non DB

            travel = Travel(
                origin_appt_id=prev_appt.id if prev_appt else None,
                dest_appt_id=appt.id if appt else None,
                cluster_id=cluster_id,
                depart_time=row["depart_time"],
                arrive_time=row["arrive_time"],
                travel_time=row["travel_time_prev"],
                distance=row["distance_prev"]
            )
            # enrichissement pour l'affichage
            travel.seq = row["sequence"]
            travel.duration_visit = row["duration_visit"]
            travel.origin = prev_appt
            travel.destination = appt

            travels.append(travel)
            prev_appt = appt

        # --- Affichage ---
        st.subheader("🕒 Planning du cluster")

        for travel in travels:
            prev_label = f"RDV {travel.origin.id}" if travel.origin else traveler_choice
            curr_label = f"RDV {travel.destination.id}" if travel.destination else traveler_choice

            st.markdown(
                f"**{travel.seq}.** {prev_label} → {curr_label}  "
                f"\nDépart : {travel.depart_time} | Arrivée : {travel.arrive_time}  "
                f"| 🚗 {travel.travel_time} min / {travel.distance:.1f} km"
            )

            if travel.destination:
                appt = travel.destination
                st.markdown("---")
                st.markdown(
                    f"👤 Client : **{appt.client.nom}**  \n"
                    f"📍 Adresse : {appt.num} {appt.rue}, {appt.ville} {appt.zip}  \n"
                    f"🏷️ Type : {appt.type or 'N/A'}  \n"
                    f"⏱️ Durée prévue : {appt.duration} min"
                )
                st.markdown("---")

    else:
        st.info("ℹ️ Aucun cluster n'a encore été généré.")

conn.close()
