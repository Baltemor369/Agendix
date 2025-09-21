import sqlite3,os
from config import *

from func.init_db import init_db
from func.geocode import geocode_appointments, geocode_address
from func.clustering import clustering
from func.tsr_plan import plan_clusters
from func.map_gen import plot_clusters_map_v2

from dotenv import load_dotenv
load_dotenv(dotenv_path=".secret")
DB_PATH     = os.getenv("DB_PATH")
ORS_API_KEY = os.getenv("ORS_API_KEY")
DEPOT = DEPOT1
SAMPLE = SAMPLES

def insert_test_appointments(db_path=DB_PATH):
    sample = SAMPLE
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    for client, num, rue, ville, zipc, typ in sample:
        c.execute("""
            INSERT INTO appointments (client, num, rue, ville, zip, type)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (client, num, rue, ville, zipc, typ))
    conn.commit()
    conn.close()
    print("* Données tests insérées")

def insert_depot(db_path=DB_PATH):
    full = f"{DEPOT["num"]} {DEPOT["rue"]}, {DEPOT["ville"]} {DEPOT["zip_code"]}"
    lat, lon = geocode_address(full, ORS_API_KEY)  # ta fonction existante

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
      INSERT INTO depots (nom, num, rue, ville, zip, lat, lon)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (DEPOT["nom"], DEPOT["num"], DEPOT["rue"], DEPOT["ville"], DEPOT["zip_code"], lat, lon))
    conn.commit()
    conn.close()
    print(f"* Dépôt '{DEPOT["nom"]}' ajouté : {lat}, {lon}")

if __name__ == "__main__":
    print("Launching Agendix.. \n")
    
    # initialisation
    init_db(DB_PATH)
    insert_depot(DB_PATH)

    # insérer les données tests -> appointments
    insert_test_appointments(DB_PATH)

    # convertion en lat,lon -> locations
    geocode_appointments(DB_PATH, ORS_API_KEY)

    # regroupement les points par proximité -> clusters
    clustering(DB_PATH)

    # Planification TSP -> itineraire
    plan_clusters(DB_PATH, ORS_API_KEY)

    # Génération de la carte interactive avec Folium
    plot_clusters_map_v2(DB_PATH, ORS_API_KEY)
