import sqlite3, folium, requests, random

def random_color():
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))

def plot_clusters_map_v2(db_path, API_key, output_html="clusters_map_routes.html"):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Récupérer le dépôt
    c.execute("SELECT lat, lon FROM depots LIMIT 1")
    depot_lat, depot_lon = c.fetchone()

    # Récupérer les clusters
    c.execute("SELECT DISTINCT cluster_id FROM itineraries")
    cluster_ids = [row[0] for row in c.fetchall()]

    m = folium.Map(location=[depot_lat, depot_lon], zoom_start=12)

    for cluster_id in cluster_ids:
        # Itinéraire trié
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
            coords.append([lon, lat])  # ORS attend [lon, lat]

            # Ajouter un marker
            folium.Marker(
                [lat, lon],
                popup=f"Cluster {cluster_id}, seq {seq}, appt {appt_id if appt_id else 'DEPOT'}"
            ).add_to(m)

        # Requête ORS directions
        ors_url = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
        headers = {"Authorization": API_key, "Content-Type": "application/json"}
        for i in range(len(coords) - 1):
            body = {"coordinates": [coords[i], coords[i+1]]}
            resp = requests.post(ors_url, json=body, headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                if "features" in data:
                    geometry = data["features"][0]["geometry"]["coordinates"]
                    route = [(lat, lon) for lon, lat in geometry]  # inversion lon/lat
                    folium.PolyLine(route, color=random_color(), weight=3, opacity=0.7).add_to(m)
                else:
                    print(f"[!] Pas de features pour cluster {cluster_id}, étape {i}: {data}")
            else:
                print(f"[!] Erreur ORS cluster {cluster_id}, étape {i}: {resp.text}")

    conn.close()
    m.save(output_html)
    print(f"Carte générée avec trajets routiers : {output_html}")