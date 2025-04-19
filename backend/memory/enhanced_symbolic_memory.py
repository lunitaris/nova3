
"""
Extension du système de mémoire symbolique avec intégration ChatGPT facultative.
"""
import os
import json
import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import aiohttp
import backoff

from backend.config import config
from backend.memory.symbolic_memory import symbolic_memory, SymbolicMemory

logger = logging.getLogger(__name__)
from backend.config import OPENAI_API_KEY

class EnhancedSymbolicMemory:
    """
    Extension du gestionnaire de mémoire symbolique avec intégration ChatGPT optionnelle.
    """
    
    def __init__(self, base_memory: SymbolicMemory = None):
        """
        Initialise l'extension de mémoire symbolique.

        Args:
            base_memory: Instance de base de SymbolicMemory
        """
        self.base_memory = base_memory or symbolic_memory
        self.openai_api_key = OPENAI_API_KEY

        # Log pour vérifier si la clé est présente (sécurisé)
        if self.openai_api_key:
            key_length = len(self.openai_api_key)
            first_chars = self.openai_api_key[:4] if key_length > 8 else ""
            last_chars = self.openai_api_key[-4:] if key_length > 8 else ""
            logger.info(f"✅ OpenAI API key configurée!")
        else:
            logger.warning("⚠️ Aucune clé API OpenAI configurée. L'extraction via ChatGPT ne sera pas disponible.")
        
    @property
    def is_chatgpt_enabled(self) -> bool:
        """Vérifie si l'utilisation de ChatGPT est activée dans la configuration."""

        logger.debug(f"⚙️ ChatGPT extraction enabled: {enabled} - "
                    f"Config: {getattr(config.memory, 'use_chatgpt_for_symbolic_memory', False)}, "
                    f"API key available: {bool(self.openai_api_key)}")

        return (
            hasattr(config.memory, "use_chatgpt_for_symbolic_memory") and 
            config.memory.use_chatgpt_for_symbolic_memory and
            self.openai_api_key
        )
        
    @backoff.on_exception(backoff.expo, 
                         (aiohttp.ClientError, asyncio.TimeoutError),
                         max_tries=3)
    async def _call_openai_api(self, prompt: str, model: str = "gpt-3.5-turbo") -> str:
        """
        Appelle l'API OpenAI avec un prompt donné.
        
        Args:
            prompt: Le prompt à envoyer à l'API
            model: Le modèle à utiliser (par défaut gpt-3.5-turbo)
            
        Returns:
            La réponse du modèle en texte
            
        Raises:
            Exception: En cas d'erreur avec l'API
        """
        if not self.openai_api_key:
            raise ValueError("Clé API OpenAI non configurée dans les variables d'environnement")
        
        logger.info(f"📤 Calling OpenAI API with model: {model}")
        logger.debug(f"📤 Prompt: '{prompt[:100]}...'")
        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_api_key}"
            }
            
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "Tu es un assistant d'extraction d'informations précis."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2  # Température basse pour des réponses plus précises
            }
            
            try:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=15  # Timeout de 15 secondes
                ) as response:
                    if response.status != 200:
                        response_text = await response.text()
                        logger.error(f"Erreur API OpenAI: {response.status} - {response_text}")
                        raise Exception(f"Erreur API OpenAI: {response.status}")
                        
                    data = await response.json()
                    return data["choices"][0]["message"]["content"]
            except Exception as e:
                logger.error(f"Erreur lors de l'appel à l'API OpenAI: {str(e)}")
                raise
    
    async def extract_entities_and_relations_with_chatgpt(self, text: str) -> Dict[str, Any]:
        """
        Extrait des entités et relations d'un texte en utilisant ChatGPT.
        
        Args:
            text: Texte à analyser
            
        Returns:
            Dictionnaire contenant les entités et relations extraites
        """
        prompt = f"""Analyse ce texte et extrais-en toutes les entités et relations importantes.

Texte à analyser: 
"{text}"

Pour les entités, identifie le nom, le type (personne, lieu, objet, concept, etc.), et tout attribut pertinent.
Pour les relations, identifie la source, le type de relation, la cible, et un niveau de confiance (0.0 à 1.0).

Réponds UNIQUEMENT au format JSON suivant:
```json
{{
  "entities": [
    {{
      "name": "Nom de l'entité",
      "type": "Type (person, place, device, concept, etc.)",
      "attributes": {{"attr1": "valeur1", "attr2": "valeur2"}},
      "confidence": 0.95
    }}
  ],
  "relations": [
    {{
      "source": "Nom de l'entité source",
      "relation": "Type de relation",
      "target": "Nom de l'entité cible",
      "confidence": 0.9
    }}
  ]
}}
```

Ne fournis que des entités et relations clairement mentionnées dans le texte, sans interprétation excessive.
"""
        logger.info(f"🧠 Starting entity and relation extraction for text: '{text[:50]}...'")
        logger.info(f"🔍 Using ChatGPT extraction: {self.is_chatgpt_enabled}")
        try:
            response = await self._call_openai_api(prompt)
            
            # Nettoyer la réponse JSON
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Essayer sans les délimiteurs markdown
                json_match = re.search(r'({.*})', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    raise ValueError("Format JSON non détecté dans la réponse")
            
            # Parser le JSON
            data = json.loads(json_str)
            
            # Valider le format de données
            if "entities" not in data or "relations" not in data:
                raise ValueError("Format de données invalide: entities ou relations manquants")
                
            for entity in data.get("entities", []):
                if "name" not in entity or "type" not in entity:
                    logger.warning(f"Entité malformée ignorée: {entity}")
                
            for relation in data.get("relations", []):
                if "source" not in relation or "relation" not in relation or "target" not in relation:
                    logger.warning(f"Relation malformée ignorée: {relation}")
            
            return data
                
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction via ChatGPT: {str(e)}")
            # En cas d'erreur, on retourne un dictionnaire vide qui sera complété par la méthode de fallback
            return {"entities": [], "relations": []}
    
    async def extract_entities_and_relations(self, text: str, confidence: float = 0.7) -> Dict[str, Any]:
        """
        Point d'entrée principal pour l'extraction d'entités et de relations.
        Utilise ChatGPT si activé, sinon utilise l'extracteur local.
        
        Args:
            text: Texte à analyser
            confidence: Niveau de confiance par défaut
            
        Returns:
            Dictionnaire contenant les entités et relations extraites
        """
        method_used = "local"
        result = {"entities": [], "relations": []}
        
        # Si ChatGPT est activé, essayer d'abord cette méthode
        if self.is_chatgpt_enabled:
            try:
                logger.info("Tentative d'extraction via ChatGPT")
                result = await self.extract_entities_and_relations_with_chatgpt(text)
                
                # Vérifier si le résultat est valide et non vide
                if result and result.get("entities") and len(result["entities"]) > 0:
                    method_used = "chatgpt"
                    logger.info(f"Extraction réussie via ChatGPT: {len(result.get('entities', []))} entités, {len(result.get('relations', []))} relations")
                else:
                    logger.warning("Extraction via ChatGPT vide ou invalide, fallback vers extraction locale")
            except Exception as e:
                logger.error(f"Erreur lors de l'extraction via ChatGPT, fallback vers extraction locale: {str(e)}")
        
        # Si ChatGPT n'est pas activé ou a échoué, utiliser l'extracteur local
        if method_used == "local" or not result.get("entities"):
            logger.info("Utilisation de l'extracteur local")
            
            # Obtenir les entités via l'extracteur local
            local_entities = await self.base_memory.extract_entities_from_text(text, confidence)
            
            # Obtenir les relations via l'extracteur local
            local_relations = await self.base_memory.extract_relations_from_text(text, confidence)
            
            # Formater les résultats dans le même format que ChatGPT
            result = {
                "entities": local_entities,
                "relations": local_relations
            }
            
            method_used = "local"
            logger.info(f"Extraction locale: {len(local_entities)} entités, {len(local_relations)} relations")
        
        # Journaliser la méthode utilisée
        logger.info(f"Méthode d'extraction utilisée: {method_used}")
        result["method_used"] = method_used
        
        return result
    
    async def update_graph_from_text(self, text: str, confidence: float = 0.7, valid_from: str = None, valid_to: str = None) -> Dict[str, int]:
        """
        Met à jour le graphe de connaissances à partir d'un texte.
        Utilise l'extraction améliorée d'entités et de relations.
        
        Args:
            text: Texte à analyser
            confidence: Niveau de confiance par défaut
            valid_from: Date ISO de début de validité (si None, date courante)
            valid_to: Date ISO de fin de validité (si None, pas de limite)
            
        Returns:
            Statistiques sur les mises à jour (entités et relations ajoutées)
        """
        try:
            # Extraire les entités et relations via la méthode améliorée
            extraction_result = await self.extract_entities_and_relations(text, confidence)
            
            # Récupérer la méthode utilisée pour les logs
            method_used = extraction_result.pop("method_used", "unknown")
            
            # Traiter les entités extraites
            entities_added = 0
            entity_ids = {}
            
            for entity in extraction_result.get("entities", []):
                entity_confidence = entity.get("confidence", confidence)
                entity_attributes = entity.get("attributes", {})
                
                # Ajouter l'entité au graphe
                entity_id = self.base_memory.add_entity(
                    name=entity["name"],
                    entity_type=entity["type"],
                    attributes=entity_attributes,
                    confidence=entity_confidence,
                    valid_from=valid_from,
                    valid_to=valid_to
                )
                
                if entity_id:
                    entity_ids[entity["name"]] = entity_id
                    entities_added += 1
            
            # Traiter les relations extraites
            relations_added = 0
            
            for relation in extraction_result.get("relations", []):
                source_name = relation.get("source")
                target_name = relation.get("target")
                relation_type = relation.get("relation")
                relation_confidence = relation.get("confidence", confidence)
                
                # Vérifier que les entités existent ou les créer au besoin
                if source_name not in entity_ids:
                    source_id = self.base_memory.add_entity(
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
                    target_id = self.base_memory.add_entity(
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
                
                # Ajouter la relation si les deux entités existent
                if source_id and target_id:
                    success = self.base_memory.add_relation(
                        source_id=source_id,
                        relation=relation_type,
                        target_id=target_id,
                        confidence=relation_confidence,
                        valid_from=valid_from,
                        valid_to=valid_to
                    )
                    
                    if success:
                        relations_added += 1
            
            return {
                "entities_added": entities_added,
                "relations_added": relations_added,
                "extraction_method": method_used
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du graphe: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "entities_added": 0,
                "relations_added": 0,
                "error": str(e),
                "extraction_method": "failed"
            }

# Instance globale de la mémoire symbolique améliorée
enhanced_symbolic_memory = EnhancedSymbolicMemory(symbolic_memory)