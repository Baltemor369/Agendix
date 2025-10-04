from datetime import datetime

# fonction utilitaire pour formater
def fmt_time(t):
    if not t:
        return "-"
    try:
        # si déjà une string style "2025-10-03T08:54:52"
        dt = datetime.fromisoformat(t)
        return dt.strftime("%H:%M")  # ou "%d/%m %H:%M"
    except Exception:
        return str(t)  # fallback