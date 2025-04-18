/**
 * Script principal de l'application Assistant IA
 * Initialise et coordonne les différents modules
 */

// Verifier la compatibilité du navigateur
function checkBrowserCompatibility() {
    const requiredAPIs = [
        'WebSocket',
        'fetch',
        'localStorage',
        'AudioContext' in window || 'webkitAudioContext' in window,
        'MediaRecorder' in window
    ];
    
    const missingFeatures = requiredAPIs.filter(api => !api);
    
    if (missingFeatures.length > 0) {
        console.error("Navigateur incompatible. Fonctionnalités manquantes:", missingFeatures);
        alert("Votre navigateur ne prend pas en charge toutes les fonctionnalités nécessaires pour cette application. Veuillez utiliser un navigateur plus récent comme Chrome, Firefox, ou Edge.");
        return false;
    }
    
    return true;
}

// Vérifier la connexion au backend
async function checkBackendConnection() {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.API.HEALTH}`, {
            method: 'GET',
            headers: {
                'Accept': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error(`Erreur de connexion: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.status !== 'ok' && data.status !== 'degraded') {
            console.warn("Statut du backend:", data.status);
            console.warn("Détails:", data);
            
            if (data.status === 'error') {
                throw new Error("Le serveur backend est en erreur");
            }
        }
        
        console.log("Backend connecté:", data);
        return data;
    } catch (error) {
        console.error("Échec de connexion au backend:", error);
        
        // Afficher une alerte à l'utilisateur
        const errorDiv = document.createElement('div');
        errorDiv.className = 'connection-error';
        errorDiv.innerHTML = `
            <div class="error-content">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>Problème de connexion</h3>
                <p>Impossible de se connecter au serveur backend. Vérifiez que le serveur est démarré et accessible.</p>
                <button id="retry-connection-btn" class="btn primary">Réessayer</button>
            </div>
        `;
        
        document.body.appendChild(errorDiv);
        
        document.getElementById('retry-connection-btn').addEventListener('click', () => {
            errorDiv.remove();
            initializeApp();
        });
        
        return false;
    }
}

// Fonction principale d'initialisation de l'application
async function initializeApp() {
    if (!checkBrowserCompatibility()) {
        return;
    }
    
    // Vérifier la connexion au backend
    const backendStatus = await checkBackendConnection();
    if (!backendStatus) {
        return;
    }
    
    // Configurer les interactions entre modules
    setupModuleInteractions();
    
    // WebSocket pour le streaming
    setupWebSocketHandlers();
    
    // Paramètres du menu contextuel
    setupContextMenu();
    
    console.log("Application initialisée avec succès!");
}

// Configuration des interactions entre modules
function setupModuleInteractions() {
    // Détection des commandes de mémorisation dans le chat
    document.getElementById('chat-input').addEventListener('input', (e) => {
        const input = e.target.value.trim();
        
        // Si on détecte une commande de mémorisation, proposer d'utiliser le modal dédié
        if (memoryManager.isMemoryRequest(input) && input.length > 15) {
            const suggestMemoryBtn = document.querySelector('.suggest-memory') || (() => {
                const btn = document.createElement('button');
                btn.className = 'suggest-memory btn secondary';
                btn.innerHTML = '<i class="fas fa-lightbulb"></i> Utiliser l\'outil de mémorisation?';
                btn.onclick = () => {
                    // Pré-remplir le modal avec l'information extraite
                    const memoryInfo = memoryManager.extractMemoryInfo(input);
                    document.getElementById('memory-content').value = memoryInfo.content;
                    document.getElementById('memory-topic').value = memoryInfo.topic;
                    
                    // Ouvrir le modal
                    uiManager.openMemoryModal();
                    
                    // Supprimer le bouton de suggestion
                    btn.remove();
                };
                document.querySelector('.input-container').prepend(btn);
                return btn;
            })();
        } else {
            // Supprimer le bouton de suggestion s'il existe
            const suggestMemoryBtn = document.querySelector('.suggest-memory');
            if (suggestMemoryBtn) {
                suggestMemoryBtn.remove();
            }
        }
    });
    
    // Gestion du mode vocal et des réponses audio
    document.addEventListener('voiceResponse', (e) => {
        if (userPreferences.get('CONVERSATION_MODE') === 'voice') {
            // Jouer la réponse vocale
            voiceManager.synthesizeSpeech(e.detail.text);
        }
    });
}

