"""
Classe de base pour le système de compétences (skills) de l'assistant IA.
"""
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class Skill:
    """Classe de base pour toutes les compétences."""
    
    name = "base_skill"
    description = "Compétence de base"
    examples = []
    
    def __init__(self, manager=None):
        """
        Initialise la compétence.
        
        Args:
            manager: Référence au gestionnaire de compétences
        """
        self.manager = manager
    
    async def can_handle(self, query: str, intent_data: Dict[str, Any]) -> float:
        """
        Vérifie si cette compétence peut traiter la requête.
        
        Args:
            query: Requête de l'utilisateur
            intent_data: Données d'intention détectées
            
        Returns:
            Score de confiance entre 0 et 1
        """
        return 0.0
    
    async def handle(self, query: str, intent_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Traite la requête utilisateur.
        
        Args:
            query: Requête de l'utilisateur
            intent_data: Données d'intention détectées
            context: Contexte additionnel
            
        Returns:
            Résultat du traitement
        """
        return {
            "success": False,
            "response": "Cette compétence n'est pas implémentée.",
            "error": "NotImplemented"
        }
    
    def get_examples(self) -> List[str]:
        """
        Retourne des exemples d'utilisation de cette compétence.
        
        Returns:
            Liste d'exemples
        """
        return self.examples