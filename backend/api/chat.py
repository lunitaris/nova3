from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, File, UploadFile, Form, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import logging
import asyncio
from datetime import datetime


import os
import networkx as nx
from backend.config import config
from backend.memory.symbolic_memory import symbolic_memory


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
                logger.debug(f"Message WebSocket reçu: {message_data}")
                
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
                try:
                    # Préparer le prompt
                    prompt = "Répondez de manière simple et concise: " + content
                    
                    # Utiliser le model manager pour obtenir le modèle adapté, mais sans streaming
                    model = model_manager._get_appropriate_model(prompt, "auto", None)
                    
                    # Générer la réponse complète sans streaming
                    response_text = await model.ainvoke(prompt)
                    
                    # Simuler le streaming en envoyant des tokens manuellement
                    last_sent = 0
                    token_size = 5  # Envoyer 5 caractères à la fois
                    
                    while last_sent < len(response_text):
                        # Extraire le prochain "token"
                        end = min(last_sent + token_size, len(response_text))
                        token = response_text[last_sent:end]
                        last_sent = end
                        
                        # Envoyer le token
                        await websocket.send_json({
                            "type": "token",
                            "content": token
                        })
                        
                        # Pause pour simuler le streaming naturel
                        await asyncio.sleep(0.1)
                    
                    # Ajouter la réponse à la conversation
                    conversation.add_message(response_text, role="assistant", metadata={"mode": mode})
                    
                    # Envoyer le message de fin
                    await websocket.send_json({
                        "type": "end",
                        "content": response_text,
                        "conversation_id": conversation.conversation_id,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                except Exception as e:
                    logger.error(f"Erreur lors de la génération: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    
                    await websocket.send_json({
                        "type": "error",
                        "content": f"Erreur: {str(e)}"
                    })
                
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



# Ajoutez ce code au fichier backend/api/chat.py

@router.get("/conversation/{conversation_id}/graph")
async def get_conversation_graph(
    conversation_id: str,
    include_deleted: bool = Query(False, description="Inclure les entités supprimées")
):
    """
    Récupère le graphe symbolique pour une conversation spécifique.
    """
    try:
        # Vérifier si la conversation existe
        if not os.path.exists(os.path.join(config.data_dir, "conversations", f"{conversation_id}.json")):
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} non trouvée")
            
        # Construire un graphe networkx
        G = nx.DiGraph()
        
        # Option 1: Récupérer toutes les entités du graphe symbolique
        entities = symbolic_memory.get_all_entities(include_expired=include_deleted)
        relations = symbolic_memory.get_all_relations(include_expired=include_deleted)
        
        # Option 2 (meilleure): Filtrer les entités et relations liées à cette conversation
        # Cette partie peut être ajustée selon la façon dont vous associez les entités aux conversations
        conversation_entities = []
        conversation_relations = []
        
        # Ajouter les entités comme nœuds
        for entity in entities:
            entity_id = entity.get("entity_id")
            
            # Propriétés du noeud
            node_props = {
                "id": entity_id,
                "name": entity.get("name", "Entité sans nom"),
                "type": entity.get("type", "unknown"),
                "confidence": entity.get("confidence", 0.0),
                "group": _get_node_group(entity.get("type", "unknown"))
            }
            
            G.add_node(entity_id, **node_props)
        
        # Ajouter les relations comme liens
        for relation in relations:
            source = relation.get("source")
            target = relation.get("target")
            
            # Vérifier que les noeuds existent
            if source in G.nodes and target in G.nodes:
                # Propriétés du lien
                edge_props = {
                    "id": f"{source}_{relation.get('relation')}_{target}",
                    "label": relation.get("relation", "lien"),
                    "confidence": relation.get("confidence", 0.0),
                    "value": relation.get("confidence", 0.5) * 2  # Épaisseur proportionnelle à la confiance
                }
                
                G.add_edge(source, target, **edge_props)
        
        # Formater pour D3.js (format force-directed graph)
        nodes = []
        links = []
        
        for node_id, node_data in G.nodes(data=True):
            nodes.append({
                "id": node_id,
                "name": node_data.get("name", node_id),
                "group": node_data.get("group", 1),
                "type": node_data.get("type", "unknown"),
                "confidence": node_data.get("confidence", 0.0)
            })
        
        for source, target, edge_data in G.edges(data=True):
            links.append({
                "source": source,
                "target": target,
                "label": edge_data.get("label", "lien"),
                "value": edge_data.get("value", 1),
                "confidence": edge_data.get("confidence", 0.5)
            })
        
        return {"nodes": nodes, "links": links}
        
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