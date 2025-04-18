"""
Module d'extraction et de gestion des informations personnelles autonome.
Système permettant à Nova de détecter et mémoriser intelligemment des informations 
personnelles sans règles codées en dur.
"""
import os
import json
import logging
import re
from typing import Dict, List, Any, Optional
from datetime import datetime

from backend.models.model_manager import model_manager
from backend.memory.vector_store import vector_store
from backend.memory.symbolic_memory import symbolic_memory

logger = logging.getLogger(__name__)

class ContextualInformationExtractor:
    """
    Extrait de manière autonome les informations personnelles importantes
    à partir de conversations, sans règles codées en dur.
    """
    
    def __init__(self, model_manager, vector_store, symbolic_memory):
        self.model_manager = model_manager
        self.vector_store = vector_store
        self.symbolic_memory = symbolic_memory
        self.conversation_context = []
        self.detected_entities_cache = {}
        
    async def process_message(self, message: str, user_id: str) -> Dict[str, Any]:
        """
        Traite un message pour en extraire des informations personnelles
        et évalue leur importance pour la mémorisation.
        """
        # 1. Mettre à jour le contexte de conversation
        self.conversation_context.append(message)
        context_window = self.conversation_context[-5:] # Garder les 5 derniers messages
        
        # 2. Extraction générique d'entités à l'aide du LLM
        entities = await self._extract_entities(message)
        
        # 3. Évaluation de la pertinence et de la durabilité
        relevance_scores = await self._evaluate_relevance(entities, context_window)
        
        # 4. Mémorisation sélective basée sur les scores
        memory_results = await self._store_information(entities, relevance_scores, user_id)
        
        return memory_results
    
    async def _extract_entities(self, message: str) -> List[Dict[str, Any]]:
        """
        Utilise le LLM pour extraire des entités personnelles sans règles prédéfinies.
        Identifie tout type d'information qui pourrait être personnelle ou utile.
        """
        prompt = """
        Extrait toutes les informations personnelles ou préférences du message suivant.
        Cherche tout type d'information qui pourrait être utile à mémoriser sur la personne.
        
        Message: "{message}"
        
        Retourne un JSON avec ce format:
        [
          {{
            "type": "nom|prénom|adresse|préférence|date_naissance|etc",
            "value": "la valeur extraite",
            "confidence": 0.0-1.0,
            "context": "contexte d'extraction"
          }}
        ]
        
        Ne retourne que les informations clairement exprimées dans le message.
        """
        
        prompt = prompt.format(message=message)
        
        try:
            response = await self.model_manager.generate_response(prompt, complexity="low")
            
            # Extraire et parser le JSON
            import json
            import re
            
            # Trouver le bloc JSON
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if not json_match:
                return []
                
            entities = json.loads(json_match.group(0))
            return entities
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction d'entités: {str(e)}")
            return []
    
    async def _evaluate_relevance(self, entities: List[Dict[str, Any]], 
                                 context: List[str]) -> Dict[str, float]:
        """
        Évalue la pertinence des entités extraites et détermine
        si elles méritent d'être mémorisées à court ou long terme.
        """
        if not entities:
            return {}
            
        # Contexte complet pour évaluation
        full_context = "\n".join(context)
        
        # Liste des entités à évaluer
        entities_list = "\n".join([
            f"- Type: {e['type']}, Valeur: {e['value']}" 
            for e in entities
        ])
        
        prompt = """
        Évalue la pertinence et l'importance de mémorisation des informations suivantes
        extraites de la conversation.
        
        Contexte de conversation:
        {context}
        
        Informations extraites:
        {entities}
        
        Pour chaque information, évalue:
        1. Importance (0.0-1.0): à quel point cette information est importante à retenir sur l'utilisateur
        2. Durabilité (0.0-1.0): si cette information est temporaire ou durable dans le temps
        3. Certitude (0.0-1.0): à quel point l'information semble certaine et non ambiguë
        
        Retourne un JSON avec ce format:
        {{
          "entity_index_0": {{ "importance": 0.9, "durability": 0.8, "certainty": 0.95 }},
          "entity_index_1": {{ "importance": 0.4, "durability": 0.7, "certainty": 0.6 }}
        }}
        
        Où les index correspondent à la position de l'entité dans la liste fournie.
        """
        
        prompt = prompt.format(context=full_context, entities=entities_list)
        
        try:
            response = await self.model_manager.generate_response(prompt, complexity="low")
            
            # Extraire et parser le JSON
            import json
            import re
            
            # Trouver le bloc JSON
            json_match = re.search(r'{.*}', response, re.DOTALL)
            if not json_match:
                return {}
                
            relevance_scores = json.loads(json_match.group(0))
            
            # Calculer un score composite pour chaque entité
            composite_scores = {}
            for idx, scores in relevance_scores.items():
                entity_idx = int(idx.split('_')[-1])
                
                # Score composite = moyenne pondérée des trois facteurs
                composite = (
                    scores.get('importance', 0) * 0.4 +
                    scores.get('durability', 0) * 0.3 +
                    scores.get('certainty', 0) * 0.3
                )
                
                composite_scores[entity_idx] = {
                    'composite_score': composite,
                    'details': scores
                }
                
            return composite_scores
                
        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation de pertinence: {str(e)}")
            return {}
    
    async def _store_information(self, entities: List[Dict[str, Any]], 
                               relevance_scores: Dict[int, Dict[str, Any]],
                               user_id: str) -> Dict[str, Any]:
        """
        Stocke les informations dans le système de mémoire approprié
        en fonction de leur pertinence et durabilité.
        """
        results = {
            'stored': [],
            'temporary': [],
            'ignored': []
        }
        
        # Filtrer et stocker chaque entité selon son score
        for idx, entity in enumerate(entities):
            if idx not in relevance_scores:
                results['ignored'].append(entity)
                continue
                
            scores = relevance_scores[idx]
            composite_score = scores['composite_score']
            details = scores['details']
            
            # Décider où stocker l'entité
            if composite_score >= 0.7:  # Mémorisation durable
                # Stocker dans la mémoire symbolique
                entity_type = self._map_entity_type(entity['type'])
                
                try:
                    # Créer une entité symbolique
                    entity_id = self.symbolic_memory.add_entity(
                        name=entity['value'],
                        entity_type=entity_type,
                        attributes={
                            'user_id': user_id,
                            'source': 'conversation',
                            'extracted_type': entity['type'],
                            'context': entity.get('context', '')
                        },
                        confidence=details.get('certainty', 0.7)
                    )
                    
                    # Créer une relation "possède" entre l'utilisateur et l'entité
                    user_entity_id = self.symbolic_memory.find_entity_by_name(user_id) or \
                                    self.symbolic_memory.add_entity(
                                        name=user_id, 
                                        entity_type='user'
                                    )
                    
                    # Ajouter une relation entre l'utilisateur et l'entité
                    relation_type = self._determine_relation_type(entity['type'])
                    self.symbolic_memory.add_relation(
                        source_id=user_entity_id,
                        relation=relation_type,
                        target_id=entity_id,
                        confidence=details.get('certainty', 0.7)
                    )
                    
                    # Enregistrer aussi dans la mémoire vectorielle pour recherche
                    vector_id = self.vector_store.add_memory(
                        content=f"L'utilisateur {user_id} a pour {entity['type']} : {entity['value']}",
                        metadata={
                            'entity_type': entity['type'],
                            'entity_value': entity['value'],
                            'user_id': user_id,
                            'symbolic_entity_id': entity_id,
                            'certainty': details.get('certainty', 0.7)
                        },
                        score_pertinence=composite_score
                    )
                    
                    results['stored'].append({
                        'entity': entity,
                        'symbolic_id': entity_id,
                        'vector_id': vector_id,
                        'score': composite_score
                    })
                
                except Exception as e:
                    logger.error(f"Erreur lors du stockage de l'entité: {str(e)}")
                    results['ignored'].append(entity)
                
            elif composite_score >= 0.4:  # Mémorisation temporaire
                # Stocker uniquement dans la mémoire vectorielle
                try:
                    vector_id = self.vector_store.add_memory(
                        content=f"Information temporaire sur {user_id}: {entity['type']} = {entity['value']}",
                        metadata={
                            'entity_type': entity['type'],
                            'entity_value': entity['value'],
                            'user_id': user_id,
                            'temporary': True
                        },
                        score_pertinence=composite_score
                    )
                    
                    results['temporary'].append({
                        'entity': entity,
                        'vector_id': vector_id,
                        'score': composite_score
                    })
                
                except Exception as e:
                    logger.error(f"Erreur lors du stockage temporaire de l'entité: {str(e)}")
                    results['ignored'].append(entity)
            
            else:  # Score trop faible, ignorer
                results['ignored'].append(entity)
                
        return results
    
    def _map_entity_type(self, extracted_type: str) -> str:
        """
        Mappe le type d'entité extraite vers un type compatible avec la mémoire symbolique.
        """
        type_mapping = {
            'nom': 'person',
            'prénom': 'person',
            'adresse': 'place',
            'ville': 'place',
            'date_naissance': 'date',
            'préférence': 'preference',
            'hobby': 'preference',
            'travail': 'profession',
            'métier': 'profession',
            'email': 'contact',
            'téléphone': 'contact'
        }
        
        # Recherche de correspondance approximative
        for key, value in type_mapping.items():
            if key in extracted_type.lower():
                return value
        
        return 'attribute'  # Type par défaut
    
    def _determine_relation_type(self, entity_type: str) -> str:
        """
        Détermine le type de relation entre l'utilisateur et l'entité.
        """
        relation_mapping = {
            'nom': 'a_pour_nom',
            'prénom': 'a_pour_prénom',
            'adresse': 'habite_à',
            'ville': 'habite_à',
            'date_naissance': 'est_né_le',
            'préférence': 'préfère',
            'hobby': 'aime',
            'travail': 'travaille_comme',
            'métier': 'exerce',
            'email': 'a_pour_email',
            'téléphone': 'a_pour_téléphone'
        }
        
        # Recherche de correspondance approximative
        for key, value in relation_mapping.items():
            if key in entity_type.lower():
                return value
        
        return 'possède'  # Relation par défaut


