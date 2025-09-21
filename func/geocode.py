import sqlite3,requests


def geocode_address(address, API_key):
    url = "https://api.openrouteservice.org/geocode/search"
    params = {
        "api_key": API_key,
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

def geocode_appointments(db_path, api_key):
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
        lat, lon = geocode_address(full_address, api_key)

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