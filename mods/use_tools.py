from datetime import datetime
try:
    from zoneinfo import ZoneInfo
    PARIS = ZoneInfo("Europe/Paris")
except Exception:
    PARIS = None

def fmt_time_iso(iso_str: str | None, show_date: bool = False) -> str:
    """
    Transforme un ISO datetime ('2025-10-06T08:00:00' ou '2025-10-06T08:00:00Z' ou avec offset)
    en affichage lisible.
    - show_date=False -> '08:00'
    - show_date=True  -> '06/10 08:00'
    Retourne '-' si iso_str est None ou invalide.
    """
    if not iso_str:
        return "-"

    s = str(iso_str)
    # fromisoformat ne supporte pas 'Z', on le remplace par +00:00
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        # fallback: on renvoie la chaîne brute si on n'arrive pas à parser
        return iso_str

    # Si on a zoneinfo, normaliser vers Europe/Paris pour l'affichage.
    # Si datetime est naïf, on l'interprète comme heure locale Europe/Paris.
    if PARIS:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=PARIS)
        else:
            dt = dt.astimezone(PARIS)

    return dt.strftime("%d/%m %H:%M") if show_date else dt.strftime("%H:%M")
