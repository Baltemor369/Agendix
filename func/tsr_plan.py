import sqlite3
import requests
from datetime import datetime, date, timedelta
from ortools.constraint_solver import routing_enums_pb2, pywrapcp


def TSP(db_path, API_key, start_hour="08:00", default_visit=60, ortools_time_limit_s=10, verbose=True):
    """
    Pour chaque cluster (cluster_name dans table clusters) :
      - construit une matrice ORS (durations + distances),
      - résout un TSP avec OR-Tools,
      - calcule arrive/depart/durée_visite/travel_time_prev/distance_prev,
      - écrit l'itinéraire dans la table itineraries (remplace les lignes existantes pour le cluster).
    Paramètres :
      - start_hour : heure de départ (HH:MM) utilisée comme date d'aujourd'hui + heure
      - default_visit : durée par défaut en minutes si appointments n'a pas de durée spécifique
      - ortools_time_limit_s : temps max (sec) pour la recherche d'amélioration OR-Tools
    """
    if verbose:
        print("TSP resolving...")

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Dépôt
    c.execute("SELECT lat, lon FROM depots LIMIT 1")
    depot = c.fetchone()
    if not depot:
        print("/!\\ Aucun dépôt trouvé.")
        conn.close()
        return
    depot_lat, depot_lon = depot

    # Détecter colonne de durée éventuelle dans appointments
    c.execute("PRAGMA table_info(appointments)")
    appt_cols = [row[1] for row in c.fetchall()]
    duration_col = None
    for candidate in ("duration_visit", "duration", "visit_duration", "service_duration"):
        if candidate in appt_cols:
            duration_col = candidate
            break

    # Récupérer les clusters distincts
    c.execute("SELECT DISTINCT cluster_name FROM clusters")
    cluster_rows = c.fetchall()
    cluster_names = [r[0] for r in cluster_rows]

    # Préparer start datetime (aujourd'hui + heure)
    try:
        start_dt_time = datetime.strptime(start_hour, "%H:%M").time()
    except Exception:
        start_dt_time = datetime.strptime("08:00", "%H:%M").time()
    start_dt_base = datetime.combine(date.today(), start_dt_time)

    for cluster_name in cluster_names:
        if verbose:
            print(f"\n--- Traitement {cluster_name} ---")

        # Récupérer RDV du cluster (avec éventuelle durée par RDV)
        if duration_col:
            c.execute(f"""
                SELECT a.id, l.lat, l.lon, COALESCE(a.{duration_col}, ?) 
                FROM clusters cl
                JOIN appointments a ON cl.appt_id = a.id
                JOIN locations l ON a.id = l.appt_id
                WHERE cl.cluster_name = ?
            """, (default_visit, cluster_name))
        else:
            c.execute("""
                SELECT a.id, l.lat, l.lon, ?
                FROM clusters cl
                JOIN appointments a ON cl.appt_id = a.id
                JOIN locations l ON a.id = l.appt_id
                WHERE cl.cluster_name = ?
            """, (default_visit, cluster_name))

        rows = c.fetchall()
        if not rows:
            if verbose:
                print(f"[!] Pas de RDV pour {cluster_name}, skip.")
            continue

        # Construire liste locations : dépôt (start), rdvs..., dépôt (end)
        # Chaque entrée : (appt_id_or_None, lat, lon, duration_minutes)
        appts = [(r[0], r[1], r[2], int(r[3])) for r in rows]
        locations = [(None, depot_lat, depot_lon, 0)] + appts + [(None, depot_lat, depot_lon, 0)]

        # Préparer coordonnées ORS en [lon, lat]
        coords = [[lon, lat] for (_, lat, lon, _) in locations]

        # Appel ORS Matrix (durations en secondes, distances en mètres)
        ors_url = "https://api.openrouteservice.org/v2/matrix/driving-car"
        headers = {"Authorization": API_key, "Content-Type": "application/json"}
        body = {"locations": coords, "metrics": ["duration", "distance"], "units": "m"}

        try:
            resp = requests.post(ors_url, json=body, headers=headers, timeout=30)
        except Exception as e:
            print(f"[X] Erreur requête ORS pour {cluster_name} : {e}")
            continue

        if not resp.ok:
            print(f"[X] ORS erreur HTTP {resp.status_code} pour {cluster_name} : {resp.text}")
            continue

        data = resp.json()
        matrix_time = data.get("durations")
        matrix_dist = data.get("distances")
        if not matrix_time or not matrix_dist:
            print(f"[X] ORS response invalide pour {cluster_name}: {data}")
            continue

        # OR-Tools setup (TSP)
        size = len(locations)
        manager = pywrapcp.RoutingIndexManager(size, 1, 0)
        routing = pywrapcp.RoutingModel(manager)

        def time_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            # ORS donne des floats en secondes; OR-Tools attend int
            return int(matrix_time[from_node][to_node])

        transit_callback_index = routing.RegisterTransitCallback(time_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # Dimension (cap large pour ne pas contraindre)
        routing.AddDimension(transit_callback_index, 0, 10**9, True, "Time")

        # Search parameters : solution initiale rapide puis amélioration guidée
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        # Activer métaheuristique pour améliorer si on a du temps
        search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        search_parameters.time_limit.FromSeconds(ortools_time_limit_s)

        solution = routing.SolveWithParameters(search_parameters)
        if solution is None:
            print(f"[X] OR-Tools n'a pas trouvé de solution pour {cluster_name}")
            continue

        # Récupérer cluster_id (pour purge inserts). On prend le premier id associé au nom.
        c.execute("SELECT id FROM clusters WHERE cluster_name = ? LIMIT 1", (cluster_name,))
        res = c.fetchone()
        if not res:
            print(f"[X] cluster_id introuvable pour {cluster_name}")
            continue
        cluster_id = res[0]
        c.execute("DELETE FROM itineraries WHERE cluster_id = ?", (cluster_id,))

        # Parcourir la solution et construire les inserts en batch
        index = routing.Start(0)
        prev_node = 0
        sequence = 0
        depart_dt = start_dt_base
        inserts = []

        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            # sauter dépôt de départ
            if node == 0:
                index = solution.Value(routing.NextVar(index))
                continue

            appt_id = locations[node][0]
            appt_duration_min = locations[node][3]  # minutes

            # travel from prev_node -> node
            travel_secs = matrix_time[prev_node][node]
            distance_m = matrix_dist[prev_node][node]

            arrive_dt = depart_dt + timedelta(seconds=int(travel_secs))
            duration_visit = int(appt_duration_min)
            depart_dt_next = arrive_dt + timedelta(minutes=duration_visit)

            inserts.append((
                cluster_id,
                appt_id,
                sequence,
                depart_dt.isoformat(timespec='seconds'),
                arrive_dt.isoformat(timespec='seconds'),
                duration_visit,
                int(travel_secs // 60),           # minutes
                float(distance_m) / 1000.0        # km
            ))

            # maj pour next
            prev_node = node
            depart_dt = depart_dt_next
            sequence += 1
            index = solution.Value(routing.NextVar(index))

        # retour au dépôt (dernier segment)
        last_node = manager.IndexToNode(index)  # normalement depot index (len-1)
        travel_secs = matrix_time[prev_node][last_node]
        distance_m = matrix_dist[prev_node][last_node]
        arrive_dt = depart_dt + timedelta(seconds=int(travel_secs))
        inserts.append((
            cluster_id,
            locations[last_node][0],  # None pour dépôt
            sequence,
            depart_dt.isoformat(timespec='seconds'),
            arrive_dt.isoformat(timespec='seconds'),
            0,                             # duration_visit pour dépôt
            int(travel_secs // 60),
            float(distance_m) / 1000.0
        ))

        # Effectuer inserts en batch
        c.executemany("""
            INSERT INTO itineraries
            (cluster_id, appt_id, sequence, depart_time, arrive_time,
             duration_visit, travel_time_prev, distance_prev)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, inserts)
        conn.commit()

        if verbose:
            print(f"* Itinéraire enregistré pour {cluster_name} ({len(inserts)} étapes)")

    conn.close()
    if verbose:
        print("TSP résolution terminé")
