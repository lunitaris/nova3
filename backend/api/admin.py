from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
import os
import json
import asyncio
import psutil
import time


from backend.config import config
from backend.models.model_manager import model_manager
from backend.memory.synthetic_memory import synthetic_memory
from backend.memory.symbolic_memory import symbolic_memory
from backend.memory.vector_store import vector_store
from backend.utils.singletons import stt_engine
from backend.utils.singletons import tts_engine
from backend.utils.singletons import hue_controller

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

        logger.info("📡 get_system_status() appelé")

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



################# API ADMIN pour EXPOSER PHILLIPS HUE #####

# Ajouter les nouvelles routes à backend/api/admin.py
# Ces routes doivent être insérées dans le fichier admin.py existant

# Modèles pour les lumières
class LightState(BaseModel):
    on: bool
    brightness: Optional[int] = None
    color: Optional[str] = None
    xy: Optional[List[float]] = None

class LightInfo(BaseModel):
    id: str
    name: str
    type: str = "light"
    room: Optional[str] = None
    state: LightState
    supports_color: bool = False
    supports_brightness: bool = True

class Room(BaseModel):
    id: str
    name: str
    lights: List[str]

# Routes pour les lumières
@router.get("/lights", response_model=List[LightInfo])
async def get_lights():
    """
    Récupère la liste de toutes les lumières.
    """
    try:
        lights = []
        
        # Tenter d'utiliser le contrôleur Hue si disponible
        if hue_controller and hue_controller.is_available:
            # Récupérer les pièces d'abord pour construire la carte de correspondance
            rooms = hue_controller.get_rooms()
            
            # Créer une map des lumières aux pièces
            light_to_room_map = {}
            
            # Pour chaque pièce, enregistrer à quelle pièce appartient chaque lumière
            for room in rooms:
                room_name = room["name"]
                for light_id in room.get("lights", []):
                    light_id_str = str(light_id)
                    light_to_room_map[light_id_str] = room_name
            
            # Maintenant, récupérer les lumières
            hue_lights = hue_controller.get_all_lights()
            
            for light in hue_lights:
                # Convertir les IDs en strings pour la validation Pydantic
                light_id = str(light["id"])
                
                # Trouver la pièce à laquelle cette lumière appartient
                room_name = light_to_room_map.get(light_id, "Non assignée")
                
                lights.append(LightInfo(
                    id=light_id,
                    name=light["name"],
                    room=room_name,
                    state=LightState(
                        on=light["state"]["on"],
                        brightness=light["state"].get("brightness", 0),
                        xy=light["state"].get("xy", None)
                    ),
                    supports_color=True,
                    supports_brightness=True
                ))
        
        # Si pas de lumières Hue ou si elles ne sont pas disponibles, utiliser les simulées
        if not lights:
            # Utiliser les lumières simulées
            skill = shared_skill            
            simulated_devices = skill.devices
            
            for name, device in simulated_devices.items():
                if "lumière" in name or device["type"] == "light":
                    lights.append(LightInfo(
                        id=name,  # Déjà une string
                        name=name,
                        room=device.get("location", None),
                        state=LightState(
                            on=device["state"] == "on",
                            brightness=100 if device["state"] == "on" else 0
                        ),
                        supports_color=False,
                        supports_brightness=True
                    ))
        
        return lights
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des lumières: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")



@router.get("/lights/rooms", response_model=List[Room])
async def get_rooms():
    """
    Récupère la liste des pièces/groupes de lumières.
    """
    try:
        rooms = []
        
        # Tenter d'utiliser le contrôleur Hue si disponible
        if hue_controller and hue_controller.is_available:
            # Récupérer les pièces Hue
            hue_rooms = hue_controller.get_rooms()
            
            for room in hue_rooms:
                rooms.append(Room(
                    id=room["id"],
                    name=room["name"],
                    lights=room.get("lights", [])
                ))
        
        # Si pas de pièces Hue, créer des groupes simulés
        if not rooms:
            # Utiliser les emplacements des lumières simulées    
            skill = shared_skill
            simulated_devices = skill.devices
            
            # Regrouper par emplacement
            locations = {}
            for name, device in simulated_devices.items():
                if "lumière" in name or device["type"] == "light":
                    location = device.get("location", "inconnu")
                    if location not in locations:
                        locations[location] = []
                    locations[location].append(name)
            
            # Créer des pièces à partir des emplacements
            for location, lights in locations.items():
                rooms.append(Room(
                    id=f"simulated_{location}",
                    name=location,
                    lights=lights
                ))
        
        return rooms
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des pièces: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

class LightControlRequest(BaseModel):
    action: str  # "on", "off", "brightness", "color", "scene"
    parameters: Optional[Dict[str, Any]] = None


# Correction à apporter dans backend/api/admin.py
# Modifier la méthode control_light()

