import sqlite3,requests
from datetime import datetime,timedelta
from ortools.constraint_solver import routing_enums_pb2, pywrapcp


def plan_clusters(db_path, API_key, start_hour="08:00", default_visit=60):
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
    c.execute("""SELECT DISTINCT cluster_name FROM clusters""")
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

        # ORS matrix
        ors_url = "https://api.openrouteservice.org/v2/matrix/driving-car"
        headers = {"Authorization": API_key, "Content-Type": "application/json"}
        body = {
            "locations": coords,
            "metrics": ["duration","distance"],
            "units": "m"
        }
        response = requests.post(ors_url, json=body, headers=headers)
        data = response.json()
        matrix_time = data["durations"]
        matrix_dist = data["distances"]

        # Résoudre le TSP avec OR-Tools
        tsp_size = len(locations)
        manager = pywrapcp.RoutingIndexManager(tsp_size, 1, 0)
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index, to_index):
            return int(matrix_time[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)])

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # Contraindre à finir au dernier point (le dépôt)
        routing.AddDimension(transit_callback_index, 0, 100000, True, "Distance")
        # Définir le retour au dépôt
        routing.SetFixedCostOfAllVehicles(0)

        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)

        solution = routing.SolveWithParameters(search_parameters)

        if not solution:
            print(f"[X] Pas de solution pour {cluster_name}")
            continue
            
        # init horaires
        start_dt = datetime.strptime(start_hour, "%H:%M")
        depart_time = start_dt

        # Enregistrer l’itinéraire
        c.execute("SELECT id FROM clusters WHERE cluster_name = ? LIMIT 1", (cluster_name,))
        cluster_id = c.fetchone()[0]
        c.execute("DELETE FROM itineraries WHERE cluster_id = ?", (cluster_id,))

        index = routing.Start(0)
        sequence = 0
        prev_node = 0
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node == 0:  # Dépôt de départ, on le saute
                index = solution.Value(routing.NextVar(index))
                continue

            appt_id = locations[node][0]

            # calculs
            travel_time_prev = matrix_time[prev_node][node]  # secondes
            distance_prev = matrix_dist[prev_node][node] / 1000.0  # km
            arrive_time = depart_time + timedelta(seconds=travel_time_prev)

            # durée visite (par ex. 15 min par défaut)
            duration_visit = default_visit
            depart_time_next = arrive_time + timedelta(minutes=duration_visit)

            # insert
            c.execute("""
                INSERT INTO itineraries
                (cluster_id, appt_id, sequence, depart_time, arrive_time,
                 duration_visit, travel_time_prev, distance_prev)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cluster_id, appt_id, sequence,
                depart_time.strftime("%H:%M"), arrive_time.strftime("%H:%M"),
                duration_visit, int(travel_time_prev/60), distance_prev
            ))
            
            # maj pour prochain etape
            prev_node = node
            depart_time = depart_time_next
            sequence += 1
            index = solution.Value(routing.NextVar(index))

        # ---- Ajouter le retour au dépôt (dernier segment) ----
        last_node = manager.IndexToNode(index)  # normalement le dépôt final (index d'end)
        # calculer trajet depuis le dernier point visité vers le dépôt final
        travel_secs = matrix_time[prev_node][last_node]
        distance_m = matrix_dist[prev_node][last_node]
        arrive_dt = depart_time + timedelta(seconds=int(travel_secs))
        # pour le dépôt on laisse duration_visit 0
        c.execute("""
            INSERT INTO itineraries
            (cluster_id, appt_id, sequence, depart_time, arrive_time,
             duration_visit, travel_time_prev, distance_prev)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cluster_id,
            locations[last_node][0],  # None pour dépôt
            sequence,
            depart_time.strftime("%H:%M"), arrive_time.strftime("%H:%M"),
            0,
            int(travel_secs // 60),
            float(distance_m) / 1000.0
        ))

        conn.commit()
        print(f"* Itinéraire enregistré pour {cluster_name}")

    conn.close()
    print("TSP résolution terminé")