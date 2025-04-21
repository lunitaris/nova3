from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, File, UploadFile, Form, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import logging
import asyncio
from datetime import datetime
import time


import os
import networkx as nx
from backend.config import config
from backend.memory.symbolic_memory import symbolic_memory


# Importations absolues au lieu d'importations relatives
from backend.memory.conversation import conversation_manager
from backend.models.model_manager import model_manager
from backend.utils.profiler import profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Modèles de données
class ChatMessage(BaseModel):
    content: str
    mode: str = "chat"  # "chat" ou "voice"
    conversation_id: Optional[str] = None
    user_id: Optional[str] = "anonymous"

class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    timestamp: str
    mode: str
    error: Optional[str] = None

class ConversationInfo(BaseModel):
    conversation_id: str
    title: str
    last_updated: str
    message_count: int
    summary: Optional[str] = None
    topics: Optional[List[str]] = None

# Endpoints
@router.post("/send", response_model=ChatResponse)
async def send_message(message: ChatMessage):
    """
    Envoie un message et reçoit une réponse.
    """
    logger.info("📩 API: requête /send - mode=%s, conv_id=%s", message.mode, message.conversation_id)
    try:
        start_time = time.time()
        logger.info("🧠 API: initialisation mise à jour symbolique")
        # 1. Injecter le message dans la mémoire symbolique
        asyncio.create_task(symbolic_memory.update_graph_from_text(message.content))

        process_start = time.time()
        logger.info("⚙️ API: appel au ConversationManager.process_user_input")
        # 2. Puis traitement normal de la conversation
        response = await conversation_manager.process_user_input(
            conversation_id=message.conversation_id,
            user_input=message.content,
            user_id=message.user_id,
            mode=message.mode,
            websocket=None  # Pas de streaming pour l'API REST
        )
        process_time = time.time() - process_start
        logger.info("✅ API: réponse générée en %.2f secondes", process_time)
        total_time = time.time() - start_time
        logger.info("🏁 API: traitement total /send en %.2f secondes", total_time)
        
        return ChatResponse(**response)
    
    except Exception as e:
        logger.error(f"Erreur lors du traitement du message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur de traitement: {str(e)}")

