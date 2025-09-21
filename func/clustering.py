import sqlite3
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

def clustering(db_path, capacity=6):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        SELECT a.id, l.lat, l.lon
        FROM appointments a
        JOIN locations l ON a.id = l.appt_id
    """)
    points = c.fetchall()   # [(appt_id, lat, lon), ...]
    conn.close()
    clusters = capacity_clusters(points, capacity)
    conn = sqlite3.connect(db_path)
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