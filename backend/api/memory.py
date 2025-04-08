from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

from memory.synthetic_memory import synthetic_memory
from memory.vector_store import vector_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["memory"])

# Modèles de données
class MemoryItem(BaseModel):
    content: str
    topic: Optional[str] = "general"
    metadata: Optional[Dict[str, Any]] = None

class MemoryResponse(BaseModel):
    memory_id: Optional[int] = None
    status: str
    message: str
    error: Optional[str] = None

class SearchQuery(BaseModel):
    query: str
    topic: Optional[str] = None
    max_results: Optional[int] = 5

class MemorySearchResult(BaseModel):
    results: List[Dict[str, Any]]
    count: int

# Endpoints
@router.post("/remember", response_model=MemoryResponse)
async def remember_information(item: MemoryItem):
    """
    Mémorise explicitement une information.
    """
    try:
        memory_id = synthetic_memory.remember_explicit_info(
            info=item.content,
            topic=item.topic
        )
        
        if memory_id >= 0:
            return MemoryResponse(
                memory_id=memory_id,
                status="success",
                message="Information mémorisée avec succès"
            )
        else:
            return MemoryResponse(
                status="error",
                message="Échec de la mémorisation",
                error="Erreur interne lors de la mémorisation"
            )
    
    except Exception as e:
        logger.error(f"Erreur lors de la mémorisation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.post("/search", response_model=MemorySearchResult)
async def search_memories(query: SearchQuery):
    """
    Recherche des informations dans la mémoire.
    """
    try:
        results = synthetic_memory.get_relevant_memories(
            query=query.query,
            topic=query.topic,
            max_results=query.max_results
        )
        
        return MemorySearchResult(
            results=results,
            count=len(results)
        )
    
    except Exception as e:
        logger.error(f"Erreur lors de la recherche en mémoire: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.get("/topics", response_model=List[str])
async def list_memory_topics():
    """
    Liste tous les sujets disponibles dans la mémoire.
    """
    try:
        topics = list(synthetic_memory.memory_data.get("topics", {}).keys())
        return topics
    
    except Exception as e:
        logger.error(f"Erreur lors de la liste des sujets: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.get("/topic/{topic}", response_model=List[Dict[str, Any]])
async def get_topic_memories(topic: str):
    """
    Récupère toutes les mémoires d'un sujet spécifique.
    """
    try:
        memories = synthetic_memory.get_memory_by_topic(topic)
        return memories
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des mémoires du sujet {topic}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.post("/compress", response_model=MemoryResponse)
async def compress_memories():
    """
    Lance une compression manuelle des mémoires synthétiques.
    """
    try:
        success = await synthetic_memory.compress_memory()
        
        if success:
            return MemoryResponse(
                status="success",
                message="Mémoires compressées avec succès"
            )
        else:
            return MemoryResponse(
                status="error",
                message="Échec de la compression des mémoires",
                error="Erreur interne lors de la compression"
            )
    
    except Exception as e:
        logger.error(f"Erreur lors de la compression des mémoires: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.delete("/memory/{memory_id}", response_model=MemoryResponse)
async def delete_memory(memory_id: str):
    """
    Supprime une mémoire spécifique.
    """
    try:
        success = vector_store.delete_memory(memory_id)
        
        if success:
            return MemoryResponse(
                status="success",
                message=f"Mémoire {memory_id} supprimée avec succès"
            )
        else:
            return MemoryResponse(
                status="error",
                message=f"Échec de la suppression de la mémoire {memory_id}",
                error="Mémoire non trouvée ou erreur interne"
            )
    
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la mémoire {memory_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.put("/memory/{memory_id}", response_model=MemoryResponse)
async def update_memory(memory_id: str, item: MemoryItem):
    """
    Met à jour une mémoire existante.
    """
    try:
        success = vector_store.update_memory(
            memory_id=memory_id,
            content=item.content,
            metadata={"topic": item.topic, **(item.metadata or {})}
        )
        
        if success:
            return MemoryResponse(
                status="success",
                message=f"Mémoire {memory_id} mise à jour avec succès"
            )
        else:
            return MemoryResponse(
                status="error",
                message=f"Échec de la mise à jour de la mémoire {memory_id}",
                error="Mémoire non trouvée ou erreur interne"
            )
    
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la mémoire {memory_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")