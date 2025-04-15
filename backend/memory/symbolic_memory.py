"""
Système de mémoire symbolique utilisant un graphe de connaissances simple.
"""
import os
import json
import logging
import time
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime

from backend.models.model_manager import model_manager
from backend.config import config

logger = logging.getLogger(__name__)

class SymbolicMemory:
    """
    Gère la mémoire symbolique de l'assistant sous forme de graphe simplifié.
    Stocke des triplets (sujet, relation, objet) pour représenter des relations.
    """
    
    def __init__(self, storage_path: str = None):
        """
        Initialise le gestionnaire de mémoire symbolique.
        
        Args:
            storage_path: Chemin de stockage du graphe de connaissances
        """
        self.storage_path = storage_path or os.path.join(config.data_dir, "memories", "symbolic_memory.json")
        self.memory_graph = self._load_graph()
        
        # Structure: {
        #   "entities": {
        #     "entity_id": {
        #       "name": "Entity Name",
        #       "type": "person|place|device|concept",
        #       "attributes": {"key": "value"},
        #       "last_updated": "timestamp"
        #     }
        #   },
        #   "relations": [
        #     {
        #       "source": "entity_id1",
        #       "relation": "relation_type",
        #       "target": "entity_id2",
        #       "confidence": 0.95,
        #       "timestamp": "timestamp"
        #     }
        #   ]
        # }
    
    def _load_graph(self) -> Dict[str, Any]:
        """Charge le graphe de connaissances existant."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Erreur lors du chargement du graphe de connaissances: {str(e)}")
                return {"entities": {}, "relations": []}
        return {"entities": {}, "relations": []}
    
    def _save_graph(self):
        """Sauvegarde le graphe de connaissances."""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.memory_graph, f, ensure_ascii=False, indent=2)
            logger.debug("Graphe de connaissances sauvegardé")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du graphe de connaissances: {str(e)}")
    
    def _generate_entity_id(self, name: str) -> str:
        """
        Génère un ID d'entité basé sur le nom.
        
        Args:
            name: Nom de l'entité
            
        Returns:
            ID de l'entité
        """
        # Simplifier le nom pour l'ID (retirer accents, espaces, etc.)
        import re
        simple_name = re.sub(r'[^a-z0-9]', '_', name.lower())
        timestamp = int(time.time() * 1000) % 10000  # Ajouter un timestamp pour éviter les collisions
        return f"{simple_name}_{timestamp}"
    
    def add_entity(self, name: str, entity_type: str, attributes: Dict[str, Any] = None) -> str:
        """
        Ajoute une entité au graphe.
        
        Args:
            name: Nom de l'entité
            entity_type: Type d'entité (person, place, device, concept)
            attributes: Attributs supplémentaires
            
        Returns:
            ID de l'entité ajoutée
        """
        try:
            # Vérifier si l'entité existe déjà par son nom
            existing_id = self.find_entity_by_name(name)
            if existing_id:
                # Mettre à jour l'entité existante
                self.memory_graph["entities"][existing_id]["type"] = entity_type
                if attributes:
                    self.memory_graph["entities"][existing_id]["attributes"].update(attributes)
                self.memory_graph["entities"][existing_id]["last_updated"] = datetime.now().isoformat()
                self._save_graph()
                return existing_id
            
            # Créer une nouvelle entité
            entity_id = self._generate_entity_id(name)
            self.memory_graph["entities"][entity_id] = {
                "name": name,
                "type": entity_type,
                "attributes": attributes or {},
                "last_updated": datetime.now().isoformat()
            }
            
            self._save_graph()
            logger.info(f"Entité ajoutée: {name} ({entity_id})")
            return entity_id
            
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout d'entité: {str(e)}")
            return ""
    
    def find_entity_by_name(self, name: str) -> Optional[str]:
        """
        Recherche une entité par son nom.
        
        Args:
            name: Nom de l'entité à rechercher
            
        Returns:
            ID de l'entité si trouvée, None sinon
        """
        name_lower = name.lower()
        for entity_id, entity in self.memory_graph["entities"].items():
            if entity["name"].lower() == name_lower:
                return entity_id
        return None
    
    def add_relation(self, source_id: str, relation: str, target_id: str, confidence: float = 0.9) -> bool:
        """
        Ajoute une relation entre deux entités.
        
        Args:
            source_id: ID de l'entité source
            relation: Type de relation
            target_id: ID de l'entité cible
            confidence: Niveau de confiance (0-1)
            
        Returns:
            True si la relation a été ajoutée avec succès
        """
        try:
            # Vérifier que les entités existent
            if source_id not in self.memory_graph["entities"] or target_id not in self.memory_graph["entities"]:
                logger.warning(f"Tentative d'ajout de relation avec des entités inexistantes: {source_id}, {target_id}")
                return False
            
            # Vérifier si la relation existe déjà
            for rel in self.memory_graph["relations"]:
                if rel["source"] == source_id and rel["relation"] == relation and rel["target"] == target_id:
                    # Mettre à jour la relation existante
                    rel["confidence"] = confidence
                    rel["timestamp"] = datetime.now().isoformat()
                    self._save_graph()
                    return True
            
            # Ajouter la nouvelle relation
            self.memory_graph["relations"].append({
                "source": source_id,
                "relation": relation,
                "target": target_id,
                "confidence": confidence,
                "timestamp": datetime.now().isoformat()
            })
            
            self._save_graph()
            logger.info(f"Relation ajoutée: {source_id} -{relation}-> {target_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout de relation: {str(e)}")
            return False
    
    def query_relations(self, entity_id: str, relation_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Interroge les relations pour une entité donnée.
        
        Args:
            entity_id: ID de l'entité
            relation_type: Type de relation spécifique (optionnel)
            
        Returns:
            Liste des relations correspondantes
        """
        results = []
        
        try:
            for rel in self.memory_graph["relations"]:
                if rel["source"] == entity_id:
                    if relation_type is None or rel["relation"] == relation_type:
                        # Obtenir des détails supplémentaires
                        target_entity = self.memory_graph["entities"].get(rel["target"], {})
                        results.append({
                            "relation": rel["relation"],
                            "target_id": rel["target"],
                            "target_name": target_entity.get("name", "Inconnu"),
                            "target_type": target_entity.get("type", "inconnu"),
                            "confidence": rel["confidence"],
                            "timestamp": rel["timestamp"]
                        })
                
                # Également inclure les relations où l'entité est la cible
                elif rel["target"] == entity_id:
                    if relation_type is None or rel["relation"] == relation_type:
                        # Obtenir des détails supplémentaires
                        source_entity = self.memory_graph["entities"].get(rel["source"], {})
                        results.append({
                            "relation": f"reverse_{rel['relation']}",  # Indiquer que c'est la relation inverse
                            "source_id": rel["source"],
                            "source_name": source_entity.get("name", "Inconnu"),
                            "source_type": source_entity.get("type", "inconnu"),
                            "confidence": rel["confidence"],
                            "timestamp": rel["timestamp"]
                        })
            
            return results
            
        except Exception as e:
            logger.error(f"Erreur lors de la requête de relations: {str(e)}")
            return []
    
    async def extract_entities_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Extrait des entités d'un texte pour enrichir le graphe.
        
        Args:
            text: Texte à analyser
            
        Returns:
            Liste des entités extraites
        """
        try:
            # Utiliser un modèle pour extraire les entités
            prompt = f"""Extrait les entités suivantes du texte:
