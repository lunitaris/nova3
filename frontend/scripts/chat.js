/**
 * Gestionnaire de chat pour l'Assistant IA
 */
class ChatManager {

    constructor() {
        this.conversations = [];
        this.currentConversationId = null;
        this.isTyping = false;
        this.messageQueue = [];
        
        // Variables pour le streaming
        this.streamingText = ""; // Pour stocker le texte en cours de streaming
        this.accumulatedTokens = "";
        this.isStreaming = false;
        
        // Éléments DOM
        this.messagesContainer = document.getElementById('messages-container');
        this.chatInput = document.getElementById('chat-input');
        this.sendButton = document.getElementById('send-button');
        this.conversationList = document.getElementById('conversation-list');
        this.conversationTitle = document.getElementById('conversation-title');
        
        // Templates pour les messages
        this.messageTemplate = document.getElementById('message-template');
        this.conversationItemTemplate = document.getElementById('conversation-item-template');
        
        // Nettoyer les indicateurs résiduels au démarrage
        this._cleanupResidualElements();
        
        // Démarrer les WebSockets
        this._initWebSocket();
        
        // Initialiser les événements
        this._initEvents();
        
        // Charger les conversations
        this.loadConversations();
    }
    

    /**
     * Initialise les connexions WebSocket
     */
    _initWebSocket() {
        // Établir la connexion
        wsManager.connectChat().catch(error => {
            console.error("Erreur de connexion WebSocket:", error);
            this._showError("Impossible de se connecter au serveur. Vérifiez votre connexion.");
        });
        
        // Configurer les callbacks de streaming
            wsManager.setStreamingCallbacks({
                start: (data) => {
                    console.log("Début du streaming");
                    
                    // FIX: Si conversation_id est renvoyé, on l'utilise comme ID officiel
                    if (data.conversation_id && chatManager.currentConversationId?.startsWith('temp_')) {
                        chatManager.currentConversationId = data.conversation_id;
                        console.log("🔁 ID temporaire remplacé par l’ID officiel :", data.conversation_id);
                    }
                
                    chatManager.isStreaming = true;
                    chatManager.accumulatedTokens = "";
                    chatManager.streamingText = "";
                    chatManager._showTypingIndicator();
                },
                token: (token) => {
                    // Ignore les tokens s’il y a eu un switch de conversation
                    if (!chatManager.isStreaming) return;
                
                    chatManager.accumulatedTokens += token;
                    chatManager._appendToTypingIndicator(token);
                },
                end: (data) => {
                    if (data.conversation_id !== chatManager.currentConversationId) {
                        console.warn("⛔ Réponse reçue pour une autre conversation, ignorée");
                        return;
                    }
                
                    const finalContent = data.content || chatManager.accumulatedTokens || "";
                    chatManager.currentConversationId = data.conversation_id;
                    chatManager._handleEndOfStreaming(finalContent, data.conversation_id);
                
                    // ✅ Attendre plus longtemps (700ms) avant de charger les conversations depuis le backend
                    setTimeout(() => {
                        chatManager.loadConversations(); 
                    }, 700);  // <- augmente à 700ms minimum
                

                    if (userPreferences.get('CONVERSATION_MODE') === 'voice') {
                        const voiceEvent = new CustomEvent('voiceResponse', {
                            detail: { text: finalContent }
                        });
                        document.dispatchEvent(voiceEvent);
                    }
                },
            error: (data) => {
                console.error("Erreur de streaming:", data);
                this._removeTypingIndicator();
                this.isStreaming = false;
                this.accumulatedTokens = "";
                this.streamingText = "";
                this._showError(data.content || "Erreur lors de la génération de la réponse.");
            }
        });
    }


//------------------------------------------------------------------------------------------------------------------------

