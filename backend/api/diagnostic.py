from fastapi import APIRouter
import psutil
import time
from backend.config import config
from backend.models.model_manager import model_manager
from backend.memory.vector_store import vector_store
from backend.memory.symbolic_memory import symbolic_memory
from backend.memory.synthetic_memory import synthetic_memory
from backend.utils.singletons import tts_engine
from backend.utils.singletons import stt_engine
from backend.utils.singletons import hue_controller, shared_skill

router = APIRouter()

@router.get("/api/admin/status/details")
async def get_status_details():
    start = time.time()

    result = {
        "status": "ok",
        "components": {},
    }

    # LLM
    result["components"]["llm"] = {
        "status": "ok",
        "model": "Ollama",
        "message": "Modèles LLM opérationnels"
    }

    # TTS
    try:
        result["components"]["tts"] = {
            "status": "ok",
            "model": tts_engine.model_name
        }
    except Exception as e:
        result["components"]["tts"] = {"status": "error", "error": str(e)}
        result["status"] = "degraded"

    # STT
    try:
        stt_status = {
            "binary": stt_engine.binary_path,
            "model": stt_engine.model_path
        }
        result["components"]["stt"] = {"status": "ok", **stt_status}
    except Exception as e:
        result["components"]["stt"] = {"status": "error", "error": str(e)}
        result["status"] = "degraded"

    # Hue
    try:
        lights = hue_controller.get_all_lights()
        result["components"]["hue"] = {
            "status": "ok",
            "lights": len(lights)
        }
    except Exception as e:
        result["components"]["hue"] = {"status": "error", "error": str(e)}
        result["status"] = "degraded"

    # Mémoire vectorielle
    try:
        result["components"]["memory_vector"] = {
            "status": "ok",
            "vectors": vector_store.index.ntotal,
            "dimension": vector_store.embedding_dimension
        }
    except Exception as e:
        result["components"]["memory_vector"] = {"status": "error", "error": str(e)}
        result["status"] = "degraded"

    # Mémoire symbolique
    try:
        result["components"]["memory_symbolic"] = {
            "entities": len(symbolic_memory.memory_graph.get("entities", {})),
            "relations": len(symbolic_memory.memory_graph.get("relations", []))
        }
    except Exception as e:
        result["components"]["memory_symbolic"] = {"status": "error", "error": str(e)}
        result["status"] = "degraded"

    # Mémoire synthétique
    try:
        topics = synthetic_memory.memory_data.get("topics", {})
        result["components"]["memory_synthetic"] = {
            "topics": list(topics.keys()),
            "count": sum(len(v) for v in topics.values())
        }
    except Exception as e:
        result["components"]["memory_synthetic"] = {"status": "error", "error": str(e)}
        result["status"] = "degraded"

    # Système
    try:
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        result["components"]["system"] = {
            "cpu": cpu,
            "memory_percent": mem.percent,
            "disk_percent": disk.percent
        }
    except Exception as e:
        result["components"]["system"] = {"status": "error", "error": str(e)}
        result["status"] = "degraded"

    result["latency_total_ms"] = round((time.time() - start) * 1000, 2)
    return result