class MemoryAdjustmentMonitor:
    """
    Module de surveillance et d'ajustement des informations mémorisées,
    permettant un apprentissage continu basé sur les interactions.
    """
    
    def __init__(self, model_manager, vector_store, symbolic_memory):
        self.model_manager = model_manager
        self.vector_store = vector_store
        self.symbolic_memory = symbolic_memory
        self.user_memories = {}  # Cache de suivi par utilisateur
        
    async def register_user_reaction(self, message_id: str, 
                                   memory_id: str,
                                   reaction: str,
                                   user_id: str) -> None:
        """
        Enregistre la réaction de l'utilisateur à une information mémorisée.
        Permet au système d'apprendre quelles informations sont pertinentes à retenir.
        
        reaction: "correct", "incorrect", "not_important", "important"
        """
        try:
            # Récupérer l'information mémorisée
            memory_metadata = None
            
            if memory_id in self.vector_store.metadata:
                memory_metadata = self.vector_store.metadata[memory_id]
            else:
                # Chercher dans la mémoire symbolique si nécessaire
                for entity_id, entity in self.symbolic_memory.memory_graph["entities"].items():
                    if entity_id == memory_id:
                        memory_metadata = entity
                        break
            
            if not memory_metadata:
                logger.warning(f"Mémoire {memory_id} non trouvée pour ajustement")
                return
            
            # Ajuster les scores selon la réaction
            if reaction in ["correct", "important"]:
                # Augmenter le score de pertinence pour ce type d'information
                adjustment = 0.1
                entity_type = memory_metadata.get("entity_type") or memory_metadata.get("type")
                
                # Enregistrer cette préférence dans le cache utilisateur
                if user_id not in self.user_memories:
                    self.user_memories[user_id] = {
                        "important_types": {},
                        "ignored_types": {}
                    }
                
                # Incrémenter le compteur pour ce type
                if entity_type:
                    if entity_type not in self.user_memories[user_id]["important_types"]:
                        self.user_memories[user_id]["important_types"][entity_type] = 0
                    self.user_memories[user_id]["important_types"][entity_type] += 1
                
                # Si l'information était temporaire, peut-être la rendre permanente
                if memory_metadata.get("temporary") and reaction == "important":
                    await self._promote_to_permanent(memory_id, user_id)
                
            elif reaction in ["incorrect", "not_important"]:
                # Diminuer le score de pertinence
                adjustment = -0.1
                entity_type = memory_metadata.get("entity_type") or memory_metadata.get("type")
                
                # Enregistrer cette préférence
                if user_id not in self.user_memories:
                    self.user_memories[user_id] = {
                        "important_types": {},
                        "ignored_types": {}
                    }
                
                # Incrémenter le compteur pour ce type à ignorer
                if entity_type:
                    if entity_type not in self.user_memories[user_id]["ignored_types"]:
                        self.user_memories[user_id]["ignored_types"][entity_type] = 0
                    self.user_memories[user_id]["ignored_types"][entity_type] += 1
                
                # Si l'information est incorrecte, la supprimer
                if reaction == "incorrect":
                    if memory_id in self.vector_store.metadata:
                        self.vector_store.delete_memory(memory_id)
                    
                    # Chercher aussi dans la mémoire symbolique
                    entity_id = memory_metadata.get("symbolic_entity_id") or memory_id
                    
                    if entity_id in self.symbolic_memory.memory_graph["entities"]:
                        # Marquer comme supprimé plutôt que de supprimer complètement
                        self.symbolic_memory.memory_graph["entities"][entity_id]["deleted"] = True
                        self.symbolic_memory.memory_graph["entities"][entity_id]["deletion_reason"] = "incorrect_information"
                        self.symbolic_memory._save_graph()
            
            # Sauvegarder les préférences utilisateur pour l'apprentissage continu
            await self._update_user_memory_preferences(user_id)
            
        except Exception as e:
            logger.error(f"Erreur lors de l'ajustement de la mémoire: {str(e)}")
    
    async def _promote_to_permanent(self, memory_id: str, user_id: str) -> None:
        """
        Promeut une information temporaire en information permanente.
        """
        try:
            if memory_id not in self.vector_store.metadata:
                return
                
            memory_data = self.vector_store.metadata[memory_id]
            
            if not memory_data.get("temporary"):
                return  # Déjà permanente
            
            # Extraire les informations nécessaires
            entity_type = memory_data.get("entity_type")
            entity_value = memory_data.get("entity_value")
            
            if not entity_type or not entity_value:
                return
            
            # Créer l'entité dans la mémoire symbolique
            symbolic_type = self._map_entity_type(entity_type)
            
            entity_id = self.symbolic_memory.add_entity(
                name=entity_value,
                entity_type=symbolic_type,
                attributes={
                    'user_id': user_id,
                    'source': 'conversation',
                    'extracted_type': entity_type,
                    'promoted_from_temporary': True
                },
                confidence=memory_data.get("score_pertinence", 0.7)
            )
            
            # Créer la relation utilisateur-entité
            user_entity_id = self.symbolic_memory.find_entity_by_name(user_id) or \
                            self.symbolic_memory.add_entity(
                                name=user_id, 
                                entity_type='user'
                            )
            
            relation_type = self._determine_relation_type(entity_type)
            self.symbolic_memory.add_relation(
                source_id=user_entity_id,
                relation=relation_type,
                target_id=entity_id,
                confidence=memory_data.get("score_pertinence", 0.7)
            )
            
            # Mettre à jour la mémoire vectorielle
            self.vector_store.metadata[memory_id]["temporary"] = False
            self.vector_store.metadata[memory_id]["symbolic_entity_id"] = entity_id
            self.vector_store.metadata[memory_id]["promoted_at"] = datetime.now().isoformat()
            self.vector_store._save_metadata()
            
        except Exception as e:
            logger.error(f"Erreur lors de la promotion de la mémoire {memory_id}: {str(e)}")
    
    async def _update_user_memory_preferences(self, user_id: str) -> None:
        """
        Met à jour les préférences de mémorisation de l'utilisateur,
        permettant au système d'apprendre ce qui doit être mémorisé.
        """
        if user_id not in self.user_memories:
            return
            
        user_prefs = self.user_memories[user_id]
        
        # Stocker ces préférences dans la mémoire symbolique
        user_entity_id = self.symbolic_memory.find_entity_by_name(user_id) or \
                         self.symbolic_memory.add_entity(
                            name=user_id, 
                            entity_type='user'
                         )
        
        # Mettre à jour les attributs de l'entité utilisateur
        if user_entity_id in self.symbolic_memory.memory_graph["entities"]:
            # Important types
            if "important_types" not in self.symbolic_memory.memory_graph["entities"][user_entity_id]["attributes"]:
                self.symbolic_memory.memory_graph["entities"][user_entity_id]["attributes"]["important_types"] = {}
            
            self.symbolic_memory.memory_graph["entities"][user_entity_id]["attributes"]["important_types"] = \
                user_prefs["important_types"]
            
            # Ignored types
            if "ignored_types" not in self.symbolic_memory.memory_graph["entities"][user_entity_id]["attributes"]:
                self.symbolic_memory.memory_graph["entities"][user_entity_id]["attributes"]["ignored_types"] = {}
            
            self.symbolic_memory.memory_graph["entities"][user_entity_id]["attributes"]["ignored_types"] = \
                user_prefs["ignored_types"]
            
            # Sauvegarder les modifications
            self.symbolic_memory._save_graph()
    
    async def get_user_memory_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Récupère les préférences de mémorisation de l'utilisateur.
        """
        # Chercher d'abord dans le cache
        if user_id in self.user_memories:
            return self.user_memories[user_id]
        
        # Sinon chercher dans la mémoire symbolique
        user_entity_id = self.symbolic_memory.find_entity_by_name(user_id)
        
        if user_entity_id and user_entity_id in self.symbolic_memory.memory_graph["entities"]:
            attributes = self.symbolic_memory.memory_graph["entities"][user_entity_id]["attributes"]
            
            prefs = {
                "important_types": attributes.get("important_types", {}),
                "ignored_types": attributes.get("ignored_types", {})
            }
            
            # Mettre à jour le cache
            self.user_memories[user_id] = prefs
            
            return prefs
        
        # Créer des préférences par défaut
        default_prefs = {
            "important_types": {},
            "ignored_types": {}
        }
        
        self.user_memories[user_id] = default_prefs
        return default_prefs
    
    def _map_entity_type(self, extracted_type: str) -> str:
        """
        Mappe le type d'entité extraite vers un type compatible avec la mémoire symbolique.
        """
        type_mapping = {
            'nom': 'person',
            'prénom': 'person',
            'adresse': 'place',
            'ville': 'place',
            'date_naissance': 'date',
            'préférence': 'preference',
            'hobby': 'preference',
            'travail': 'profession',
            'métier': 'profession',
            'email': 'contact',
            'téléphone': 'contact'
        }
        
        # Recherche de correspondance approximative
        for key, value in type_mapping.items():
            if key in extracted_type.lower():
                return value
        
        return 'attribute'  # Type par défaut
    
    def _determine_relation_type(self, entity_type: str) -> str:
        """
        Détermine le type de relation entre l'utilisateur et l'entité.
        """
        relation_mapping = {
            'nom': 'a_pour_nom',
            'prénom': 'a_pour_prénom',
            'adresse': 'habite_à',
            'ville': 'habite_à',
            'date_naissance': 'est_né_le',
            'préférence': 'préfère',
            'hobby': 'aime',
            'travail': 'travaille_comme',
            'métier': 'exerce',
            'email': 'a_pour_email',
            'téléphone': 'a_pour_téléphone'
        }
        
        # Recherche de correspondance approximative
        for key, value in relation_mapping.items():
            if key in entity_type.lower():
                return value
        
        return 'possède'  # Relation par défaut


class ConversationMemoryProcessor:
    """
    Intègre les extracteurs d'information dans le processus de conversation.
    """
    
    def __init__(self, model_manager, vector_store, symbolic_memory):
        self.model_manager = model_manager
        self.extractor = ContextualInformationExtractor(
            model_manager, vector_store, symbolic_memory
        )
        self.adjustment_monitor = MemoryAdjustmentMonitor(
            model_manager, vector_store, symbolic_memory
        )
        self.last_memory_operations = {}  # Cache des dernières opérations par utilisateur
    
    async def process_conversation_message(self, user_message: str, user_id: str) -> Dict[str, Any]:
        """
        Traite un message de conversation pour extraire et mémoriser des informations.
        Retourne un résumé des opérations effectuées.
        """
        # Extraire et évaluer les informations
        memory_results = await self.extractor.process_message(user_message, user_id)
        
        # Conserver les résultats récents pour ce message
        self.last_memory_operations[user_id] = memory_results
        
        # Récupérer les préférences de mémorisation de l'utilisateur
        user_prefs = await self.adjustment_monitor.get_user_memory_preferences(user_id)
        
        # Appliquer les préférences pour ajuster la mémorisation 
        # (ignorer les types que l'utilisateur ne veut pas mémoriser)
        for memory_id in memory_results.get('stored', []):
            entity_type = memory_id['entity']['type']
            
            # Si ce type est souvent marqué comme non important, le supprimer
            if entity_type in user_prefs["ignored_types"] and user_prefs["ignored_types"][entity_type] > 2:
                # Supprimer cette information
                if 'vector_id' in memory_id:
                    self.vector_store.delete_memory(str(memory_id['vector_id']))
                
                if 'symbolic_id' in memory_id:
                    # Marquer comme supprimé
                    entity_id = memory_id['symbolic_id']
                    if entity_id in self.symbolic_memory.memory_graph["entities"]:
                        self.symbolic_memory.memory_graph["entities"][entity_id]["deleted"] = True
                        self.symbolic_memory.memory_graph["entities"][entity_id]["deletion_reason"] = "user_preference"
                        self.symbolic_memory._save_graph()
        
        # Simplifier les résultats pour la réponse
        summary = {
            'stored_count': len(memory_results.get('stored', [])),
            'temporary_count': len(memory_results.get('temporary', [])),
            'ignored_count': len(memory_results.get('ignored', [])),
            'stored_types': [item['entity']['type'] for item in memory_results.get('stored', [])],
            'temporary_types': [item['entity']['type'] for item in memory_results.get('temporary', [])]
        }
        
        return summary
    
    async def should_acknowledge_memory(self, memory_results: Dict[str, Any]) -> bool:
        """
        Détermine si l'assistant doit mentionner qu'il a mémorisé quelque chose.
        """
        # Si des informations importantes ont été mémorisées, peut-être le mentionner
        if memory_results.get('stored_count', 0) > 0:
            # Mais pas trop souvent pour ne pas être ennuyeux
            # Logique aléatoire simple ici, peut être améliorée
            import random
            return random.random() < 0.3  # 30% de chances de mentionner la mémorisation
            
        return False
    
    def get_memory_acknowledgment(self, memory_results: Dict[str, Any]) -> str:
        """
        Génère une mention naturelle que l'assistant a mémorisé quelque chose.
        """
        if memory_results.get('stored_count', 0) == 0:
            return ""
            
        stored_types = memory_results.get('stored_types', [])
        
        if len(stored_types) == 1:
            return f"(J'ai noté votre {stored_types[0]})"
        elif len(stored_types) > 1:
            types_str = ", ".join(stored_types[:-1]) + " et " + stored_types[-1]
            return f"(J'ai mémorisé ces informations : {types_str})"
            
        return "(J'ai mémorisé cette information)"
    
    async def register_user_reaction(self, message_id: str, memory_id: str, 
                                   reaction: str, user_id: str) -> None:
        """
        Enregistre la réaction de l'utilisateur à une information mémorisée.
        """
        await self.adjustment_monitor.register_user_reaction(
            message_id, memory_id, reaction, user_id
        )


class PersonalContextRetriever:
    """
    Récupère des informations personnelles pertinentes
    pour enrichir le contexte de conversation.
    """
    
    def __init__(self, model_manager, vector_store, symbolic_memory):
        self.model_manager = model_manager
        self.vector_store = vector_store
        self.symbolic_memory = symbolic_memory
        
    async def get_relevant_context(self, message: str, user_id: str) -> str:
        """
        Récupère le contexte personnel pertinent pour un message donné.
        Détecte les questions sur l'identité de l'utilisateur et autres informations personnelles.
        
        Args:
            message: Le message de l'utilisateur
            user_id: L'identifiant de l'utilisateur
            
        Returns:
            Contexte personnel formaté
        """
        try:
            # 0. Vérifier s'il s'agit d'une question sur l'identité de l'utilisateur
            identity_question = self._is_identity_question(message)
            
            # 1. Extraire les sujets/thèmes potentiels du message
            topics = await self._extract_topics(message)
            
            # Ajouter explicitement "identité" ou "personnel" si c'est une question sur l'identité
            if identity_question and "identité" not in topics and "personnel" not in topics:
                topics.append("identité")
                topics.append("personnel")
            
            # 2. Rechercher dans la mémoire vectorielle
            vector_results = await self._search_vector_memory(message, user_id)
            
            # 3. Rechercher dans la mémoire symbolique
            symbolic_results = await self._query_symbolic_memory(topics, user_id)
            
            # 4. Ajouter automatiquement le prénom si disponible et qu'on n'a pas d'autres résultats
            if (identity_question or not symbolic_results) and not vector_results:
                user_name = self._get_user_name(user_id)
                if user_name:
                    # Ajouter manuellement cette information aux résultats symboliques
                    symbolic_results.append({
                        "relation": "a_pour_prénom",
                        "value": user_name,
                        "confidence": 1.0
                    })
            
            # 5. Combiner les résultats
            combined_context = self._format_personal_context(
                vector_results, symbolic_results, user_id
            )
            
            # Si c'est une question d'identité et qu'on n'a toujours pas d'information, ajouter une réponse claire
            if identity_question and not combined_context:
                combined_context = f"Aucune information sur le nom ou prénom de l'utilisateur {user_id} n'est disponible."
            
            return combined_context
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du contexte personnel: {str(e)}")
            return ""
        
    
    async def _extract_topics(self, message: str) -> List[str]:
        """
        Extrait les sujets du message pour la recherche contextuelle.
        """
        prompt = """
        Analyse ce message et identifie les sujets clés qui pourraient nécessiter
        des informations personnelles sur l'utilisateur.
        
        Message: "{message}"
        
        Exemples de sujets: famille, travail, préférences, coordonnées, etc.
        Retourne une liste JSON simple de sujets identifiés:
        ["sujet1", "sujet2", "sujet3"]
        
        N'inclus que des sujets clairement liés au message.
        """
        
        prompt = prompt.format(message=message)
        
        try:
            response = await self.model_manager.generate_response(prompt, complexity="low")
            
            # Extraire et parser le JSON
            import json
            import re
            
            # Trouver le bloc JSON
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if not json_match:
                return []
                
            topics = json.loads(json_match.group(0))
            return topics
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction de sujets: {str(e)}")
            return []
    
    async def _search_vector_memory(self, message: str, user_id: str) -> List[Dict[str, Any]]:
        """
        Recherche des informations pertinentes dans la mémoire vectorielle.
        """
        # Effectuer la recherche par similarité
        results = self.vector_store.search_memories(
            query=message,
            k=5,  # Limiter à 5 résultats
            min_score=0.0  # Pas de score minimum pour commencer
        )
        
        # Filtrer pour ne garder que les informations de cet utilisateur
        filtered_results = [
            r for r in results 
            if r.get("metadata", {}).get("user_id") == user_id
        ]
        
        # Trier par score de pertinence
        filtered_results.sort(
            key=lambda x: x.get("score", 0), 
            reverse=True
        )
        
        return filtered_results[:3]  # Limiter aux 3 plus pertinents


    def _is_identity_question(self, message: str) -> bool:
        """
        Détecte si le message est une question sur l'identité de l'utilisateur.
        
        Args:
            message: Le message de l'utilisateur
            
        Returns:
            True si c'est une question sur l'identité, False sinon
        """
        message_lower = message.lower()
        
        # Patterns de questions d'identité
        identity_patterns = [
            "comment je m'appelle", 
            "quel est mon nom", 
            "quel est mon prénom",
            "tu connais mon nom",
            "tu sais comment je m'appelle",
            "qui suis-je",
            "mon identité",
            "c'est quoi mon nom",
            "c'est quoi mon prénom"
        ]
        
        return any(pattern in message_lower for pattern in identity_patterns)


    def _get_user_name(self, user_id: str) -> Optional[str]:
        """
        Récupère le nom/prénom de l'utilisateur directement dans la mémoire symbolique.
        
        Args:
            user_id: L'identifiant de l'utilisateur
            
        Returns:
            Le prénom ou nom de l'utilisateur s'il existe, None sinon
        """
        # Chercher l'entité utilisateur
        user_entity_id = self.symbolic_memory.find_entity_by_name(user_id)
        
        if not user_entity_id:
            return None
        
        # Chercher les relations spécifiques au nom/prénom
        name_relations = ["a_pour_prénom", "a_pour_nom", "s'appelle", "est_nommé"]
        
        # Récupérer toutes les relations
        relations = self.symbolic_memory.query_relations(user_entity_id)
        
        if not relations:
            return None
        
        # Chercher en priorité les relations de type nom/prénom
        for relation in relations:
            relation_type = relation.get("relation", "")
            
            if any(name_rel in relation_type for name_rel in name_relations):
                return relation.get("target_name", "")
        
        # Si on n'a pas trouvé de nom/prénom spécifique, vérifier s'il y a une entité de type personne
        for relation in relations:
            target_type = relation.get("target_type", "")
            
            if target_type == "person":
                return relation.get("target_name", "")
        
        return None


    
    async def _query_symbolic_memory(self, topics: List[str], user_id: str) -> List[Dict[str, Any]]:
        """
        Interroge la mémoire symbolique pour des informations pertinentes.
        """
        results = []
        
        # Trouver l'entité utilisateur
        user_entity_id = self.symbolic_memory.find_entity_by_name(user_id)
        
        if not user_entity_id:
            return results
            
        # Récupérer les relations de l'utilisateur
        relations = self.symbolic_memory.query_relations(user_entity_id)
        
        if not relations:
            return results
            
        # Filtrer par pertinence avec les sujets
        for relation in relations:
            # Vérifier si cette relation est liée à l'un des sujets
            is_relevant = False
            relation_type = relation.get("relation", "")
            
            for topic in topics:
                # Vérifier si le type de relation correspond au sujet
                topic_lower = topic.lower()
                
                # Correspondance simple entre sujets et relations
                if topic_lower in relation_type.lower():
                    is_relevant = True
                    break
                    
                # Correspondances spécifiques
                topic_relation_map = {
                    "famille": ["parent", "enfant", "frère", "soeur", "famille"],
                    "travail": ["travaille", "métier", "profession"],
                    "préférences": ["préfère", "aime", "déteste"],
                    "coordonnées": ["adresse", "téléphone", "email"],
                    "personnel": ["nom", "prénom", "date_naissance"],
                    "localisation": ["habite", "ville", "pays"]
                }
                
                for key, values in topic_relation_map.items():
                    if topic_lower == key:
                        if any(val in relation_type.lower() for val in values):
                            is_relevant = True
                            break
            
            if is_relevant:
                # Ajouter cette relation aux résultats
                target_name = relation.get("target_name", "")
                
                if target_name:
                    results.append({
                        "relation": relation.get("relation", ""),
                        "value": target_name,
                        "confidence": relation.get("confidence", 0.0)
                    })
        
        # Trier par confiance
        results.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        
        return results
    
    def _format_personal_context(self, vector_results: List[Dict[str, Any]], 
                               symbolic_results: List[Dict[str, Any]],
                               user_id: str) -> str:
        """
        Formate les résultats en un contexte utilisable par l'assistant.
        """
        if not vector_results and not symbolic_results:
            return ""
            
        context_parts = [f"Informations connues sur l'utilisateur {user_id}:"]
        
        # Ajouter les informations symboliques (plus structurées)
        if symbolic_results:
            for result in symbolic_results:
                relation = result.get("relation", "").replace("_", " ")
                value = result.get("value", "")
                
                # Formater en langage naturel
                if relation.startswith("a pour"):
                    context_parts.append(f"- {relation.replace('a pour', 'Son').strip()} est {value}")
                elif relation.startswith("est"):
                    context_parts.append(f"- {relation} {value}")
                else:
                    context_parts.append(f"- {relation} {value}")
        
        # Ajouter les informations vectorielles
        if vector_results:
            for result in vector_results:
                content = result.get("content", "")
                
                # Ne pas dupliquer des informations déjà présentes
                if not any(content in part for part in context_parts):
                    # Nettoyer et reformater
                    cleaned = content.replace(f"L'utilisateur {user_id}", "L'utilisateur")
                    cleaned = cleaned.replace(f"Information temporaire sur {user_id}:", "")
                    cleaned = cleaned.strip()
                    
                    if cleaned:
                        context_parts.append(f"- {cleaned}")
        
        return "\n".join(context_parts)