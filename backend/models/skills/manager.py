"""
Gestionnaire central de compétences (skills) pour l'assistant IA.
Charge et orchestre l'utilisation des différentes compétences.
"""
import os
import importlib
import inspect
import pkgutil
import logging
import asyncio
from typing import Dict, List, Any, Type, Optional

from backend.models.model_manager import model_manager
from backend.config import config
from backend.models.skills.base import Skill

# Importer explicitement les compétences disponibles
from backend.models.skills.weather import WeatherSkill
from backend.models.skills.home_automation import HomeAutomationSkill
from backend.models.skills.timer_reminder import TimerReminderSkill
from backend.models.skills.general_qa import GeneralQASkill

logger = logging.getLogger(__name__)

class SkillsManager:
    """
    Gestionnaire central des compétences de l'assistant.
    """
    
    def __init__(self):
        """Initialise le gestionnaire de compétences."""
        self.skills = {}
        self._load_skills()
    
    def _load_skills(self):
        """Charge toutes les compétences disponibles."""
        # Méthode manuelle (plus fiable)
        self._register_skill(WeatherSkill)
        self._register_skill(HomeAutomationSkill)
        self._register_skill(TimerReminderSkill)
        self._register_skill(GeneralQASkill)
        
        logger.info(f"Compétences chargées: {', '.join(self.skills.keys())}")
    
    def _register_skill(self, skill_class: Type[Skill]):
        """
        Enregistre une classe de compétence.
        
        Args:
            skill_class: Classe de compétence à enregistrer
        """
        skill_instance = skill_class(self)
        self.skills[skill_instance.name] = skill_instance
        logger.debug(f"Compétence enregistrée: {skill_instance.name}")
    
    async def detect_intent(self, query: str) -> Dict[str, Any]:
        """
        Détecte l'intention de l'utilisateur.
        
        Args:
            query: Requête de l'utilisateur
            
        Returns:
            Données d'intention détectées
        """
        intent_prompt = f"""Analyse la requête suivante et détermine l'intention de l'utilisateur.
Requête: "{query}"

Réponds avec un objet JSON contenant les propriétés suivantes:
- "intent": le type d'intention ("weather", "home_automation", "timer", "reminder", "general_qa", etc.)
- "confidence": niveau de confiance entre 0 et 1
- "entities": un objet avec les entités détectées (localisation, appareil, durée, etc.)

Par exemple:
{{
  "intent": "weather",
  "confidence": 0.9,
  "entities": {{ "location": "Paris" }}
}}
"""
        
        try:
            # Utiliser un modèle léger pour la détection d'intention
            response = await model_manager.generate_response(intent_prompt, complexity="low")
            
            # Extraire le JSON de la réponse
            import json
            import re
            
            # Rechercher un bloc JSON potentiel
            json_match = re.search(r'({.*})', response.replace('\n', ' '), re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                try:
                    intent_data = json.loads(json_str)
                    logger.info(f"Intention détectée: {intent_data.get('intent', 'inconnue')} "
                             f"(confiance: {intent_data.get('confidence', 0.0):.2f})")
                    return intent_data
                except json.JSONDecodeError:
                    logger.warning(f"Impossible de décoder la réponse JSON: {json_str}")
            
            # Fallback: détection simple
            intent_data = {
                "intent": "general_qa",
                "confidence": 0.5,
                "entities": {}
            }
            
            # Détecter quelques intentions courantes
            query_lower = query.lower()
            
            if any(word in query_lower for word in ["météo", "temps", "température", "climat"]):
                intent_data["intent"] = "weather"
                intent_data["confidence"] = 0.7
            
            elif any(word in query_lower for word in ["allume", "éteins", "ouvre", "ferme", "règle"]):
                intent_data["intent"] = "home_automation"
                intent_data["confidence"] = 0.7
            
            elif any(word in query_lower for word in ["minuteur", "timer", "rappelle-moi", "rappel"]):
                intent_data["intent"] = "timer_reminder"
                intent_data["confidence"] = 0.7
            
            logger.info(f"Intention détectée (fallback): {intent_data['intent']} "
                     f"(confiance: {intent_data['confidence']:.2f})")
            return intent_data
            
        except Exception as e:
            logger.error(f"Erreur lors de la détection d'intention: {str(e)}")
            return {
                "intent": "general_qa",
                "confidence": 0.5,
                "entities": {}
            }
    
    async def process_query(self, query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Traite une requête utilisateur en sélectionnant la compétence la plus appropriée.
        
        Args:
            query: Requête de l'utilisateur
            context: Contexte additionnel pour la requête
            
        Returns:
            Résultat du traitement
        """
        # Détecter l'intention
        intent_data = await self.detect_intent(query)
        
        # Trouver la compétence la plus appropriée
        best_skill = None
        best_score = 0.0
        
        # Évaluer chaque compétence
        for skill_name, skill in self.skills.items():
            score = await skill.can_handle(query, intent_data)
            logger.debug(f"Compétence {skill_name}: score {score:.2f}")
            
            if score > best_score:
                best_score = score
                best_skill = skill
        
        # Si aucune compétence n'est suffisamment confiante, utiliser la compétence générale
        if best_score < 0.4 or best_skill is None:
            best_skill = self.skills.get("general_qa")
            logger.info("Aucune compétence spécifique trouvée, utilisation de la compétence générale")
        
        # Traiter la requête avec la compétence sélectionnée
        logger.info(f"Traitement de la requête avec la compétence: {best_skill.name} (score: {best_score:.2f})")
        result = await best_skill.handle(query, intent_data, context)
        
        # Ajouter des métadonnées sur la compétence utilisée
        result["skill"] = best_skill.name
        result["confidence"] = best_score
        
        return result
    
    def get_available_skills(self) -> List[Dict[str, Any]]:
        """
        Récupère la liste des compétences disponibles.
        
        Returns:
            Liste des compétences avec leurs informations
        """
        skills_info = []
        
        for name, skill in self.skills.items():
            skills_info.append({
                "name": name,
                "description": skill.description,
                "examples": skill.get_examples()
            })
        
        return skills_info

# Instance globale du gestionnaire de compétences
skills_manager = SkillsManager()