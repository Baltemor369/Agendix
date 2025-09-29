import streamlit as st
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import sqlite3,folium, requests

from func.geocode import geocode_appointments
from func.clustering import clustering
from func.tsr_plan import plan_clusters
from func.map_gen import plot_clusters_map_v2

import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=".secret")
DB_PATH = os.getenv("DB_PATH")
ORS_API_KEY = os.getenv("ORS_API_KEY")

if "message" not in st.session_state:
    st.session_state["message"] = None

if st.session_state["message"]:
    if st.session_state["message"][1] > 1:
        st.session_state["message"] = None
    else:
        st.session_state["message"] = (st.session_state["message"][0],2)
        st.success(st.session_state["message"][0])

st.title("📅 Agendix Routing - Agenda & Itinéraires")

# Connexion DB
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Choisir cluster
c.execute("""
    SELECT DISTINCT i.cluster_id, c.cluster_name
    FROM itineraries i
    JOIN clusters c ON i.cluster_id = c.id
""")
clusters = c.fetchall()

# Afficher les noms dans le selectbox
cluster_choice = st.selectbox(
    "Choisir un cluster :",
    options=[name for _, name in clusters]
)

# Retrouver l'id correspondant
if cluster_choice:
    cluster_id = next(cid for cid, name in clusters if name == cluster_choice)


    # Récupérer itinéraire
    c.execute("""
        SELECT appt_id, sequence
        FROM itineraries
        WHERE cluster_id = ?
        ORDER BY sequence
    """, (cluster_id,))
    itin = c.fetchall()

    # Récupérer dépôt
    c.execute("SELECT lat, lon FROM depots LIMIT 1")
    depot_lat, depot_lon = c.fetchone()

    ###########################
    # Construire carte
    m = folium.Map(location=[depot_lat, depot_lon], zoom_start=10)
    coords = []
    for appt_id, seq in itin:
        if appt_id is None:
            lat, lon = depot_lat, depot_lon
        else:
            c.execute("SELECT lat, lon FROM locations WHERE appt_id = ?", (appt_id,))
            lat, lon = c.fetchone()
        coords.append([lat, lon])
        folium.Marker([lat, lon], popup=f"Seq {seq} - {appt_id or 'DEPOT'}").add_to(m)

    # Construire coords [lon, lat]
    coords_lonlat = [[lon, lat] for lat, lon in coords]

    # Appeler ORS pour l'itinéraire routier
    ors_url = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
    headers = {"Authorization": ORS_API_KEY, "Content-Type": "application/json"}
    body = {"coordinates": coords_lonlat}

    resp = requests.post(ors_url, json=body, headers=headers)

    if resp.status_code == 200:
        features = resp.json()["features"]
        if features:
            geometry = features[0]["geometry"]["coordinates"]  # [lon, lat]
            route = [(lat, lon) for lon, lat in geometry]      # conversion [lat, lon]
            folium.PolyLine(route, color="blue", weight=3, opacity=0.7).add_to(m)
        else:
            st.warning(f"Aucune route trouvée pour le cluster {cluster_choice}")
    else:
        st.error(f"Erreur ORS: {resp.text}")

    # st_folium(m, width=700, height=500)
    ######################################

    # Construire planning temporel (simplifié)
    start_time = st.time_input("Heure de début journée", value=datetime.strptime("09:00", "%H:%M").time())
    rdv_duration = st.number_input("Durée d'un RDV (minutes)", value=60)

    current_time = datetime.combine(datetime.today(), start_time)
    planning = []
    for i, (appt_id, seq) in enumerate(itin):
        planning.append((seq, appt_id or "Maison", current_time.strftime("%H:%M")))
        current_time += timedelta(minutes=rdv_duration)

    st.subheader("🕒 Planning du cluster")
    for seq, appt, heure in planning:
        st.write(f"{heure} → {appt}")

st.title("🗺️ Optimisation des rendez-vous")

if st.button("Lancer l'optimisation des RDV 🚀"):
    try:
        # Étape 1 : conversion adresses -> coordonnées
        st.info("📍 Géocodage des adresses...")
        geocode_appointments(DB_PATH, ORS_API_KEY)

        # Étape 2 : clustering
        st.info("🔗 Regroupement par proximité...")
        clustering(DB_PATH)

        # Étape 3 : planification TSP
        st.info("🛣️ Planification des itinéraires...")
        plan_clusters(DB_PATH, ORS_API_KEY)

        # Étape 4 : génération de la carte
        st.info("🗺️ Génération de la carte interactive...")
        plot_clusters_map_v2(DB_PATH, ORS_API_KEY)

        st.session_state["message"]=("✅ Optimisation terminée ! La carte a été générée.",1)
        st.rerun()
    
    except Exception as e:
        st.error(f"❌ Une erreur est survenue : {e}")
