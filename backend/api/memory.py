from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
import csv
import io
from enum import Enum
from datetime import datetime

from backend.memory.synthetic_memory import synthetic_memory
from backend.memory.vector_store import vector_store
from backend.memory.symbolic_memory import symbolic_memory
import networkx as nx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["memory"])

# Modèles de données
class MemoryItem(BaseModel):
    content: str
    topic: Optional[str] = "general"
    metadata: Optional[Dict[str, Any]] = None
    score_pertinence: Optional[float] = None
    source_conversation_id: Optional[str] = None

class MemoryResponse(BaseModel):
    memory_id: Optional[int] = None
    status: str
    message: str
    error: Optional[str] = None

class SearchQuery(BaseModel):
    query: str
    topic: Optional[str] = None
    max_results: Optional[int] = 5
    min_score: Optional[float] = 0.0
    max_age_days: Optional[int] = None

class MemorySearchResult(BaseModel):
    results: List[Dict[str, Any]]
    count: int

class SortField(str, Enum):
    date = "date"
    score = "score"
    topic = "topic"
    relevance = "relevance"

class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"

class MemoryAuditQuery(BaseModel):
    include_deleted: Optional[bool] = False
    include_expired: Optional[bool] = False
    memory_type: Optional[str] = "all"  # "vector", "symbol", "all"
    sort_by: Optional[SortField] = SortField.date
    sort_order: Optional[SortOrder] = SortOrder.desc
    topic: Optional[str] = None
    min_confidence: Optional[float] = 0.0
    format: Optional[str] = "json"  # "json", "csv"

# Routes existantes

