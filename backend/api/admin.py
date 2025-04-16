from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
import os
import json
import asyncio
import psutil

from backend.config import config
from backend.models.model_manager import model_manager
from backend.memory.synthetic_memory import synthetic_memory
from backend.memory.symbolic_memory import symbolic_memory
from backend.memory.vector_store import vector_store
from backend.voice.stt import stt_engine
from backend.voice.tts import tts_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Modèles de données
class SystemStatus(BaseModel):
    version: str = "1.0.0"
    status: str = "ok"  # "ok", "degraded", "error"
    cpu_usage: float
    memory_usage: Dict[str, float]
    disk_usage: Dict[str, float]
    components: Dict[str, Dict[str, Any]]

class ComponentStatus(BaseModel):
    status: str
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class ModelInfo(BaseModel):
    id: str
    name: str
    type: str
    status: str
    parameters: Dict[str, Any]

class MemoryStats(BaseModel):
    vector_count: int
    topics: List[str]
    total_entities: int
    total_relations: int
    size_kb: float

class SystemConfig(BaseModel):
    models: Dict[str, Any]
    voice: Dict[str, Any]
    memory: Dict[str, Any]
    data_dir: str

class ConfigUpdateRequest(BaseModel):
    section: str
    key: str
    value: Any

# Routes
@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """
    Récupère le statut global du système et de ses composants.
    """
    try:
        # Collecter les informations système
        cpu_percent = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Vérifier les statuts des composants
        components = {
            "llm": await check_llm_status(),
            "stt": await check_stt_status(),
            "tts": await check_tts_status(),
            "memory": await check_memory_status()
        }
        
        # Déterminer le statut global
        global_status = "ok"
        for comp in components.values():
            if comp["status"] == "error":
                global_status = "error"
                break
            elif comp["status"] == "degraded" and global_status != "error":
                global_status = "degraded"
        
        return SystemStatus(
            status=global_status,
            cpu_usage=cpu_percent,
            memory_usage={
                "total_gb": memory.total / (1024**3),
                "used_percent": memory.percent,
                "available_gb": memory.available / (1024**3)
            },
            disk_usage={
                "total_gb": disk.total / (1024**3),
                "used_percent": disk.percent,
                "free_gb": disk.free / (1024**3)
            },
            components=components
        )
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du statut système: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

