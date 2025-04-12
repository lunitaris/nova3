"""
Compétence de domotique pour l'assistant IA.
"""
import re
import logging
from typing import Dict, List, Any, Tuple

from models.skills.base import Skill

logger = logging.getLogger(__name__)

class HomeAutomationSkill(Skill):
    """Compétence pour la domotique."""
    
    name = "home_automation"
    description = "Contrôle les appareils domotiques"
    examples = [
        "Allume la lumière du salon",
        "Éteins toutes les lumières",
        "Règle le thermostat sur 22 degrés",
        "Ferme les volets"
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
    
    actions = ["allumer", "éteindre", "ouvrir", "fermer", "régler", "monter", "baisser", "augmenter", "diminuer"]
    
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
                
                # Action trouvée mais pas d'appareil spécifique
                return 0.7
        
        # Rechercher directement des appareils
        for device in self.devices:
            if device in query_lower:
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
            
            # Exécuter l'action
            result = self._execute_action(action, device_name, parameters)
            
            return {
                "success": result["success"],
                "response": result["message"],
                "data": {
                    "device": device_name,
                    "action": action,
                    "parameters": parameters,
                    "state": self.devices.get(device_name, {})
                }
            }
        except Exception as e:
            logger.error(f"Erreur dans HomeAutomationSkill: {str(e)}")
            return {
                "success": False,
                "response": "Désolé, je n'ai pas pu exécuter cette commande domotique.",
                "error": str(e)
            }
    
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
        
        # Chercher l'appareil
        detected_device = None
        for device in self.devices:
            if device in query_lower:
                detected_device = device
                break
        
        # Si "toutes les lumières" est mentionné
        if "toutes les lumières" in query_lower:
            detected_device = "toutes les lumières"
        
        # Extraire des paramètres potentiels (valeurs numériques)
        parameters = {}
        value_match = re.search(r'(\d+)(?:\s*degrés|\s*%)?', query_lower)
        if value_match:
            parameters["value"] = int(value_match.group(1))
        
        return detected_action, detected_device, parameters
    
    def _execute_action(self, action: str, device_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Exécute une action sur un appareil.
        
        Args:
            action: Action à effectuer
            device_name: Nom de l'appareil
            parameters: Paramètres additionnels
            
        Returns:
            Résultat de l'action
        """
        # Gérer le cas "toutes les lumières"
        if device_name == "toutes les lumières":
            if action == "allumer":
                # Allumer toutes les lumières
                for dev_name, device in self.devices.items():
                    if device["type"] == "light":
                        device["state"] = "on"
                return {"success": True, "message": "Toutes les lumières ont été allumées."}
            
            elif action == "éteindre":
                # Éteindre toutes les lumières
                for dev_name, device in self.devices.items():
                    if device["type"] == "light":
                        device["state"] = "off"
                return {"success": True, "message": "Toutes les lumières ont été éteintes."}
        
        # Vérifier si l'appareil existe
        if device_name not in self.devices:
            return {"success": False, "message": f"Je ne trouve pas l'appareil '{device_name}'."}
        
        device = self.devices[device_name]
        
        # Exécuter l'action selon le type d'appareil
        if device["type"] == "light":
            if action == "allumer":
                device["state"] = "on"
                return {"success": True, "message": f"J'ai allumé {device_name}."}
            elif action == "éteindre":
                device["state"] = "off"
                return {"success": True, "message": f"J'ai éteint {device_name}."}
        
        elif device["type"] == "thermostat":
            if action in ["régler", "augmenter", "diminuer"]:
                if "value" in parameters:
                    if action == "augmenter":
                        device["temperature"] += parameters["value"]
                    elif action == "diminuer":
                        device["temperature"] -= parameters["value"]
                    else:  # régler
                        device["temperature"] = parameters["value"]
                    
                    return {"success": True, "message": f"Thermostat réglé à {device['temperature']}°C."}
                else:
                    return {"success": False, "message": "Je n'ai pas compris la température souhaitée."}
        
        elif device["type"] == "blinds":
            if action == "ouvrir":
                device["state"] = "open"
                return {"success": True, "message": f"J'ai ouvert {device_name}."}
            elif action == "fermer":
                device["state"] = "closed"
                return {"success": True, "message": f"J'ai fermé {device_name}."}
        
        return {"success": False, "message": f"Je ne sais pas comment {action} {device_name}."}