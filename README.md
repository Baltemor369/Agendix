Formulaire client → Stockage → Géocodage → Clustering → Matrice de distances 
→ Optimisation par jour → Génération planning + Carte

1. Entrée des données
Formulaire client (adresse complète, type de RDV, éventuellement durée)
Stockage (mail → import, ou base de données directe)
Point de départ (domicile/bureau défini dans la config)

2. Pré-traitement
Géocodage (conversion "N° rue, ville, CP" → latitude/longitude via API OpenRouteService ou équivalent)
Nettoyage des données (ex : adresses manquantes, doublons)
Normalisation du type de RDV (si besoin, pour gérer la durée standard)

3. Regroupement géographique
Clustering spatial (regrouper les RDV proches)
Méthodes possibles :
K-Means (nombre de clusters = nb de jours disponibles)
DBSCAN (groupes naturels selon distance)
Simple heuristique (découpage par zones : Nancy, Metz, Épinal, etc.)
Résultat attendu : chaque cluster correspond à une journée de travail.

4. Calcul des trajets
Matrice de distance/temps :
Calculer tous les temps de trajet entre :
Point de départ ↔ RDV
RDV ↔ RDV
RDV ↔ retour au départ
Utiliser OpenRouteService Matrix API.

5. Optimisation intra-cluster
Pour chaque cluster (jour de RDV) :
Résoudre un TSP (Traveling Salesman Problem) avec OR-Tools → ordre optimal des RDV.
Ajouter contraintes horaires :
Durée fixe du RDV (ex. 1h ou selon type).
Plage horaire journalière (9h–18h, pause midi).
Vérifier que le total (trajet + RDV) tient dans la journée.
Si ça dépasse : déplacer un RDV au cluster suivant.

6. Sortie (planning)
Tableau :
Jour 1 → RDV 1 (10h00), RDV 2 (11h30)…
Jour 2 → …
Carte interactive :
Points (RDV) + itinéraire du jour.
Option : export (Google Calendar, PDF, Excel).

depots : 8 Gr Grande Rue, 55210 Avillers-Sainte-Croix