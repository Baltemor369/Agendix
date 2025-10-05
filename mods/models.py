from dataclasses import dataclass
from typing import Optional
from mods.ORM import BaseModel

# 📌 Clients
@dataclass
class Client(BaseModel):
    table: str = "clients"
    id: Optional[int] = None
    nom: str = ""
    address: Optional[str] = None
    phone: Optional[str] = None
    mail: Optional[str] = None
    notes: Optional[str] = None


# 📌 Dépôts
@dataclass
class Depot(BaseModel):
    table: str = "depots"
    id: Optional[int] = None
    nom: str = ""
    num: Optional[str] = None
    rue: Optional[str] = None
    ville: Optional[str] = None
    zip: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    notes: Optional[str] = None


# 📌 RDV
@dataclass
class Appointment(BaseModel):
    table: str = "appointments"
    id: Optional[int] = None
    client_id: int = 0
    num: Optional[str] = None
    rue: Optional[str] = None
    ville: Optional[str] = None
    zip: Optional[str] = None
    type: Optional[str] = None
    fixe: int = 0
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    duration: int = 60
    notes: Optional[str] = None


# 📌 Locations
@dataclass
class Location(BaseModel):
    table: str = "locations"
    id: Optional[int] = None
    appt_id: int = 0
    address: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


# 📌 Clusters
@dataclass
class Cluster(BaseModel):
    table: str = "clusters"
    id: Optional[int] = None
    cluster_name: str = ""
    appt_id: int = 0


# 📌 Travels
@dataclass
class Travel(BaseModel):
    table: str = "travels"
    id: Optional[int] = None
    origin_appt_id: Optional[int] = None
    dest_appt_id: Optional[int] = None
    cluster_id: Optional[int] = None
    depart_time: Optional[str] = None
    arrive_time: Optional[str] = None
    travel_time: Optional[int] = None
    distance: Optional[float] = None


# 📌 Itineraries
@dataclass
class Itinerary(BaseModel):
    table: str = "itineraries"
    id: Optional[int] = None
    cluster_id: int = 0
    appt_id: Optional[int] = None
    sequence: int = 0
    depart_time: Optional[str] = None
    arrive_time: Optional[str] = None
    duration_visit: Optional[int] = None
    travel_time_prev: Optional[int] = None
    distance_prev: Optional[float] = None
