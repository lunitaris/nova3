"""
Contrôleur pour les lumières Philips Hue intégré à l'Assistant IA
"""
import os
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from phue import Bridge, Light
from backend.utils.profiler import profile
from backend.utils.startup_log import add_startup_event


logger = logging.getLogger(__name__)

class HueLightController:
    """
    Gère la communication avec le Philips Hue Bridge et les lumières.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialise le contrôleur de lumières Hue.
        
        Args:
            config_path: Chemin vers le fichier de configuration Hue (optionnel)
        """
        # logger.info("🧪 HueLightController __init__ appelé")  ## DEBUG
        self.bridge = None
        self.lights = {}
        self.rooms = {}
        self.config = {}
        self.is_available = False
        self._lights_loaded = False
        
        # Déterminer le chemin de configuration
        if not config_path:
            # Utiliser le chemin par défaut dans le répertoire de données
            # Remonter deux niveaux depuis le fichier actuel (utils) pour atteindre la racine du projet
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
            config_path = os.path.join(project_root, "data", "config", "hue_config.json")
        
        self._connect(config_path)
    
    def _connect(self, config_path: str) -> bool:
        """
        Établit la connexion avec le Hue Bridge.
        
        Args:
            config_path: Chemin vers le fichier de configuration
            
        Returns:
            True si la connexion a réussi, False sinon
        """
        try:
            if not os.path.exists(config_path):
                logger.warning(f"Fichier de configuration Hue non trouvé: {config_path}")
                return False
            
            # Charger la configuration
            with open(config_path, 'r') as f:
                self.config = json.load(f)
            
            if not self.config.get("bridge_ip") or not self.config.get("username"):
                logger.warning("Configuration Hue incomplète (IP ou username manquant)")
                return False
            
            # Se connecter au bridge
            self.bridge = Bridge(self.config["bridge_ip"], username=self.config["username"])
            
            # Essayer de récupérer les lumières pour vérifier la connexion
            self._refresh_lights()
            
            # logger.info(f"✅ Connecté au Hue Bridge à {self.config['bridge_ip']} avec succès")    ## DEBUG
            add_startup_event({"icon": "💡", "label": "Lumières", "message": "Lights system opérationnel"})

            self.is_available = True
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la connexion au Hue Bridge: {str(e)}")
            self.is_available = False
            return False
    
    def _refresh_lights(self, force: bool = False) -> None:
        """Récupère et met à jour la liste des lumières disponibles."""
        if not self.bridge or (self._lights_loaded and not force):
            return
        
        try:
            # Récupérer les objets Light
            light_objects = self.bridge.get_light_objects()
            
            # Créer un dictionnaire plus facilement utilisable
            self.lights = {light.name.lower(): light for light in light_objects}
            
            logger.debug(f"Lumières Hue rafraîchies: {len(self.lights)} trouvées")
            
            # Récupérer les groupes/pièces si disponibles
            try:
                groups = self.bridge.get_group()
                self.rooms = {
                    g['name'].lower(): {'id': gid, 'lights': g['lights']} 
                    for gid, g in groups.items() 
                    if 'name' in g and g['type'] == 'Room'
                }
                logger.debug(f"Pièces Hue rafraîchies: {len(self.rooms)} trouvées")
            except:
                logger.warning("Impossible de récupérer les pièces/groupes Hue")
            self._lights_loaded = True
                
        except Exception as e:
            logger.error(f"Erreur lors du rafraîchissement des lumières: {str(e)}")
    
    def get_light(self, name: str) -> Optional[Light]:
        """
        Récupère une lumière par son nom (insensible à la casse).
        
        Args:
            name: Nom de la lumière
            
        Returns:
            Objet Light ou None si non trouvé
        """
        name_lower = name.lower()
        
        # Recherche directe
        if name_lower in self.lights:
            return self.lights[name_lower]
        
        # Recherche par correspondance partielle
        matches = [light for light_name, light in self.lights.items() 
                  if name_lower in light_name]
        
        if matches:
            return matches[0]
        
        return None
    
    def control_light(self, name: str, action: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Contrôle une lumière spécifique.
        
        Args:
            name: Nom de la lumière
            action: Action à effectuer (on, off, brightness, color, etc.)
            params: Paramètres supplémentaires pour l'action
            
        Returns:
            Résultat de l'opération avec statut et message
        """
        if not self.bridge or not self.is_available:
            return {
                "success": False,
                "message": "Bridge Hue non connecté"
            }
        
        # Mettre à jour la liste des lumières au cas où
        if not self.lights:
            self._refresh_lights()
        
        # Gestion des pièces/groupes
        is_room = False
        room_id = None
        
        if "pièce" in name.lower() or "salon" in name.lower() or "chambre" in name.lower():
            # Extraire le nom de la pièce
            room_name = name.lower()
            for room in self.rooms.keys():
                if room in room_name:
                    is_room = True
                    room_id = self.rooms[room]['id']
                    break
        
        if is_room and room_id:
            return self._control_room(room_id, action, params or {})
            
        # Gestion des lumières individuelles
        light = self.get_light(name)
        
        if not light:
            return {
                "success": False,
                "message": f"Lumière '{name}' non trouvée"
            }
        
        try:
            if action == "on":
                light.on = True
                return {
                    "success": True,
                    "message": f"Lumière {light.name} allumée"
                }
                
            elif action == "off":
                light.on = False
                return {
                    "success": True,
                    "message": f"Lumière {light.name} éteinte"
                }
                
            elif action == "brightness":
                # Valeur entre 0 et 254
                brightness = params.get("value", 254)
                
                # Conversion si la valeur est en pourcentage (0-100)
                if brightness <= 100:
                    brightness = int(brightness * 254 / 100)
                
                light.brightness = min(254, max(0, brightness))
                return {
                    "success": True,
                    "message": f"Luminosité de {light.name} réglée à {brightness}"
                }
                
            elif action == "color":
                color = params.get("color", "white")
                
                # Utiliser les coordonnées xy pour la couleur
                if color == "red":
                    light.xy = [0.675, 0.322]
                elif color == "green":
                    light.xy = [0.409, 0.518]
                elif color == "blue":
                    light.xy = [0.167, 0.04]
                elif color == "yellow":
                    light.xy = [0.468, 0.476]
                elif color == "pink":
                    light.xy = [0.39, 0.25]
                else:  # white
                    light.xy = [0.32, 0.336]
                
                return {
                    "success": True,
                    "message": f"Couleur de {light.name} changée en {color}"
                }
                
            elif action == "scene":
                scene = params.get("scene", "relax")
                
                if scene == "relax":
                    light.brightness = 144
                    light.xy = [0.5019, 0.4152]
                elif scene == "concentrate":
                    light.brightness = 219
                    light.xy = [0.368, 0.3686]  # Blanc froid
                elif scene == "energize":
                    light.brightness = 254
                    light.xy = [0.3151, 0.3252]  # Blanc très vif
                elif scene == "reading":
                    light.brightness = 240
                    light.xy = [0.4448, 0.4066]  # Blanc légèrement chaud
                else:
                    return {
                        "success": False,
                        "message": f"Scène '{scene}' non reconnue"
                    }
                
                return {
                    "success": True,
                    "message": f"Scène '{scene}' appliquée à {light.name}"
                }
            
            else:
                return {
                    "success": False,
                    "message": f"Action '{action}' non reconnue"
                }
                
        except Exception as e:
            logger.error(f"Erreur lors du contrôle de la lumière {light.name}: {str(e)}")
            return {
                "success": False,
                "message": f"Erreur: {str(e)}"
            }
    
    def _control_room(self, room_id: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Contrôle toutes les lumières d'une pièce/groupe.
        
        Args:
            room_id: ID de la pièce/groupe
            action: Action à effectuer
            params: Paramètres supplémentaires
            
        Returns:
            Résultat de l'opération
        """
        try:
            if action == "on":
                self.bridge.set_group(room_id, 'on', True)
                return {
                    "success": True,
                    "message": f"Lumières de la pièce allumées"
                }
                
            elif action == "off":
                self.bridge.set_group(room_id, 'on', False)
                return {
                    "success": True,
                    "message": f"Lumières de la pièce éteintes"
                }
                
            elif action == "brightness":
                brightness = params.get("value", 254)
                
                # Conversion si en pourcentage
                if brightness <= 100:
                    brightness = int(brightness * 254 / 100)
                
                self.bridge.set_group(room_id, 'bri', min(254, max(0, brightness)))
                return {
                    "success": True,
                    "message": f"Luminosité de la pièce réglée à {brightness}"
                }
                
            elif action == "scene":
                scene = params.get("scene", "relax")
                
                if scene == "relax":
                    self.bridge.set_group(room_id, 'bri', 144)
                    self.bridge.set_group(room_id, 'xy', [0.5019, 0.4152])
                elif scene == "concentrate":
                    self.bridge.set_group(room_id, 'bri', 219)
                    self.bridge.set_group(room_id, 'xy', [0.368, 0.3686])
                elif scene == "energize":
                    self.bridge.set_group(room_id, 'bri', 254)
                    self.bridge.set_group(room_id, 'xy', [0.3151, 0.3252])
                elif scene == "reading":
                    self.bridge.set_group(room_id, 'bri', 240)
                    self.bridge.set_group(room_id, 'xy', [0.4448, 0.4066])
                else:
                    return {
                        "success": False,
                        "message": f"Scène '{scene}' non reconnue"
                    }
                
                return {
                    "success": True,
                    "message": f"Scène '{scene}' appliquée à la pièce"
                }
            
            else:
                return {
                    "success": False,
                    "message": f"Action '{action}' non reconnue pour une pièce"
                }
                
        except Exception as e:
            logger.error(f"Erreur lors du contrôle de la pièce {room_id}: {str(e)}")
            return {
                "success": False,
                "message": f"Erreur: {str(e)}"
            }


    @profile("hue_lights")
    def get_all_lights(self) -> List[Dict[str, Any]]:
        """
        Récupère la liste de toutes les lumières avec leur statut.
        
        Returns:
            Liste des lumières avec leurs informations
        """
        if not self.bridge or not self.is_available:
            return []
        
        try:
            # Rafraîchir les lumières
            self._refresh_lights()
            
            # Formater les informations
            lights_info = []
            
            for name, light in self.lights.items():
                lights_info.append({
                    "name": light.name,
                    "id": light.light_id,
                    "state": {
                        "on": light.on,
                        "brightness": light.brightness if light.on else 0,
                        "reachable": light.reachable
                    }
                })
            
            return lights_info
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des lumières: {str(e)}")
            return []
    



    def get_rooms(self) -> List[Dict[str, Any]]:
        """
        Récupère la liste des pièces/groupes.
        
        Returns:
            Liste des pièces avec leurs informations
        """
        if not self.bridge or not self.is_available:
            return []
        
        try:
            # Rafraîchir les informations
            self._refresh_lights()
            
            rooms_info = []
            
            for name, room in self.rooms.items():
                rooms_info.append({
                    "name": name,
                    "id": room["id"],
                    "lights": room["lights"],  # Inclure la liste complète des lumières
                    "lights_count": len(room["lights"])
                })
            
            return rooms_info
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des pièces: {str(e)}")
            return []