    /**
     * Gère la fin du streaming de manière fiable
     * @param {string} finalContent - Contenu final du message
     * @param {string} conversationId - ID de la conversation
     */
    _handleEndOfStreaming(finalContent, conversationId) {
        console.log("HANDLER: Gestion de fin de streaming", {
            finalContent: finalContent.substring(0, 30) + "...",
            conversationId: conversationId
        });
        
        // Stocker ces informations dans des variables globales pour récupération d'urgence
        window._lastFinalContent = finalContent;
        window._lastConversationId = conversationId;
        
        // 1. Supprimer tous les indicateurs de frappe existants
        const indicators = document.querySelectorAll('#typing-indicator, .typing-indicator');
        indicators.forEach(indicator => {
            if (indicator && indicator.parentNode) {
                indicator.parentNode.removeChild(indicator);
            }
        });
        
        // 2. Réinitialiser toutes les variables d'état
        this.isStreaming = false;
        this.accumulatedTokens = "";
        this.streamingText = "";
        
        // 3. Ajouter le message finalisé au DOM après un petit délai
        setTimeout(() => {
            try {
                // Vérifier si le message existe déjà (éviter les doublons)
                const messageId = `msg_${Date.now()}`;
                const existingMessages = Array.from(document.querySelectorAll('.message.assistant .message-text'));
                const messageExists = existingMessages.some(el => el.textContent === finalContent);
                
                if (!messageExists) {
                    console.log("HANDLER: Ajout du message au DOM");
                    
                    // Créer le message manuellement 
                    const messageContainer = document.createElement('div');
                    messageContainer.className = 'message assistant';
                    messageContainer.id = messageId;
                    
                    messageContainer.innerHTML = `
                        <div class="message-avatar">
                            <i class="fas fa-robot"></i>
                        </div>
                        <div class="message-content">
                            <div class="message-text">${finalContent}</div>
                            <div class="message-time">${new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}</div>
                        </div>
                    `;
                    
                    // IMPORTANT: S'assurer que le message est ajouté au bon container
                    if (this.messagesContainer) {
                        this.messagesContainer.appendChild(messageContainer);

                        //-------------------------------------------------------------------------------------
                        // 🎯 Surveillance du message assistant injecté
                        const observer = new MutationObserver((mutations) => {
                            mutations.forEach(mutation => {
                                mutation.removedNodes.forEach(node => {
                                    if (node === messageContainer) {
                                        console.warn("🧨 MESSAGE ASSISTANT SUPPRIMÉ DU DOM !");
                                        console.log("Timestamp suppression:", new Date().toLocaleTimeString());
                                        debugger; // ← ça déclenchera l'inspecteur Chrome/Firefox si ouvert
                                    }
                                });
                            });
                        });

                        observer.observe(this.messagesContainer, { childList: true });
                        //-------------------------------------------------------------------------------------
                        
                        // Force browser reflow/repaint
                        void this.messagesContainer.offsetHeight;
                        
                        // Forcer un repaint + scroll en cascade
                        requestAnimationFrame(() => {
                            requestAnimationFrame(() => {
                                this._scrollToBottom();
                            });
                        });
                    }
                    
                    // Vérifier après un court délai que le message est toujours là
                    setTimeout(() => {
                        const addedMessage = document.getElementById(messageId);
                        console.log("HANDLER: Vérification après ajout:", addedMessage ? "Message présent" : "Message ABSENT!");
                        
                        // Si le message a disparu, tenter de le restaurer
                        if (!addedMessage && this.messagesContainer) {
                            console.warn("RESTAURATION: Le message a disparu, tentative de restauration...");
                            const restoredMessage = messageContainer.cloneNode(true);
                            restoredMessage.id = messageId + "_restored";
                            this.messagesContainer.appendChild(restoredMessage);
                            this._scrollToBottom();
                        }
                    }, 200);
                } else {
                    console.log("HANDLER: Message déjà présent, pas de duplication");
                }
            } catch (error) {
                console.error("HANDLER ERROR:", error);
            }
            
            // 4. Mettre à jour les métadonnées de conversation
            try {
                if (conversationId) {
                    this.currentConversationId = conversationId;
                    
                    // Titre de la conversation
                    if (this.conversationTitle.textContent === 'Nouvelle conversation') {
                        const tempTitle = finalContent.split('.')[0];
                        this.conversationTitle.textContent = tempTitle.length > 30 
                            ? tempTitle.substring(0, 30) + '...' 
                            : tempTitle;
                    }
                    
                    // Rafraîchir la liste après un délai
                    setTimeout(() => {
                        this.loadConversations();
                    }, 300);
                }
            } catch (error) {
                console.error("HANDLER ERROR (conversationId):", error);
            }
        }, 100);
    }

//------------------------------------------------------------------------------------------------------------------------




    async debugFixConversations() {
        console.log("🔧 DEBUGGING: Tentative de récupération forcée des conversations");
        
        try {
            // 1. Forcer une requête directe avec des paramètres de cache différents
            const timestamp = Date.now();
            const url = `${CONFIG.API_BASE_URL}${CONFIG.API.CHAT}/conversations?_nocache=${timestamp}`;
            
            console.log("🔧 DEBUGGING: Requête directe vers:", url);
            
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
            });
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const conversations = await response.json();
            console.log("🔧 DEBUGGING: Conversations récupérées:", conversations);
            
