import os
import sys

# Supprimer toutes les variantes ambiguës d'import du module model_manager
for key in list(sys.modules.keys()):
    if key == "models" or key.startswith("models.") or key == "model_manager" or key.startswith("model_manager."):
        del sys.modules[key]

# Ajouter le répertoire parent au chemin Python pour permettre les importations absolues
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

import logging
# Configuration du logger (console + file) 
# 🔕 Silence de certains modules tiers
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
logging.getLogger("profiler").setLevel(logging.INFO)
logging.getLogger("faiss.loader").setLevel(logging.WARNING)
logging.getLogger("phue").setLevel(logging.WARNING)
logging.getLogger("faiss").setLevel(logging.WARNING)
# logging.getLogger("httpx").setLevel(logging.WARNING)  # Facultatif si trop bavard aussi


from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import uvicorn
from backend.api.health_monitor import monitor_health

from logging.handlers import RotatingFileHandler
from contextlib import asynccontextmanager


## Désactiver l'accélération (pour fix les pb avec vectors embeddings)
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["USE_TORCH"] = "0"
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"



######### MONITORING #########################
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Démarrage Nova avec lifespan")
    asyncio.create_task(monitor_health())           # Lancer le monitoring santé
    from backend.utils.startup_log import log_startup_summary
    log_startup_summary(logger)

    yield                                            # ⬅️ démarre l'app ici
    logger.info("🛑 Arrêt Nova (fin de lifespan)")


# Initialisation de l'application FastAPI
app = FastAPI(
    title="Assistant IA Local",
    description="API pour un assistant IA local avec fonctionnalités vocales et textuelles",
    version="0.1.0",
    lifespan=lifespan
)

# Configuration du CORS pour permettre les requêtes du frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modèles de données
class ChatMessage(BaseModel):
    content: str
    mode: str = "chat"  # "chat" ou "voice"

class ChatResponse(BaseModel):
    response: str
    sources: Optional[List[Dict[str, Any]]] = None

# Gestionnaire de connexions WebSocket
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Nouvelle connexion WebSocket établie. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"Connexion WebSocket fermée. Total: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# Endpoint de santé
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "Assistant IA Local"}

# Endpoint WebSocket pour le streaming des réponses
@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Ici, nous traiterons le message et enverrons la réponse
            # Pour l'instant, simple écho
            await manager.send_personal_message(f"Vous avez dit: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Routes pour les API
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(message: ChatMessage):
    """
    Endpoint pour les messages texte.
    Sera remplacé par une implémentation complète avec LLM.
    """
    # Implémentation à compléter
    return ChatResponse(
        response=f"Echo du message: {message.content}",
        sources=[]
    )

@app.post("/api/voice/stt")
async def speech_to_text():
    """
    Endpoint pour la conversion parole-texte.
    Sera implémenté avec Whisper.
    """
    # Implémentation à compléter
    return {"text": "Transcription à implémenter"}

@app.post("/api/memory/remember")
async def remember_info(info: Dict[str, Any]):
    """
    Endpoint pour stocker explicitement des informations en mémoire.
    """
    # Implémentation à compléter
    return {"status": "stored", "info": info}

# Importer les routers après la définition de l'application
# pour éviter les importations circulaires
try:
    # Importer les routers d'API
    from api.chat import router as chat_router
    from api.voice import router as voice_router
    from api.memory import router as memory_router

    # Inclure les routers
    app.include_router(chat_router)
    app.include_router(voice_router)
    app.include_router(memory_router)
    
except Exception as e:
    logger.error(f"Erreur lors du chargement des routers: {str(e)}")
    raise





"""
/////////////////////// ADMIN PAGE //////////////////////////////////////////////////////////////
"""

# Importer les routers après la définition de l'application
# pour éviter les importations circulaires
try:
    # Importer les routers d'API
    from api.chat import router as chat_router
    from api.voice import router as voice_router
    from api.memory import router as memory_router
    from api.admin import router as admin_router
    from api.diagnostic import router as diagnostic_router
    from api.health_monitor import router as health_router
    from backend.api import health_monitor




    # Inclure les routers
    app.include_router(chat_router)
    app.include_router(voice_router)
    app.include_router(memory_router)
    app.include_router(admin_router)
    app.include_router(diagnostic_router)
    app.include_router(health_router)
    app.include_router(health_monitor.router)  # Ajouter le routeur health_monitor


    
except Exception as e:
    logger.error(f"Erreur lors du chargement des routers: {str(e)}")
    raise



# Point d'entrée pour l'exécution directe
if __name__ == "__main__":
    # Code exécuté une seule fois
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)