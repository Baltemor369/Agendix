# 📌 README – Agendix Routing

## 🚀 Présentation

Ce projet permet de **planifier et visualiser des itinéraires optimisés** pour des rendez-vous clients à partir d’une base SQLite.  
L’application :  
- Regroupe des rendez-vous en **clusters**.  
- Calcule des itinéraires optimisés (TSP) à partir du **dépôt**.  
- Stocke la séquence dans une table `itineraries`.  
- Génère une **carte interactive Folium** montrant le trajet réel en voiture, cluster par cluster, grâce à l’API **OpenRouteService (ORS)**.  

---

## ✨ Fonctionnalités

- Récupération des rendez-vous par cluster depuis la base.  
- Optimisation des tournées avec OR-Tools (TSP).  
- Sauvegarde des itinéraires ordonnés en base (`itineraries`).  
- Visualisation des trajets routiers :  
  - Dépôt marqué en début et fin d’itinéraire.  
  - Marqueurs pour chaque rendez-vous avec popup d’info (cluster, séquence, id).  
  - Lignes de trajets routiers en **voiture** (ORS Directions).  
  - **Couleur différente par cluster** pour la lisibilité.  

---

## 🛠️ Prérequis

- Python 3.9+  
- SQLite3  
- Clé API [OpenRouteService](https://openrouteservice.org/sign-up/)  
- Librairies Python :  
  ```bash
  pip install sqlite3 folium requests ortools openrouteservice
  ```

---

## 📂 Base de données

La base SQLite doit contenir :  

- **depots**  
  ```sql
  CREATE TABLE depots (
      id INTEGER PRIMARY KEY,
      lat REAL,
      lon REAL
  );
  ```

- **appointments**  
  (tes rendez-vous)

- **locations**  
  (coordonnées liées aux `appointments`)  
  ```sql
  CREATE TABLE locations (
      id INTEGER PRIMARY KEY,
      appt_id INTEGER,
      lat REAL,
      lon REAL
  );
  ```

- **clusters**  
  (groupement de rendez-vous par cluster_name)

- **itineraries**  
  (résultat du TSP + ordre des RDV)  
  ```sql
  CREATE TABLE itineraries (
      id INTEGER PRIMARY KEY,
      cluster_id INTEGER,
      appt_id INTEGER, -- NULL = dépôt
      sequence INTEGER
  );
  ```

---

## ⚙️ Configuration

Dans ton fichier Python :  

```python
DB_PATH = "chemin/vers/ta_base.sqlite"
ORS_API_KEY = "TA_CLE_API"
```

---

## ▶️ Utilisation

### 1. Générer les itinéraires optimisés
```python
plan_clusters(DB_PATH)
```
👉 Cela remplit la table `itineraries` avec la séquence optimisée pour chaque cluster.

### 2. Générer la carte interactive
```python
plot_clusters_map_v2(DB_PATH)
```

👉 Cela crée un fichier `clusters_map_routes.html` avec :  
- Les trajets routiers réels en voiture entre dépôt et RDV.  
- Des couleurs différentes par cluster.  
- Des marqueurs cliquables.  

---

## 🗺️ Exemple visuel attendu

- **Markers bleus/verts/rouges** → points du cluster.  
- **Dépôt** visible au départ et à l’arrivée (appt_id = NULL).  
- **Lignes colorées** reliant les rendez-vous via les routes routières (pas vol d’oiseau).  

---

## 🚧 Limitations actuelles

- L’API ORS a une limite de **50 appels/minute** → le code fait un appel par segment (robuste, mais peut ralentir si beaucoup de RDV).  
- Multi-dépôts non encore géré.  
- Couleur aléatoire par cluster (possible de stabiliser avec un mapping `cluster_id → couleur fixe`).  

---

## 📌 Prochaines améliorations possibles

- Export en PDF ou Excel des itinéraires.  
- Ajout d’une UI (Flask/Django) pour gérer les RDV.  
- Multi-dépôts et gestion des véhicules.  
- Gestion offline avec OSRM en local.  
