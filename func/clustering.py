import sqlite3
from geopy.distance import geodesic

def clustering(db_path, capacity=6, max_distance_km=30, verbose=True):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Récupérer le dépôt
    c.execute("SELECT lat, lon FROM depots LIMIT 1")
    depot = c.fetchone()
    if not depot:
        print("[X] Aucun dépôt trouvé dans la table depots")
        conn.close()
        return
    depot_lat, depot_lon = depot

    # Récupérer les rendez-vous
    c.execute("""
        SELECT a.id, l.lat, l.lon
        FROM appointments a
        JOIN locations l ON a.id = l.appt_id
    """)
    points = c.fetchall()  # [(appt_id, lat, lon), ...]

    if not points:
        print("[X] Aucun rendez-vous trouvé")
        conn.close()
        return

    # Calculer distance au dépôt
    points_with_dist = [
        (appt_id, lat, lon, geodesic((depot_lat, depot_lon), (lat, lon)).km)
        for appt_id, lat, lon in points
    ]

    # Trier par distance au dépôt
    points_with_dist.sort(key=lambda x: x[3])

    # Supprimer anciens clusters
    c.execute("DELETE FROM clusters;")

     # Créer les clusters sous forme de dictionnaire
    clusters = {}
    current_cluster = []
    current_cluster_name = 1
    prev_point = None

    for appt_id, lat, lon, dist in points_with_dist:
        if prev_point is not None:
            dist_to_prev = geodesic((prev_point[1], prev_point[2]), (lat, lon)).km
            if dist_to_prev > max_distance_km or len(current_cluster) >= capacity:
                if current_cluster:
                    clusters[f"Jour {current_cluster_name}"] = current_cluster
                    current_cluster_name += 1
                    current_cluster = []

        current_cluster.append((appt_id, lat, lon, dist))
        prev_point = (appt_id, lat, lon, dist)

    # Ajouter le dernier cluster
    if current_cluster:
        clusters[f"Jour {current_cluster_name}"] = current_cluster

    # Sauvegarde en DB et affichage
    for cluster_name, cluster_points in clusters.items():
        if verbose:
            print(f"\n{cluster_name} → {len(cluster_points)} RDV(s)")
            for appt_id, lat, lon, dist in cluster_points:
                print(f"  RDV {appt_id} | {dist:.2f} km du dépôt | coords: ({lat:.5f}, {lon:.5f})")
        for appt_id, lat, lon, dist in cluster_points:
            c.execute("""
                INSERT INTO clusters (cluster_name, appt_id)
                VALUES (?, ?)
            """, (cluster_name, appt_id))

    conn.commit()
    conn.close()
    print(f"* Clustering terminé → {len(clusters)} paquets créés")