// Configuration des gestionnaires WebSocket
function setupWebSocketHandlers() {
    // Événement personnalisé pour signaler une nouvelle réponse
    const voiceResponseEvent = new CustomEvent('voiceResponse', {
        detail: { text: '' }
    });
    
    // Quand une réponse complète est reçue en mode streaming
    wsManager.setStreamingCallbacks({
        end: (data) => {
            // Déclencher l'événement de réponse vocale si on est en mode vocal
            voiceResponseEvent.detail.text = data.content;
            document.dispatchEvent(voiceResponseEvent);
        }
    });
}

// Configuration du menu contextuel personnalisé
function setupContextMenu() {
    // Élément pour le menu contextuel
    const contextMenu = document.createElement('div');
    contextMenu.className = 'context-menu';
    contextMenu.style.display = 'none';
    document.body.appendChild(contextMenu);
    
    // Événement pour le clic droit sur les messages
    document.addEventListener('contextmenu', (e) => {
        // Vérifier si on clique sur un message
        const messageEl = e.target.closest('.message');
        if (messageEl) {
            e.preventDefault();
            
            // Récupérer le texte du message
            const messageText = messageEl.querySelector('.message-text').textContent;
            
            // Créer le menu contextuel
            contextMenu.innerHTML = `
                <div class="context-menu-item copy-text">
                    <i class="fas fa-copy"></i> Copier le texte
                </div>
                <div class="context-menu-item memorize">
                    <i class="fas fa-brain"></i> Mémoriser
                </div>
                <div class="context-menu-item speak">
                    <i class="fas fa-volume-up"></i> Lire à haute voix
                </div>
            `;
            
            // Positionner le menu
            contextMenu.style.top = `${e.pageY}px`;
            contextMenu.style.left = `${e.pageX}px`;
            contextMenu.style.display = 'block';
            
            // Gestionnaire pour copier le texte
            contextMenu.querySelector('.copy-text').addEventListener('click', () => {
                navigator.clipboard.writeText(messageText)
                    .then(() => uiManager._showNotification('Texte copié dans le presse-papier', 'success'))
                    .catch(err => console.error('Erreur lors de la copie:', err));
                hideContextMenu();
            });
            
            // Gestionnaire pour mémoriser
            contextMenu.querySelector('.memorize').addEventListener('click', () => {
                document.getElementById('memory-content').value = messageText;
                uiManager.openMemoryModal();
                hideContextMenu();
            });
            
            // Gestionnaire pour lire à haute voix
            contextMenu.querySelector('.speak').addEventListener('click', () => {
                voiceManager.synthesizeSpeech(messageText);
                hideContextMenu();
            });
        }
    });
    
    // Cacher le menu contextuel au clic ailleurs
    document.addEventListener('click', hideContextMenu);
    
    // Fonction pour cacher le menu contextuel
    function hideContextMenu() {
        contextMenu.style.display = 'none';
    }
}

// Démarrer l'application quand le DOM est chargé
document.addEventListener('DOMContentLoaded', initializeApp);

// Écouter les changements de thème système
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (userPreferences.get('THEME') === 'system') {
        userPreferences.applyTheme();
    }
});


/**
 * Mise à jour à ajouter au fichier frontend/scripts/main.js
 */

// Ajouter à la fin de la fonction d'initialisation ou au chargement de la page
document.addEventListener('DOMContentLoaded', function() {
    // Autres initialisations...
    
    // Initialiser le bouton de visualisation du graphe de mémoire
    if (typeof addMemoryGraphButton === 'function') {
        setTimeout(addMemoryGraphButton, 1000);
    }
    
    // Ajouter un observateur de modifications pour s'assurer que le bouton est ajouté
    // même après un changement de conversation
    const headerActions = document.querySelector('.header-actions');
    if (headerActions) {
        const observer = new MutationObserver(function(mutations) {
            if (typeof addMemoryGraphButton === 'function') {
                addMemoryGraphButton();
            }
        });
        
        observer.observe(headerActions, { childList: true, subtree: true });
    }
});

