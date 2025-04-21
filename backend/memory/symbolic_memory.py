"""
Système de mémoire symbolique utilisant un graphe de connaissances simple.
"""
import os
import json
import logging
import time
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime
import re
import unicodedata

from backend.models.model_manager import model_manager
from backend.utils.profiler import profile
from backend.config import config
from backend.utils.startup_log import add_startup_event
from backend.memory.graph_postprocessor import postprocess_graph



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
        
        # Initialiser les règles
        self.entity_aliases = {}
        self.entity_types = {}
        self.relation_rewrites = {}
        self.reload_rules()  # Charger les règles dynamiquement
        print(f"[DEBUG] Graph path: {self.storage_path}")

    
    
    def _load_graph(self) -> Dict[str, Any]:
        """Charge le graphe de connaissances existant."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    graph = json.load(f)
                    add_startup_event(f"Graph mémoire symbolique chargé ({len(graph.get('entities', {}))} entités)")
                    return graph


            except Exception as e:
                logger.error(f"Erreur lors du chargement du graphe de connaissances: {str(e)}")
                add_startup_event("Graph mémoire symbolique initialisé vide (échec du chargement)")
                return {"entities": {}, "relations": []}
        return {"entities": {}, "relations": []}


    def _save_graph(self):
        """Sauvegarde le graphe de connaissances avec post-traitement, en créant un backup."""

        try:
            # 📍 1. Chemin de sauvegarde
            path = self.storage_path

            # 📦 2. Sauvegarde le fichier actuel si présent
            if os.path.exists(path):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                backup_path = path.replace(".json", f"_backup_{timestamp}.json")
                import shutil
                shutil.copy2(path, backup_path)
                logger.info(f"📦 Backup mémoire symbolique créé : {backup_path}")

            # 🔄 3. Post-traitement
            from backend.memory.graph_postprocessor import postprocess_graph
            cleaned = postprocess_graph(self.memory_graph)
            self.memory_graph = cleaned

            # 💾 4. Écriture du fichier principal
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.memory_graph, f, ensure_ascii=False, indent=2)

            logger.info("💾 Graphe symbolique sauvegardé avec succès (optimisé)")

        except Exception as e:
            logger.error(f"❌ Erreur lors de la sauvegarde du graphe symbolique : {str(e)}")


    def _generate_entity_id(self, name: str) -> str:
        """
        Génère un ID stable et lisible basé sur le nom, sans timestamp.
        Si l'ID existe déjà, ajoute un suffixe numérique.
        """
        name = unicodedata.normalize("NFD", name)
        name = name.encode("ascii", "ignore").decode("utf-8")
        # Nettoyer le nom (minuscule, accents retirés, alphanum uniquement)
        base = re.sub(r'[^a-z0-9]', '_', name.lower())
    

        # S'assurer que l'ID est unique dans le graphe
        entity_ids = set(self.memory_graph.get("entities", {}).keys())
        entity_id = base
        count = 1

        while entity_id in entity_ids:
            entity_id = f"{base}_{count}"
            count += 1

        return entity_id
    
    def add_entity(self, name: str, entity_type: str, attributes: Dict[str, Any] = None, 
                confidence: float = 0.9, valid_from: str = None, valid_to: str = None, batched: bool = False) -> str:

        """
        Ajoute une entité au graphe.
        
        Args:
            name: Nom de l'entité
            entity_type: Type d'entité (person, place, device, concept)
            attributes: Attributs supplémentaires
            confidence: Niveau de confiance (0-1)
            valid_from: Date ISO de début de validité (si None, date courante)
            valid_to: Date ISO de fin de validité (si None, pas de limite)
            
        Returns:
            ID de l'entité ajoutée
        """
        batched: bool = False
        try:
            # Si valid_from n'est pas spécifié, utiliser la date courante
            if valid_from is None:
                valid_from = datetime.now().isoformat()
                
            # Vérifier si l'entité existe déjà par son nom
            existing_id = self.find_entity_by_name(name)
            if existing_id:
                # Créer un historique si l'entité existe déjà
                old_data = self.memory_graph["entities"][existing_id].copy()
                
                # Vérifier si l'historique existe déjà
                if "history" not in self.memory_graph["entities"][existing_id]:
                    self.memory_graph["entities"][existing_id]["history"] = []
                
                # Ajouter l'ancien état à l'historique
                self.memory_graph["entities"][existing_id]["history"].append({
                    "timestamp": datetime.now().isoformat(),
                    "old_value": {
                        "type": old_data.get("type"),
                        "attributes": old_data.get("attributes", {}),
                        "confidence": old_data.get("confidence"),
                        "valid_from": old_data.get("valid_from"),
                        "valid_to": old_data.get("valid_to")
                    }
                })
                
                # Mettre à jour l'entité existante
                self.memory_graph["entities"][existing_id]["type"] = entity_type
                if attributes:
                    self.memory_graph["entities"][existing_id]["attributes"].update(attributes)
                self.memory_graph["entities"][existing_id]["last_updated"] = datetime.now().isoformat()
                
                # Mettre à jour les nouveaux champs
                self.memory_graph["entities"][existing_id]["confidence"] = confidence
                self.memory_graph["entities"][existing_id]["valid_from"] = valid_from
                if valid_to:
                    self.memory_graph["entities"][existing_id]["valid_to"] = valid_to
                
                return existing_id
            
            # Créer une nouvelle entité
            entity_id = self._generate_entity_id(name)
            self.memory_graph["entities"][entity_id] = {
                "name": name,
                "type": entity_type,
                "attributes": attributes or {},
                "last_updated": datetime.now().isoformat(),
                "confidence": confidence,
                "valid_from": valid_from,
                "history": []  # Historique vide pour les nouvelles entités
            }
            
            # Ajouter valid_to si spécifié
            if valid_to:
                self.memory_graph["entities"][entity_id]["valid_to"] = valid_to
            
            if not batched:
                self._save_graph()
                logger.info(f"Entité ajoutée: {name} ({entity_id}) avec confiance {confidence:.2f}")

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
    
    def add_relation(self, source_id: str, relation: str, target_id: str, 
                    confidence: float = 0.9, valid_from: str = None, valid_to: str = None, batched: bool = False) -> bool:

        """
        Ajoute une relation entre deux entités.
        
        Args:
            source_id: ID de l'entité source
            relation: Type de relation
            target_id: ID de l'entité cible
            confidence: Niveau de confiance (0-1)
            valid_from: Date ISO de début de validité (si None, date courante)
            valid_to: Date ISO de fin de validité (si None, pas de limite)
            
        Returns:
            True si la relation a été ajoutée avec succès
        """
        try:
            # Vérifier que les entités existent
            if source_id not in self.memory_graph["entities"] or target_id not in self.memory_graph["entities"]:
                logger.warning(f"Tentative d'ajout de relation avec des entités inexistantes: {source_id}, {target_id}")
                return False
            
            # Si valid_from n'est pas spécifié, utiliser la date courante
            if valid_from is None:
                valid_from = datetime.now().isoformat()
                
            # Vérifier si la relation existe déjà
            for rel in self.memory_graph["relations"]:
                if rel["source"] == source_id and rel["relation"] == relation and rel["target"] == target_id:
                    # Mettre à jour la relation existante
                    rel["confidence"] = confidence
                    rel["timestamp"] = datetime.now().isoformat()
                    rel["valid_from"] = valid_from
                    if valid_to:
                        rel["valid_to"] = valid_to
                    self._save_graph()
                    return True
            
            # Ajouter la nouvelle relation
            new_relation = {
                "source": source_id,
                "relation": relation,
                "target": target_id,
                "confidence": confidence,
                "timestamp": datetime.now().isoformat(),
                "valid_from": valid_from
            }
            
            # Ajouter valid_to si spécifié
            if valid_to:
                new_relation["valid_to"] = valid_to
                
            self.memory_graph["relations"].append(new_relation)
            
            if not batched:
                self._save_graph()
                logger.info(f"Relation ajoutée: {source_id} -{relation}-> {target_id} avec confiance {confidence:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout de relation: {str(e)}")
            return False
    
    def query_relations(self, entity_id: str, relation_type: Optional[str] = None,
                       include_expired: bool = False) -> List[Dict[str, Any]]:
        """
        Interroge les relations pour une entité donnée.
        
        Args:
            entity_id: ID de l'entité
            relation_type: Type de relation spécifique (optionnel)
            include_expired: Inclure les relations expirées
            
        Returns:
            Liste des relations correspondantes
        """
        results = []
        
        try:
            current_date = datetime.now().isoformat()
            
            for rel in self.memory_graph["relations"]:
                # Vérifier la date de validité si on n'inclut pas les relations expirées
                if not include_expired and "valid_to" in rel and rel["valid_to"] < current_date:
                    continue
                    
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
                            "timestamp": rel["timestamp"],
                            "valid_from": rel.get("valid_from"),
                            "valid_to": rel.get("valid_to")
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
                            "timestamp": rel["timestamp"],
                            "valid_from": rel.get("valid_from"),
                            "valid_to": rel.get("valid_to")
                        })
            
            return results
            
        except Exception as e:
            logger.error(f"Erreur lors de la requête de relations: {str(e)}")
            return []
    
    def get_all_entities(self, include_expired: bool = False) -> List[Dict[str, Any]]:
        """
        Récupère toutes les entités du graphe avec leurs attributs.
        
        Args:
            include_expired: Inclure les entités expirées
            
        Returns:
            Liste de toutes les entités
        """
        entities = []
        current_date = datetime.now().isoformat()
        
        try:
            for entity_id, entity_data in self.memory_graph["entities"].items():
                # Vérifier la date de validité si on n'inclut pas les entités expirées
                if not include_expired and "valid_to" in entity_data and entity_data["valid_to"] < current_date:
                    continue
                    
                # Copier l'entité et ajouter son ID
                entity_copy = entity_data.copy()
                entity_copy["entity_id"] = entity_id
                
                entities.append(entity_copy)
                
            return entities
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de toutes les entités: {str(e)}")
            return []
    
    def get_all_relations(self, include_expired: bool = False) -> List[Dict[str, Any]]:
        """
        Récupère toutes les relations du graphe.
        
        Args:
            include_expired: Inclure les relations expirées
            
        Returns:
            Liste de toutes les relations avec des informations sur les entités connectées
        """
        relations = []
        current_date = datetime.now().isoformat()
        
        try:
            for relation in self.memory_graph["relations"]:
                # Vérifier la date de validité si on n'inclut pas les relations expirées
                if not include_expired and "valid_to" in relation and relation["valid_to"] < current_date:
                    continue
                    
                # Enrichir la relation avec des informations sur les entités
                source_entity = self.memory_graph["entities"].get(relation["source"], {})
                target_entity = self.memory_graph["entities"].get(relation["target"], {})
                
                enriched_relation = relation.copy()
                enriched_relation["source_name"] = source_entity.get("name", "Inconnu")
                enriched_relation["target_name"] = target_entity.get("name", "Inconnu")
                
                relations.append(enriched_relation)
                
            return relations
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de toutes les relations: {str(e)}")
            return []
            
    def get_entity_history(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Récupère l'historique complet d'une entité.
        
        Args:
            entity_id: ID de l'entité
            
        Returns:
            Liste des changements historiques de l'entité
        """
        try:
            if entity_id not in self.memory_graph["entities"]:
                return []
                
            entity = self.memory_graph["entities"][entity_id]
            
            # Commencer par l'état actuel
            history = [{
                "timestamp": entity.get("last_updated"),
                "state": {
                    "name": entity.get("name"),
                    "type": entity.get("type"),
                    "attributes": entity.get("attributes", {}),
                    "confidence": entity.get("confidence"),
                    "valid_from": entity.get("valid_from"),
                    "valid_to": entity.get("valid_to")
                }
            }]
            
            # Ajouter l'historique sauvegardé
            if "history" in entity:
                for entry in entity["history"]:
                    history.append({
                        "timestamp": entry.get("timestamp"),
                        "state": entry.get("old_value", {})
                    })
            
            # Trier par timestamp, plus récent d'abord
            history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            return history
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'historique de l'entité {entity_id}: {str(e)}")
            return []
    
    async def extract_entities_from_text(self, text: str, confidence: float = 0.7) -> List[Dict[str, Any]]:
        """
        Extrait des entités d'un texte pour enrichir le graphe.
        
        Args:
            text: Texte à analyser
            confidence: Niveau de confiance par défaut pour les entités extraites
            
        Returns:
            Liste des entités extraites
        """
        try:
            # Utiliser le LLM pour extraire les entités
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
                                "type": mapped_type,
                                "confidence": confidence
                            })
                
                return extracted_entities
                
            except json.JSONDecodeError:
                logger.warning(f"Réponse non parsable: {response}")
                return []
                
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction d'entités: {str(e)}")
            return []
    




    async def extract_relations_from_text(self, text: str, confidence: float = 0.7) -> List[Dict[str, Any]]:
        """
        Extrait des relations d'un texte pour enrichir le graphe.
        
        Args:
            text: Texte à analyser
            confidence: Niveau de confiance par défaut pour les relations extraites
            
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
            
            # CORRECTION : Échapper les accolades dans l'exemple JSON
            prompt = f"""Identifie les relations entre ces entités extraites du texte:
    {entities_list}

    Texte original: {text}

    Retourne une liste de relations au format JSON sous forme de tableau où chaque élément contient:
    - "source": nom de l'entité source
    - "relation": type de relation (possède, est situé à, aime, connaît, etc.)
    - "target": nom de l'entité cible
    - "confidence": niveau de confiance (0.0 à 1.0)

    Retourne UNIQUEMENT le tableau JSON, sans aucun texte d'explication avant ou après.
    Exemple: [{{"source": "Jean", "relation": "possède", "target": "voiture", "confidence": 0.9}}]

    Ne crée des relations que si elles sont clairement exprimées dans le texte.
    """
            
            response = await model_manager.generate_response(prompt, complexity="medium")
            
            try:
                # Nettoyer la réponse
                import re
                json_match = re.search(r'(\[.*?\])', response, re.DOTALL)
                
                if not json_match:
                    logger.warning(f"Aucun JSON trouvé dans la réponse: {response}")
                    return []
                
                clean_response = json_match.group(1)
                
                # Nettoyage supplémentaire
                clean_response = clean_response.replace("'", '"')  # Remplacer les apostrophes par des guillemets
                clean_response = re.sub(r',\s*]', ']', clean_response)  # Supprimer les virgules finales
                
                # Log pour le debug
                logger.debug(f"JSON nettoyé avant parsing: {clean_response}")
                
                # Essai de parsing
                try:
                    relations_data = json.loads(clean_response)
                    
                    # Vérification des données
                    valid_relations = []
                    for relation in relations_data:
                        if all(k in relation for k in ['source', 'relation', 'target']):
                            # S'assurer que confidence est un float
                            if 'confidence' not in relation:
                                relation['confidence'] = confidence
                            else:
                                try:
                                    relation['confidence'] = float(relation['confidence'])
                                except:
                                    relation['confidence'] = confidence
                            
                            valid_relations.append(relation)
                    
                    return valid_relations
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Erreur JSON: {e}, Réponse: {clean_response}")
                    
                    # Tentative de récupération avec ast.literal_eval
                    import ast
                    try:
                        relations_data = ast.literal_eval(clean_response)
                        logger.info(f"Récupération réussie avec ast.literal_eval - {len(relations_data)} relations trouvées")
                        return relations_data
                    except:
                        logger.warning(f"Échec de la récupération avec ast.literal_eval")
                        return []
                    
            except Exception as e:
                logger.warning(f"Réponse de relations non parsable: {response}\nErreur: {str(e)}")
                return []
                
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction de relations: {str(e)}")
            return []




    async def update_graph_from_text(self, text: str, confidence: float = 0.7, valid_from: str = None, valid_to: str = None) -> Dict[str, int]:
        """
        Met à jour le graphe de connaissances à partir d'un texte.
        
        Args:
            text: Texte à analyser
            confidence: Niveau de confiance par défaut
            valid_from: Date ISO de début de validité (si None, date courante)
            valid_to: Date ISO de fin de validité (si None, pas de limite)
            
        Returns:
            Statistiques sur les mises à jour (entités et relations ajoutées)
        """
        try:
            # 1. Extraire les entités et les ajouter au graphe
            extracted_entities = await self.extract_entities_from_text(text, confidence=confidence)
            
            entity_ids = {}
            entities_added = 0
            
            for entity in extracted_entities:
                entity_id = self.add_entity(
                    name=entity["name"],
                    entity_type=entity["type"],
                    confidence=entity.get("confidence", confidence),
                    valid_from=valid_from,
                    valid_to=valid_to,
                    batched=True
                )
                if entity_id:
                    entity_ids[entity["name"]] = entity_id
                    entities_added += 1
            
            # 2. Extraire les relations et les ajouter au graphe
            extracted_relations = await self.extract_relations_from_text(text, confidence=confidence)
            
            # Log détaillé des relations extraites
            logger.info(f"Relations extraites ({len(extracted_relations)}): {json.dumps(extracted_relations, ensure_ascii=False)}")
            logger.info(f"Entités disponibles: {entity_ids}")
            
            relations_added = 0
            failed_relations = []
            
            for relation in extracted_relations:
                source_name = relation.get("source")
                target_name = relation.get("target")
                relation_type = relation.get("relation")
                
                logger.debug(f"Traitement relation: {source_name} -{relation_type}-> {target_name}")
                
                # Vérifier que les entités existent
                if source_name in entity_ids and target_name in entity_ids:
                    source_id = entity_ids[source_name]
                    target_id = entity_ids[target_name]
                    
                    relation_confidence = relation.get("confidence", confidence)
                    success = self.add_relation(
                        source_id=source_id, 
                        relation=relation_type, 
                        target_id=target_id, 
                        confidence=relation_confidence,
                        valid_from=valid_from, 
                        valid_to=valid_to,
                        batched=True
                    )
                    
                    if success:
                        relations_added += 1
                        logger.debug(f"Relation ajoutée: {source_name} ({source_id}) -{relation_type}-> {target_name} ({target_id})")
                    else:
                        failed_relations.append(f"{source_name} -> {target_name}")
                else:
                    # Entités non trouvées, on les crée au besoin
                    if source_name not in entity_ids:
                        logger.debug(f"Entité source '{source_name}' non trouvée, création automatique")
                        source_id = self.add_entity(
                            name=source_name,
                            entity_type="concept",  # Type par défaut
                            confidence=confidence * 0.8,  # Confiance réduite car entité implicite
                            valid_from=valid_from,
                            valid_to=valid_to
                        )
                        if source_id:
                            entity_ids[source_name] = source_id
                    else:
                        source_id = entity_ids[source_name]
                        
                    if target_name not in entity_ids:
                        logger.debug(f"Entité cible '{target_name}' non trouvée, création automatique")
                        target_id = self.add_entity(
                            name=target_name,
                            entity_type="concept",  # Type par défaut
                            confidence=confidence * 0.8,  # Confiance réduite car entité implicite
                            valid_from=valid_from,
                            valid_to=valid_to
                        )
                        if target_id:
                            entity_ids[target_name] = target_id
                    else:
                        target_id = entity_ids[target_name]
                    
                    # Ajouter la relation si les deux entités ont été créées
                    if source_id and target_id:
                        relation_confidence = relation.get("confidence", confidence) * 0.8  # Confiance réduite
                        if self.add_relation(
                            source_id=source_id, 
                            relation=relation_type, 
                            target_id=target_id, 
                            confidence=relation_confidence,
                            valid_from=valid_from, 
                            valid_to=valid_to
                        ):
                            relations_added += 1
                            logger.debug(f"Relation ajoutée après création d'entités: {source_name} ({source_id}) -{relation_type}-> {target_name} ({target_id})")
            
            if failed_relations:
                logger.warning(f"Échec d'ajout pour {len(failed_relations)} relations: {', '.join(failed_relations)}")
            
            self._save_graph()

            return {
                "entities_added": entities_added,
                "relations_added": relations_added
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du graphe: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
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




    def reload_rules(self):
        """
        Recharge les règles de post-traitement depuis le fichier de règles.
        """
        try:
            rules_path = os.path.join(config.data_dir, "memories", "symbolic_rules.json")
            if os.path.exists(rules_path):
                with open(rules_path, 'r', encoding='utf-8') as f:
                    rules = json.load(f)
                    
                    # Mettre à jour les règles en mémoire
                    self.entity_aliases = rules.get("entity_aliases", {})
                    self.entity_types = rules.get("entity_types", {})
                    self.relation_rewrites = rules.get("relation_rewrites", {})
                    
                    logger.info("Règles symboliques rechargées avec succès")
                    return True
        except Exception as e:
            logger.error(f"Erreur lors du rechargement des règles: {str(e)}")
        
        return False



# Instance globale du gestionnaire de mémoire symbolique
symbolic_memory = SymbolicMemory()




##########################################################################################

