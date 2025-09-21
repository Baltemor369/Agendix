import sqlite3
from pathlib import Path
import requests
import folium
from ortools.constraint_solver import routing_enums_pb2, pywrapcp
from dotenv import load_dotenv
import os
from config import *

load_dotenv(dotenv_path=".secret")  # ou ".env.secret"
DB_PATH     = os.getenv("DB_PATH")
ORS_API_KEY = os.getenv("ORS_API_KEY")
DEPOT = DEPOT1
SAMPLE = SAMPLES

def init_db(db_path=DB_PATH):
    # Supprime l'ancienne BDD et ne crée que 2 tables
    db_file = Path(db_path)
    if db_file.exists():
        db_file.unlink()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.executescript("""
    PRAGMA foreign_keys = ON;
    
    CREATE TABLE appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client TEXT NOT NULL,
        num TEXT,
        rue TEXT,
        ville TEXT,
        zip TEXT,
        type TEXT
    );

    CREATE TABLE locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        appt_id INTEGER NOT NULL,
        lat REAL,
        lon REAL,
        FOREIGN KEY(appt_id) REFERENCES appointments(id) ON DELETE CASCADE
    );

    CREATE TABLE clusters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cluster_name TEXT,
        appt_id INTEGER NOT NULL,
        assign_day INTEGER,
        FOREIGN KEY(appt_id) REFERENCES appointments(id) ON DELETE CASCADE
    );
                    
    CREATE TABLE depots (
        id    INTEGER PRIMARY KEY AUTOINCREMENT,
        nom   TEXT    NOT NULL,
        num   TEXT,
        rue   TEXT,
        ville TEXT,
        zip   TEXT,
        lat   REAL,
        lon   REAL
    );
                    
    CREATE TABLE IF NOT EXISTS itineraries (
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
    );

    """)
    conn.commit()
    conn.close()
    print("* BDD initialisée (appointments + locations)")

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

def geocode_address(address):
    url = "https://api.openrouteservice.org/geocode/search"
    params = {
        "api_key": ORS_API_KEY,
        "text": address,
        "size": 1
    }
    response = requests.get(url, params=params)
    data = response.json()
    try:
        coords = data["features"][0]["geometry"]["coordinates"]
        lon, lat = coords  # ORS retourne [lon, lat]
        return lat, lon
    except (KeyError, IndexError):
        return None, None

def geocode_appointments(db_path=DB_PATH):
    print("* Convertion des adresses en geocode (lat,lon)")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # RDV sans location
    c.execute("""
        SELECT a.id, a.num, a.rue, a.ville, a.zip
        FROM appointments a
        LEFT JOIN locations l ON a.id = l.appt_id
        WHERE l.id IS NULL
    """)
    appointments = c.fetchall()
    done = 0
    for appt_id, num, rue, ville, zip_code in appointments:
        full_address = f"{num} {rue}, {ville} {zip_code}"
        lat, lon = geocode_address(full_address)

        if lat and lon:
            c.execute("""
                INSERT INTO locations (appt_id, lat, lon)
                VALUES (?, ?, ?)
            """, (appt_id, lat, lon))
            print(f"- {full_address} → {lat}, {lon}")
            done+=1
        else:
            print(f"[X] Géocodage échoué pour {full_address}")

    conn.commit()
    conn.close()
    print(f"* {done}/{len(appointments)} Géocodage ORS terminé et stocké dans 'locations'")

def insert_depot(db_path=DB_PATH):
    full = f"{DEPOT["num"]} {DEPOT["rue"]}, {DEPOT["ville"]} {DEPOT["zip_code"]}"
    lat, lon = geocode_address(full)  # ta fonction existante

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
      INSERT INTO depots (nom, num, rue, ville, zip, lat, lon)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (DEPOT["nom"], DEPOT["num"], DEPOT["rue"], DEPOT["ville"], DEPOT["zip_code"], lat, lon))
    conn.commit()
    conn.close()
    print(f"* Dépôt '{DEPOT["nom"]}' ajouté : {lat}, {lon}")

from geopy.distance import geodesic

def capacity_clusters(points, capacity=6, max_distance_km=30):
    remaining = points.copy()
    clusters = []

    while remaining:
        seed = remaining.pop(0)
        cluster = [seed]

        # Points restants triés par distance au seed
        sorted_points = sorted(remaining, key=lambda p: geodesic((seed[1], seed[2]), (p[1], p[2])).km)

        for candidate in sorted_points:
            if len(cluster) >= capacity:
                break
            distance = geodesic((seed[1], seed[2]), (candidate[1], candidate[2])).km
            if distance <= max_distance_km:
                cluster.append(candidate)
                remaining.remove(candidate)

        clusters.append(cluster)

    return clusters

##########################################

