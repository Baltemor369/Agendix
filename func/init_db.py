import sqlite3
from pathlib import Path

def init_db(db_path):
    # Supprime l'ancienne BDD et ne crée que 2 tables
    db_file = Path(db_path)
    if db_file.exists():
        db_file.unlink()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.executescript("""
    PRAGMA foreign_keys = ON;
    
    CREATE TABLE appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client TEXT NOT NULL,
        num TEXT,
        rue TEXT,
        ville TEXT,
        zip TEXT,
        type TEXT
    );

    CREATE TABLE locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        appt_id INTEGER NOT NULL,
        address TEXT,
        lat REAL,
        lon REAL,
        FOREIGN KEY(appt_id) REFERENCES appointments(id) ON DELETE CASCADE
    );

    CREATE TABLE clusters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cluster_name TEXT,
        appt_id INTEGER NOT NULL,
        assign_day INTEGER,
        FOREIGN KEY(appt_id) REFERENCES appointments(id) ON DELETE CASCADE
    );
                    
    CREATE TABLE travelers (
        id    INTEGER PRIMARY KEY AUTOINCREMENT,
        nom   TEXT    NOT NULL,
        num   TEXT,
        rue   TEXT,
        ville TEXT,
        zip   TEXT,
        lat   REAL,
        lon   REAL
    );
                    
    CREATE TABLE IF NOT EXISTS itineraries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cluster_id INTEGER NOT NULL,
        appt_id INTEGER,
        sequence INTEGER NOT NULL,
        depart_time TEXT,
        arrive_time TEXT,
        duration_visit INTEGER,
        travel_time_prev INTEGER,
        FOREIGN KEY(cluster_id) REFERENCES clusters(id),
        FOREIGN KEY(appt_id) REFERENCES appointments(id)
    );

    """)
    conn.commit()
    conn.close()
    print("* BDD initialisée (appointments + locations)")