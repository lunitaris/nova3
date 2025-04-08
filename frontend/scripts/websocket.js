/**
 * Gestionnaire de connexions WebSocket pour l'Assistant IA
 */
class WebSocketManager {
    constructor() {
        this.socket = null;
        this.clientId = this._generateClientId();
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000; // ms
        
        // Callbacks
        this.onMessageCallbacks = [];
        this.onConnectCallbacks = [];
        this.onDisconnectCallbacks = [];
        this.onErrorCallbacks = [];
        
        // Callback spécifiques pour les réponses streaming
        this.streamingCallbacks = {
            start: null,
            token: null,
            end: null,
            error: null
        };
        
        // Callback spécifiques pour le flux audio
        this.voiceCallbacks = {
            transcription: null,
            audioStart: null,
            audioChunk: null,
            audioEnd: null,
            error: null
        };
    }
    
    /**
     * Génère un ID client unique
     * @returns {string} ID client
     */
    _generateClientId() {
        return 'client_' + Math.random().toString(36).substring(2, 15);
    }
    
    /**
     * Connecte au serveur WebSocket pour le chat
     * @returns {Promise} Promesse résolue quand la connexion est établie
     */


    connectChat() {
        return new Promise((resolve, reject) => {
            // Si déjà connecté, résoudre immédiatement
            if (this.socket && this.socket.readyState === WebSocket.OPEN) {
                resolve(this.socket);
                return;
            }
            
            // Si une connexion est en cours, fermer d'abord
            if (this.socket) {
                try {
                    this.socket.close();
                } catch (e) {
                    console.warn("Erreur lors de la fermeture du socket existant:", e);
                }
            }
            
            const url = `${CONFIG.WEBSOCKET_BASE_URL}${CONFIG.API.CHAT}/ws/${this.clientId}`;
            this.socket = new WebSocket(url);
            
            this.socket.onopen = () => {
                console.log("WebSocket connecté");
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this._triggerCallbacks(this.onConnectCallbacks, this.socket);
                resolve(this.socket);
            };
            
        // Modification à apporter au fichier frontend/scripts/websocket.js
        // Améliorer le handler des messages WebSocket dans la méthode connectChat()
            this.socket.onmessage = (event) => {
                try {
                    console.log("Raw WebSocket message received:", event.data);
                    const data = JSON.parse(event.data);
                    console.log("WebSocket message parsed:", data);
                    
                    // Router selon le type de message
                    switch(data.type) {
                        case 'start':
                            console.log("⭐ START message received");
                            if (this.streamingCallbacks.start) {
                                this.streamingCallbacks.start(data);
                            }
                            break;
                        case 'token':
                            if (this.streamingCallbacks.token) {
                                this.streamingCallbacks.token(data.content);
                                console.log(`🔤 TOKEN handled: "${data.content}"`);
                            } else {
                                console.error("No token callback configured!");
                            }
                            break;
                        case 'end':
                            console.log("🏁 END message received with content:", data.content);
                            if (this.streamingCallbacks.end) {
                                // S'assurer que l'indicateur de frappe est bien nettoyé
                                this.streamingCallbacks.end(data);
                            } else {
                                console.error("No end callback configured!");
                            }
                            break;
                        case 'error':
                            console.error("⚠️ ERROR message received:", data);
                            if (this.streamingCallbacks.error) {
                                this.streamingCallbacks.error(data);
                            }
                            break;
                        default:
                            // Transmettre aux callbacks génériques
                            console.log("⚠️ UNKNOWN message type:", data.type);
                            this._triggerCallbacks(this.onMessageCallbacks, data);
                    }
                } catch (error) {
                    console.error("❌ Error parsing WebSocket message:", error, event.data);
                    if (this.streamingCallbacks.error) {
                        this.streamingCallbacks.error({
                            type: 'error',
                            content: "Erreur de communication avec le serveur."
                        });
                    }
                }
            };
            
            this.socket.onclose = (event) => {
                console.log("WebSocket déconnecté", event.code, event.reason);
                this.isConnected = false;
                this._triggerCallbacks(this.onDisconnectCallbacks, event);
                
                // Tentative de reconnexion automatique
                if (this.reconnectAttempts < this.maxReconnectAttempts) {
                    console.log(`Tentative de reconnexion dans ${this.reconnectDelay}ms...`);
                    setTimeout(() => {
                        this.reconnectAttempts++;
                        this.connectChat().catch(error => {
                            console.error("Échec de la reconnexion:", error);
                        });
                    }, this.reconnectDelay);
                }
            };
            
            this.socket.onerror = (error) => {
                console.error("Erreur WebSocket:", error);
                this._triggerCallbacks(this.onErrorCallbacks, error);
                reject(error);
            };
        });
    }
    


