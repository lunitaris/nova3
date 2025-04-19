import time
import asyncio
from fastapi import APIRouter
from backend.api.diagnostic import get_status_details

# Cache mémoire de statut
current_status = {
    "last_check": time.strftime("%Y-%m-%d %H:%M:%S"),
    "status": "unknown",
    "components": {},
    "latency_total_ms": None
}

router = APIRouter()

async def monitor_health(interval_seconds=30):
    """
    Tâche de fond qui met à jour le statut système à intervalles réguliers.
    """
    while True:
        try:
            details = await get_status_details()
            current_status.update(details)
            current_status["last_check"] = time.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            current_status.update({
                "status": "error",
                "components": {},
                "latency_total_ms": None,
                "last_check": time.strftime("%Y-%m-%d %H:%M:%S"),
                "error": str(e)
            })
        await asyncio.sleep(interval_seconds)

@router.get("/api/admin/status/live")
def get_cached_status():
    """
    Retourne le dernier état connu du système (instantané, rapide).
    """
    return current_status

@router.post("/api/admin/status/refresh")
async def force_refresh():
    """
    Rafraîchit immédiatement le statut système.
    """
    details = await get_status_details()
    current_status.update(details)
    current_status["last_check"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return current_status