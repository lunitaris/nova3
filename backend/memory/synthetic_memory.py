import os
import json
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

# Remplacer l'importation relative par une importation absolue
from backend.models.model_manager import model_manager
from backend.memory.vector_store import vector_store
from backend.config import config

logger = logging.getLogger(__name__)

class SyntheticMemory:
    """
    Gère la mémoire synthétique de l'assistant.
    La mémoire synthétique condense les conversations et informations
    pour réduire la taille du contexte tout en conservant les informations importantes.
    """
    
    def __init__(self, storage_path: str = None):
        """
        Initialise le gestionnaire de mémoire synthétique.
        
        Args:
            storage_path: Chemin de stockage des mémoires synthétiques
        """
        self.storage_path = storage_path or os.path.join(config.data_dir, "memories", "synthetic_memory.json")
        self.vector_store = vector_store
        self.memory_data = self._load_memories()
        
    def _load_memories(self) -> Dict[str, Any]:
        """Charge les mémoires synthétiques existantes."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Erreur lors du chargement des mémoires synthétiques: {str(e)}")
                return {"topics": {}, "last_update": None}
        return {"topics": {}, "last_update": None}
    
    def _save_memories(self):
        """Sauvegarde les mémoires synthétiques."""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.memory_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des mémoires synthétiques: {str(e)}")
    
    async def synthesize_conversation(self, conversation_history: List[Dict[str, Any]], topic: str = "general") -> str:
        """
        Synthétise une conversation en un résumé concis.
        
        Args:
            conversation_history: Historique de la conversation
            topic: Sujet ou catégorie de la conversation
            
        Returns:
            Résumé synthétique de la conversation
        """
        try:
            # Formater l'historique de conversation pour le prompt
            formatted_history = "\n".join([
                f"{'Utilisateur' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
                for msg in conversation_history
            ])
            
            # Remplacer les placeholder dans le template
            prompt = MEMORY_SYNTHESIS_TEMPLATE.replace("{conversation_history}", formatted_history)
            
            # Générer la synthèse avec un modèle léger
            synthesis = await model_manager.generate_response(prompt, complexity="low")
            
            # Stocker la synthèse
            timestamp = datetime.now().isoformat()
            
            if topic not in self.memory_data["topics"]:
                self.memory_data["topics"][topic] = []
            
            self.memory_data["topics"][topic].append({
                "timestamp": timestamp,
                "content": synthesis,
                "message_count": len(conversation_history)
            })
            
            # Limiter la taille des synthèses par sujet
            max_syntheses = 5
            if len(self.memory_data["topics"][topic]) > max_syntheses:
                # Garder seulement les plus récentes
                self.memory_data["topics"][topic] = self.memory_data["topics"][topic][-max_syntheses:]
            
            self.memory_data["last_update"] = timestamp
            self._save_memories()
            
            # Stocker également dans la mémoire vectorielle pour la recherche
            vector_store.add_memory(
                content=synthesis,
                metadata={
                    "type": "synthetic",
                    "topic": topic,
                    "timestamp": timestamp,
                    "message_count": len(conversation_history)
                }
            )
            
            logger.info(f"Synthèse générée pour le sujet '{topic}'")
            return synthesis
            
        except Exception as e:
            logger.error(f"Erreur lors de la synthèse de conversation: {str(e)}")
            return "Erreur lors de la génération de la synthèse."
    
    async def compress_memory(self) -> bool:
        """
        Compresse les mémoires synthétiques accumulées.
        Combine les synthèses plus anciennes en une seule plus concise.
        
        Returns:
            True si la compression a réussi, False sinon
        """
        try:
            for topic, syntheses in self.memory_data["topics"].items():
                # Vérifier s'il y a assez de synthèses pour justifier une compression
                if len(syntheses) < 3:
                    continue
                
                # Prendre toutes les synthèses sauf la plus récente
                old_syntheses = syntheses[:-1]
                recent_synthesis = syntheses[-1]
                
                # Concaténer les anciennes synthèses
                combined_text = "\n\n".join([s["content"] for s in old_syntheses])
                
                # Prompt pour compresser les anciennes synthèses
                prompt = f"""Voici plusieurs résumés de conversations passées:
                
