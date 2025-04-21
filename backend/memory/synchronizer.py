"""
Module de synchronisation entre la mémoire vectorielle et symbolique.
Permet de maintenir la cohérence entre les différents types de mémoire.
"""
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from backend.memory.vector_store import vector_store
from backend.memory.symbolic_memory import symbolic_memory
from backend.models.model_manager import model_manager

logger = logging.getLogger(__name__)

class MemorySynchronizer:
    """
    Gestionnaire de synchronisation entre mémoire vectorielle et symbolique.
    Assure la cohérence des informations entre les deux systèmes de mémoire.
    """
    
    def __init__(self):
        """Initialise le synchroniseur de mémoire."""
        self.vector_store = vector_store
        self.symbolic_memory = symbolic_memory
        
    async def extract_facts_from_memory(self, memory_id: str) -> List[Dict[str, Any]]:
        """
        Extrait des faits symboliques à partir d'un souvenir vectoriel.
        
        Args:
            memory_id: ID du souvenir vectoriel
            
        Returns:
            Liste des faits extraits sous forme de triplets (sujet, relation, objet)
        """
        try:
            # Récupérer le souvenir
            memory_metadata = self.vector_store.metadata.get(memory_id)
            if not memory_metadata:
                logger.warning(f"Souvenir {memory_id} non trouvé")
                return []
            
            content = memory_metadata.get("content", "")
            if not content:
                return []
            
            # Utiliser le LLM pour extraire des faits structurés
            prompt = f"""Extrait des faits objectifs sous forme de triplets (sujet, relation, objet) à partir du texte suivant:

Texte: "{content}"

Renvoie uniquement les faits clairement établis, pas d'inférences ou de suppositions.
Format souhaité: liste JSON de triplets
[
  {{"subject": "Jean", "relation": "aime", "object": "café"}},
  {{"subject": "Paris", "relation": "est", "object": "capitale de la France"}}
]
Limite-toi aux faits clairs et explicites.
"""
            
            response = await model_manager.generate_response(prompt, complexity="low")
            
            # Parser la réponse JSON
            import json
            import re
            
            # Extraire la partie JSON entre crochets
            json_match = re.search(r'\[(.*?)\]', response, re.DOTALL)
            if not json_match:
                return []
                
            # Corriger le format JSON potentiellement mal formaté
            json_str = f"[{json_match.group(1)}]"
            json_str = json_str.replace("'", '"')  # Remplacer les apostrophes par des guillemets doubles
            
            try:
                facts = json.loads(json_str)
                return facts
            except json.JSONDecodeError:
                logger.warning(f"Impossible de parser la réponse JSON: {json_str}")
                return []
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des faits: {str(e)}")
            return []
    
    async def sync_memory_to_symbolic(self, memory_id: str, confidence: float = 0.7) -> Dict[str, int]:
        """
        Synchronise un souvenir vectoriel vers le graphe symbolique.
        
        Args:
            memory_id: ID du souvenir vectoriel
            confidence: Niveau de confiance pour les entités/relations extraites
            
        Returns:
            Statistiques sur les entités et relations ajoutées
        """
        try:
            # Extraire des faits
            facts = await self.extract_facts_from_memory(memory_id)
            
            if not facts:
                return {"entities_added": 0, "relations_added": 0}
            
            # Convertir les faits en entités et relations
            entities_added = 0
            relations_added = 0
            
            # Récupérer le score_pertinence pour l'utiliser comme base de confiance
            memory_metadata = self.vector_store.metadata.get(memory_id, {})
            score_pertinence = memory_metadata.get("score_pertinence", 0.7)
            
            # Ajuster la confiance en fonction du score de pertinence
            adjusted_confidence = confidence * (0.5 + 0.5 * score_pertinence)
            
            # Date de validité
            valid_from = datetime.now().isoformat()
            
            # Pour chaque fait, créer/mettre à jour les entités et relations
            for fact in facts:
                subject = fact.get("subject")
                relation_type = fact.get("relation")
                obj = fact.get("object")
                
                if not subject or not relation_type or not obj:
                    continue
                
                # Créer ou mettre à jour les entités
                subject_id = self.symbolic_memory.add_entity(
                    name=subject,
                    entity_type="concept",  # Type par défaut
                    confidence=adjusted_confidence,
                    valid_from=valid_from
                )
                
                if subject_id and subject_id not in self.symbolic_memory.memory_graph["entities"]:
                    entities_added += 1
                
                object_id = self.symbolic_memory.add_entity(
                    name=obj,
                    entity_type="concept",  # Type par défaut
                    confidence=adjusted_confidence,
                    valid_from=valid_from
                )
                
                if object_id and object_id not in self.symbolic_memory.memory_graph["entities"]:
                    entities_added += 1
                
                # Créer la relation
                if subject_id and object_id:
                    if self.symbolic_memory.add_relation(
                        source_id=subject_id,
                        relation=relation_type,
                        target_id=object_id,
                        confidence=adjusted_confidence,
                        valid_from=valid_from
                    ):
                        relations_added += 1
            
            return {
                "entities_added": entities_added,
                "relations_added": relations_added,
                "facts_extracted": len(facts)
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la synchronisation de la mémoire {memory_id}: {str(e)}")
            return {"entities_added": 0, "relations_added": 0, "error": str(e)}
    
    async def sync_recent_memories(self, max_memories: int = 10) -> Dict[str, int]:
        """
        Synchronise les souvenirs vectoriels récents vers le graphe symbolique.
        
        Args:
            max_memories: Nombre maximum de souvenirs à synchroniser
            
        Returns:
            Statistiques sur les entités et relations ajoutées
        """
        try:
            # Récupérer tous les souvenirs
            all_memories = self.vector_store.get_all_memories(include_deleted=False)
            
            # Trier par date, plus récent d'abord
            all_memories.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            # Limiter au nombre demandé
            recent_memories = all_memories[:max_memories]
            
            # Synchroniser chaque mémoire
            total_entities = 0
            total_relations = 0
            
            for memory in recent_memories:
                memory_id = memory.get("memory_id")
                
                # Calculer la confiance en fonction du score de pertinence
                score_pertinence = memory.get("score_pertinence", 0.7)
                confidence = 0.6 + (0.4 * score_pertinence)  # Entre 0.6 et 1.0
                
                results = await self.sync_memory_to_symbolic(memory_id, confidence)
                
                total_entities += results.get("entities_added", 0)
                total_relations += results.get("relations_added", 0)
            
            return {
                "memories_processed": len(recent_memories),
                "entities_added": total_entities,
                "relations_added": total_relations
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la synchronisation des mémoires récentes: {str(e)}")
            return {
                "memories_processed": 0,
                "entities_added": 0, 
                "relations_added": 0,
                "error": str(e)
            }
    
    async def enrich_memory_with_symbolic(self, memory_id: str, query: str = None) -> bool:
        """
        Enrichit un souvenir vectoriel avec des informations du graphe symbolique.
        
        Args:
            memory_id: ID du souvenir à enrichir
            query: Requête spécifique pour filtrer les informations pertinentes
            
        Returns:
            True si l'enrichissement a réussi
        """
        try:
            # Vérifier que le souvenir existe
            if memory_id not in self.vector_store.metadata:
                logger.warning(f"Souvenir {memory_id} non trouvé pour enrichissement")
                return False
            
            # Extraire des entités du souvenir pour trouver des correspondances
            memory_content = self.vector_store.metadata[memory_id].get("content", "")
            if not memory_content:
                return False
            
            # Si pas de requête spécifique, utiliser le contenu comme requête
            if not query:
                query = memory_content
            
            logger.warning("⏭️ Enrichissement symbolique désactivé (extraction d’entités supprimée)")
            return False
            
            # Collecter les informations symboliques pertinentes
            symbolic_context = []
            
            for entity in entities:
                entity_name = entity.get("name")
                entity_id = self.symbolic_memory.find_entity_by_name(entity_name)
                
                if entity_id:
                    # Obtenir les relations de cette entité
                    relations = self.symbolic_memory.query_relations(entity_id)
                    
                    if relations:
                        # Formater les relations pour enrichir le contexte
                        entity_info = f"Informations sur {entity_name}:\n"
                        
                        for rel in relations:
                            if "target_name" in rel:
                                entity_info += f"- {rel['relation']} {rel['target_name']}\n"
                            elif "source_name" in rel:
                                entity_info += f"- {rel['source_name']} {rel['relation'].replace('reverse_', '')}\n"
                        
                        symbolic_context.append(entity_info)
            
            # Si des informations symboliques ont été trouvées, les ajouter aux métadonnées
            if symbolic_context:
                # Mettre à jour les métadonnées avec le contexte symbolique
                if "symbolic_context" not in self.vector_store.metadata[memory_id]:
                    self.vector_store.metadata[memory_id]["symbolic_context"] = []
                
                self.vector_store.metadata[memory_id]["symbolic_context"] = symbolic_context
                self.vector_store.metadata[memory_id]["symbolic_updated_at"] = datetime.now().isoformat()
                
                # Sauvegarder les modifications
                self.vector_store._save_metadata()
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur lors de l'enrichissement du souvenir {memory_id}: {str(e)}")
            return False
    
    def get_synchronization_status(self) -> Dict[str, Any]:
        """
        Fournit des statistiques sur l'état de synchronisation entre les mémoires.
        
        Returns:
            Statistiques de synchronisation
        """
        try:
            # Compter les souvenirs vectoriels
            vector_memories = self.vector_store.get_all_memories(include_deleted=False)
            vector_count = len(vector_memories)
            
            # Compter les souvenirs avec contexte symbolique
            enriched_count = sum(1 for memory in vector_memories if "symbolic_context" in memory)
            
            # Calculer le pourcentage de synchronisation
            sync_percentage = (enriched_count / vector_count * 100) if vector_count > 0 else 0
            
            # Compter les entités et relations symboliques
            entity_count = len(self.symbolic_memory.memory_graph["entities"])
            relation_count = len(self.symbolic_memory.memory_graph["relations"])
            
            return {
                "vector_memories": vector_count,
                "enriched_memories": enriched_count,
                "sync_percentage": sync_percentage,
                "symbolic_entities": entity_count,
                "symbolic_relations": relation_count,
                "last_checked": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques de synchronisation: {str(e)}")
            return {
                "error": str(e),
                "last_checked": datetime.now().isoformat()
            }

# Instance globale du synchroniseur de mémoire
memory_synchronizer = MemorySynchronizer()