@router.get("/conversations", response_model=List[ConversationInfo])
async def list_conversations(
    user_id: str = Query("anonymous", alias="user_id"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_latest: bool = Query(True)  # Nouveau paramètre pour inclure la dernière conversation
):
    """
    Liste les conversations disponibles.
    """
    try:
        # Récupérer les conversations normalement
        conversations = conversation_manager.list_conversations(
            user_id=user_id,
            limit=limit,
            offset=offset
        )
        
        # Log pour débogage
        logger.info(f"Récupération de {len(conversations)} conversations pour l'utilisateur {user_id}")
        
        return conversations
    
    except Exception as e:
        logger.error(f"Erreur lors de la liste des conversations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.get("/conversation/{conversation_id}", response_model=Dict[str, Any])
async def get_conversation(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=200),
    include_metadata: bool = False
):
    """
    Récupère les messages d'une conversation.
    """
    try:
        conversation = conversation_manager.get_conversation(conversation_id)
        messages = conversation.get_messages(limit=limit, include_metadata=include_metadata)
        
        return {
            "conversation_id": conversation_id,
            "messages": messages,
            "metadata": conversation.metadata
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la conversation {conversation_id}: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Conversation non trouvée: {str(e)}")

@router.delete("/conversation/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """
    Supprime une conversation.
    """
    try:
        success = conversation_manager.delete_conversation(conversation_id)
        
        if success:
            return {"status": "success", "message": "Conversation supprimée"}
        else:
            raise HTTPException(status_code=404, detail="Conversation non trouvée")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la conversation {conversation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.post("/conversation/{conversation_id}/clear")
async def clear_conversation_history(conversation_id: str):
    """
    Efface l'historique d'une conversation tout en conservant ses métadonnées.
    """
    try:
        conversation = conversation_manager.get_conversation(conversation_id)
        conversation.clear_history()
        
        return {"status": "success", "message": "Historique de conversation effacé"}
    
    except Exception as e:
        logger.error(f"Erreur lors de l'effacement de l'historique {conversation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

# Gestionnaire de WebSocket pour les discussions en streaming
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Client WebSocket {client_id} connecté. Total: {len(self.active_connections)}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"Client WebSocket {client_id} déconnecté. Total: {len(self.active_connections)}")

    async def send_message(self, client_id: str, message: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)

manager = ConnectionManager()

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                # Analyser le message JSON
                message_data = json.loads(data)
                logger.info("🔄 WebSocket: message reçu - client=%s", client_id)
                logger.debug(f"🔄 WebSocket: message reçu {message_data}")

                
                # Extraire les informations
                conversation_id = message_data.get("conversation_id")
                content = message_data.get("content", "")
                mode = message_data.get("mode", "chat")
                user_id = message_data.get("user_id", "anonymous")
                logger.info("🧠 WebSocket: traitement de la requête - conv_id=%s, len=%d", conversation_id, len(content))
                

                start_time = time.time()
                if not content:
                    await websocket.send_json({
                        "type": "error",
                        "content": "Message vide"
                    })
                    continue
                
                # Envoyer un message de début explicite
                await websocket.send_json({
                    "type": "start",
                    "content": "",
                    "conversation_id": conversation_id
                })
                
                # Ajouter le message utilisateur
                conversation = conversation_manager.get_conversation(conversation_id, user_id)
                message = conversation.add_message(content, role="user", metadata={"mode": mode})
                
                
                # Créer une version simplifiée de la génération avec streaming manuel
                logger.info("🔄 WebSocket: utilisation du SmartRouter avec streaming")
                try:
                    # Utiliser le même pipeline optimisé que /send
                    result = await conversation_manager.process_user_input(
                        conversation_id=conversation_id,
                        user_input=content,
                        user_id=user_id,
                        mode=mode,
                        websocket=websocket  # Passer le websocket pour permettre le streaming
                    )
                    
                    # Pas besoin d'ajouter manuellement la réponse car process_user_input le fait déjà
                    # Pas besoin d'envoyer le message de fin car le SmartRouter s'en charge
                    
                except Exception as e:
                    logger.error(f"Erreur lors du traitement via SmartRouter: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    
                    await websocket.send_json({
                        "type": "error",
                        "content": f"Erreur: {str(e)}"
                    })

                process_time = time.time() - start_time
                logger.info("⏱️ WebSocket: requête traitée en %.2f secondes", process_time)
                
            except json.JSONDecodeError:
                logger.error(f"Format JSON invalide: {data}")
                await websocket.send_json({
                    "type": "error",
                    "content": "Format JSON invalide"
                })
            except Exception as e:
                logger.error(f"Erreur WebSocket: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "content": f"Erreur: {str(e)}"
                })
                
    except WebSocketDisconnect:
        manager.disconnect(client_id)




@router.get("/conversation/{conversation_id}/graph")
async def get_conversation_graph(
    conversation_id: str,
    include_deleted: bool = Query(False, description="Inclure les entités supprimées")
):
    """
    Récupère le graphe symbolique pour une conversation spécifique.
    Redirection vers l'endpoint unifié de l'API memory.
    """
    try:
        # Vérifier si la conversation existe
        conversation_file_path = os.path.join(config.data_dir, "conversations", f"{conversation_id}.json")
        if not os.path.exists(conversation_file_path):
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} non trouvée")
        
        # Rediriger vers l'API unifiée de graphe avec le paramètre conversation_id
        from backend.api.memory import get_memory_graph
        
        # Appeler l'API unifiée
        return await get_memory_graph(
            format="d3",
            include_expired=include_deleted,  # Note: renamed from include_deleted for consistency
            conversation_id=conversation_id
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du graphe pour la conversation {conversation_id}: {str(e)}")
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