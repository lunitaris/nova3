/**
 * Gestionnaire de chat pour l'Assistant IA
 */
class ChatManager {
    constructor() {
        this.conversations = [];
        this.currentConversationId = null;
        this.isTyping = false;
        this.messageQueue = [];
        
        // Éléments DOM
        this.messagesContainer = document.getElementById('messages-container');
        this.chatInput = document.getElementById('chat-input');
        this.sendButton = document.getElementById('send-button');
        this.conversationList = document.getElementById('conversation-list');
        this.conversationTitle = document.getElementById('conversation-title');
        
        // Template pour les messages
        this.messageTemplate = document.getElementById('message-template');
        this.conversationItemTemplate = document.getElementById('conversation-item-template');
        
        this._cleanupTypingIndicator();         // Nettoyer les indicateurs résiduels
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
                console.log("LOG17: Callback de début de streaming appelé");  // LOG 17
                this._showTypingIndicator();
            },
            token: (token) => {
                console.log(`LOG18: Callback de token appelé avec: ${token}`);  // LOG 18
                this._appendToTypingIndicator(token);
            },
            end: (data) => {
                console.log("Callback de fin de streaming appelé avec contenu:", data.content);
    
                // Supprimer l'indicateur de frappe AVANT d'ajouter le message final
                const accumulatedText = this._removeTypingIndicator();
                
                // Petit délai pour s'assurer que le DOM est mis à jour
                setTimeout(() => {
                    // Utiliser le texte accumulé ou le contenu du message de fin
                    const finalContent = accumulatedText || data.content;
                    
                    // Ajouter le message à l'historique
                    this._addMessage(finalContent, 'assistant');
                    
                    // Mettre à jour la liste des conversations
                    this.loadConversations();
                }, 10);
            },
            error: (data) => {
                console.error("LOG20: Erreur de streaming reçue:", data);  // LOG 20
                this._removeTypingIndicator();
                this._showError(data.content || "Erreur lors de la génération de la réponse.");
            }
        });
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
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.API.CHAT}/conversations`);
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const conversations = await response.json();
            this.conversations = conversations;
            
            // Mettre à jour l'affichage de la liste
            this._updateConversationList();
            
            // Si pas de conversation active, en sélectionner une ou en créer une nouvelle
            if (!this.currentConversationId && conversations.length > 0) {
                this.selectConversation(conversations[0].conversation_id);
            } else if (!this.currentConversationId) {
                this.startNewConversation();
            }
            
            return conversations;
        } catch (error) {
            console.error("Erreur de chargement des conversations:", error);
            this._showError("Impossible de charger les conversations.");
            return [];
        }
    }
    
    /**
     * Met à jour l'affichage de la liste des conversations
     */
    _updateConversationList() {
        // Vider la liste
        this.conversationList.innerHTML = '';
        
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
            if (conv.conversation_id === this.currentConversationId) {
                container.classList.add('active');
            }
            
            // Définir le contenu
            item.querySelector('.conversation-title').textContent = conv.title || 'Nouvelle conversation';
            
            // Formater la date
            const date = new Date(conv.last_updated);
            const formattedDate = date.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
            item.querySelector('.conversation-time').textContent = formattedDate;
            
            // Gérer le clic pour sélectionner
            container.addEventListener('click', (e) => {
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
            
            this.conversationList.appendChild(item);
        });
    }
    
    /**
     * Sélectionne une conversation et charge ses messages
     * @param {string} conversationId - ID de la conversation
     */
    async selectConversation(conversationId) {
        this.currentConversationId = conversationId;
        
        // Mettre à jour la liste de conversations (pour l'élément actif)
        this._updateConversationList();
        
        // Vider la zone de messages
        this.messagesContainer.innerHTML = '';
        
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
        // Réinitialiser l'ID de conversation
        this.currentConversationId = null;
        
        // Vider la zone de messages
        this.messagesContainer.innerHTML = '';
        
        // Afficher le message de bienvenue
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
        
        // Mettre à jour la liste
        this._updateConversationList();
        
        // Vider l'input
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
        
        // Envoyer via WebSocket pour le streaming
        if (wsManager.isConnected) {
            wsManager.sendMessage({
                content: content,
                conversation_id: this.currentConversationId,
                mode: mode
            });
        } 
        // Ou via API REST si WebSocket non disponible
        else {
            this._sendViaRest(content, mode);
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
            
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.API.CHAT}/send`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    content: content,
                    conversation_id: this.currentConversationId,
                    mode: mode
                })
            });
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Mettre à jour l'ID de conversation si c'est une nouvelle
            if (!this.currentConversationId) {
                this.currentConversationId = data.conversation_id;
                
                // Rafraîchir la liste des conversations
                this.loadConversations();
            }
            
            // Ajouter la réponse
            this._removeTypingIndicator();
            this._addMessage(data.response, 'assistant');
            
            return data;
        } catch (error) {
            console.error("Erreur d'envoi de message:", error);
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
    _addMessage(content, role, scroll = true) {
        console.log(`Ajout de message: role=${role}, contenu=${content.substring(0, 30)}...`);
        
        // Cloner le template
        const messageEl = this.messageTemplate.content.cloneNode(true);
        const container = messageEl.querySelector('.message');
        
        // Ajouter les classes et contenu
        container.classList.add(role);
        const iconEl = container.querySelector('.message-avatar i');
        iconEl.className = role === 'user' ? 'fas fa-user' : 'fas fa-robot';
        
        const contentEl = container.querySelector('.message-text');
        contentEl.textContent = content;
        
        const timeEl = container.querySelector('.message-time');
        timeEl.textContent = new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
        
        // Ajouter à la zone de messages
        this.messagesContainer.appendChild(container);
        
        // Défiler si demandé
        if (scroll) {
            this._scrollToBottom();
        }
        
        return container;
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
        
        // Ajouter l'élément spécial pour accumuler le texte pendant le streaming
        const hiddenTextEl = document.createElement('div');
        hiddenTextEl.style.display = 'none';
        hiddenTextEl.id = 'typing-text';
        typingEl.appendChild(hiddenTextEl);
        
        // Créer un espace visible pour le texte
        const visibleTextEl = document.createElement('div');
        visibleTextEl.className = 'visible-text';
        visibleTextEl.style.display = 'none'; // Initialement caché, apparaît quand du texte est ajouté
        typingEl.appendChild(visibleTextEl);
        
        // Ajouter à la zone de messages
        this.messagesContainer.appendChild(typingEl);
        
        // Défiler vers le bas
        this._scrollToBottom();
    }
    

    /**
     * Ajoute du texte à l'indicateur de frappe (pour le streaming)
     * @param {string} text - Texte à ajouter
     */
    _appendToTypingIndicator(text) {
        console.log(`Ajout au typing indicator: "${text}"`);
        const typingIndicator = document.getElementById('typing-indicator');
        
        if (!typingIndicator) {
            console.error("L'indicateur de frappe n'existe pas!");
            typingIndicator.classList.add('message-finished');
            this._showTypingIndicator(); // Recréer l'indicateur s'il n'existe pas
            return this._appendToTypingIndicator(text); // Réessayer
        }
        
        // S'assurer que l'élément pour stocker le texte complet existe
        let typingTextEl = document.getElementById('typing-text');
        if (!typingTextEl) {
            typingTextEl = document.createElement('div');
            typingTextEl.id = 'typing-text';
            typingTextEl.style.display = 'none';
            typingIndicator.appendChild(typingTextEl);
        }
        
        // Ajouter le texte à l'élément caché qui stocke le contenu complet
        typingTextEl.textContent += text;
        
        // Obtenir ou créer l'élément pour le texte visible
        let visibleTextEl = typingIndicator.querySelector('.visible-text');
        if (!visibleTextEl) {
            visibleTextEl = document.createElement('div');
            visibleTextEl.className = 'visible-text';
            typingIndicator.appendChild(visibleTextEl);
        }
        
        // Afficher le conteneur de texte visible
        visibleTextEl.style.display = 'block';
        
        // Mettre à jour le texte visible
        visibleTextEl.textContent = typingTextEl.textContent;
        
        // Défiler vers le bas
        this._scrollToBottom();
    }



    /**
     * Supprime l'indicateur de frappe
     * @returns {string} Le texte accumulé
     */
    _removeTypingIndicator() {
        // Récupérer d'abord le texte accumulé
        let accumulatedText = '';
        const typingTextEl = document.getElementById('typing-text');
        if (typingTextEl) {
            accumulatedText = typingTextEl.textContent;
        }
        
        // Approche plus agressive pour nettoyer tous les éléments liés au typing
        const cleanupElements = [
            document.getElementById('typing-indicator'),
            ...Array.from(document.querySelectorAll('.typing-indicator')),
            ...Array.from(document.querySelectorAll('.typing-dot')),
            ...Array.from(document.querySelectorAll('.dots-container')),
            ...Array.from(document.querySelectorAll('.visible-text'))
        ];
        
        // Supprimer chaque élément trouvé
        cleanupElements.forEach(el => {
            if (el && el.parentNode) {
                el.parentNode.removeChild(el);
            }
        });
        
        // Forcer une micro pause pour permettre au DOM de se mettre à jour
        setTimeout(() => {
            // Double vérification après la pause
            const remainingIndicators = document.querySelectorAll('.typing-indicator, .typing-dot');
            remainingIndicators.forEach(el => {
                if (el && el.parentNode) {
                    el.parentNode.removeChild(el);
                }
            });
        }, 0);
        
        console.log("Indicateur de frappe supprimé, texte accumulé:", accumulatedText);
        return accumulatedText;
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

// Instance globale
const chatManager = new ChatManager();