            // 2. Forcer la mise à jour de l'interface, quelle que soit la réponse
            if (conversations && Array.isArray(conversations)) {
                this.conversations = conversations;
                
                // Vider complètement la liste actuelle
                this.conversationList.innerHTML = '';
                
                if (conversations.length === 0) {
                    // S'il n'y a vraiment aucune conversation
                    const emptyMessage = document.createElement('div');
                    emptyMessage.className = 'empty-conversations';
                    emptyMessage.textContent = 'Aucune conversation';
                    this.conversationList.appendChild(emptyMessage);
                } else {
                    // Recréer manuellement chaque élément de conversation
                    conversations.forEach(conv => {
                        const item = document.createElement('div');
                        item.className = 'conversation-item';
                        item.dataset.id = conv.conversation_id;
                        
                        if (conv.conversation_id === this.currentConversationId) {
                            item.classList.add('active');
                        }
                        
                        // Ajouter le contenu
                        const date = new Date(conv.last_updated);
                        const formattedDate = date.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
                        
                        item.innerHTML = `
                            <div class="conversation-title">${conv.title || 'Nouvelle conversation'}</div>
                            <div class="conversation-time">${formattedDate}</div>
                            <button class="delete-conversation-item-btn">
                                <i class="fas fa-times"></i>
                            </button>
                        `;
                        
                        // Ajouter les gestionnaires d'événements
                        item.addEventListener('click', (e) => {
                            if (!e.target.closest('.delete-conversation-item-btn')) {
                                this.selectConversation(conv.conversation_id);
                            }
                        });
                        
                        const deleteBtn = item.querySelector('.delete-conversation-item-btn');
                        deleteBtn.addEventListener('click', (e) => {
                            e.stopPropagation();
                            this.deleteConversation(conv.conversation_id);
                        });
                        
                        this.conversationList.appendChild(item);
                    });
                }
                
                console.log("🔧 DEBUGGING: Interface mise à jour avec succès!");
                return conversations;
            }
        } catch (error) {
            console.error("🔧 DEBUGGING: Erreur lors de la récupération forcée:", error);
        }
        
        // 3. Si tout échoue, créer une entrée factice pour la conversation actuelle
        if (this.currentConversationId) {
            console.log("🔧 DEBUGGING: Création d'une entrée factice pour la conversation actuelle");
            
            // Vider la liste et créer une entrée pour la conversation actuelle
            this.conversationList.innerHTML = '';
            
            const fakeConversation = {
                conversation_id: this.currentConversationId,
                title: this.conversationTitle.textContent || 'Conversation actuelle',
                last_updated: new Date().toISOString()
            };
            
            const item = document.createElement('div');
            item.className = 'conversation-item active';
            item.dataset.id = fakeConversation.conversation_id;
            
            item.innerHTML = `
                <div class="conversation-title">${fakeConversation.title}</div>
                <div class="conversation-time">${new Date().toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}</div>
                <button class="delete-conversation-item-btn">
                    <i class="fas fa-times"></i>
                </button>
            `;
            
            item.addEventListener('click', () => {
                // Ne rien faire, c'est déjà la conversation active
            });
            
            item.querySelector('.delete-conversation-item-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteConversation(fakeConversation.conversation_id);
            });
            
            this.conversationList.appendChild(item);
            this.conversations = [fakeConversation]; // Mise à jour de la liste locale
            
            console.log("🔧 DEBUGGING: Entrée factice créée!");
        }
    }

    /**
     * Ajoute localement une conversation à la liste sans attendre le serveur
     * @param {string} conversationId - ID de la conversation
     * @param {string} title - Titre de la conversation
     */
    // Ajouter cette méthode à la classe ChatManager
    _addLocalConversation(conversationId, title) {
        // Vérifier si la conversation existe déjà dans notre liste locale
        const exists = this.conversations.some(conv => conv.conversation_id === conversationId);
        
        if (!exists) {
            console.log(`Ajout local de la conversation ${conversationId} à la liste`);
            
            // Créer un objet conversation similaire à ce que renverrait l'API
            const newConversation = {
                conversation_id: conversationId,
                title: title || 'Nouvelle conversation',
                last_updated: new Date().toISOString(),
                message_count: 0,
                summary: ""
            };
            
            // Ajouter au début de la liste (car c'est la plus récente)
            this.conversations.unshift(newConversation);
            
            // Mettre à jour l'affichage
            this._updateConversationList();
        }
    }

    /**
     * Nettoie les éléments résiduels qui pourraient rester d'une session précédente
     */
    _cleanupResidualElements() {
        // Supprimer uniquement les indicateurs de frappe, pas les messages
        const residualIndicators = document.querySelectorAll('#typing-indicator, .typing-indicator');
        residualIndicators.forEach(el => {
            if (el && el.parentNode) {
                el.parentNode.removeChild(el);
            }
        });
        
        // Réinitialiser les variables d'état
        this.streamingText = "";
        this.accumulatedTokens = "";
        this.isStreaming = false;
        
        console.log("Nettoyage des éléments résiduels terminé");
    }



    // Ajouter une méthode pour vérifier et nettoyer les éléments résiduels
    _cleanupTypingIndicator() {
        // S'assurer qu'il n'y a pas d'éléments typing-indicator résiduels au chargement
        const oldIndicators = document.querySelectorAll('#typing-indicator');
        if (oldIndicators.length > 0) {
            oldIndicators.forEach(el => el.remove());
        }
    }
    
    /**
     * Initialise les événements
     */
    _initEvents() {
        // Envoi de message par clic sur le bouton
        this.sendButton.addEventListener('click', () => {
            this.sendMessage();
        });
        
        // Envoi de message par appui sur Entrée (sans Shift)
        this.chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Bouton pour créer une nouvelle conversation
        document.getElementById('new-chat-btn').addEventListener('click', () => {
            this.startNewConversation();
        });
        
        // Bouton pour effacer l'historique de la conversation actuelle
        document.getElementById('clear-conversation-btn').addEventListener('click', () => {
            this.clearCurrentConversation();
        });
        
        // Bouton pour supprimer la conversation actuelle
        document.getElementById('delete-conversation-btn').addEventListener('click', () => {
            this.deleteCurrentConversation();
        });
    }
    
    /**
     * Charge la liste des conversations depuis l'API
     */
    async loadConversations() {
        try {
            console.log("Chargement des conversations...");
            
            // Ajouter un cache-busting pour éviter les problèmes de cache
            const cacheBuster = `?_=${Date.now()}`;
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.API.CHAT}/conversations${cacheBuster}`);
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const conversations = await response.json();
            console.log(`${conversations.length} conversations chargées`);
            console.log("Conversation active:", this.currentConversationId);
            
            // Mise à jour critique: toujours mettre à jour la liste, même si elle semble identique
            this.conversations = conversations;
            
            // Forcer la mise à jour de l'interface quelle que soit la situation
            this._rebuildConversationList();
            
            return conversations;
        } catch (error) {
            console.error("Erreur de chargement des conversations:", error);
            this._showError("Impossible de charger les conversations.");
            return [];
        }
    }

    
    // Nouvelle méthode qui reconstruit complètement la liste des conversations
    _rebuildConversationList() {
        // Vider complètement la liste actuelle
        this.conversationList.innerHTML = '';
        
        // Si pas de conversations, afficher un message
        if (this.conversations.length === 0) {
            const emptyMessage = document.createElement('div');
            emptyMessage.className = 'empty-conversations';
            emptyMessage.textContent = 'Aucune conversation';
            this.conversationList.appendChild(emptyMessage);
            return;
        }
        
        // Fragment pour améliorer les performances
        const fragment = document.createDocumentFragment();
        
        // Créer un élément pour chaque conversation
        this.conversations.forEach(conv => {
            const item = document.createElement('div');
            item.className = 'conversation-item';
            if (conv.conversation_id === this.currentConversationId) {
                item.classList.add('active');
            }
            item.dataset.id = conv.conversation_id;
            
            // Formater la date
            const date = new Date(conv.last_updated);
            const formattedDate = date.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
            
            item.innerHTML = `
                <div class="conversation-title">${conv.title || 'Nouvelle conversation'}</div>
                <div class="conversation-time">${formattedDate}</div>
                <button class="delete-conversation-item-btn">
                    <i class="fas fa-times"></i>
                </button>
            `;
            
            // Gérer le clic pour sélectionner
            item.addEventListener('click', (e) => {
                if (!e.target.closest('.delete-conversation-item-btn')) {
                    this.selectConversation(conv.conversation_id);
                }
            });
            
            // Gérer le clic sur le bouton de suppression
            const deleteBtn = item.querySelector('.delete-conversation-item-btn');
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteConversation(conv.conversation_id);
            });
            
            fragment.appendChild(item);
        });
        
        // Ajouter tous les éléments en une seule opération DOM
        this.conversationList.appendChild(fragment);
    }
    
    /**
     * Met à jour l'affichage de la liste des conversations
     */
    _updateConversationList() {
        // Vider la liste actuelle
        this.conversationList.innerHTML = '';
        
        // Ajouter un log pour déboguer
        console.log(`Mise à jour de la liste des conversations: ${this.conversations.length} conversations`);
        console.log(`Conversation actuelle: ${this.currentConversationId}`);
        
        // Si pas de conversations, afficher un message
        if (this.conversations.length === 0) {
            const emptyMessage = document.createElement('div');
            emptyMessage.className = 'empty-conversations';
            emptyMessage.textContent = 'Aucune conversation';
            this.conversationList.appendChild(emptyMessage);
            return;
        }
        
        // Créer un élément pour chaque conversation
        this.conversations.forEach(conv => {
            const item = this.conversationItemTemplate.content.cloneNode(true);
            const container = item.querySelector('.conversation-item');
            
            // Définir les attributs
            container.dataset.id = conv.conversation_id;
            
            // CORRECTION: S'assurer que l'élément actif est correctement marqué
            if (conv.conversation_id === this.currentConversationId) {
                container.classList.add('active');
                console.log(`Conversation marquée active: ${conv.conversation_id}`);
            }
            
            // Définir le contenu
            const titleElement = item.querySelector('.conversation-title');
            titleElement.textContent = conv.title || 'Nouvelle conversation';
            
            // Formater la date
            const date = new Date(conv.last_updated);
            const formattedDate = date.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
            item.querySelector('.conversation-time').textContent = formattedDate;
            
            // Gérer le clic pour sélectionner
            container.addEventListener('click', (e) => {
                if (!e.target.closest('.delete-conversation-item-btn')) {
                    console.log(`Sélection de la conversation: ${conv.conversation_id}`);
                    this.selectConversation(conv.conversation_id);
                }
            });
            
            // Gérer le clic sur le bouton de suppression
            const deleteBtn = item.querySelector('.delete-conversation-item-btn');
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteConversation(conv.conversation_id);
            });
            
            this.conversationList.appendChild(item);
        });
    }
    
    /**
     * Sélectionne une conversation et charge ses messages
     * @param {string} conversationId - ID de la conversation
     */
    async selectConversation(conversationId) {
        this.currentConversationId = conversationId;
        console.log("📥 selectConversation triggered for:", conversationId);
        console.log("📥 DOM message count BEFORE:", this.messagesContainer.querySelectorAll('.message').length);

        
        // Mettre à jour la liste de conversations (pour l'élément actif)
        this._updateConversationList();
        
        // Vider la zone de messages
        this.messagesContainer.innerHTML = '';
        console.warn("🧹 messagesContainer vidé !");
        
        try {
            // Charger les messages
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.API.CHAT}/conversation/${conversationId}`);
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Mettre à jour le titre
            this.conversationTitle.textContent = data.metadata.title || 'Conversation';
            
            // Afficher les messages
            data.messages.forEach(message => {
                this._addMessage(message.content, message.role, false);
            });
            
            // Faire défiler vers le bas
            this._scrollToBottom();
            
            return data;
        } catch (error) {
            console.error("Erreur de chargement des messages:", error);
            this._showError("Impossible de charger les messages.");
            return null;
        }
    }
    
    /**
     * Démarre une nouvelle conversation
     */
    startNewConversation() {
        // Générer un ID temporaire unique
        const tempId = 'temp_' + Date.now();
        this.currentConversationId = tempId;
        
        // Ne pas sélectionner immédiatement : on va construire la liste mais ne pas recharger
        this._rebuildConversationList(); // OK visuellement
        
        // Vider la zone de messages
        this.messagesContainer.innerHTML = `
            <div class="welcome-message">
                <h3>Bienvenue sur votre Assistant IA Local</h3>
                <p>Je suis là pour vous aider. Posez-moi vos questions ou demandez-moi d'accomplir des tâches.</p>
                <div class="features">
                    <div class="feature">
                        <i class="fas fa-comments"></i>
                        <h4>Mode Chat</h4>
                        <p>Discutez avec moi par texte</p>
                    </div>
                    <div class="feature">
                        <i class="fas fa-microphone"></i>
                        <h4>Mode Vocal</h4>
                        <p>Parlez-moi et je vous répondrai</p>
                    </div>
                    <div class="feature">
                        <i class="fas fa-brain"></i>
                        <h4>Mémoire</h4>
                        <p>Je me souviens de nos conversations</p>
                    </div>
                </div>
            </div>
        `;
        
        // Mettre à jour le titre
        this.conversationTitle.textContent = 'Nouvelle conversation';
        
        // Créer l'objet conversation et l'ajouter en tête de liste
        const newConversation = {
            conversation_id: tempId,
            title: 'Nouvelle conversation',
            last_updated: new Date().toISOString(),
            message_count: 0
        };
        
        // Insérer en première position
        this.conversations.unshift(newConversation);
        
        // Utiliser la méthode _rebuildConversationList pour une reconstruction complète
        // au lieu de _updateConversationList
        this._rebuildConversationList();
        
        // Vider et focus l'input
        this.chatInput.value = '';
        this.chatInput.focus();
    }
    /**
     * Envoie un message
     */

    async sendMessage() {
        const content = this.chatInput.value.trim();
        
        if (!content) {
            return;
        }
        
        // Vider l'input
        this.chatInput.value = '';
        
        // Ajouter le message de l'utilisateur à l'interface
        this._addMessage(content, 'user');
        
        // Déterminer le mode actuel
        const mode = userPreferences.get('CONVERSATION_MODE', 'chat');
        
        // CORRECTION: Logging pour déboguer l'envoi de l'ID de conversation
        console.log("------------------------------------------- État avant envoi du message:");
        console.log("- ID de conversation actuel:", this.currentConversationId);
        console.log("- WebSocket connecté:", wsManager.isConnected);
        
        const messageData = {
            content: content,
            mode: mode
        };
        
        // Toujours ajouter l'ID de conversation s'il existe
        if (this.currentConversationId) {
            messageData.conversation_id = this.currentConversationId;
            console.log(`Envoi du message avec conversation_id: ${this.currentConversationId}`);
        } else {
            console.log("Envoi du message sans conversation_id (nouvelle conversation)");
        }
        
        // Utiliser WebSocket si disponible, sinon REST
        if (wsManager.isConnected) {
            const success = wsManager.sendMessage(messageData);
            
            // Si l'envoi a échoué, essayer via REST
            if (!success) {
                console.log("Échec de l'envoi WebSocket, tentative via REST");
                await this._sendViaRest(content, mode);
            }
        } else {
            console.log("WebSocket non connecté, envoi via REST");
            await this._sendViaRest(content, mode);
        }
    }



    /**
     * Envoie un message via l'API REST (fallback)
     * @param {string} content - Contenu du message
     * @param {string} mode - Mode de conversation ('chat' ou 'voice')
     */
    async _sendViaRest(content, mode) {
        try {
            this._showTypingIndicator();
            
            console.log("Envoi via REST avec conversation_id:", this.currentConversationId);
            
            // Préparer les données à envoyer
            const requestData = {
                content: content,
                mode: mode
            };
            
            // Ajouter l'ID de conversation s'il existe
            if (this.currentConversationId) {
                requestData.conversation_id = this.currentConversationId;
            }
            
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.API.CHAT}/send`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Si nous recevons un nouvel ID de conversation, mettre à jour
            if (data.conversation_id) {
                const isNewConversation = !this.currentConversationId || 
                                        this.currentConversationId.startsWith('temp_') ||
                                        this.currentConversationId !== data.conversation_id;
                
                this.currentConversationId = data.conversation_id;
            
                if (isNewConversation) {
                    // Rafraîchir complètement depuis le serveur
                    await this.loadConversations();
                }
            }
            
            // Ajouter la réponse
            this._removeTypingIndicator();
            this._addMessage(data.response, 'assistant');
            
            return data;
        } catch (error) {
            console.error("Erreur d'envoi de message via REST:", error);
            this._removeTypingIndicator();
            this._showError("Impossible d'envoyer le message. Réessayez plus tard.");
            return null;
        }
    }
    
    /**
     * Efface l'historique de la conversation actuelle
     */
    async clearCurrentConversation() {
        if (!this.currentConversationId) {
            return;
        }
        
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.API.CHAT}/conversation/${this.currentConversationId}/clear`, {
                method: 'POST'
            });
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            // Recharger la conversation
            this.selectConversation(this.currentConversationId);
        } catch (error) {
            console.error("Erreur d'effacement de conversation:", error);
            this._showError("Impossible d'effacer l'historique. Réessayez plus tard.");
        }
    }
    
    /**
     * Supprime la conversation actuelle
     */
    async deleteCurrentConversation() {
        if (!this.currentConversationId) {
            return;
        }
        
        const confirmation = confirm("Voulez-vous vraiment supprimer cette conversation ?");
        
        if (!confirmation) {
            return;
        }
        
        await this.deleteConversation(this.currentConversationId);
    }
    
    /**
     * Supprime une conversation spécifique
     * @param {string} conversationId - ID de la conversation à supprimer
     */
    async deleteConversation(conversationId) {
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.API.CHAT}/conversation/${conversationId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            // Si c'était la conversation active, en créer une nouvelle
            if (conversationId === this.currentConversationId) {
                this.startNewConversation();
            }
            
            // Rafraîchir la liste des conversations
            this.loadConversations();
        } catch (error) {
            console.error("Erreur de suppression de conversation:", error);
            this._showError("Impossible de supprimer la conversation. Réessayez plus tard.");
        }
    }
    
    /**
     * Ajoute un message à l'interface
     * @param {string} content - Contenu du message
     * @param {string} role - Rôle ('user' ou 'assistant')
     * @param {boolean} scroll - Défilement automatique
     */