@router.post("/lights/{light_id}/control")
async def control_light(light_id: str, request: LightControlRequest):
    """
    Contrôle une lumière spécifique.
    """
    try:
        # Tenter d'utiliser le contrôleur Hue si disponible
        if hue_controller and hue_controller.is_available:
            # Rechercher la lumière par ID et nom
            light = None
            for hue_light in hue_controller.get_all_lights():
                # Convertir l'ID de la lumière en string pour la comparaison
                hue_light_id = str(hue_light["id"])
                if hue_light_id == light_id or hue_light["name"].lower() == light_id.lower():
                    light = hue_light
                    break
            
            if light:
                result = hue_controller.control_light(
                    light["name"],
                    request.action,
                    request.parameters or {}
                )
                return result
        
        skill = shared_skill

        
        # Rechercher la lumière simulée
        if light_id in skill.devices:
            device = skill.devices[light_id]
            
            # Mettre à jour l'état simulé
            if request.action == "on":
                device["state"] = "on"
                return {"success": True, "message": f"Lumière {light_id} allumée"}
            elif request.action == "off":
                device["state"] = "off"
                return {"success": True, "message": f"Lumière {light_id} éteinte"}
            elif request.action == "brightness":
                device["state"] = "on"  # Allumer si réglage de luminosité
                value = request.parameters.get("value", 100)
                return {"success": True, "message": f"Luminosité de {light_id} réglée à {value}%"}
            elif request.action == "color":
                device["state"] = "on"  # Allumer si changement de couleur
                color = request.parameters.get("color", "white")
                return {"success": True, "message": f"Couleur de {light_id} changée en {color}"}
        
        # Lumière non trouvée
        raise HTTPException(status_code=404, detail=f"Lumière '{light_id}' non trouvée")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors du contrôle de la lumière {light_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")



# Correction à apporter dans backend/api/admin.py
# Modifier la méthode control_room()

@router.post("/lights/rooms/{room_id}/control")
async def control_room(room_id: str, request: LightControlRequest):
    """
    Contrôle toutes les lumières d'une pièce/groupe.
    """
    try:
        # Tenter d'utiliser le contrôleur Hue si disponible
        if hue_controller and hue_controller.is_available:
            # Rechercher la pièce par ID
            for room in hue_controller.get_rooms():
                # Convertir l'ID de la pièce en string pour la comparaison
                room_id_str = str(room["id"])
                if room_id_str == room_id or room["name"].lower() == room_id.lower():
                    # Contrôler le groupe directement
                    result = hue_controller._control_room(
                        room["id"],  # Utiliser l'ID original pour l'API
                        request.action,
                        request.parameters or {}
                    )
                    return result
        
        skill = shared_skill
        
        # Pour les pièces simulées, identifier toutes les lumières de cette pièce
        location = room_id.replace("simulated_", "")
        affected_lights = []
        
        for name, device in skill.devices.items():
            if ("lumière" in name or device["type"] == "light") and device.get("location") == location:
                affected_lights.append(name)
                
                # Mettre à jour l'état simulé
                if request.action == "on":
                    device["state"] = "on"
                elif request.action == "off":
                    device["state"] = "off"
        
        if affected_lights:
            return {
                "success": True,
                "message": f"{len(affected_lights)} lumières affectées dans {location}",
                "affected": affected_lights
            }
        
        # Pièce non trouvée
        raise HTTPException(status_code=404, detail=f"Pièce '{room_id}' non trouvée")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors du contrôle de la pièce {room_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")



@router.get("/memory/graph")
async def get_admin_memory_graph(
    include_deleted: bool = Query(False, description="Inclure les entités supprimées"),
    format: str = Query("d3", enum=["d3", "cytoscape"], description="Format de sortie")
):
    """
    Récupère le graphe de mémoire symbolique pour la visualisation dans l'interface d'administration.
    Redirection vers l'endpoint unifié de l'API memory.
    """
    try:
        # Rediriger vers l'API unifiée de graphe
        from backend.api.memory import get_memory_graph
        
        # Appeler l'API unifiée
        return await get_memory_graph(
            format=format,
            include_expired=include_deleted,  # Note: renamed from include_deleted for consistency
            conversation_id=None  # Pas de filtrage par conversation dans l'interface admin
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du graphe de mémoire: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")


def _get_node_group(entity_type: str) -> int:
    """
    Attribue un groupe (utilisé pour la couleur) selon le type d'entité.
    """
    type_groups = {
        "person": 1,
        "place": 2,
        "date": 3,
        "concept": 4,
        "preference": 5,
        "profession": 6,
        "contact": 7,
        "device": 8,
        "user": 0  # Utilisateurs en groupe spécial
    }
    
    return type_groups.get(entity_type.lower(), 9)  # 9 = autre type


@router.get("/lights/full")
async def get_lights_and_rooms():
    """
    Récupère à la fois la liste des lumières et des pièces dans un seul appel.
    """
    try:
        if hue_controller and hue_controller.is_available:
            # Forcer un seul refresh
            hue_controller._refresh_lights(force=True)
            rooms = hue_controller.get_rooms()
            lights = hue_controller.get_all_lights()
        else:
            rooms = []
            lights = []

        return {
            "rooms": rooms,
            "lights": lights
        }
    
    except Exception as e:
        logger.error(f"Erreur lors du chargement combiné lumières/pièces: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur lors du chargement des lumières et pièces")
