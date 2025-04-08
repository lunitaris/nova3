/**
 * Gestionnaire des fonctionnalités vocales pour l'Assistant IA
 */
class VoiceManager {
    constructor() {
        this.isRecording = false;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.audioContext = null;
        this.audioQueue = [];
        this.isPlaying = false;
        this.currentAudioSource = null;
        
        // Éléments DOM
        this.micButton = document.getElementById('mic-button');
        this.voiceStatusText = document.getElementById('voice-status-text');
        this.voiceVisualization = document.getElementById('voice-visualization');
        
        // Initialiser les événements
        this._initEvents();
        
        // Initialiser WebAudio API
        this._initAudioContext();
    }
    
    /**
     * Initialise le contexte audio
     */
    _initAudioContext() {
        // Créer ou réutiliser le contexte audio
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    
    /**
     * Initialise les événements
     */
    _initEvents() {
        // Gestion du clic sur le bouton microphone
        this.micButton.addEventListener('click', () => {
            if (this.isRecording) {
                this.stopRecording();
            } else {
                this.startRecording();
            }
        });
        
        // Configuration des callbacks pour le WebSocket vocal
        wsManager.setVoiceCallbacks({
            transcription: (text) => {
                this._handleTranscription(text);
            },
            audioStart: () => {
                this._clearAudioQueue();
            },
            audioChunk: (chunk) => {
                this._handleAudioChunk(chunk);
            },
            audioEnd: () => {
                this._finishPlayback();
            },
            error: (data) => {
                this._showVoiceError(data.text || "Erreur lors du traitement vocal");
            }
        });
    }
    
    /**
     * Démarre l'enregistrement audio
     */
    async startRecording() {
        try {
            // Vérifier si on est déjà en enregistrement
            if (this.isRecording) {
                return;
            }
            
            // Demander l'autorisation d'accès au micro
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            
            // Mise à jour de l'interface
            this.isRecording = true;
            this.micButton.classList.add('recording');
            this.voiceStatusText.textContent = "Enregistrement en cours...";
            this.voiceVisualization.classList.add('recording');
            
            // Réinitialiser les morceaux audio
            this.audioChunks = [];
            
            // Créer le MediaRecorder
            this.mediaRecorder = new MediaRecorder(stream);
            
            // Collecter les données
            this.mediaRecorder.addEventListener('dataavailable', (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            });
            
            // Quand l'enregistrement est terminé
            this.mediaRecorder.addEventListener('stop', () => {
                // Libérer les pistes
                stream.getTracks().forEach(track => track.stop());
                
                // Envoyer l'audio pour traitement
                this._processRecording();
            });
            
            // Commencer l'enregistrement
            this.mediaRecorder.start(100); // Collecter des chunks toutes les 100ms
            
            // Si pas déjà connecté au WebSocket vocal, se connecter
            await this._ensureVoiceConnection();
            
            // Envoyer la commande de début d'enregistrement
            wsManager.sendVoiceCommand({
                command: "start_recording",
                user_id: "anonymous",
                conversation_id: chatManager.currentConversationId || null
            });
        } catch (error) {
            console.error("Erreur lors du démarrage de l'enregistrement:", error);
            this._showVoiceError("Impossible d'accéder au microphone. Vérifiez les permissions du navigateur.");
            this.isRecording = false;
        }
    }
    
    /**
     * Arrête l'enregistrement audio
     */
    stopRecording() {
        if (!this.isRecording || !this.mediaRecorder) {
            return;
        }
        
        // Mise à jour de l'interface
        this.isRecording = false;
        this.micButton.classList.remove('recording');
        this.voiceStatusText.textContent = "Traitement en cours...";
        this.voiceVisualization.classList.remove('recording');
        
        // Arrêter l'enregistrement
        this.mediaRecorder.stop();
        
        // Envoyer la commande de fin d'enregistrement
        wsManager.sendVoiceCommand({
            command: "stop_recording",
            user_id: "anonymous",
            conversation_id: chatManager.currentConversationId || null
        });
    }
    
    /**
     * S'assure que la connexion WebSocket vocale est établie
     */
    async _ensureVoiceConnection() {
        try {
            // Vérifier si on a une connexion active
            if (wsManager.voiceSocket && wsManager.voiceSocket.readyState === WebSocket.OPEN) {
                return;
            }
            
            // Se connecter au WebSocket vocal
            await wsManager.connectVoice(chatManager.currentConversationId || "new");
        } catch (error) {
            console.error("Erreur de connexion WebSocket vocal:", error);
            throw error;
        }
    }
    
    /**
     * Traite l'enregistrement audio
     */
    async _processRecording() {
        // Si pas d'audio ou connexion perdue, on abandonne
        if (this.audioChunks.length === 0 || !wsManager.voiceSocket) {
            this.voiceStatusText.textContent = "Prêt à écouter";
            return;
        }
        
        try {
            // Créer un Blob à partir des chunks
            const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
            
            // Envoyer le blob au serveur via WebSocket
            wsManager.sendAudioData(audioBlob);
            
            // Attendre la transcription (gérée par les callbacks)
            this.voiceStatusText.textContent = "Analyse de votre message...";
        } catch (error) {
            console.error("Erreur lors du traitement de l'enregistrement:", error);
            this._showVoiceError("Erreur lors du traitement de l'audio.");
            this.voiceStatusText.textContent = "Prêt à écouter";
        }
    }
    
    /**
     * Gère la transcription reçue
     * @param {string} text - Texte transcrit
     */
    _handleTranscription(text) {
        // Afficher le texte transcrit
        this.voiceStatusText.textContent = "Message reconnu !";
        
        // Vider les chunks audio
        this.audioChunks = [];
        
        // Ajouter le message à l'interface de chat
        chatManager._addMessage(text, 'user');
    }
    
    /**
     * Gère les chunks audio reçus pour la lecture
     * @param {Blob} chunk - Morceau audio
     */
    async _handleAudioChunk(chunk) {
        // Ajouter à la file d'attente de lecture
        this.audioQueue.push(chunk);
        
        // Si pas en lecture, commencer
        if (!this.isPlaying) {
            this._playNextAudio();
        }
    }
    
    /**
     * Joue le prochain morceau audio de la file d'attente
     */
    async _playNextAudio() {
        // Si la file est vide, rien à faire
        if (this.audioQueue.length === 0) {
            this.isPlaying = false;
            return;
        }
        
        this.isPlaying = true;
        
        try {
            // Récupérer le prochain chunk
            const chunk = this.audioQueue.shift();
            
            // Convertir le Blob en ArrayBuffer
            const arrayBuffer = await chunk.arrayBuffer();
            
            // Décoder l'audio
            const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
            
            // Créer une source
            const source = this.audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(this.audioContext.destination);
            
            // Garder une référence pour pouvoir l'arrêter
            this.currentAudioSource = source;
            
            // Quand la lecture est terminée, passer au suivant
            source.onended = () => {
                this.currentAudioSource = null;
                this._playNextAudio();
            };
            
            // Démarrer la lecture
            source.start(0);
        } catch (error) {
            console.error("Erreur lors de la lecture audio:", error);
            // Passer au suivant en cas d'erreur
            this._playNextAudio();
        }
    }
    
    /**
     * Vide la file d'attente audio
     */
    _clearAudioQueue() {
        // Arrêter la lecture en cours
        if (this.currentAudioSource) {
            try {
                this.currentAudioSource.stop();
            } catch (e) {
                // Ignorer les erreurs
            }
            this.currentAudioSource = null;
        }
        
        // Vider la file
        this.audioQueue = [];
        this.isPlaying = false;
    }
    
    /**
     * Termine la lecture (appelé quand tous les chunks ont été reçus)
     */
    _finishPlayback() {
        // Si la file est vide, on a terminé
        if (this.audioQueue.length === 0 && !this.currentAudioSource) {
            this.voiceStatusText.textContent = "Prêt à écouter";
        }
    }
    
    /**
     * Synthétise la parole à partir d'un texte
     * @param {string} text - Texte à synthétiser
     */
    async synthesizeSpeech(text) {
        try {
            // S'assurer que la connexion est établie
            await this._ensureVoiceConnection();
            
            // Envoyer la commande de synthèse
            wsManager.sendVoiceCommand({
                command: "synthesize",
                text: text,
                voice: userPreferences.get('TTS_VOICE')
            });
            
            // Mise à jour de l'interface
            this.voiceStatusText.textContent = "Génération de la réponse vocale...";
        } catch (error) {
            console.error("Erreur lors de la synthèse vocale:", error);
            this._showVoiceError("Impossible de générer la réponse vocale.");
        }
    }
    
    /**
     * Affiche un message d'erreur vocal
     * @param {string} message - Message d'erreur
     */
    _showVoiceError(message) {
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
            <i class="fas fa-microphone-slash"></i>
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
        
        // Réinitialiser l'état
        this.voiceStatusText.textContent = "Prêt à écouter";
        this.isRecording = false;
        this.micButton.classList.remove('recording');
        this.voiceVisualization.classList.remove('recording');
    }
}

// Instance globale
const voiceManager = new VoiceManager();