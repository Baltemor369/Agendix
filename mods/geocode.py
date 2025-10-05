import sqlite3,requests


def geocode_address(address, API_key, conn):
    c = conn.cursor()

    # Vérifier si déjà présent dans locations
    c.execute("SELECT lat, lon FROM locations WHERE address = ? LIMIT 1", (address,))
    row = c.fetchone()
    if row:
        return row[0], row[1]  # lat, lon

    # Sinon appel API ORS
    url = "https://api.openrouteservice.org/geocode/search"
    params = {"api_key": API_key, "text": address, "size": 1}
    response = requests.get(url, params=params)
    data = response.json()

    try:
        coords = data["features"][0]["geometry"]["coordinates"]
        lon, lat = coords
        return lat, lon
    except (KeyError, IndexError):
        return None, None


def geocode_appointments(db_path, api_key):
    print("* Mise à jour des géocodes (lat, lon)")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Ajouter la colonne address si elle n’existe pas
    try:
        c.execute("ALTER TABLE locations ADD COLUMN address TEXT")
    except sqlite3.OperationalError:
        pass  # colonne existe déjà

    # Récupérer tous les RDV
    c.execute("SELECT id, num, rue, ville, zip FROM appointments")
    appointments = c.fetchall()

    done, updated = 0, 0
    for appt_id, num, rue, ville, zip_code in appointments:
        full_address = f"{num} {rue}, {ville} {zip_code}"

        # Vérifier si déjà en base
        c.execute("SELECT address FROM locations WHERE appt_id = ?", (appt_id,))
        row = c.fetchone()

        if row:
            # Si l'adresse a changé → mettre à jour
            if row[0] != full_address:
                lat, lon = geocode_address(full_address, api_key, conn)
                if lat and lon:
                    c.execute("""
                        UPDATE locations 
                        SET address = ?, lat = ?, lon = ?
                        WHERE appt_id = ?
                    """, (full_address, lat, lon, appt_id))
                    print(f"~ Adresse mise à jour : {full_address} → {lat}, {lon}")
                    updated += 1
                else:
                    print(f"[X] Mise à jour échouée pour {full_address}")
        else:
            # Sinon → nouvel enregistrement
            lat, lon = geocode_address(full_address, api_key, conn)
            if lat and lon:
                c.execute("""
                    INSERT INTO locations (appt_id, address, lat, lon)
                    VALUES (?, ?, ?, ?)
                """, (appt_id, full_address, lat, lon))
                print(f"+ Nouvelle adresse : {full_address} → {lat}, {lon}")
                done += 1
            else:
                print(f"[X] Géocodage échoué pour {full_address}")

    conn.commit()
    conn.close()
    print(f"* {done} nouvelles adresses ajoutées, {updated} mises à jour.")