/**
 * Ajoute un message à l'interface
 * @param {string} content - Contenu du message
 * @param {string} role - Rôle ('user' ou 'assistant')
 * @param {boolean} scroll - Défiler automatiquement (par défaut true)
 */
    _addMessage(content, role, scroll = true) {
        console.log(`Ajout de message: role=${role}, contenu=${content.substring(0, 30)}...`);

        // Cloner le template
        const messageEl = this.messageTemplate.content.cloneNode(true);
        const container = messageEl.querySelector('.message');

        // Ajouter la classe du rôle
        container.classList.add(role);

        // Définir les icônes en fonction du rôle
        const iconEl = container.querySelector('.message-avatar i');
        iconEl.className = role === 'user' ? 'fas fa-user' : 'fas fa-robot';

        // Ajouter le contenu
        const contentEl = container.querySelector('.message-text');
        contentEl.textContent = content;

        // Ajouter l'heure
        const timeEl = container.querySelector('.message-time');
        timeEl.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        // Ajouter au DOM
        this.messagesContainer.appendChild(container);

        // ✅ Forcer un reflow pour certains navigateurs (important pour Chrome et Safari)
        void container.offsetHeight;

        // ✅ Forcer scroll ET render proprement
        if (scroll) {
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    container.scrollIntoView({ behavior: "smooth", block: "end" });

                    // Double sécurité avec scroll direct
                    this._scrollToBottom();
                });
            });
        }

        // ✅ Debug DOM
        console.log("Message DOM injecté :", container.outerHTML);

        return container;
    }


    /**
     * Ajoute du texte à l'indicateur de frappe (pour le streaming)
     * @param {string} text - Texte à ajouter
     */
    _appendToTypingIndicator(text) {
        // Ajouter le texte au tampon de streaming
        this.streamingText += text;
        
        // Trouver l'indicateur de frappe
        const indicator = document.getElementById('typing-indicator');
        if (!indicator) {
            // Si l'indicateur n'existe pas, le créer
            this._showTypingIndicator();
            // Puis rappeler cette fonction
            return this._appendToTypingIndicator(text);
        }
        
        // Mettre à jour le texte visible
        const visibleTextEl = indicator.querySelector('.visible-text');
        if (visibleTextEl) {
            // Afficher l'élément s'il était caché
            if (visibleTextEl.style.display === 'none') {
                visibleTextEl.style.display = 'block';
            }
            visibleTextEl.textContent = this.streamingText;
        }
        
        // Mettre à jour aussi le texte caché (pour pouvoir le récupérer plus tard)
        const hiddenTextEl = document.getElementById('typing-text');
        if (hiddenTextEl) {
            hiddenTextEl.textContent = this.streamingText;
        }
        
        // Défiler vers le bas
        this._scrollToBottom();
    }

    /**
     * Supprime l'indicateur de frappe
     * @returns {string} Le texte accumulé
     */
    _removeTypingIndicator() {
        // Récupérer d'abord le texte accumulé
        let accumulatedText = this.streamingText;
        
        // Réinitialiser le texte accumulé
        this.streamingText = '';
        
        // Supprimer l'indicateur de frappe SEULEMENT, sans toucher aux messages
        const indicator = document.getElementById('typing-indicator');
        if (indicator && indicator.parentNode) {
            indicator.parentNode.removeChild(indicator);
        }
        
        return accumulatedText;
    }

    /**
     * Affiche l'indicateur de frappe
     */
    _showTypingIndicator() {
        // Supprimer l'indicateur existant s'il y en a un
        this._removeTypingIndicator();
        
        // Créer l'indicateur
        const typingEl = document.createElement('div');
        typingEl.className = 'typing-indicator';
        typingEl.id = 'typing-indicator';
        
        // Ajouter les points d'animation
        const dotsContainer = document.createElement('div');
        dotsContainer.className = 'dots-container';
        dotsContainer.innerHTML = `
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        `;
        typingEl.appendChild(dotsContainer);
        
        // Ajouter l'élément pour le texte caché
        const hiddenTextEl = document.createElement('div');
        hiddenTextEl.style.display = 'none';
        hiddenTextEl.id = 'typing-text';
        typingEl.appendChild(hiddenTextEl);
        
        // Créer un espace visible pour le texte
        const visibleTextEl = document.createElement('div');
        visibleTextEl.className = 'visible-text';
        visibleTextEl.style.display = 'none'; // Initialement caché
        typingEl.appendChild(visibleTextEl);
        
        // Ajouter à la zone de messages
        this.messagesContainer.appendChild(typingEl);
        
        // Défiler vers le bas
        this._scrollToBottom();
    }

    /**
     * Fait défiler la zone de messages vers le bas
     */
    _scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }
    
    /**
     * Affiche un message d'erreur
     * @param {string} message - Message d'erreur
     */
    _showError(message) {
        // Créer un toast
        const toastContainer = document.querySelector('.toast-container') || (() => {
            const container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
            return container;
        })();
        
        const toast = document.createElement('div');
        toast.className = 'toast error';
        toast.innerHTML = `
            <i class="fas fa-exclamation-circle"></i>
            <div class="toast-content">${message}</div>
        `;
        
        toastContainer.appendChild(toast);
        
        // Supprimer après un délai
        setTimeout(() => {
            toast.remove();
            
            // Supprimer le conteneur s'il est vide
            if (toastContainer.children.length === 0) {
                toastContainer.remove();
            }
        }, 5000);
    }
}

