/**
 * Gestionnaire de l'interface utilisateur pour l'Assistant IA
 */
class UIManager {
    constructor() {
        // Éléments modaux
        this.settingsModal = document.getElementById('settings-modal');
        this.memoryModal = document.getElementById('memory-modal');
        
        // Éléments de l'interface
        this.toggleModeBtn = document.getElementById('toggle-mode-btn');
        this.settingsBtn = document.getElementById('settings-btn');
        this.chatInputArea = document.getElementById('chat-input-area');
        this.voiceInputArea = document.getElementById('voice-input-area');
        this.conversationMode = document.getElementById('conversation-mode');
        
        // Éléments des paramètres
        this.modelPreference = document.getElementById('model-preference');
        this.ttsVoice = document.getElementById('tts-voice');
        this.speechRate = document.getElementById('speech-rate');
        this.speechRateValue = document.getElementById('speech-rate-value');
        this.themeSelect = document.getElementById('theme-select');
        
        // Initialiser les événements
        this._initEvents();
        
        // Initialiser l'état de l'interface
        this._initUIState();
    }
    
    /**
     * Initialise les événements de l'interface
     */
    _initEvents() {
        // Bouton de basculement mode chat/vocal
        this.toggleModeBtn.addEventListener('click', () => {
            this.toggleConversationMode();
        });
        
        // Bouton des paramètres
        this.settingsBtn.addEventListener('click', () => {
            this.openSettingsModal();
        });
        
        // Fermeture des modaux
        document.querySelectorAll('.close-modal-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.closeAllModals();
            });
        });
        
        // Clic en dehors des modaux pour fermer
        window.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal')) {
                this.closeAllModals();
            }
        });
        
        // Sauvegarder les paramètres
        document.getElementById('save-settings-btn').addEventListener('click', () => {
            this.saveSettings();
        });
        
        // Changement de la valeur du speech rate
        this.speechRate.addEventListener('input', () => {
            this.speechRateValue.textContent = this.speechRate.value;
        });
        
        // Ajout d'une information à mémoriser
        document.getElementById('save-memory-btn').addEventListener('click', () => {
            this.saveMemory();
        });
        
        // Support des raccourcis clavier
        document.addEventListener('keydown', (e) => {
            // Échap pour fermer les modaux
            if (e.key === 'Escape') {
                this.closeAllModals();
            }
            
            // Ctrl+/ pour basculer le mode
            if (e.ctrlKey && e.key === '/') {
                e.preventDefault();
                this.toggleConversationMode();
            }
            
            // Ctrl+, pour ouvrir les paramètres
            if (e.ctrlKey && e.key === ',') {
                e.preventDefault();
                this.openSettingsModal();
            }
        });
    }
    
    /**
     * Initialise l'état de l'interface
     */
    _initUIState() {
        // Définir le mode actuel
        const mode = userPreferences.get('CONVERSATION_MODE', 'chat');
        this._setConversationMode(mode);
        
        // Remplir les paramètres
        this.modelPreference.value = userPreferences.get('MODEL_PREFERENCE', 'auto');
        this.ttsVoice.value = userPreferences.get('TTS_VOICE', 'fr_FR-siwis-medium');
        this.speechRate.value = userPreferences.get('SPEECH_RATE', 1.0);
        this.speechRateValue.textContent = this.speechRate.value;
        this.themeSelect.value = userPreferences.get('THEME', 'light');
        
        // Appliquer le thème
        userPreferences.applyTheme();
    }
    
    /**
     * Ouvre le modal des paramètres
     */
    openSettingsModal() {
        this.closeAllModals();
        this.settingsModal.classList.add('active');
    }
    
    /**
     * Ouvre le modal de mémorisation
     */
    openMemoryModal() {
        this.closeAllModals();
        this.memoryModal.classList.add('active');
        document.getElementById('memory-content').focus();
    }
    
    /**
     * Ferme tous les modaux
     */
    closeAllModals() {
        document.querySelectorAll('.modal').forEach(modal => {
            modal.classList.remove('active');
        });
    }
    
    /**
     * Bascule entre les modes chat et vocal
     */
    toggleConversationMode() {
        const currentMode = userPreferences.get('CONVERSATION_MODE', 'chat');
        const newMode = currentMode === 'chat' ? 'voice' : 'chat';
        
        this._setConversationMode(newMode);
        userPreferences.set('CONVERSATION_MODE', newMode);
    }
    
    /**
     * Définit le mode de conversation
     * @param {string} mode - Mode ('chat' ou 'voice')
     */
    _setConversationMode(mode) {
        // Mettre à jour l'interface
        if (mode === 'chat') {
            this.chatInputArea.classList.add('active');
            this.voiceInputArea.classList.remove('active');
            this.toggleModeBtn.innerHTML = '<i class="fas fa-microphone"></i> Mode Vocal';
            this.conversationMode.textContent = 'Mode Chat';
        } else {
            this.chatInputArea.classList.remove('active');
            this.voiceInputArea.classList.add('active');
            this.toggleModeBtn.innerHTML = '<i class="fas fa-comments"></i> Mode Chat';
            this.conversationMode.textContent = 'Mode Vocal';
        }
    }
    
    /**
     * Sauvegarde les paramètres
     */
    saveSettings() {
        // Récupérer les valeurs
        const modelPreference = this.modelPreference.value;
        const ttsVoice = this.ttsVoice.value;
        const speechRate = parseFloat(this.speechRate.value);
        const theme = this.themeSelect.value;
        
        // Enregistrer dans les préférences
        userPreferences.set('MODEL_PREFERENCE', modelPreference);
        userPreferences.set('TTS_VOICE', ttsVoice);
        userPreferences.set('SPEECH_RATE', speechRate);
        userPreferences.set('THEME', theme);
        
        // Fermer le modal
        this.closeAllModals();
        
        // Notification
        this._showNotification('Paramètres enregistrés', 'success');
    }
    
    /**
     * Sauvegarde une information en mémoire
     */
    async saveMemory() {
        const content = document.getElementById('memory-content').value.trim();
        const topic = document.getElementById('memory-topic').value.trim();
        
        if (!content) {
            this._showNotification('Veuillez entrer une information à mémoriser', 'error');
            return;
        }
        
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.API.MEMORY}/remember`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    content,
                    topic: topic || 'user_info'
                })
            });
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this._showNotification('Information mémorisée avec succès', 'success');
                
                // Ajouter un message à la conversation
                chatManager._addMessage(`Je me souviendrai de : "${content}"`, 'assistant');
                
                // Vider et fermer le modal
                document.getElementById('memory-content').value = '';
                this.closeAllModals();
            } else {
                throw new Error(data.error || 'Erreur inconnue');
            }
        } catch (error) {
            console.error("Erreur lors de la mémorisation:", error);
            this._showNotification(`Erreur: ${error.message}`, 'error');
        }
    }
    
    /**
     * Affiche une notification
     * @param {string} message - Message à afficher
     * @param {string} type - Type de notification ('success', 'error', 'warning')
     */
    _showNotification(message, type = 'info') {
        // Créer le conteneur s'il n'existe pas
        const toastContainer = document.querySelector('.toast-container') || (() => {
            const container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
            return container;
        })();
        
        // Créer le toast
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        // Icône selon le type
        let icon = 'info-circle';
        if (type === 'success') icon = 'check-circle';
        if (type === 'error') icon = 'exclamation-circle';
        if (type === 'warning') icon = 'exclamation-triangle';
        
        toast.innerHTML = `
            <i class="fas fa-${icon}"></i>
            <div class="toast-content">${message}</div>
        `;
        
        toastContainer.appendChild(toast);
        
        // Supprimer après 5 secondes
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
const uiManager = new UIManager();