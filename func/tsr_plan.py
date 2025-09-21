import sqlite3,requests
from ortools.constraint_solver import routing_enums_pb2, pywrapcp


def plan_clusters(db_path, API_key):
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
        headers = {"Authorization": API_key, "Content-Type": "application/json"}
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