//////////////////////////// GRAPH UI ///////////////:



/**
 * Modification de l'UI pour ajouter la visualisation du graphe dans la conversation
 * À ajouter au fichier frontend/scripts/chat.js
 */

// Ajouter un bouton pour visualiser le graphe symbolique
function addMemoryGraphButton() {
    // Vérifier si le bouton existe déjà
    if (document.getElementById('view-memory-graph-btn')) {
        return;
    }
    
    // Créer le bouton et l'ajouter aux actions de l'en-tête
    const headerActions = document.querySelector('.header-actions');
    
    if (headerActions) {
        const graphButton = document.createElement('button');
        graphButton.id = 'view-memory-graph-btn';
        graphButton.className = 'btn secondary';
        graphButton.innerHTML = '<i class="fas fa-project-diagram"></i> Graph Symbolique de la conv';
        graphButton.addEventListener('click', showMemoryGraph);
        
        // Insérer avant le bouton Effacer
        const clearButton = document.getElementById('clear-conversation-btn');
        if (clearButton) {
            headerActions.insertBefore(graphButton, clearButton);
        } else {
            headerActions.appendChild(graphButton);
        }
    }
}

// Créer et afficher le modal du graphe de mémoire
function showMemoryGraph() {
    // Créer le modal s'il n'existe pas déjà
    let graphModal = document.getElementById('memory-graph-modal');
    
    if (!graphModal) {
        graphModal = document.createElement('div');
        graphModal.id = 'memory-graph-modal';
        graphModal.className = 'modal';
        
        graphModal.innerHTML = `
            <div class="modal-content large">
                <div class="modal-header">
                    <h2>Graphe de Mémoire Symbolique</h2>
                    <button class="close-modal-btn">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="controls">
                        <label>
                            <input type="checkbox" id="include-deleted-graph"> Inclure les entités supprimées
                        </label>
                        <button id="refresh-graph-btn" class="btn secondary">
                            <i class="fas fa-sync-alt"></i> Actualiser
                        </button>
                    </div>
                    <div class="graph-container" id="conversation-graph-container">
                        <div class="loading-indicator">
                            <i class="fas fa-spinner fa-spin"></i> Chargement du graphe...
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(graphModal);
        
        // Ajouter les événements
        graphModal.querySelector('.close-modal-btn').addEventListener('click', () => {
            graphModal.classList.remove('active');
        });
        
        document.getElementById('refresh-graph-btn').addEventListener('click', loadConversationGraph);
        document.getElementById('include-deleted-graph').addEventListener('change', loadConversationGraph);
        
        // Ajouter les styles si nécessaire
        addMemoryGraphStyles();
    }
    
    // Afficher le modal
    graphModal.classList.add('active');
    
    // Charger le graphe
    loadConversationGraph();
}

// Charge le graphe de la conversation actuelle
async function loadConversationGraph() {
    try {
        const graphContainer = document.getElementById('conversation-graph-container');
        const includeDeleted = document.getElementById('include-deleted-graph').checked;
        
        // Afficher l'indicateur de chargement
        graphContainer.innerHTML = `
            <div class="loading-indicator">
                <i class="fas fa-spinner fa-spin"></i> Chargement du graphe...
            </div>
        `;
        
        // Récupérer l'ID de la conversation active
        const conversationId = getCurrentConversationId();
        
        if (!conversationId) {
            graphContainer.innerHTML = `
                <div class="empty-state">
                    <p>Aucune conversation active.</p>
                </div>
            `;
            return;
        }
        
        // Récupérer les données du graphe depuis l'API
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/chat/conversation/${conversationId}/graph?include_deleted=${includeDeleted}`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const graphData = await response.json();
        
        // Vérifier si le graphe est vide
        if (!graphData.nodes || graphData.nodes.length === 0) {
            graphContainer.innerHTML = `
                <div class="empty-state">
                    <p>Aucune mémoire symbolique disponible pour cette conversation.</p>
                    <p>Continuez à discuter pour enrichir la mémoire de l'assistant.</p>
                </div>
            `;
            return;
        }
        
        // Vider le container pour la visualisation
        graphContainer.innerHTML = '';
        
        // Créer la visualisation avec D3.js
        createForceDirectedGraph(graphData, graphContainer);
        
    } catch (error) {
        console.error("Erreur lors du chargement du graphe:", error);
        const graphContainer = document.getElementById('conversation-graph-container');
        
        graphContainer.innerHTML = `
            <div class="error-state">
                <p>Erreur lors du chargement du graphe</p>
                <p class="error-details">${error.message}</p>
            </div>
        `;
    }
}

