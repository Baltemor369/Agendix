# Agendix/pages/5_Planning.py
import streamlit as st
from streamlit_calendar import calendar
import sqlite3,os
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv(dotenv_path=".secret")
DB_PATH = os.getenv("DB_PATH")

st.set_page_config(page_title="📅 Planning", layout="wide")

st.title("📅 Planning des rendez-vous")


# --- Fonctions BDD ---
def get_appointments():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, title, start_time, end_time FROM appointments")
    rows = cur.fetchall()
    conn.close()

    events = []
    for r in rows:
        events.append({
            "id": r[0],
            "title": r[1],
            "start": r[2],
            "end": r[3],
        })
    return events


def add_appointment(title, start, end):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO appointments (title, start_time, end_time) VALUES (?, ?, ?)", (title, start, end))
    conn.commit()
    conn.close()


def update_appointment(id, start, end):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE appointments SET start_time=?, end_time=? WHERE id=?", (start, end, id))
    conn.commit()
    conn.close()


def delete_appointment(id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM appointments WHERE id=?", (id,))
    conn.commit()
    conn.close()


# --- Affichage du calendrier ---
st.subheader("Vue calendrier")

events = get_appointments()

state = calendar(
    events=events,
    options={
        "editable": True,
        "initialView": "timeGridWeek",
        "locale": "fr",
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay,listWeek"
        },
    },
    key="calendar",
)

# --- Événements du calendrier ---
if state.get("eventClick"):
    event = state["eventClick"]["event"]
    st.info(f"Événement sélectionné : {event['title']}")
    if st.button("🗑 Supprimer cet événement"):
        delete_appointment(event["id"])
        st.rerun()

if state.get("eventChange"):
    event = state["eventChange"]["event"]
    update_appointment(event["id"], event["start"], event["end"])
    st.success("Événement mis à jour !")
    st.rerun()

# --- Ajout manuel ---
with st.expander("➕ Ajouter un nouveau rendez-vous"):
    with st.form("new_event"):
        title = st.text_input("Titre du rendez-vous")
        start = st.datetime_input("Début", datetime.now())
        end = st.datetime_input("Fin", datetime.now() + timedelta(hours=1))
        if st.form_submit_button("Ajouter"):
            add_appointment(title, start.isoformat(), end.isoformat())
            st.success("Rendez-vous ajouté ✅")
            st.rerun()