    /**
     * Connecte au serveur WebSocket pour le streaming vocal
     * @param {string} conversationId - ID de la conversation
     * @returns {Promise} Promesse résolue quand la connexion est établie
     */
    connectVoice(conversationId) {
        return new Promise((resolve, reject) => {
            const url = `${CONFIG.WEBSOCKET_BASE_URL}${CONFIG.API.VOICE}/ws/stream/${conversationId}`;
            this.voiceSocket = new WebSocket(url);
            
            this.voiceSocket.onopen = () => {
                console.log("WebSocket vocal connecté");
                resolve(this.voiceSocket);
            };
            
            this.voiceSocket.onmessage = (event) => {
                // Si c'est un message texte, c'est une commande ou une notification
                if (typeof event.data === 'string') {
                    try {
                        const data = JSON.parse(event.data);
                        console.log("WebSocket vocal message texte reçu:", data);
                        
                        // Router selon le type de message
                        switch(data.type) {
                            case 'transcription':
                                if (this.voiceCallbacks.transcription) {
                                    this.voiceCallbacks.transcription(data.text);
                                }
                                break;
                            case 'response_text':
                                // Géré par l'application
                                break;
                            case 'response_audio_start':
                                if (this.voiceCallbacks.audioStart) {
                                    this.voiceCallbacks.audioStart();
                                }
                                break;
                            case 'response_audio_end':
                                if (this.voiceCallbacks.audioEnd) {
                                    this.voiceCallbacks.audioEnd();
                                }
                                break;
                            case 'error':
                                if (this.voiceCallbacks.error) {
                                    this.voiceCallbacks.error(data);
                                }
                                break;
                        }
                    } catch (error) {
                        console.error("Erreur de parsing WebSocket vocal:", error);
                    }
                } 
                // Si c'est un Blob, c'est un morceau audio
                else if (event.data instanceof Blob) {
                    if (this.voiceCallbacks.audioChunk) {
                        this.voiceCallbacks.audioChunk(event.data);
                    }
                }
            };
            
            this.voiceSocket.onclose = (event) => {
                console.log("WebSocket vocal déconnecté", event.code, event.reason);
            };
            
            this.voiceSocket.onerror = (error) => {
                console.error("Erreur WebSocket vocal:", error);
                reject(error);
            };
        });
    }
    
    /**
     * Envoie un message texte via WebSocket
     * @param {Object} message - Message à envoyer 
     * @returns {boolean} Succès de l'envoi
     */
    sendMessage(message) {
        if (!this.socket || !this.isConnected) {
            console.error("WebSocket non connecté");
            return false;
        }
        
        try {
            const messageStr = typeof message === 'string' ? message : JSON.stringify(message);
            this.socket.send(messageStr);
            return true;
        } catch (error) {
            console.error("Erreur d'envoi WebSocket:", error);
            return false;
        }
    }
    
    /**
     * Envoie des données audio via WebSocket vocal
     * @param {Blob} audioBlob - Données audio à envoyer
     * @returns {boolean} Succès de l'envoi
     */
    sendAudioData(audioBlob) {
        if (!this.voiceSocket || this.voiceSocket.readyState !== WebSocket.OPEN) {
            console.error("WebSocket vocal non connecté");
            return false;
        }
        
        try {
            this.voiceSocket.send(audioBlob);
            return true;
        } catch (error) {
            console.error("Erreur d'envoi audio WebSocket:", error);
            return false;
        }
    }
    
    /**
     * Envoie une commande au WebSocket vocal
     * @param {Object} command - Commande à envoyer
     * @returns {boolean} Succès de l'envoi
     */
    sendVoiceCommand(command) {
        if (!this.voiceSocket || this.voiceSocket.readyState !== WebSocket.OPEN) {
            console.error("WebSocket vocal non connecté");
            return false;
        }
        
        try {
            this.voiceSocket.send(JSON.stringify(command));
            return true;
        } catch (error) {
            console.error("Erreur d'envoi de commande WebSocket vocal:", error);
            return false;
        }
    }
    
    /**
     * Déconnecte du serveur WebSocket
     */
    disconnect() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        
        if (this.voiceSocket) {
            this.voiceSocket.close();
            this.voiceSocket = null;
        }
        
        this.isConnected = false;
    }
    
    /**
     * Enregistre un callback pour les messages
     * @param {Function} callback - Fonction à appeler
     */
    onMessage(callback) {
        this.onMessageCallbacks.push(callback);
    }
    
    /**
     * Enregistre un callback pour la connexion
     * @param {Function} callback - Fonction à appeler
     */
    onConnect(callback) {
        this.onConnectCallbacks.push(callback);
    }
    
    /**
     * Enregistre un callback pour la déconnexion
     * @param {Function} callback - Fonction à appeler
     */
    onDisconnect(callback) {
        this.onDisconnectCallbacks.push(callback);
    }
    
    /**
     * Enregistre un callback pour les erreurs
     * @param {Function} callback - Fonction à appeler
     */
    onError(callback) {
        this.onErrorCallbacks.push(callback);
    }
    
    /**
     * Configure les callbacks pour le streaming
     * @param {Object} callbacks - Objet contenant les callbacks
     */
    setStreamingCallbacks(callbacks) {
        this.streamingCallbacks = { ...this.streamingCallbacks, ...callbacks };
    }
    
    /**
     * Configure les callbacks pour le vocal
     * @param {Object} callbacks - Objet contenant les callbacks
     */
    setVoiceCallbacks(callbacks) {
        this.voiceCallbacks = { ...this.voiceCallbacks, ...callbacks };
    }
    
    /**
     * Déclenche tous les callbacks d'une liste
     * @param {Array} callbackList - Liste de callbacks à appeler
     * @param {any} data - Données à passer aux callbacks
     */
    _triggerCallbacks(callbackList, data) {
        for (const callback of callbackList) {
            try {
                callback(data);
            } catch (error) {
                console.error("Erreur dans un callback:", error);
            }
        }
    }



    reset() {
        // Fermer toutes les connexions existantes
        if (this.socket) {
            try {
                this.socket.close();
            } catch (e) {
                console.warn("Erreur lors de la fermeture du socket:", e);
            }
            this.socket = null;
        }
        
        if (this.voiceSocket) {
            try {
                this.voiceSocket.close();
            } catch (e) {
                console.warn("Erreur lors de la fermeture du socket vocal:", e);
            }
            this.voiceSocket = null;
        }
        
        // Réinitialiser l'état
        this.isConnected = false;
        this.reconnectAttempts = 0;
        
        // Générer un nouveau clientId
        this.clientId = this._generateClientId();
        
        console.log("WebSocketManager réinitialisé avec clientId:", this.clientId);
    }




}

// Instance globale
const wsManager = new WebSocketManager();