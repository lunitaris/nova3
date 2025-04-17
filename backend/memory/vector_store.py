import os
import json
import time
import faiss
import numpy as np
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import pickle

# Remplacer HuggingFaceEmbeddings par FakeEmbeddings pour le développement
from langchain_community.embeddings import FakeEmbeddings

from backend.config import config

logger = logging.getLogger(__name__)

class VectorMemoryStore:
    """
    Système de mémoire vectorielle utilisant FAISS pour stocker et rechercher des souvenirs.
    """
    
    def __init__(self, embedding_dimension: int = None, index_path: str = None):
        """
        Initialise le stockage de mémoire vectorielle.
        
        Args:
            embedding_dimension: Dimension des vecteurs d'embedding
            index_path: Chemin pour charger/sauvegarder l'index
        """
        self.embedding_dimension = embedding_dimension or config.memory.vector_dimension
        self.index_path = index_path or os.path.join(config.data_dir, "memories", "vector_index")
        self.metadata_path = os.path.join(config.data_dir, "memories", "vector_metadata.json")
        
        # Initialiser un modèle d'embedding factice pour le développement
        self.embeddings = FakeEmbeddings(size=self.embedding_dimension)
        
        # Initialiser ou charger l'index
        self._initialize_index()
        
        # Charger les métadonnées
        self.metadata = self._load_metadata()
        
        # ID actuel pour les nouveaux vecteurs
        self.current_id = max(map(int, self.metadata.keys()), default=0) + 1

        
    def _initialize_index(self):
        """Initialise ou charge l'index FAISS."""
        try:
            if os.path.exists(f"{self.index_path}.faiss"):
                logger.info("Chargement d'un index FAISS existant")
                self.index = faiss.read_index(f"{self.index_path}.faiss")
                logger.info(f"Index chargé avec {self.index.ntotal} vecteurs")
            else:
                logger.info(f"Création d'un nouvel index FAISS de dimension {self.embedding_dimension}")
                self.index = faiss.IndexFlatL2(self.embedding_dimension)
                logger.info("Nouvel index créé")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de l'index: {str(e)}")
            logger.info("Création d'un nouvel index par défaut")
            self.index = faiss.IndexFlatL2(self.embedding_dimension)
    
    def _load_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Charge les métadonnées associées aux vecteurs."""
        if os.path.exists(self.metadata_path):
            try:
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Erreur lors du chargement des métadonnées: {str(e)}")
                return {}
        return {}
    
    def _save_metadata(self):
        """Sauvegarde les métadonnées associées aux vecteurs."""
        try:
            os.makedirs(os.path.dirname(self.metadata_path), exist_ok=True)
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des métadonnées: {str(e)}")
            
    def _save_index(self):
        """Sauvegarde l'index FAISS."""
        try:
            os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
            faiss.write_index(self.index, f"{self.index_path}.faiss")
            logger.info(f"Index sauvegardé avec {self.index.ntotal} vecteurs")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de l'index: {str(e)}")
    
    def add_memory(self, content: str, metadata: Dict[str, Any] = None, score_pertinence: float = None, source_conversation_id: str = None) -> int:
        """
        Ajoute un nouveau souvenir à l'index.
        
        Args:
            content: Contenu textuel du souvenir
            metadata: Métadonnées associées au souvenir
            score_pertinence: Score de pertinence (0-1), calculé automatiquement si non spécifié
            source_conversation_id: ID de la conversation source
            
        Returns:
            ID du souvenir ajouté
        """
        try:
            # Générer l'embedding
            vector = self.embeddings.embed_query(content)
            vector_np = np.array([vector], dtype=np.float32)
            
            # Ajouter à l'index
            self.index.add(vector_np)
            
            # Calculer le score de pertinence si non spécifié
            if score_pertinence is None:
                # Algorithme simple: longueur relative du contenu (jusqu'à un maximum raisonnable)
                content_length = len(content.split())
                score_pertinence = min(content_length / 100, 1.0) * 0.7 + 0.3
                # Le score est entre 0.3 et 1.0, avec 0.3 comme score minimal
            
            # Préparer les métadonnées
            memory_id = str(self.current_id)
            memory_metadata = {
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "score_pertinence": score_pertinence,
                "type": "explicit",
                **(metadata or {})
            }
            
            # Ajouter le source_conversation_id si spécifié
            if source_conversation_id:
                memory_metadata["source_conversation_id"] = source_conversation_id
                
            # Stocker les métadonnées
            self.metadata[memory_id] = memory_metadata
            
            # Incrémenter l'ID courant
            self.current_id += 1
            
            # Sauvegarder
            self._save_metadata()
            self._save_index()
            
            logger.info(f"Souvenir ajouté avec l'ID {memory_id}, score: {score_pertinence:.2f}")
            return int(memory_id)
            
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout d'un souvenir: {str(e)}")
            return -1
    
    def search_memories(self, query: str, k: int = 5, min_score: float = 0.0, max_age_days: int = None) -> List[Dict[str, Any]]:
        """
        Recherche des souvenirs pertinents.
        
        Args:
            query: Requête textuelle
            k: Nombre de résultats à retourner
            min_score: Score minimal de pertinence pour filtrer les résultats
            max_age_days: Âge maximal des souvenirs en jours
            
        Returns:
            Liste des souvenirs pertinents avec leurs métadonnées
        """
        try:
            # Vérifier si l'index est vide
            if self.index.ntotal == 0:
                logger.info("Index vide, aucun souvenir disponible")
                return []
            
            # Générer l'embedding de la requête
            query_vector = self.embeddings.embed_query(query)
            query_vector_np = np.array([query_vector], dtype=np.float32)
            
            # Limiter k au nombre de vecteurs disponibles
            k = min(k, self.index.ntotal)
            
            # Rechercher les vecteurs les plus proches
            distances, indices = self.index.search(query_vector_np, k)
            
            # Récupérer les métadonnées
            results = []
            for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
                # L'index retourné par FAISS correspond à la position dans l'index
                # Nous devons retrouver l'ID correspondant dans les métadonnées
                matching_ids = [mid for mid, mdata in self.metadata.items() 
                                if mdata.get("faiss_idx", None) == idx]
                
                if matching_ids:
                    memory_id = matching_ids[0]
                    metadata = self.metadata[memory_id].copy()
                    metadata["score"] = float(1.0 / (1.0 + dist))  # Convertir la distance en score
                    metadata["memory_id"] = memory_id
                    
                    # Filtrer par score de pertinence
                    if metadata.get("score_pertinence", 0) < min_score:
                        continue
                    
                    # Filtrer par âge si spécifié
                    if max_age_days is not None and "timestamp" in metadata:
                        try:
                            mem_date = datetime.fromisoformat(metadata["timestamp"])
                            age_days = (datetime.now() - mem_date).days
                            if age_days > max_age_days:
                                continue
                        except:
                            # Ignorer les erreurs de parsing de date
                            pass
                    
                    results.append(metadata)
            
            # Trier par score décroissant
            results.sort(key=lambda x: x["score"], reverse=True)
            
            return results
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de souvenirs: {str(e)}")
            return []
    
    def delete_memory(self, memory_id: str) -> bool:
        """
        Supprime un souvenir.
        Note: La suppression dans FAISS est complexe, on marque simplement comme supprimé dans les métadonnées.
        
        Args:
            memory_id: ID du souvenir à supprimer
            
        Returns:
            True si supprimé avec succès, False sinon
        """
        try:
            if memory_id in self.metadata:
                self.metadata[memory_id]["deleted"] = True
                self.metadata[memory_id]["deletion_timestamp"] = datetime.now().isoformat()
                self._save_metadata()
                logger.info(f"Souvenir {memory_id} marqué comme supprimé")
                return True
            else:
                logger.warning(f"Souvenir {memory_id} non trouvé pour suppression")
                return False
        except Exception as e:
            logger.error(f"Erreur lors de la suppression du souvenir {memory_id}: {str(e)}")
            return False

    def update_memory(self, memory_id: str, content: str = None, metadata: Dict[str, Any] = None, score_pertinence: float = None) -> bool:
        """
        Met à jour un souvenir existant.
        Si le contenu est modifié, cela nécessite de réindexer.
        
        Args:
            memory_id: ID du souvenir à mettre à jour
            content: Nouveau contenu (facultatif)
            metadata: Métadonnées à mettre à jour (facultatif)
            score_pertinence: Nouveau score de pertinence (facultatif)
            
        Returns:
            True si mis à jour avec succès, False sinon
        """
        try:
            if memory_id not in self.metadata:
                logger.warning(f"Souvenir {memory_id} non trouvé pour mise à jour")
                return False
            
            if content:
                # Marquer l'ancien comme supprimé
                self.delete_memory(memory_id)
                
                # Préparer les métadonnées combinées
                combined_metadata = self.metadata[memory_id].copy()
                if metadata:
                    combined_metadata.update(metadata)
                
                # Mettre à jour le score de pertinence si spécifié
                if score_pertinence is not None:
                    combined_metadata["score_pertinence"] = score_pertinence
                
                # Conserver l'ID de la conversation source si présent
                source_conversation_id = combined_metadata.get("source_conversation_id")
                
                # Ajouter le nouveau contenu avec les métadonnées combinées
                new_id = self.add_memory(content, combined_metadata, 
                                         score_pertinence=combined_metadata.get("score_pertinence"),
                                         source_conversation_id=source_conversation_id)
                logger.info(f"Souvenir {memory_id} réindexé avec nouvel ID {new_id}")
                return True
            
            elif metadata or score_pertinence is not None:
                # Mise à jour des métadonnées uniquement
                if metadata:
                    self.metadata[memory_id].update(metadata)
                
                # Mettre à jour le score de pertinence si spécifié
                if score_pertinence is not None:
                    self.metadata[memory_id]["score_pertinence"] = score_pertinence
                
                self.metadata[memory_id]["updated_at"] = datetime.now().isoformat()
                self._save_metadata()
                logger.info(f"Métadonnées du souvenir {memory_id} mises à jour")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du souvenir {memory_id}: {str(e)}")
            return False

    def rebuild_index(self):
        """
        Reconstruit l'index FAISS à partir des métadonnées (utile pour le nettoyage).
        """
        try:
            # Créer un nouvel index
            new_index = faiss.IndexFlatL2(self.embedding_dimension)
            
            # Mettre à jour les métadonnées
            updated_metadata = {}
            current_idx = 0
            
            for memory_id, metadata in self.metadata.items():
                # Ignorer les souvenirs supprimés
                if metadata.get("deleted", False):
                    continue
                
                # Récupérer le contenu
                content = metadata.get("content", "")
                if not content:
                    continue
                
                # Générer l'embedding
                vector = self.embeddings.embed_query(content)
                vector_np = np.array([vector], dtype=np.float32)
                
                # Ajouter à l'index
                new_index.add(vector_np)
                
                # Mettre à jour les métadonnées
                metadata["faiss_idx"] = current_idx
                updated_metadata[memory_id] = metadata
                current_idx += 1
            
            # Remplacer l'index et les métadonnées
            self.index = new_index
            self.metadata = updated_metadata
            
            # Sauvegarder
            self._save_index()
            self._save_metadata()
            
            logger.info(f"Index reconstruit avec {self.index.ntotal} vecteurs")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la reconstruction de l'index: {str(e)}")
            return False
            
    def get_all_memories(self, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """
        Récupère tous les souvenirs stockés avec leurs métadonnées.
        
        Args:
            include_deleted: Si True, inclut également les souvenirs supprimés
            
        Returns:
            Liste de tous les souvenirs avec leurs métadonnées
        """
        memories = []
        
        for memory_id, metadata in self.metadata.items():
            # Ignorer les souvenirs supprimés si demandé
            if not include_deleted and metadata.get("deleted", False):
                continue
                
            # Copier les métadonnées et ajouter l'ID
            memory_data = metadata.copy()
            memory_data["memory_id"] = memory_id
            
            # Si l'ID FAISS n'est pas nécessaire, le supprimer pour clarté
            if "faiss_idx" in memory_data:
                del memory_data["faiss_idx"]
                
            memories.append(memory_data)
            
        return memories

# Instance globale du gestionnaire de mémoire vectorielle
vector_store = VectorMemoryStore()