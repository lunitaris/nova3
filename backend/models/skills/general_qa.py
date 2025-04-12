"""
Compétence de questions-réponses générales pour l'assistant IA.
"""
import logging
from typing import Dict, List, Any

from models.skills.base import Skill
from models.model_manager import model_manager

logger = logging.getLogger(__name__)

class GeneralQASkill(Skill):
    """Compétence pour les questions-réponses générales."""
    
    name = "general_qa"
    description = "Répond aux questions générales de connaissances"
    examples = [
        "Quelle est la population de la France?",
        "Qui a inventé la théorie de la relativité?",
        "Quand a eu lieu la Révolution française?"
    ]
    
    async def can_handle(self, query: str, intent_data: Dict[str, Any]) -> float:
        """
        Cette compétence peut gérer presque toutes les requêtes, mais avec une priorité plus faible
        que les compétences spécialisées.
        """
        # Si l'intention est spécifiquement "general_qa"
        if intent_data.get("intent") == "general_qa":
            return intent_data.get("confidence", 0.7)
        
        # Détecter les questions
        if query.strip().endswith("?"):
            return 0.6
        
        # Mots interrogatifs courants
        question_starters = ["qui", "quoi", "quand", "où", "pourquoi", "comment", "est-ce que", "qu'est-ce"]
        query_lower = query.lower()
        
        for starter in question_starters:
            if query_lower.startswith(starter):
                return 0.6
        
        # Capacité par défaut à traiter les requêtes générales
        return 0.4
    
    async def handle(self, query: str, intent_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Traite une question générale."""
        try:
            # Déterminer la complexité selon la longueur de la question
            complexity = "low" if len(query.split()) < 15 else "medium"
            
            # Extraire des information pertinentes du contexte
            persona_context = ""
            if context and "persona" in context:
                persona_context = f"Répondez en tant que {context['persona']}. "
            
            # Préparer le prompt
            prompt = f"{persona_context}Question: {query}\n\nRéponse:"
            
            # Générer la réponse
            response = await model_manager.generate_response(prompt, complexity=complexity)
            
            return {
                "success": True,
                "response": response.strip(),
                "used_context": bool(persona_context),
                "topic": intent_data.get("topic", "général")
            }
        except Exception as e:
            logger.error(f"Erreur dans GeneralQASkill: {str(e)}")
            return {
                "success": False,
                "response": "Je ne peux pas répondre à cette question pour le moment.",
                "error": str(e)
            }