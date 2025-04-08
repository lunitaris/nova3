/**
 * Gestionnaire de mémoire pour l'Assistant IA
 */
class MemoryManager {
    constructor() {
        this.memoryCache = {};
    }
    
    /**
     * Recherche des souvenirs en mémoire
     * @param {string} query - Requête de recherche
     * @param {string} topic - Sujet de mémoire (optionnel)
     * @param {number} maxResults - Nombre maximal de résultats
     * @returns {Promise<Array>} Résultats de la recherche
     */
    async searchMemories(query, topic = null, maxResults = 5) {
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.API.MEMORY}/search`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    query,
                    topic,
                    max_results: maxResults
                })
            });
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const data = await response.json();
            return data.results;
        } catch (error) {
            console.error("Erreur lors de la recherche en mémoire:", error);
            return [];
        }
    }
    
    /**
     * Ajoute une information à la mémoire explicite
     * @param {string} content - Contenu à mémoriser
     * @param {string} topic - Sujet de la mémoire
     * @returns {Promise<Object>} Résultat de l'opération
     */
    async rememberInfo(content, topic = "user_info") {
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.API.MEMORY}/remember`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    content,
                    topic
                })
            });
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error("Erreur lors de l'enregistrement en mémoire:", error);
            throw error;
        }
    }
    
    /**
     * Récupère les sujets disponibles en mémoire
     * @returns {Promise<Array>} Liste des sujets
     */
    async getTopics() {
        try {
            // Vérifier si on a un cache récent
            if (this.memoryCache.topics && 
                (Date.now() - this.memoryCache.topicsTimestamp) < 60000) {
                return this.memoryCache.topics;
            }
            
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.API.MEMORY}/topics`);
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const topics = await response.json();
            
            // Mettre en cache
            this.memoryCache.topics = topics;
            this.memoryCache.topicsTimestamp = Date.now();
            
            return topics;
        } catch (error) {
            console.error("Erreur lors de la récupération des sujets:", error);
            return [];
        }
    }
    
    /**
     * Récupère les mémoires d'un sujet spécifique
     * @param {string} topic - Sujet à récupérer
     * @returns {Promise<Array>} Liste des mémoires du sujet
     */
    async getMemoriesByTopic(topic) {
        try {
            // Vérifier si on a un cache récent
            const cacheKey = `topic_${topic}`;
            if (this.memoryCache[cacheKey] && 
                (Date.now() - this.memoryCache[`${cacheKey}_timestamp`]) < 60000) {
                return this.memoryCache[cacheKey];
            }
            
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.API.MEMORY}/topic/${topic}`);
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const memories = await response.json();
            
            // Mettre en cache
            this.memoryCache[cacheKey] = memories;
            this.memoryCache[`${cacheKey}_timestamp`] = Date.now();
            
            return memories;
        } catch (error) {
            console.error(`Erreur lors de la récupération des mémoires du sujet ${topic}:`, error);
            return [];
        }
    }
    
    /**
     * Supprime une mémoire spécifique
     * @param {string} memoryId - ID de la mémoire à supprimer
     * @returns {Promise<boolean>} Succès de la suppression
     */
    async deleteMemory(memoryId) {
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.API.MEMORY}/memory/${memoryId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const result = await response.json();
            
            // Invalider le cache
            this.invalidateCache();
            
            return result.status === 'success';
        } catch (error) {
            console.error(`Erreur lors de la suppression de la mémoire ${memoryId}:`, error);
            return false;
        }
    }
    
    /**
     * Met à jour une mémoire existante
     * @param {string} memoryId - ID de la mémoire
     * @param {string} content - Nouveau contenu
     * @param {string} topic - Nouveau sujet (optionnel)
     * @returns {Promise<boolean>} Succès de la mise à jour
     */
    async updateMemory(memoryId, content, topic = null) {
        try {
            const payload = { content };
            if (topic) payload.topic = topic;
            
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.API.MEMORY}/memory/${memoryId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const result = await response.json();
            
            // Invalider le cache
            this.invalidateCache();
            
            return result.status === 'success';
        } catch (error) {
            console.error(`Erreur lors de la mise à jour de la mémoire ${memoryId}:`, error);
            return false;
        }
    }
    
    /**
     * Compresse les mémoires (traitement de maintenance)
     * @returns {Promise<boolean>} Succès de la compression
     */
    async compressMemories() {
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.API.MEMORY}/compress`, {
                method: 'POST'
            });
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const result = await response.json();
            
            // Invalider le cache
            this.invalidateCache();
            
            return result.status === 'success';
        } catch (error) {
            console.error("Erreur lors de la compression des mémoires:", error);
            return false;
        }
    }
    
    /**
     * Invalide le cache de mémoire
     */
    invalidateCache() {
        this.memoryCache = {};
    }
    
    /**
     * Détecte si un message contient une demande de mémorisation
     * @param {string} message - Message à analyser
     * @returns {boolean} True si c'est une demande de mémorisation
     */
    isMemoryRequest(message) {
        const lowerMessage = message.toLowerCase().trim();
        return lowerMessage.startsWith("souviens-toi") || 
               lowerMessage.startsWith("rappelle-toi") || 
               lowerMessage.startsWith("mémorise") ||
               lowerMessage.startsWith("retiens");
    }
    
    /**
     * Extrait l'information à mémoriser d'un message
     * @param {string} message - Message contenant une demande de mémorisation
     * @returns {Object} Information extraite et sujet
     */
    extractMemoryInfo(message) {
        const lowerMessage = message.toLowerCase().trim();
        let content = "";
        let topic = "user_info";
        
        // Trouver le premier espace pour extraire le reste du message
        const firstSpace = message.indexOf(' ');
        if (firstSpace !== -1) {
            content = message.substring(firstSpace + 1).trim();
        }
        
        // Chercher si un sujet est spécifié (format: "... sujet: xyz")
        const topicMatch = content.match(/sujet\s*:\s*([a-zA-Z0-9_]+)/i);
        if (topicMatch && topicMatch[1]) {
            topic = topicMatch[1].toLowerCase();
            // Retirer la partie "sujet: xyz" du contenu
            content = content.replace(/sujet\s*:\s*([a-zA-Z0-9_]+)/i, '').trim();
        }
        
        return { content, topic };
    }
}

// Instance globale
const memoryManager = new MemoryManager();