def plan_clusters(db_path=DB_PATH):
    print("TSP resolving...")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Récupérer le dépôt
    c.execute("SELECT lat, lon FROM depots LIMIT 1")
    depot = c.fetchone()
    if not depot:
        print("/!\\ Aucun dépôt trouvé.")
        return
    depot_lat, depot_lon = depot

    # Récupérer les clusters
    c.execute("""
        SELECT DISTINCT cluster_name FROM clusters
    """)
    cluster_names = [row[0] for row in c.fetchall()]

    for cluster_name in cluster_names:
        # Récupérer les RDV du cluster
        c.execute("""
            SELECT a.id, l.lat, l.lon
            FROM clusters c
            JOIN appointments a ON c.appt_id = a.id
            JOIN locations l ON a.id = l.appt_id
            WHERE c.cluster_name = ?
        """, (cluster_name,))
        appts = c.fetchall()

        # Ajouter le dépôt au début et à la fin
        locations = [(None, depot_lat, depot_lon)] + appts + [(None, depot_lat, depot_lon)]

        # Construire la matrice de distance avec ORS
        coords = [[lon, lat] for _, lat, lon in locations]
        ors_url = "https://api.openrouteservice.org/v2/matrix/driving-car"
        headers = {"Authorization": ORS_API_KEY, "Content-Type": "application/json"}
        body = {
            "locations": coords,
            "metrics": ["duration"],
            "units": "m"
        }
        response = requests.post(ors_url, json=body, headers=headers)
        matrix = response.json()["durations"]

        # Résoudre le TSP avec OR-Tools
        tsp_size = len(locations)
        manager = pywrapcp.RoutingIndexManager(tsp_size, 1, 0)
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index, to_index):
            return int(matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)])

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # Contraindre à finir au dernier point (le dépôt)
        routing.AddDimension(
            transit_callback_index,
            0,
            100000,
            True,
            "Distance"
        )

        # Définir le retour au dépôt
        routing.SetFixedCostOfAllVehicles(0)
        # routing.AddVariableMinimizedByFinalizer(transit_callback_index)

        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)

        solution = routing.SolveWithParameters(search_parameters)

        if not solution:
            print(f"[X] Pas de solution pour {cluster_name}")
            continue

        # Enregistrer l’itinéraire
        c.execute("SELECT id FROM clusters WHERE cluster_name = ? LIMIT 1", (cluster_name,))
        cluster_id = c.fetchone()[0]

        c.execute("DELETE FROM itineraries WHERE cluster_id = ?", (cluster_id,))
        index = routing.Start(0)
        sequence = 0
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node == 0:  # Dépôt de départ, on le saute
                index = solution.Value(routing.NextVar(index))
                continue
            appt_id = locations[node][0]
            c.execute("""
                INSERT INTO itineraries (cluster_id, appt_id, sequence)
                VALUES (?, ?, ?)
            """, (cluster_id, appt_id, sequence))
            sequence += 1
            index = solution.Value(routing.NextVar(index))

        # Ajouter le retour au dépôt
        last_node = manager.IndexToNode(index)
        c.execute("""
            INSERT INTO itineraries (cluster_id, appt_id, sequence)
            VALUES (?, ?, ?)
        """, (cluster_id, locations[last_node][0], sequence))

        conn.commit()
        print(f"* Itinéraire enregistré pour {cluster_name}")

    conn.close()
    print("TSP résolution terminé")

def plot_clusters_map(db_path=DB_PATH, output_html="clusters_map.html"):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Récupérer le dépôt (on suppose 1 seul pour l’instant)
    c.execute("SELECT lat, lon FROM depots LIMIT 1")
    depot_lat, depot_lon = c.fetchone()

    # Récupérer les clusters
    c.execute("SELECT DISTINCT cluster_id FROM itineraries")
    cluster_ids = [row[0] for row in c.fetchall()]

    # Créer une carte centrée sur le dépôt
    m = folium.Map(location=[depot_lat, depot_lon], zoom_start=12)

    colors = ["red", "blue", "green", "purple", "orange", "darkred",
              "lightred", "beige", "darkblue", "darkgreen", "cadetblue",
              "darkpurple", "white", "pink", "lightblue", "lightgreen",
              "gray", "black", "lightgray"]

    for i, cluster_id in enumerate(cluster_ids):
        color = colors[i % len(colors)]

        # Récupérer l’itinéraire du cluster trié par séquence
        c.execute("""
            SELECT appt_id, sequence
            FROM itineraries
            WHERE cluster_id = ?
            ORDER BY sequence
        """, (cluster_id,))
        itin = c.fetchall()

        coords = []
        for appt_id, seq in itin:
            if appt_id is None:  # Dépôt
                lat, lon = depot_lat, depot_lon
            else:
                c.execute("SELECT lat, lon FROM locations WHERE appt_id = ?", (appt_id,))
                lat, lon = c.fetchone()
            coords.append((lat, lon))

            # Marqueurs
            folium.Marker(
                [lat, lon],
                popup=f"Cluster {cluster_id}, seq {seq}, appt {appt_id if appt_id else 'DEPOT'}",
                icon=folium.Icon(color=color, icon="info-sign")
            ).add_to(m)

        # Tracer le chemin (Polyline)
        folium.PolyLine(coords, color=color, weight=3, opacity=0.7).add_to(m)

    conn.close()
    m.save(output_html)
    print(f"Carte générée : {output_html}")

##########################################

if __name__ == "__main__":
    print("Launching Agendix.. \n")
    
    # initialisation
    init_db()
    insert_depot()

    # insérer les données tests -> appointments
    insert_test_appointments()

    # convertion en lat,lon -> locations
    geocode_appointments()

    # regroupement les points par proximité -> clusters
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT a.id, l.lat, l.lon
        FROM appointments a
        JOIN locations l ON a.id = l.appt_id
    """)
    points = c.fetchall()   # [(appt_id, lat, lon), ...]
    conn.close()
    clusters = capacity_clusters(points, capacity=6)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM clusters;")
    for i, cluster in enumerate(clusters, start=1):
        for appt_id, _, _ in cluster:
            c.execute("""
                INSERT INTO clusters (cluster_name, appt_id)
                VALUES (?, ?)
            """, (f"Cluster {i}", appt_id))
    conn.commit()
    conn.close()
    print("* clusters terminés et enregistrés dans clusters")

    # Planification TSP -> itineraire
    plan_clusters()

    # Génération de la carte interactive avec Folium
    plot_clusters_map()