async def check_llm_status() -> Dict[str, Any]:
    """Vérifie l'état des modèles LLM."""
    try:
        available_models = []
        status = "ok"
        error = None
        
        for model_id, model_config in config.models.items():
            try:
                # Tester une requête simple
                if model_id == "fast":
                    start_time = time.time()
                    response = await model_manager.generate_response("Test", complexity="low")
                    elapsed_time = time.time() - start_time
                    
                    available_models.append({
                        "id": model_id,
                        "name": model_config.name,
                        "type": model_config.type,
                        "status": "ok",
                        "latency": elapsed_time
                    })
                else:
                    # Ne pas tester tous les modèles pour économiser des ressources
                    available_models.append({
                        "id": model_id,
                        "name": model_config.name,
                        "type": model_config.type,
                        "status": "unknown"
                    })
            except Exception as e:
                logger.warning(f"Modèle {model_id} non disponible: {str(e)}")
                available_models.append({
                    "id": model_id,
                    "name": model_config.name,
                    "type": model_config.type,
                    "status": "error",
                    "error": str(e)
                })
                status = "degraded"
        
        if not available_models:
            status = "error"
            error = "Aucun modèle disponible"
        
        return {
            "status": status,
            "details": {
                "models": available_models
            },
            "error": error
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de la vérification des modèles: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

async def check_stt_status() -> Dict[str, Any]:
    """Vérifie l'état du système de reconnaissance vocale."""
    try:
        # Vérifier l'existence du binaire et du modèle
        stt_ok = True
        details = {}
        error = None
        
        if not os.path.exists(stt_engine.binary_path):
            stt_ok = False
            error = f"Binaire Whisper.cpp non trouvé: {stt_engine.binary_path}"
        else:
            details["binary"] = stt_engine.binary_path
        
        if not os.path.exists(stt_engine.model_path):
            stt_ok = False
            error = f"Modèle Whisper.cpp non trouvé: {stt_engine.model_path}"
        else:
            details["model"] = stt_engine.model_path
        
        return {
            "status": "ok" if stt_ok else "error",
            "details": details,
            "error": error
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de la vérification du système STT: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

async def check_tts_status() -> Dict[str, Any]:
    """Vérifie l'état du système de synthèse vocale."""
    try:
        # Vérifier l'installation de Piper
        import subprocess
        status = "ok"
        details = {"model": tts_engine.model_name}
        error = None
        
        try:
            result = subprocess.run(["piper", "--help"], capture_output=True, check=False)
            if result.returncode != 0:
                status = "error"
                error = "Piper TTS non installé ou non disponible"
        except FileNotFoundError:
            status = "error"
            error = "Piper TTS non installé"
        
        # Vérifier l'existence du modèle
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        model_path = os.path.join(project_root, tts_engine.model_name)

        if not os.path.exists(model_path):
            status = "error" if status != "error" else status
            error = f"Modèle Piper non trouvé: {model_path}"
        
        return {
            "status": status,
            "details": details,
            "error": error
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de la vérification du système TTS: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

async def check_memory_status() -> Dict[str, Any]:
    """Vérifie l'état des systèmes de mémoire."""
    try:
        status = "ok"
        error = None
        details = {}
        
        # Vérifier la mémoire vectorielle
        try:
            vector_count = vector_store.index.ntotal if hasattr(vector_store, 'index') else 0
            details["vector"] = {
                "count": vector_count,
                "dimension": vector_store.embedding_dimension
            }
        except Exception as e:
            status = "degraded"
            error = f"Problème avec la mémoire vectorielle: {str(e)}"
        
        # Vérifier la mémoire synthétique
        try:
            topics = list(synthetic_memory.memory_data.get("topics", {}).keys())
            details["synthetic"] = {
                "topics": topics,
                "count": sum(len(items) for items in synthetic_memory.memory_data.get("topics", {}).values())
            }
        except Exception as e:
            status = "degraded"
            error = f"Problème avec la mémoire synthétique: {str(e)}"
        
        # Vérifier la mémoire symbolique
        try:
            entity_count = len(symbolic_memory.memory_graph.get("entities", {}))
            relation_count = len(symbolic_memory.memory_graph.get("relations", []))
            details["symbolic"] = {
                "entities": entity_count,
                "relations": relation_count
            }
        except Exception as e:
            status = "degraded"
            error = f"Problème avec la mémoire symbolique: {str(e)}"
        
        return {
            "status": status,
            "details": details,
            "error": error
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de la vérification des systèmes de mémoire: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

@router.get("/models", response_model=List[ModelInfo])
async def list_models():
    """
    Liste tous les modèles configurés avec leur statut.
    """
    try:
        models_info = []
        
        for model_id, model_config in config.models.items():
            # Vérifier si le modèle est disponible
            status = "unknown"
            try:
                if model_id in model_manager.models:
                    status = "ok"
                elif model_config.type == "cloud" and os.environ.get("OPENAI_API_KEY"):
                    status = "ok"
                else:
                    status = "unavailable"
            except:
                status = "error"
            
            models_info.append(ModelInfo(
                id=model_id,
                name=model_config.name,
                type=model_config.type,
                status=status,
                parameters=model_config.parameters
            ))
        
        return models_info
    
    except Exception as e:
        logger.error(f"Erreur lors de la liste des modèles: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.get("/memory/stats", response_model=MemoryStats)
async def get_memory_stats():
    """
    Récupère les statistiques des systèmes de mémoire.
    """
    try:
        # Statistiques de la mémoire vectorielle
        vector_count = vector_store.index.ntotal if hasattr(vector_store, 'index') else 0
        
        # Statistiques de la mémoire synthétique
        topics = list(synthetic_memory.memory_data.get("topics", {}).keys())
        
        # Statistiques de la mémoire symbolique
        entity_count = len(symbolic_memory.memory_graph.get("entities", {}))
        relation_count = len(symbolic_memory.memory_graph.get("relations", []))
        
        # Taille des fichiers
        vector_size = os.path.getsize(vector_store.index_path + ".faiss") / 1024 if os.path.exists(vector_store.index_path + ".faiss") else 0
        metadata_size = os.path.getsize(vector_store.metadata_path) / 1024 if os.path.exists(vector_store.metadata_path) else 0
        synthetic_size = os.path.getsize(synthetic_memory.storage_path) / 1024 if os.path.exists(synthetic_memory.storage_path) else 0
        symbolic_size = os.path.getsize(symbolic_memory.storage_path) / 1024 if os.path.exists(symbolic_memory.storage_path) else 0
        
        total_size = vector_size + metadata_size + synthetic_size + symbolic_size
        
        return MemoryStats(
            vector_count=vector_count,
            topics=topics,
            total_entities=entity_count,
            total_relations=relation_count,
            size_kb=total_size
        )
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques de mémoire: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.post("/memory/compact")
async def compact_memory():
    """
    Compacte les systèmes de mémoire pour optimiser l'espace et les performances.
    """
    try:
        results = {}
        
        # Compresser la mémoire synthétique
        synthetic_result = await synthetic_memory.compress_memory()
        results["synthetic"] = {
            "status": "success" if synthetic_result else "error",
            "message": "Mémoire synthétique compressée" if synthetic_result else "Échec de compression"
        }
        
        # Reconstruire l'index vectoriel
        try:
            vector_result = vector_store.rebuild_index()
            results["vector"] = {
                "status": "success" if vector_result else "error",
                "message": f"Index vectoriel reconstruit ({vector_store.index.ntotal} vecteurs)" if vector_result else "Échec de reconstruction"
            }
        except Exception as e:
            results["vector"] = {
                "status": "error",
                "message": f"Erreur: {str(e)}"
            }
        
        return {
            "status": "success",
            "results": results
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de la compaction de la mémoire: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.get("/config")
async def get_config():
    """
    Récupère la configuration actuelle du système.
    """
    try:
        # Ne pas exposer les clés API ou informations sensibles
        sanitized_config = {
            "models": {
                model_id: {
                    "name": model.name,
                    "type": model.type,
                    "priority": model.priority,
                    "parameters": {
                        k: v for k, v in model.parameters.items() 
                        if k not in ["api_key", "token", "secret"]
                    }
                }
                for model_id, model in config.models.items()
            },
            "voice": {
                "stt_model": config.voice.stt_model,
                "tts_model": config.voice.tts_model,
                "tts_sample_rate": config.voice.tts_sample_rate
            },
            "memory": {
                "vector_dimension": config.memory.vector_dimension,
                "max_history_length": config.memory.max_history_length,
                "synthetic_memory_refresh_interval": config.memory.synthetic_memory_refresh_interval
            },
            "data_dir": config.data_dir
        }
        
        return sanitized_config
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.post("/config/update")
async def update_config(update: ConfigUpdateRequest):
    """
    Met à jour un paramètre de configuration.
    """
    try:
        # Vérifier que la section existe
        if not hasattr(config, update.section):
            raise HTTPException(status_code=400, detail=f"Section de configuration inconnue: {update.section}")
        
        section = getattr(config, update.section)
        
        # Vérifier que la clé existe dans la section
        if update.section == "models":
            if update.key not in section:
                raise HTTPException(status_code=400, detail=f"Modèle inconnu: {update.key}")
            
            # Mise à jour d'un paramètre de modèle
            if isinstance(update.value, dict):
                for param_key, param_value in update.value.items():
                    if hasattr(section[update.key], param_key):
                        setattr(section[update.key], param_key, param_value)
        else:
            # Mise à jour directe d'un paramètre
            if not hasattr(section, update.key):
                raise HTTPException(status_code=400, detail=f"Paramètre inconnu: {update.key}")
            
            setattr(section, update.key, update.value)
        
        # Sauvegarder la configuration
        # Note: Implémenter cette méthode ou adapter selon votre système
        # config.save()
        
        return {
            "status": "success",
            "message": f"Configuration mise à jour: {update.section}.{update.key}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.post("/restart")
async def restart_system():
    """
    Redémarre les services du système.
    """
    try:
        # Réinitialiser les composants
        async def restart_components():
            await asyncio.sleep(1)  # Petit délai pour permettre à la réponse HTTP de partir
            
            # Réinitialiser le gestionnaire de modèles
            model_manager._initialize_models()
            
            # Recharger les configurations
            # Simuler un redémarrage partiel
            logger.info("Redémarrage des composants système")
            
            # Dans un système de production, vous pourriez redémarrer le processus ou les services
            # os.execv(sys.executable, ['python'] + sys.argv)
        
        # Lancer le redémarrage en arrière-plan
        asyncio.create_task(restart_components())
        
        return {
            "status": "success",
            "message": "Redémarrage des services en cours..."
        }
    
    except Exception as e:
        logger.error(f"Erreur lors du redémarrage du système: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.get("/logs", response_model=List[Dict[str, Any]])
async def get_logs(
    level: Optional[str] = Query("INFO", enum=["DEBUG", "INFO", "WARNING", "ERROR"]),
    limit: int = Query(100, ge=1, le=1000),
    component: Optional[str] = Query(None)
):
    """
    Récupère les logs récents du système.
    """
    try:
        # Cette fonction est une simulation - dans un système réel, vous liriez les logs du système
        log_file = os.path.join(config.data_dir, "logs", "assistant.log")
        
        if not os.path.exists(log_file):
            return []
        
        # Convertir le niveau en entier
        level_map = {
            "DEBUG": 10,
            "INFO": 20,
            "WARNING": 30,
            "ERROR": 40
        }
        level_int = level_map.get(level, 20)
        
        # Lire les logs
        logs = []
        with open(log_file, 'r') as f:
            for line in f:
                try:
                    parts = line.strip().split(' - ', 3)
                    if len(parts) >= 4:
                        timestamp, logger_name, log_level, message = parts
                        
                        # Filtrer par niveau
                        if log_level not in level_map or level_map[log_level] < level_int:
                            continue
                        
                        # Filtrer par composant
                        if component and component not in logger_name:
                            continue
                        
                        logs.append({
                            "timestamp": timestamp,
                            "component": logger_name,
                            "level": log_level,
                            "message": message
                        })
                except:
                    # Ignorer les lignes mal formatées
                    continue
        
        # Tri par timestamp, plus récent d'abord
        logs.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # Limiter le nombre de logs
        return logs[:limit]
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")