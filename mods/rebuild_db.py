import sqlite3,os
from config import SAMPLES,DEPOT1, TABLES_SQL

# --- Fonctions ---
def rebuild_database(db_path: str):
    """Supprime et recrée toutes les tables selon TABLES_SQL."""
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"🧹 Ancienne base supprimée : {db_path}")

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Créer toutes les tables
    for name, sql in TABLES_SQL.items():
        c.execute(sql)
        print(f"✅ Table créée : {name}")
    # --- Insertion dépôt ---
    c.execute("""
        INSERT INTO depots (nom, num, rue, ville, zip)
        VALUES (?, ?, ?, ?, ?)
    """, (DEPOT1["nom"], DEPOT1["num"], DEPOT1["rue"], DEPOT1["ville"], DEPOT1["zip"]))
    print("🏠 Dépôt inséré.")

    # --- Insertion clients + RDV ---
    for nom, num, rue, ville, zip_code, type_ in SAMPLES:
        address = f"{num} {rue}, {ville} {zip_code}"

        # Vérifier si le client existe déjà
        c.execute("SELECT id FROM clients WHERE nom = ? AND address = ?", (nom, address))
        result = c.fetchone()
        if result:
            client_id = result[0]
        else:
            c.execute("INSERT INTO clients (nom, address) VALUES (?, ?)", (nom, address))
            client_id = c.lastrowid

        # Créer le RDV
        c.execute("""
            INSERT INTO appointments (client_id, num, rue, ville, zip, type)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (client_id, num, rue, ville, zip_code, type_))

    conn.commit()
    conn.close()
    print("🎯 Base de test reconstruite avec succès !")