// Crée le graphe avec D3.js
function createForceDirectedGraph(data, container) {
    // Importer D3.js depuis CDN si nécessaire
    if (!window.d3) {
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js';
        document.head.appendChild(script);
        
        script.onload = () => {
            // Une fois D3 chargé, initialiser le graphe
            initGraph(data, container);
        };
    } else {
        // D3 est déjà chargé, initialiser directement
        initGraph(data, container);
    }
}

// Initialise le graphe D3.js
function initGraph(data, container) {
    const width = container.clientWidth;
    const height = 500;
    
    // Couleurs pour les groupes d'entités
    const color = d3.scaleOrdinal(d3.schemeCategory10);
    
    // Créer le SVG
    const svg = d3.select(container)
        .append("svg")
        .attr("viewBox", [0, 0, width, height])
        .attr("width", "100%")
        .attr("height", height)
        .attr("class", "memory-graph");
        
    // Ajouter un groupe pour le zoom
    const g = svg.append("g");
    
    // Ajouter le zoom
    svg.call(d3.zoom()
        .extent([[0, 0], [width, height]])
        .scaleExtent([0.1, 8])
        .on("zoom", (event) => {
            g.attr("transform", event.transform);
        }));
    
    // Créer les flèches pour les liens dirigés
    svg.append("defs").selectAll("marker")
        .data(["arrow"])
        .enter().append("marker")
        .attr("id", d => d)
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 15)
        .attr("refY", 0)
        .attr("markerWidth", 6)
        .attr("markerHeight", 6)
        .attr("orient", "auto")
        .append("path")
        .attr("fill", "#999")
        .attr("d", "M0,-5L10,0L0,5");
    
    // Créer la simulation de force
    const simulation = d3.forceSimulation(data.nodes)
        .force("link", d3.forceLink(data.links).id(d => d.id).distance(100))
        .force("charge", d3.forceManyBody().strength(-300))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("x", d3.forceX(width / 2).strength(0.1))
        .force("y", d3.forceY(height / 2).strength(0.1));
    
    // Créer les liens
    const link = g.append("g")
        .attr("stroke", "#999")
        .attr("stroke-opacity", 0.6)
        .selectAll("line")
        .data(data.links)
        .enter().append("line")
        .attr("stroke-width", d => Math.max(1, d.value))
        .attr("marker-end", "url(#arrow)")
        .on("mouseover", function(event, d) {
            // Afficher le libellé du lien au survol
            tooltip.transition()
                .duration(200)
                .style("opacity", .9);
            tooltip.html(`Relation: ${d.label}<br>Confiance: ${(d.confidence * 100).toFixed(0)}%`)
                .style("left", (event.pageX + 5) + "px")
                .style("top", (event.pageY - 28) + "px");
        })
        .on("mouseout", function() {
            tooltip.transition()
                .duration(500)
                .style("opacity", 0);
        });
    
    // Créer les nœuds
    const node = g.append("g")
        .attr("stroke", "#fff")
        .attr("stroke-width", 1.5)
        .selectAll("circle")
        .data(data.nodes)
        .enter().append("circle")
        .attr("r", 8)
        .attr("fill", d => color(d.group))
        .call(drag(simulation))
        .on("mouseover", function(event, d) {
            // Afficher les détails du nœud au survol
            tooltip.transition()
                .duration(200)
                .style("opacity", .9);
            tooltip.html(`<strong>${d.name}</strong><br>Type: ${d.type}<br>Confiance: ${(d.confidence * 100).toFixed(0)}%`)
                .style("left", (event.pageX + 5) + "px")
                .style("top", (event.pageY - 28) + "px");
        })
        .on("mouseout", function() {
            tooltip.transition()
                .duration(500)
                .style("opacity", 0);
        })
        .on("click", function(event, d) {
            // Sélectionner/désélectionner un nœud
            const isSelected = d3.select(this).classed("selected");
            
            // Réinitialiser tous les nœuds et liens
            node.classed("selected", false)
                .classed("related", false);
            link.classed("highlighted", false)
                .classed("faded", false);
            
            if (!isSelected) {
                // Sélectionner ce nœud
                d3.select(this).classed("selected", true);
                
                // Mettre en évidence les liens connectés
                link.classed("highlighted", l => l.source.id === d.id || l.target.id === d.id)
                    .classed("faded", l => l.source.id !== d.id && l.target.id !== d.id);
                
                // Mettre en évidence les nœuds connectés
                node.classed("related", n => {
                    if (n.id === d.id) return false;
                    return data.links.some(l => 
                        (l.source.id === d.id && l.target.id === n.id) || 
                        (l.source.id === n.id && l.target.id === d.id)
                    );
                });
            }
        });
    
    // Ajouter les étiquettes des nœuds
    const label = g.append("g")
        .attr("class", "labels")
        .selectAll("text")
        .data(data.nodes)
        .enter().append("text")
        .attr("font-size", 10)
        .attr("dx", 12)
        .attr("dy", ".35em")
        .text(d => d.name);
    
    // Ajouter un infobulle interactive
    const tooltip = d3.select("body").append("div")
        .attr("class", "graph-tooltip")
        .style("opacity", 0);
    
    // Mise à jour de la simulation à chaque tick
    simulation.on("tick", () => {
        link
            .attr("x1", d => d.source.x)
            .attr("y1", d => d.source.y)
            .attr("x2", d => d.target.x)
            .attr("y2", d => d.target.y);
            
        node
            .attr("cx", d => d.x = Math.max(10, Math.min(width - 10, d.x)))
            .attr("cy", d => d.y = Math.max(10, Math.min(height - 10, d.y)));
            
        label
            .attr("x", d => d.x)
            .attr("y", d => d.y);
    });
    
    // Fonction pour le glisser-déposer des nœuds
    function drag(simulation) {
        function dragstarted(event) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            event.subject.fx = event.subject.x;
            event.subject.fy = event.subject.y;
        }
        
        function dragged(event) {
            event.subject.fx = event.x;
            event.subject.fy = event.y;
        }
        
        function dragended(event) {
            if (!event.active) simulation.alphaTarget(0);
            event.subject.fx = null;
            event.subject.fy = null;
        }
        
        return d3.drag()
            .on("start", dragstarted)
            .on("drag", dragged)
            .on("end", dragended);
    }
}

