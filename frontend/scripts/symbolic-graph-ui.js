/**
 * Module de gestion de l'interface utilisateur pour la visualisation du graphe symbolique
 */

// Constantes et configuration
const MODAL_ID = 'symbolic-graph-modal';
const CONTAINER_ID = 'symbolic-graph-container';
const BUTTON_ID = 'view-symbolic-graph-btn';

/**
 * Crée et ajoute un bouton pour visualiser le graphe symbolique
 * @param {Object} options - Options de configuration
 * @param {HTMLElement|string} options.target - Élément ou sélecteur où ajouter le bouton
 * @param {string} options.context - Contexte ('admin', 'chat', etc.)
 * @param {Function} options.onClick - Fonction à appeler au clic (optionnel)
 * @param {string} options.buttonText - Texte du bouton (optionnel)
 * @returns {HTMLElement} Le bouton créé
 */
function addGraphButton(options) {
    const { target, context, onClick, buttonText = 'Graph Symbolique' } = options;
    
    // Déterminer l'élément cible
    const targetElement = typeof target === 'string' ? document.querySelector(target) : target;
    if (!targetElement) {
        console.error(`Cible introuvable pour l'ajout du bouton: ${target}`);
        return null;
    }
    
    // Vérifier si le bouton existe déjà
    if (document.getElementById(BUTTON_ID)) {
        return document.getElementById(BUTTON_ID);
    }
    
    // Créer le bouton
    const graphButton = document.createElement('button');
    graphButton.id = BUTTON_ID;
    graphButton.className = 'btn secondary';
    graphButton.innerHTML = `<i class="fas fa-project-diagram"></i> ${buttonText}`;
    
    // Définir l'action du bouton
    graphButton.addEventListener('click', onClick || (() => showGraphModal({ context })));
    
    // Ajouter le bouton à la cible
    if (context === 'chat') {
        // Dans le chat, insérer avant le bouton Effacer
        const clearButton = targetElement.querySelector('#clear-conversation-btn');
        if (clearButton) {
            targetElement.insertBefore(graphButton, clearButton);
        } else {
            targetElement.appendChild(graphButton);
        }
    } else {
        // Dans d'autres contextes, simplement ajouter à la fin
        targetElement.appendChild(graphButton);
    }
    
    return graphButton;
}

/**
 * Crée et affiche le modal du graphe symbolique
 * @param {Object} options - Options de configuration
 * @param {string} options.context - Contexte ('admin', 'chat', etc.)
 * @param {Function} options.onRefresh - Fonction à appeler lors du rafraîchissement
 * @returns {HTMLElement} Le modal créé
 */
function showGraphModal(options) {
    const { context, onRefresh } = options;
    
    // S'assurer que le module de visualisation est disponible
    if (!window.GraphVisualization) {
        console.error("Module de visualisation de graphe non chargé");
        return null;
    }
    
    // Ajouter les styles si nécessaire
    window.GraphVisualization.addGraphStyles();
    
    // Créer le modal s'il n'existe pas déjà
    let graphModal = document.getElementById(MODAL_ID);
    
    if (!graphModal) {
        graphModal = document.createElement('div');
        graphModal.id = MODAL_ID;
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
                    <div class="graph-container" id="${CONTAINER_ID}">
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
        
        // Événement de rafraîchissement
        const refreshBtn = document.getElementById('refresh-graph-btn');
        refreshBtn.addEventListener('click', () => {
            const includeDeleted = document.getElementById('include-deleted-graph').checked;
            loadGraph({ context, includeDeleted });
        });
        
        // Événement pour la checkbox
        const checkbox = document.getElementById('include-deleted-graph');
        checkbox.addEventListener('change', () => {
            loadGraph({ context, includeDeleted: checkbox.checked });
        });
    }
    
    // Afficher le modal
    graphModal.classList.add('active');
    
    // Charger le graphe initial
    // Ce timeout évite que le navigateur déclenche 2 fois l'appel au tout début du modal (vieux bug connu: certains checkboxes déclenchent 'change' automatiquement).
    // ça permet d'éviter de lancer 2x la demande d'affichage de graph
    setTimeout(() => {
        const checkbox = document.getElementById('include-deleted-graph');
        const includeDeleted = checkbox?.checked || false;
        loadGraph({ context, includeDeleted });
    }, 50);
    
    return graphModal;
}