{combined_text}

Synthétise ces informations en un résumé unifié qui capture toutes les informations importantes
de manière concise. Ne garde que les informations essentielles sur les préférences
et les faits importants mentionnés par l'utilisateur.

Résumé unifié:"""
                
                # Générer la compression
                compressed = await model_manager.generate_response(prompt, complexity="medium")
                
                # Mise à jour de la mémoire
                self.memory_data["topics"][topic] = [{
                    "timestamp": datetime.now().isoformat(),
                    "content": compressed,
                    "message_count": sum(s["message_count"] for s in old_syntheses),
                    "compressed": True
                }, recent_synthesis]
            
            self.memory_data["last_update"] = datetime.now().isoformat()
            self._save_memories()
            
            logger.info("Compression des mémoires synthétiques effectuée")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la compression des mémoires: {str(e)}")
            return False
    
    def get_relevant_memories(self, query: str, topic: str = None, max_results: int = 3) -> List[Dict[str, Any]]:
        """
        Récupère les mémoires synthétiques pertinentes.
        
        Args:
            query: Requête pour la recherche
            topic: Filtre optionnel par sujet
            max_results: Nombre maximal de résultats à retourner
            
        Returns:
            Liste des mémoires pertinentes
        """
        # Recherche vectorielle
        vector_results = self.vector_store.search_memories(query, k=max_results*2)
        
        # Filtrer par type "synthetic"
        vector_results = [r for r in vector_results if r.get("type") == "synthetic"]
        
        # Filtrer par sujet si spécifié
        if topic:
            vector_results = [r for r in vector_results if r.get("topic") == topic]
        
        # Limiter le nombre de résultats
        vector_results = vector_results[:max_results]
        
        # Si pas assez de résultats, ajouter les plus récentes du sujet
        if topic and len(vector_results) < max_results:
            topic_memories = self.memory_data["topics"].get(topic, [])
            # Prendre les plus récentes, en évitant les doublons
            vector_ids = set(r.get("memory_id") for r in vector_results if "memory_id" in r)
            for memory in reversed(topic_memories):
                if len(vector_results) >= max_results:
                    break
                # Ajouter seulement si pas déjà dans les résultats
                if memory.get("id", "") not in vector_ids:
                    vector_results.append({
                        "content": memory["content"],
                        "timestamp": memory["timestamp"],
                        "type": "synthetic",
                        "topic": topic,
                        "score": 0.5  # Score arbitraire pour les résultats non vectoriels
                    })
        
        return vector_results
    
    def get_memory_by_topic(self, topic: str) -> List[Dict[str, Any]]:
        """
        Récupère les mémoires synthétiques d'un sujet spécifique.
        
        Args:
            topic: Sujet des mémoires à récupérer
            
        Returns:
            Liste des mémoires du sujet
        """
        return self.memory_data["topics"].get(topic, [])
    
    def remember_explicit_info(self, info: str, topic: str = "user_info") -> int:
        """
        Mémorise explicitement une information demandée par l'utilisateur.
        
        Args:
            info: Information à mémoriser
            topic: Sujet ou catégorie de l'information
            
        Returns:
            ID de la mémoire créée
        """
        try:
            # Stocker dans la mémoire vectorielle
            memory_id = self.vector_store.add_memory(
                content=info,
                metadata={
                    "type": "explicit",
                    "topic": topic,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            
            logger.info(f"Information mémorisée explicitement avec ID {memory_id}")
            return memory_id
            
        except Exception as e:
            logger.error(f"Erreur lors de la mémorisation explicite: {str(e)}")
            return -1

# Instance globale du gestionnaire de mémoire synthétique
synthetic_memory = SyntheticMemory()