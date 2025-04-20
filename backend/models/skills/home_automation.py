"""
Compétence de domotique pour l'assistant IA.
"""
import re
import logging
from typing import Dict, List, Any, Tuple, Optional
import os

from backend.models.skills.base import Skill
from backend.utils.hue_controller import HueLightController

logger = logging.getLogger(__name__)

class HomeAutomationSkill(Skill):
    """Compétence pour la domotique."""
    
    name = "home_automation"
    description = "Contrôle les appareils domotiques"
    examples = [
        "Allume la lumière du salon",
        "Éteins toutes les lumières",
        "Règle le thermostat sur 22 degrés",
        "Ferme les volets",
        "Mets la lumière du salon en bleu",
        "Règle la luminosité du salon à 50%"
    ]
    
    # Appareils simulés
    devices = {
        "lumière salon": {"type": "light", "state": "off", "location": "salon"},
        "lumière cuisine": {"type": "light", "state": "off", "location": "cuisine"},
        "lumière chambre": {"type": "light", "state": "off", "location": "chambre"},
        "thermostat": {"type": "thermostat", "temperature": 20, "state": "on", "location": "maison"},
        "volets salon": {"type": "blinds", "state": "open", "location": "salon"},
        "volets chambre": {"type": "blinds", "state": "open", "location": "chambre"},
        "tv": {"type": "tv", "state": "off", "channel": 1, "location": "salon"}
    }
    
    actions = ["allumer", "éteindre", "ouvrir", "fermer", "régler", "monter", "baisser", "augmenter", 
               "diminuer", "mettre", "changer", "modifier"]
    
    def __init__(self, manager=None):
        """
        Initialise la compétence.
        
        Args:
            manager: Référence au gestionnaire de compétences
        """
        super().__init__(manager)
        
        # Initialiser le contrôleur Hue si possible
        self.hue_controller = self._init_hue_controller()
        self.use_real_devices = self.hue_controller is not None and self.hue_controller.is_available
        
        if self.use_real_devices:
            # logger.info("Contrôleur Philips Hue initialisé avec succès - utilisation des lumières réelles")   ## DEBUG
            pass
        else:
            logger.info("Utilisation des appareils domotiques simulés")
    
    def _init_hue_controller(self) -> Optional[HueLightController]:
        """
        Initialise le contrôleur Philips Hue.
        
        Returns:
            Instance de HueLightController ou None si non disponible
        """
        try:
            controller = HueLightController()
            if controller.is_available:
                return controller
        except Exception as e:
            logger.warning(f"Impossible d'initialiser le contrôleur Hue: {str(e)}")
        
        return None
    
    async def can_handle(self, query: str, intent_data: Dict[str, Any]) -> float:
        """Vérifie si la requête concerne la domotique."""
        query_lower = query.lower()
        
        # Vérifier l'intention détectée
        if intent_data.get("intent") == "home_automation":
            return intent_data.get("confidence", 0.8)
        
        # Rechercher des actions domotiques
        for action in self.actions:
            if action in query_lower:
                # Vérifier si un appareil est mentionné
                for device in self.devices:
                    if device in query_lower:
                        return 0.9
                
                # Vérifier les lumières Hue si disponibles
                if self.use_real_devices:
                    for light_name in self.hue_controller.lights.keys():
                        if light_name in query_lower or "lumière" in query_lower:
                            return 0.9
                
                # Action trouvée mais pas d'appareil spécifique
                return 0.7
        
        # Rechercher directement des appareils
        for device in self.devices:
            if device in query_lower:
                return 0.8
        
        # Rechercher des lumières Hue si disponibles
        if self.use_real_devices:
            for light_name in self.hue_controller.lights.keys():
                if light_name in query_lower:
                    return 0.8
                    
            # Vérifier si "lumières" est mentionné (pour toutes les lumières)
            if "lumières" in query_lower or "toutes les lumières" in query_lower:
                return 0.8
        
        return 0.0
    
    async def handle(self, query: str, intent_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Traite une requête domotique."""
        try:
            # Analyser la commande
            action, device_name, parameters = self._parse_command(query, intent_data)
            
            if not device_name:
                return {
                    "success": False,
                    "response": "Je n'ai pas compris quel appareil vous souhaitez contrôler."
                }
            
            if not action:
                return {
                    "success": False,
                    "response": f"Je ne sais pas quelle action effectuer sur {device_name}."
                }
            
            # Déterminer si on doit utiliser les appareils réels ou simulés
            if self.use_real_devices and self._is_light_device(device_name):
                # Exécuter l'action sur les lumières Hue réelles
                result = self._execute_hue_action(action, device_name, parameters)
            else:
                # Exécuter l'action sur les appareils simulés
                result = self._execute_action(action, device_name, parameters)
            
            return {
                "success": result["success"],
                "response": result["message"],
                "data": {
                    "device": device_name,
                    "action": action,
                    "parameters": parameters,
                    "state": result.get("state", {})
                }
            }
        except Exception as e:
            logger.error(f"Erreur dans HomeAutomationSkill: {str(e)}")
            return {
                "success": False,
                "response": "Désolé, je n'ai pas pu exécuter cette commande domotique.",
                "error": str(e)
            }
    
    def _is_light_device(self, device_name: str) -> bool:
        """
        Vérifie si l'appareil est une lumière pouvant être contrôlée par Hue.
        
        Args:
            device_name: Nom de l'appareil
            
        Returns:
            True si c'est une lumière, False sinon
        """
        device_lower = device_name.lower()
        
        # Vérifier si c'est "toutes les lumières"
        if "toutes les lumières" in device_lower:
            return True
        
        # Vérifier si c'est une lumière (par le nom)
        if "lumière" in device_lower or "lampe" in device_lower:
            return True
        
        # Vérifier si le nom correspond à une lumière Hue connue
        if self.use_real_devices:
            for light_name in self.hue_controller.lights.keys():
                if light_name in device_lower:
                    return True
                    
            # Vérifier les pièces/groupes
            for room_name in self.hue_controller.rooms.keys():
                if room_name in device_lower:
                    return True
        
        return False
    
    def _parse_command(self, query: str, intent_data: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
        """
        Parse la commande domotique.
        
        Returns:
            Tuple (action, device_name, parameters)
        """
        query_lower = query.lower()
        
        # Tenter d'extraire depuis les entités reconnues
        if "entities" in intent_data:
            action = intent_data["entities"].get("action")
            device = intent_data["entities"].get("device")
            value = intent_data["entities"].get("value")
            
            if action and device:
                return action, device, {"value": value} if value else {}
        
        # Chercher l'action
        detected_action = None
        for action in self.actions:
            if action in query_lower:
                detected_action = action
                break
        
        # Cartographier les actions vers des commandes standardisées
        if detected_action:
            if detected_action in ["allumer", "ouvrir"]:
                detected_action = "on"
            elif detected_action in ["éteindre", "fermer"]:
                detected_action = "off"
            elif detected_action in ["régler", "mettre", "changer"]:
                # Déterminer le type de réglage
                if "luminosité" in query_lower or "intensité" in query_lower:
                    detected_action = "brightness"
                elif "couleur" in query_lower:
                    detected_action = "color"
                elif "ambiance" in query_lower or "scène" in query_lower:
                    detected_action = "scene"
                else:
                    # Par défaut, considérer comme un réglage générique
                    detected_action = "set"