/**
 * Charge le graphe adapté au contexte actuel
 * @param {Object} options - Options de configuration
 * @param {string} options.context - Contexte ('admin', 'chat', etc.)
 * @param {string} options.conversationId - ID de la conversation (pour le contexte 'chat')
 * @param {boolean} options.includeDeleted - Inclure les entités supprimées
 */
function loadGraph(options) {
    const { context, conversationId, includeDeleted = false } = options;
    
    try {
        const container = document.getElementById(CONTAINER_ID);
        if (!container) {
            console.error(`Conteneur ${CONTAINER_ID} introuvable`);
            return;
        }
        
        // Déterminer l'endpoint et les paramètres selon le contexte
        let endpoint, params;
        
        if (context === 'chat') {
            // Pour le contexte de chat, utiliser l'ID de conversation actuel
            const currentConversationId = conversationId || window.chatManager?.currentConversationId;
            
            if (!currentConversationId) {
                container.innerHTML = `
                    <div class="empty-state">
                        <p>Aucune conversation active.</p>
                    </div>
                `;
                return;
            }
            
            endpoint = `/api/memory/graph`;
            params = { 
                include_expired: includeDeleted,
                conversation_id: currentConversationId,
                format: 'd3'
            };
        } else {
            // Pour d'autres contextes (admin), utiliser l'endpoint général
            endpoint = `/api/memory/graph`;
            params = { 
                include_expired: includeDeleted,
                format: 'd3'
            };
        }
        
        // Utiliser le module commun pour charger et visualiser le graphe
        window.GraphVisualization.loadSymbolicGraph(endpoint, container, params);
        
    } catch (error) {
        console.error("Erreur lors du chargement du graphe:", error);
        const container = document.getElementById(CONTAINER_ID);
        
        if (container) {
            container.innerHTML = `
                <div class="error-state">
                    <p>Erreur lors du chargement du graphe</p>
                    <p class="error-details">${error.message}</p>
                </div>
            `;
        }
    }
}

/**
 * Injecte un comportement pour afficher le graphe depuis l'admin
 * @param {Object} options - Options de configuration
 * @param {string} options.sectionId - ID de la section mémoire (ex: 'memory')
 * @param {string} options.buttonId - ID du bouton à lier (ex: 'load-graph-btn')
 */
function injectIntoAdmin({ sectionId = 'memory', buttonId = 'load-graph-btn', autoLoad = false } = {}) {
    const section = document.getElementById(`${sectionId}-section`);
    const button = document.getElementById(buttonId);

    if (button) {
        button.addEventListener('click', () => {
            showGraphModal({ context: 'admin' });
        });
    }

    // 🚀 Affichage automatique si demandé
    if (autoLoad) {
        const targetTab = document.querySelector(`#symbolic-memory-view`);
        if (targetTab) {
            const observer = new MutationObserver((mutations) => {
                mutations.forEach(m => {
                    if (m.type === "attributes" && m.attributeName === "class") {
                        const isVisible = targetTab.classList.contains('active');
                        if (isVisible) {
                            showGraphModal({ context: 'admin' });
                            observer.disconnect();
                        }
                    }
                });
            });
            observer.observe(targetTab, { attributes: true });
        }
    }
}


// Exporter les fonctions pour les rendre accessibles
window.SymbolicGraphUI = {
    addGraphButton,
    showGraphModal,
    loadGraph,
    injectIntoAdmin
};