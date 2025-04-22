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
from backend.utils.profiler import profile

logger = logging.getLogger(__name__)
from backend.config import OPENAI_API_KEY


def log_extraction_summary(method: str, entities: List[dict], relations: List[dict]):
    """Log le résultat de l'extraction avec un identifiant unique pour le suivi"""
    extract_id = f"extract_{int(time.time() * 1000) % 10000:04d}"
    
    logger.info(f"""
🧠 [{extract_id}] Résultat extraction via {method.upper()} :
• Entités extraites   : {len(entities)}
• Relations extraites : {len(relations)}
• Relations brutes    : {json.dumps(relations, ensure_ascii=False) if relations else "[]"}
""".strip())
    
    return extract_id  # Retourner l'identifiant pour le traçage

class EnhancedSymbolicMemory:
    """
    Extension du gestionnaire de mémoire symbolique avec intégration ChatGPT optionnelle.
    """

    def __init__(self, base_memory: SymbolicMemory = None):
        self.base_memory = base_memory or symbolic_memory
        self.openai_api_key = OPENAI_API_KEY
        self._extraction_cache = {}
        self._cache_timestamps = {}
        self._successful_extractions = set()

        if self.openai_api_key:
            key_length = len(self.openai_api_key)
            first_chars = self.openai_api_key[:4] if key_length > 8 else ""
            last_chars = self.openai_api_key[-4:] if key_length > 8 else ""
            # logger.info(f"✅ OpenAI API key configurée!")     ## DEBUG
        else:
            logger.warning("⚠️ Aucune clé API OpenAI configurée. L'extraction via ChatGPT ne sera pas disponible.")


    def __getattr__(self, attr):
        return getattr(self.base_memory, attr)

    @property
    def is_chatgpt_enabled(self) -> bool:
        enabled = (
            hasattr(config.memory, "use_chatgpt_for_symbolic_memory") and 
            config.memory.use_chatgpt_for_symbolic_memory and
            self.openai_api_key
        )
        logger.debug(f"⚙️ ChatGPT extraction enabled: {enabled} - Config: {getattr(config.memory, 'use_chatgpt_for_symbolic_memory', False)}, API key available: {bool(self.openai_api_key)}")
        return enabled

    @backoff.on_exception(backoff.expo, (aiohttp.ClientError, asyncio.TimeoutError), max_tries=3)
    async def _call_openai_api(self, prompt: str, model: str = "gpt-3.5-turbo") -> str:
        if not self.openai_api_key:
            raise ValueError("Clé API OpenAI non configurée")

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
                    {"role": "system", "content": "Tu es un assistant d'extraction d'informations symboliques intelligent, exhaustif, et structurant."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2
            }
            async with session.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=15) as response:
                if response.status != 200:
                    response_text = await response.text()
                    logger.error(f"Erreur API OpenAI: {response.status} - {response_text}")
                    raise Exception(f"Erreur API OpenAI: {response.status}")
                data = await response.json()
                return data["choices"][0]["message"]["content"]


    async def extract_entities_and_relations(self, text: str, confidence: float = 0.7) -> Dict[str, Any]:
        """
        Alias de compatibilité vers extract_entities_and_relations_with_chatgpt.
        Utilise l’extraction hybride (ChatGPT si activé, sinon fallback local).
        """
        return await self.extract_entities_and_relations_with_chatgpt(text, confidence)



    async def extract_entities_and_relations_with_chatgpt(self, text: str, confidence: float = 0.7) -> Dict[str, Any]:
        cache_key = hash(text)  # ✅ doit être en haut
        current_time = time.time()

        # ✅ Vérification verrou global des extractions déjà réussies
        if cache_key in self._successful_extractions:
            logger.debug("⏭️ Extraction déjà réalisée pour ce texte (hash connu)")
            return {
                "entities": [],
                "relations": [],
                "method_used": "cache_skip"
            }

        # ✅ Vérification du cache mémoire court terme (moins de 10 minutes)
        if cache_key in self._extraction_cache:
            cache_time = self._cache_timestamps.get(cache_key, 0)
            if current_time - cache_time < 600:
                logger.info("🔍 Utilisation du cache d'extraction symbolique (âge: %.1f min)", (current_time - cache_time) / 60)
                return self._extraction_cache[cache_key]

        prompt_template = """
Analyse le texte ci-dessous et extrait toutes les entités, attributs et relations possibles.
Inclut également les préférences, rôles, professions, et toute information implicite évidente.

Texte :
"{text}"

Objectifs :
1. Détecte les entités (nom, type comme person/place/device/concept/etc, attributs, confiance).
2. Déduis toutes les relations logiques entre ces entités (même implicites ou affectives).
3. Garde un style synthétique, compact, mais précis. Ne rate rien.

Format attendu (JSON uniquement) :
```json
{
  "entities": [
    {
      "name": "Nom",
      "type": "person/place/device/concept/...",
      "attributes": {"key": "valeur", ...},
      "confidence": 0.9
    }
  ],
  "relations": [
    {
      "source": "Nom",
      "relation": "relation",
      "target": "Nom",
      "confidence": 0.9
    }
  ]
}
```"""
        prompt = prompt_template.replace("{text}", text)
        result = {"entities": [], "relations": []}
        method_used = "local"  # valeur par défaut

        if self.is_chatgpt_enabled:
            try:
                logger.info("Tentative d'extraction via ChatGPT")
                response = await self._call_openai_api(prompt)

                # Nettoyer les balises Markdown si présentes
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0].strip()
                elif "```" in response:
                    response = response.split("```")[1].strip()

                parsed = json.loads(response)
                result["entities"] = parsed.get("entities", [])
                result["relations"] = parsed.get("relations", [])
                method_used = "chatgpt"  # ✅ on note le succès ici

            except Exception as e:
                logger.error(f"(Ehanced memory) Erreur lors de l'extraction via ChatGPT, fallback vers extraction locale: {str(e)}")

        # Fallback local (non implémenté)
        if method_used != "chatgpt" or not result.get("entities"):
            logger.warning("(Ehanced memory) Extraction locale désactivée — aucune entité/relation extraite")
            result["entities"] = []
            result["relations"] = []
            method_used = "local"

        result["method_used"] = method_used



        #########################£ Mettre en cache
        self._extraction_cache[cache_key] = result
        self._cache_timestamps[cache_key] = current_time

        # Nettoyage : on garde max 50 entrées
        if len(self._extraction_cache) > 50:
            oldest_keys = sorted(self._cache_timestamps.keys(), key=lambda k: self._cache_timestamps[k])[:10]
            for key in oldest_keys:
                self._extraction_cache.pop(key, None)
                self._cache_timestamps.pop(key, None)
            logger.info(f"🧹 Nettoyage du cache d'extraction (suppression de {len(oldest_keys)} entrées)")



        # ✅ Mémoriser que cette extraction a réussi
        if result.get("entities") or result.get("relations"):
            self._successful_extractions.add(cache_key)

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
            
            log_extraction_summary(method_used, extraction_result.get("entities", []), extraction_result.get("relations", []))
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


    def get_recent_context(self, user_id: str = "anonymous", max_items: int = 3) -> List[str]:
        """
        Renvoie une liste de triplets récents liés à l'utilisateur spécifié, à titre de rappel rapide.
        """
        try:
            recent = self.base_memory.get_recent_statements_about(user_id, limit=max_items)
            return [f"{r['source']} {r['relation']} {r['target']}" for r in recent]
        except Exception as e:
            logger.warning(f"⚠️ get_recent_context: erreur lors de la récupération des relations récentes pour {user_id} → {e}")
            return []


# Instance globale de la mémoire symbolique améliorée
enhanced_symbolic_memory = EnhancedSymbolicMemory(symbolic_memory)