- Personnes
- Lieux
- Objets/Appareils
- Concepts

Texte: {text}

Retourne les résultats au format JSON avec les clés "persons", "places", "devices", "concepts", chacune contenant une liste d'entités.
"""
            
            response = await model_manager.generate_response(prompt, complexity="low")
            
            try:
                # Nettoyer la réponse
                clean_response = response.replace("```json", "").replace("```", "").strip()
                # Charger le JSON
                entities_data = json.loads(clean_response)
                
                extracted_entities = []
                
                # Traiter chaque type d'entité
                for entity_type, entities in entities_data.items():
                    type_mapping = {
                        "persons": "person",
                        "places": "place",
                        "devices": "device",
                        "concepts": "concept"
                    }
                    
                    mapped_type = type_mapping.get(entity_type, "unknown")
                    
                    for entity in entities:
                        if isinstance(entity, str) and entity.strip():
                            extracted_entities.append({
                                "name": entity.strip(),
                                "type": mapped_type
                            })
                
                return extracted_entities
                
            except json.JSONDecodeError:
                logger.warning(f"Réponse non parsable: {response}")
                return []
                
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction d'entités: {str(e)}")
            return []
    
    async def extract_relations_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Extrait des relations d'un texte pour enrichir le graphe.
        
        Args:
            text: Texte à analyser
            
        Returns:
            Liste des relations extraites
        """
        try:
            # Extraire d'abord les entités
            entities = await self.extract_entities_from_text(text)
            
            if not entities:
                return []
            
            # Construire un prompt pour extraire les relations
            entities_list = "\n".join([f"- {entity['name']} ({entity['type']})" for entity in entities])
            
            prompt = f"""Identifie les relations entre ces entités extraites du texte:
{entities_list}

Texte original: {text}

Retourne une liste de relations au format JSON sous forme de tableau où chaque élément contient:
- "source": nom de l'entité source
- "relation": type de relation (possède, est situé à, aime, connaît, etc.)
- "target": nom de l'entité cible
- "confidence": niveau de confiance (0.0 à 1.0)

Exemple:
[
  {{"source": "Jean", "relation": "possède", "target": "voiture", "confidence": 0.9}},
  {{"source": "Marie", "relation": "habite", "target": "Paris", "confidence": 0.8}}
]

Ne crée des relations que si elles sont clairement exprimées dans le texte.
"""
            
            response = await model_manager.generate_response(prompt, complexity="medium")
            
            try:
                # Nettoyer la réponse
                clean_response = response.replace("```json", "").replace("```", "").strip()
                
                # Si la réponse est vide ou ne contient pas de relations
                if "[]" in clean_response or not clean_response:
                    return []
                
                # Charger le JSON
                relations_data = json.loads(clean_response)
                
                return relations_data
                
            except json.JSONDecodeError:
                logger.warning(f"Réponse de relations non parsable: {response}")
                return []
                
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction de relations: {str(e)}")
            return []
    
    async def update_graph_from_text(self, text: str) -> Dict[str, int]:
        """
        Met à jour le graphe de connaissances à partir d'un texte.
        
        Args:
            text: Texte à analyser
            
        Returns:
            Statistiques sur les mises à jour (entités et relations ajoutées)
        """
        try:
            # 1. Extraire les entités et les ajouter au graphe
            extracted_entities = await self.extract_entities_from_text(text)
            
            entity_ids = {}
            entities_added = 0
            
            for entity in extracted_entities:
                entity_id = self.add_entity(
                    name=entity["name"],
                    entity_type=entity["type"]
                )
                if entity_id:
                    entity_ids[entity["name"]] = entity_id
                    entities_added += 1
            
            # 2. Extraire les relations et les ajouter au graphe
            extracted_relations = await self.extract_relations_from_text(text)
            
            relations_added = 0
            
            for relation in extracted_relations:
                source_name = relation.get("source")
                target_name = relation.get("target")
                relation_type = relation.get("relation")
                confidence = relation.get("confidence", 0.7)
                
                # Vérifier que les entités existent
                if source_name in entity_ids and target_name in entity_ids:
                    source_id = entity_ids[source_name]
                    target_id = entity_ids[target_name]
                    
                    if self.add_relation(source_id, relation_type, target_id, confidence):
                        relations_added += 1
            
            return {
                "entities_added": entities_added,
                "relations_added": relations_added
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du graphe: {str(e)}")
            return {
                "entities_added": 0,
                "relations_added": 0,
                "error": str(e)
            }
    
    def get_context_for_query(self, query: str, max_results: int = 3) -> str:
        """
        Récupère le contexte pertinent du graphe pour une requête.
        
        Args:
            query: Requête utilisateur
            max_results: Nombre maximal de résultats
            
        Returns:
            Contexte formaté pour le prompt
        """
        try:
            relevant_entities = []
            
            # Recherche simple par correspondance de noms
            for entity_id, entity in self.memory_graph["entities"].items():
                if entity["name"].lower() in query.lower():
                    relevant_entities.append({
                        "id": entity_id,
                        "name": entity["name"],
                        "type": entity["type"],
                        "attributes": entity["attributes"]
                    })
            
            # Limiter le nombre de résultats
            relevant_entities = relevant_entities[:max_results]
            
            if not relevant_entities:
                return ""
            
            # Récupérer les relations pour chaque entité
            context = "Informations du graphe de connaissances:\n"
            
            for entity in relevant_entities:
                context += f"\n- {entity['name']} ({entity['type']}):\n"
                
                # Ajouter les attributs
                if entity["attributes"]:
                    context += "  Attributs:\n"
                    for key, value in entity["attributes"].items():
                        context += f"    - {key}: {value}\n"
                
                # Ajouter les relations
                relations = self.query_relations(entity["id"])
                if relations:
                    context += "  Relations:\n"
                    for rel in relations[:5]:  # Limiter à 5 relations par entité
                        if "target_name" in rel:
                            context += f"    - {rel['relation']} {rel['target_name']}\n"
                        elif "source_name" in rel:
                            context += f"    - {rel['source_name']} {rel['relation'].replace('reverse_', '')}\n"
            
            return context
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du contexte du graphe: {str(e)}")
            return ""

# Instance globale du gestionnaire de mémoire symbolique
symbolic_memory = SymbolicMemory()