@router.post("/remember", response_model=MemoryResponse)
async def remember_information(item: MemoryItem):
    """
    Mémorise explicitement une information.
    """
    try:
        memory_id = vector_store.add_memory(
            content=item.content,
            metadata={"topic": item.topic, **(item.metadata or {})},
            score_pertinence=item.score_pertinence,
            source_conversation_id=item.source_conversation_id
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
        results = vector_store.search_memories(
            query=query.query,
            k=query.max_results,
            min_score=query.min_score,
            max_age_days=query.max_age_days
        )
        
        # Filtrer par sujet si spécifié
        if query.topic:
            results = [r for r in results if r.get("topic") == query.topic]
        
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
            metadata={"topic": item.topic, **(item.metadata or {})},
            score_pertinence=item.score_pertinence
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

# Nouvelle route d'audit pour la mémoire
@router.get("/audit")
async def audit_memories(
    include_deleted: bool = Query(False, description="Inclure les souvenirs supprimés"),
    include_expired: bool = Query(False, description="Inclure les souvenirs expirés"),
    memory_type: str = Query("all", description="Type de mémoire: vector, symbol, all"),
    sort_by: SortField = Query(SortField.date, description="Champ de tri"),
    sort_order: SortOrder = Query(SortOrder.desc, description="Ordre de tri"),
    topic: Optional[str] = Query(None, description="Filtrer par sujet"),
    min_confidence: float = Query(0.0, description="Score de confiance minimal"),
    format: str = Query("json", description="Format de sortie: json, csv")
):
    """
    Récupère tous les souvenirs pour audit et analyse.
    Permet de filtrer, trier et exporter les données de mémoire.
    """
    try:
        all_memories = []
        
        # Récupérer les mémoires vectorielles si demandé
        if memory_type in ["vector", "all"]:
            vector_memories = vector_store.get_all_memories(include_deleted=include_deleted)
            for memory in vector_memories:
                # Ajouter le type de mémoire pour différenciation
                memory["memory_type"] = "vector"
                
                # Filtrer par sujet si demandé
                if topic and memory.get("topic") != topic:
                    continue
                    
                # Filtrer par score de confiance
                if memory.get("score_pertinence", 0) < min_confidence:
                    continue
                    
                all_memories.append(memory)
        
        # Récupérer les entités symboliques si demandé
        if memory_type in ["symbol", "all"]:
            # Entités
            symbolic_entities = symbolic_memory.get_all_entities(include_expired=include_expired)
            for entity in symbolic_entities:
                # Convertir l'entité au format mémoire pour l'audit
                memory_entry = {
                    "memory_type": "symbolic_entity",
                    "entity_id": entity.get("entity_id"),
                    "content": f"Entité: {entity.get('name')} (Type: {entity.get('type')})",
                    "timestamp": entity.get("last_updated"),
                    "confidence": entity.get("confidence", 0),
                    "valid_from": entity.get("valid_from"),
                    "valid_to": entity.get("valid_to"),
                    "attributes": entity.get("attributes"),
                    "name": entity.get("name"),
                    "type": entity.get("type")
                }
                
                # Filtrer par score de confiance
                if memory_entry.get("confidence", 0) < min_confidence:
                    continue
                    
                all_memories.append(memory_entry)
            
            # Relations
            symbolic_relations = symbolic_memory.get_all_relations(include_expired=include_expired)
            for relation in symbolic_relations:
                # Convertir la relation au format mémoire pour l'audit
                memory_entry = {
                    "memory_type": "symbolic_relation",
                    "content": f"Relation: {relation.get('source_name')} - {relation.get('relation')} -> {relation.get('target_name')}",
                    "timestamp": relation.get("timestamp"),
                    "confidence": relation.get("confidence", 0),
                    "valid_from": relation.get("valid_from"),
                    "valid_to": relation.get("valid_to"),
                    "source": relation.get("source"),
                    "relation": relation.get("relation"),
                    "target": relation.get("target"),
                    "source_name": relation.get("source_name"),
                    "target_name": relation.get("target_name")
                }
                
                # Filtrer par score de confiance
                if memory_entry.get("confidence", 0) < min_confidence:
                    continue
                    
                all_memories.append(memory_entry)
        
        # Trier les résultats
        sort_key = None
        if sort_by == SortField.date:
            sort_key = lambda x: x.get("timestamp", "")
        elif sort_by == SortField.score:
            sort_key = lambda x: x.get("score_pertinence", x.get("confidence", 0))
        elif sort_by == SortField.topic:
            sort_key = lambda x: x.get("topic", "")
        elif sort_by == SortField.relevance:
            sort_key = lambda x: (x.get("score_pertinence", 0), x.get("confidence", 0))
        
        if sort_key:
            reverse = sort_order == SortOrder.desc
            all_memories.sort(key=sort_key, reverse=reverse)
        
        # Retourner au format demandé
        if format.lower() == "csv":
            # Préparer le CSV
            output = io.StringIO()
            
            # Déterminer les champs du CSV
            fieldnames = set()
            for memory in all_memories:
                fieldnames.update(memory.keys())
            fieldnames = sorted(list(fieldnames))
            
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            
            for memory in all_memories:
                writer.writerow(memory)
            
            csv_content = output.getvalue()
            output.close()
            
            # Retourner comme fichier CSV à télécharger
            headers = {
                "Content-Disposition": f"attachment; filename=memory_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
            return JSONResponse(
                content=csv_content,
                media_type="text/csv",
                headers=headers
            )
        else:
            # Format JSON par défaut
            return {
                "memories": all_memories,
                "count": len(all_memories),
                "filters": {
                    "include_deleted": include_deleted,
                    "include_expired": include_expired,
                    "memory_type": memory_type,
                    "sort_by": sort_by,
                    "sort_order": sort_order,
                    "topic": topic,
                    "min_confidence": min_confidence
                }
            }
    
    except Exception as e:
        logger.error(f"Erreur lors de l'audit des mémoires: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

# Route pour l'historique d'une entité (pour la roadmap étape 3)
@router.get("/timeline/{entity_id}")
async def get_entity_timeline(entity_id: str):
    """
    Récupère l'historique complet d'une entité symbolique.
    """
    try:
        history = symbolic_memory.get_entity_history(entity_id)
        
        if not history:
            raise HTTPException(status_code=404, detail=f"Entité {entity_id} non trouvée ou sans historique")
            
        return {
            "entity_id": entity_id,
            "history": history,
            "count": len(history)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'historique: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")




############################## API FOR SYMBLIC GRAPH #########################################

@router.get("/graph")
async def get_memory_graph(format: str = Query("d3", description="Format de sortie: d3, cytoscape"),
                          include_deleted: bool = Query(False, description="Inclure les entités supprimées")):
    """
    Récupère le graphe de connaissances symbolique dans un format adapté à la visualisation.
    """
    try:
        # Créer un graphe NetworkX
        G = nx.DiGraph()
        
        # Récupérer toutes les entités et relations

        entities = symbolic_memory.get_all_entities(include_expired=include_deleted)
        relations = symbolic_memory.get_all_relations(include_expired=include_deleted)
        
        # Ajouter les entités comme noeuds
        for entity in entities:
            entity_id = entity.get("entity_id")
            
            # Propriétés du noeud
            node_props = {
                "id": entity_id,
                "label": entity.get("name", "Entité sans nom"),
                "type": entity.get("type", "unknown"),
                "attributes": entity.get("attributes", {}),
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
                    "confidence": relation.get("confidence", 0.0)
                }
                
                G.add_edge(source, target, **edge_props)
        
        # Formater selon le format demandé
        if format == "d3":
            result = _format_graph_d3(G)
        elif format == "cytoscape":
            result = _format_graph_cytoscape(G)
        else:
            result = _format_graph_d3(G)  # D3 par défaut
        
        return result
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du graphe: {str(e)}")
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

def _format_graph_d3(G: nx.DiGraph) -> Dict[str, Any]:
    """
    Formate le graphe pour D3.js (format force-directed graph).
    """
    # Convertir le graphe en format attendu par D3.js
    nodes = []
    links = []
    
    for node_id, node_data in G.nodes(data=True):
        nodes.append({
            "id": node_id,
            "name": node_data.get("label", node_id),
            "group": node_data.get("group", 1),
            "type": node_data.get("type", "unknown"),
            "confidence": node_data.get("confidence", 0.0)
        })
    
    for source, target, edge_data in G.edges(data=True):
        links.append({
            "source": source,
            "target": target,
            "label": edge_data.get("label", "lien"),
            "value": edge_data.get("confidence", 0.5) * 2,  # Épaisseur proportionnelle à la confiance
            "confidence": edge_data.get("confidence", 0.5)
        })
    
    return {"nodes": nodes, "links": links}

def _format_graph_cytoscape(G: nx.DiGraph) -> Dict[str, Any]:
    """
    Formate le graphe pour Cytoscape.js.
    """
    elements = []
    
    # Nodes
    for node_id, node_data in G.nodes(data=True):
        elements.append({
            "data": {
                "id": node_id,
                "label": node_data.get("label", node_id),
                "group": node_data.get("group", 1),
                "type": node_data.get("type", "unknown"),
                "confidence": node_data.get("confidence", 0.0)
            }
        })
    
    # Edges
    for source, target, edge_data in G.edges(data=True):
        elements.append({
            "data": {
                "id": edge_data.get("id", f"{source}-{target}"),
                "source": source,
                "target": target,
                "label": edge_data.get("label", "lien"),
                "weight": edge_data.get("confidence", 0.5),
                "confidence": edge_data.get("confidence", 0.5)
            }
        })
    
    return {"elements": elements}