// Ajouter les styles CSS pour le graphe
function addMemoryGraphStyles() {
    if (document.getElementById('memory-graph-styles')) return;
    
    const style = document.createElement('style');
    style.id = 'memory-graph-styles';
    style.textContent = `
        .graph-container {
            width: 100%;
            height: 500px;
            border: 1px solid #ddd;
            border-radius: 8px;
            overflow: hidden;
            position: relative;
        }
        
        .memory-graph {
            background-color: #f9f9f9;
            border-radius: 8px;
        }
        
        .graph-tooltip {
            position: absolute;
            padding: 8px;
            background: rgba(0, 0, 0, 0.8);
            color: #fff;
            border-radius: 4px;
            pointer-events: none;
            font-size: 12px;
            z-index: 1000;
        }
        
        .memory-graph circle {
            cursor: pointer;
            transition: r 0.2s;
        }
        
        .memory-graph circle:hover {
            r: 10;
        }
        
        .memory-graph circle.selected {
            stroke: #ff5722;
            stroke-width: 3px;
            r: 12;
        }
        
        .memory-graph circle.related {
            stroke: #ffc107;
            stroke-width: 2px;
            r: 10;
        }
        
        .memory-graph line {
            transition: stroke-opacity 0.3s, stroke-width 0.3s;
        }
        
        .memory-graph line.highlighted {
            stroke: #ff5722;
            stroke-opacity: 1;
            stroke-width: 3;
        }
        
        .memory-graph line.faded {
            stroke-opacity: 0.1;
        }
        
        .modal-content.large {
            width: 90%;
            max-width: 1000px;
        }
        
        .controls {
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            text-align: center;
            color: #666;
            padding: 20px;
        }
        
        .error-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            text-align: center;
            color: #f44336;
            padding: 20px;
        }
        
        [data-theme="dark"] .memory-graph {
            background-color: #2c2c2c;
        }
        
        [data-theme="dark"] .empty-state,
        [data-theme="dark"] .error-state {
            color: #aaa;
        }
    `;
    
    document.head.appendChild(style);
}

// Fonction pour obtenir l'ID de la conversation active
function getCurrentConversationId() {
    return activeConversationId;
}

// Ajouter le bouton quand l'application est initialisée
document.addEventListener('DOMContentLoaded', function() {
    // Vérifie que le bouton est ajouté après le chargement de l'interface
    setTimeout(addMemoryGraphButton, 500);
});



// Instance globale
const chatManager = new ChatManager();
window.chatManager = chatManager;


