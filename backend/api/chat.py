from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, File, UploadFile, Form, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import logging
import asyncio

# Importations absolues au lieu d'importations relatives
from memory.conversation import conversation_manager
from models.model_manager import model_manager

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
    try:
        response = await conversation_manager.process_user_input(
            conversation_id=message.conversation_id,
            user_input=message.content,
            user_id=message.user_id,
            mode=message.mode
        )
        
        return ChatResponse(**response)
    
    except Exception as e:
        logger.error(f"Erreur lors du traitement du message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur de traitement: {str(e)}")

@router.get("/conversations", response_model=List[ConversationInfo])
async def list_conversations(
    user_id: str = "anonymous",
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    Liste les conversations disponibles.
    """
    try:
        conversations = conversation_manager.list_conversations(
            user_id=user_id,
            limit=limit,
            offset=offset
        )
        
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
                
                # Extraire les informations
                conversation_id = message_data.get("conversation_id")
                content = message_data.get("content", "")
                mode = message_data.get("mode", "chat")
                user_id = message_data.get("user_id", "anonymous")
                
                if not content:
                    await websocket.send_json({
                        "type": "error",
                        "content": "Message vide"
                    })
                    continue
                
                # Traiter le message en temps réel avec streaming
                # Envoyer un message de début
                await websocket.send_json({
                    "type": "start",
                    "content": "",
                    "conversation_id": conversation_id
                })
                
                # Traiter la requête
                response = await conversation_manager.process_user_input(
                    conversation_id=conversation_id,
                    user_input=content,
                    user_id=user_id,
                    mode=mode,
                    websocket=websocket  # Pour le streaming direct
                )
                
                # Envoyer un message de fin avec la réponse complète
                await websocket.send_json({
                    "type": "end",
                    "content": response["response"],
                    "conversation_id": response["conversation_id"],
                    "timestamp": response["timestamp"]
                })
                
            except json.JSONDecodeError:
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