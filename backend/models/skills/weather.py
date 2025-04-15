"""
Compétence de météo pour l'assistant IA.
"""
import re
import logging
import random
from typing import Dict, List, Any

from backend.models.skills.base import Skill

logger = logging.getLogger(__name__)

class WeatherSkill(Skill):
    """Compétence pour les requêtes météo."""
    
    name = "weather"
    description = "Fournit des informations météorologiques"
    examples = [
        "Quel temps fait-il à Paris?",
        "Quelle est la météo pour demain?",
        "Est-ce qu'il va pleuvoir aujourd'hui?"
    ]
    
    weather_keywords = [
        "météo", "temps", "température", "climat", "pleuvoir", "neiger",
        "ensoleillé", "nuageux", "orageux", "venteux", "chaud", "froid"
    ]
    
    async def can_handle(self, query: str, intent_data: Dict[str, Any]) -> float:
        """Vérifie si la requête concerne la météo."""
        query_lower = query.lower()
        
        # Vérifier l'intention détectée
        if intent_data.get("intent") == "weather":
            return intent_data.get("confidence", 0.8)
        
        # Recherche de mots-clés météo
        for keyword in self.weather_keywords:
            if keyword in query_lower:
                return 0.8
        
        return 0.0
    
    async def handle(self, query: str, intent_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Traite une requête météo."""
        try:
            # Extraire la localisation
            location = self._extract_location(query, intent_data)
            
            # Simulation de données météo
            weather_data = self._get_simulated_weather(location)
            
            # Formater la réponse
            response = f"La météo à {location}: {weather_data['condition']}, {weather_data['temperature']}°C. "
            response += f"Humidité: {weather_data['humidity']}%, vent: {weather_data['wind']} km/h."
            
            return {
                "success": True,
                "response": response,
                "data": weather_data
            }
        except Exception as e:
            logger.error(f"Erreur dans WeatherSkill: {str(e)}")
            return {
                "success": False,
                "response": "Désolé, je n'ai pas pu obtenir les informations météo.",
                "error": str(e)
            }
    
    def _extract_location(self, query: str, intent_data: Dict[str, Any]) -> str:
        """Extrait la localisation de la requête."""
        # Essayer d'obtenir depuis les entités d'intention
        if "entities" in intent_data and "location" in intent_data["entities"]:
            return intent_data["entities"]["location"]
        
        # Recherche de patterns courants
        location_patterns = [
            r"à ([A-Za-zÀ-ÖØ-öø-ÿ\s]+)(?:\?|$|\s)",
            r"pour ([A-Za-zÀ-ÖØ-öø-ÿ\s]+)(?:\?|$|\s)",
            r"météo (?:de|à|pour) ([A-Za-zÀ-ÖØ-öø-ÿ\s]+)(?:\?|$|\s)"
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, query)
            if match:
                return match.group(1).strip()
        
        # Valeur par défaut
        return "Paris"
    
    def _get_simulated_weather(self, location: str) -> Dict[str, Any]:
        """Génère des données météo simulées."""
        conditions = ["ensoleillé", "partiellement nuageux", "nuageux", "pluvieux", "orageux"]
        
        return {
            "location": location,
            "temperature": random.randint(10, 30),
            "condition": random.choice(conditions),
            "humidity": random.randint(30, 90),
            "wind": random.randint(0, 30)
        }