import sqlite3
import requests
from datetime import datetime, date, timedelta
from ortools.constraint_solver import routing_enums_pb2, pywrapcp


def TSP(db_path, API_key, start_hour="08:00", default_visit=60, ortools_time_limit_s=10, verbose=True):
    """
    Résout le TSP pour chaque cluster de la base SQLite.
    Ajout de robustesse sur la vérification des coordonnées et l'appel ORS.
    """
    def ors_matrix(coords, api_key, cluster_name="(unknown)"):
        """Wrapper robuste pour l'appel ORS Matrix."""
        ors_url = "https://api.openrouteservice.org/v2/matrix/driving-car"
        headers = {"Authorization": api_key, "Content-Type": "application/json"}
        body = {"locations": coords, "metrics": ["duration", "distance"], "units": "m"}

        try:
            resp = requests.post(ors_url, json=body, headers=headers, timeout=30)
        except requests.exceptions.Timeout:
            print(f"[X] ORS timeout pour {cluster_name}")
            return None
        except Exception as e:
            print(f"[X] Erreur ORS ({cluster_name}): {e}")
            return None

        if not resp.ok:
            print(f"[X] ORS HTTP {resp.status_code} pour {cluster_name} : {resp.text[:200]}")
            return None

        try:
            data = resp.json()
        except Exception as e:
            print(f"[X] Réponse ORS invalide ({cluster_name}): {e}")
            return None

        if "durations" not in data or "distances" not in data:
            print(f"[X] ORS a renvoyé un JSON sans matrices ({cluster_name})")
            return None

        return data

    # --- Connexion DB ---
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # --- Dépôt ---
    c.execute("SELECT lat, lon FROM depots LIMIT 1")
    depot = c.fetchone()
    if not depot:
        print("/!\\ Aucun dépôt trouvé.")
        conn.close()
        return
    depot_lat, depot_lon = depot

    # --- Détection de la colonne de durée ---
    c.execute("PRAGMA table_info(appointments)")
    appt_cols = [row[1] for row in c.fetchall()]
    duration_col = next((col for col in ("duration_visit", "duration", "visit_duration", "service_duration") if col in appt_cols), None)

    # --- Récupération des clusters ---
    c.execute("SELECT DISTINCT cluster_name FROM clusters")
    cluster_names = [r[0] for r in c.fetchall()]

    # --- Heure de départ ---
    try:
        start_dt_time = datetime.strptime(start_hour, "%H:%M").time()
    except Exception:
        start_dt_time = datetime.strptime("08:00", "%H:%M").time()
    start_dt_base = datetime.combine(date.today(), start_dt_time)

    # --- Boucle clusters ---
    for cluster_name in cluster_names:
        if verbose:
            print(f"\n--- Traitement {cluster_name} ---")

        # Récupération des RDV du cluster
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
            print(f"[!] Aucun RDV pour {cluster_name}, ignoré.")
            continue

        # Construction des points
        appts = [(r[0], r[1], r[2], int(r[3])) for r in rows]
        locations = [(None, depot_lat, depot_lon, 0)] + appts + [(None, depot_lat, depot_lon, 0)]

        # Filtrage des coordonnées invalides
        print(f"--- Diagnostic des coordonnées pour {cluster_name} ---")
        for (appt_id, lat, lon, dur) in locations:
            status = "OK"
            if lat is None or lon is None:
                status = "❌ None"
            elif not (-90 <= lat <= 90):
                status = f"❌ lat hors limite ({lat})"
            elif not (-180 <= lon <= 180):
                status = f"❌ lon hors limite ({lon})"
            elif lat == 0 and lon == 0:
                status = "⚠️ lat/lon = 0 (géocodage manquant)"
            print(f"id={appt_id}, lat={lat}, lon={lon}, {status}")

        filtered_locations = []
        for (appt_id, lat, lon, dur) in locations:
            if (
                isinstance(lat, (float, int)) and isinstance(lon, (float, int))
                and -90 <= lat <= 90 and -180 <= lon <= 180
            ):
                filtered_locations.append((appt_id, lat, lon, dur))
            else:
                print(f"[!] Coordonnée invalide ignorée : id={appt_id}, lat={lat}, lon={lon}")

        if len(filtered_locations) < 3:
            print(f"[!] Cluster {cluster_name} ignoré : trop peu de points valides ({len(filtered_locations)})")
            continue

        # Préparer coords pour ORS
        coords = [[lon, lat] for (_, lat, lon, _) in filtered_locations]
        if verbose:
            print(f"  {len(coords)} points à envoyer à ORS")

        # Récupérer la matrice ORS
        data = ors_matrix(coords, API_key, cluster_name)
        if not data:
            print(f"[X] Échec ORS pour {cluster_name}, passage au suivant.")
            continue

        matrix_time = data["durations"]
        matrix_dist = data["distances"]

        # --- OR-Tools ---
        size = len(filtered_locations)
        manager = pywrapcp.RoutingIndexManager(size, 1, 0)
        routing = pywrapcp.RoutingModel(manager)

        def time_callback(from_index, to_index):
            f, t = manager.IndexToNode(from_index), manager.IndexToNode(to_index)
            return int(matrix_time[f][t])

        transit_callback_index = routing.RegisterTransitCallback(time_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
        routing.AddDimension(transit_callback_index, 0, 10**9, True, "Time")

        search_params = pywrapcp.DefaultRoutingSearchParameters()
        search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        search_params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        search_params.time_limit.FromSeconds(ortools_time_limit_s)

        solution = routing.SolveWithParameters(search_params)
        if not solution:
            print(f"[X] OR-Tools n’a pas trouvé de solution pour {cluster_name}")
            continue

        # --- Récupérer cluster_id ---
        c.execute("SELECT id FROM clusters WHERE cluster_name = ? LIMIT 1", (cluster_name,))
        row = c.fetchone()
        if not row:
            print(f"[X] cluster_id introuvable pour {cluster_name}")
            continue
        cluster_id = row[0]
        c.execute("DELETE FROM itineraries WHERE cluster_id = ?", (cluster_id,))

        # --- Parcours de la solution ---
        index = routing.Start(0)
        prev_node = 0
        seq = 0
        depart_dt = start_dt_base
        inserts = []

        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node == 0:
                index = solution.Value(routing.NextVar(index))
                continue

            appt_id = filtered_locations[node][0]
            visit_dur = filtered_locations[node][3]
            travel_s = matrix_time[prev_node][node]
            dist_m = matrix_dist[prev_node][node]

            arrive_dt = depart_dt + timedelta(seconds=travel_s)
            depart_next = arrive_dt + timedelta(minutes=visit_dur)

            inserts.append((
                cluster_id,
                appt_id,
                seq,
                depart_dt.isoformat(timespec="seconds"),
                arrive_dt.isoformat(timespec="seconds"),
                visit_dur,
                int(travel_s // 60),
                dist_m / 1000.0,
            ))

            prev_node = node
            depart_dt = depart_next
            seq += 1
            index = solution.Value(routing.NextVar(index))

        # Dernier segment retour au dépôt
        last_node = manager.IndexToNode(index)
        travel_s = matrix_time[prev_node][last_node]
        dist_m = matrix_dist[prev_node][last_node]
        arrive_dt = depart_dt + timedelta(seconds=travel_s)

        inserts.append((
            cluster_id,
            None,
            seq,
            depart_dt.isoformat(timespec="seconds"),
            arrive_dt.isoformat(timespec="seconds"),
            0,
            int(travel_s // 60),
            dist_m / 1000.0,
        ))

        # --- Insertion ---
        c.executemany("""
            INSERT INTO itineraries
            (cluster_id, appt_id, sequence, depart_time, arrive_time,
             duration_visit, travel_time_prev, distance_prev)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, inserts)
        conn.commit()

        print(f"✅ Itinéraire enregistré pour {cluster_name} ({len(inserts)} étapes)")

    conn.close()
    print("\nTSP résolution terminée.")
