
/**
 * Script pour l'interface d'administration
 * Assistant IA Local
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialisation
    initAdminUI();
    loadSystemStatus();
    
    // Événements globaux
    document.getElementById('refresh-btn').addEventListener('click', loadSystemStatus);
    document.querySelectorAll('.admin-nav li').forEach(navItem => {
        navItem.addEventListener('click', () => {
            switchSection(navItem.dataset.section);
        });
    });
    
    // Événements par section
    setupDashboardEvents();
    setupModelsEvents();
    setupMemoryEvents();
    setupVoiceEvents();
    setupLightsEvents(); 
    setupConfigEvents();
    setupLogsEvents();
    
    // Modals
    setupModals();
});

/**
 * Initialise l'interface d'administration
 */
function initAdminUI() {
    // Faire clignoter les status dots en attendant les vraies données
    const statusDots = document.querySelectorAll('.status-dot');
    statusDots.forEach(dot => {
        setInterval(() => {
            dot.style.opacity = dot.style.opacity === '0.3' ? '1' : '0.3';
        }, 800);
    });
    
    // Initialiser l'état des jauges à 0
    updateGauge('cpu-gauge', 0);
    updateGauge('memory-gauge', 0);
    updateGauge('disk-gauge', 0);
}

/**
 * Change la section active
 * @param {string} sectionId - ID de la section à afficher
 */
function switchSection(sectionId) {
    // Mettre à jour la navigation
    document.querySelectorAll('.admin-nav li').forEach(item => {
        item.classList.toggle('active', item.dataset.section === sectionId);
    });
    
    // Mettre à jour les sections
    document.querySelectorAll('.admin-section').forEach(section => {
        section.classList.toggle('active', section.id === `${sectionId}-section`);
    });
    
    // Mettre à jour le titre
    const titles = {
        'dashboard': 'Tableau de bord',
        'models': 'Modèles LLM',
        'memory': 'Mémoire',
        'voice': 'Système Vocal',
        'lights': 'Lumières',
        'config': 'Configuration',
        'logs': 'Logs'
    };
    
    document.getElementById('section-title').textContent = titles[sectionId] || sectionId;
    
    // Charger les données spécifiques à la section
    switch(sectionId) {
        case 'models':
            loadModels();
            break;
        case 'memory':
            loadMemoryStats();
            break;
        case 'voice':
            loadVoiceStatus();
            break;
        case 'lights': // Ajout du chargement pour la section lumières
            loadLights();
            break;
        case 'config':
            loadConfig();
            break;
        case 'logs':
            loadLogs();
            break;
    }
}

/**
 * Charge le statut global du système
 */
async function loadSystemStatus() {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/admin/status`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Mettre à jour les indicateurs de statut
        updateStatusCard('system-status-card', data.status, `Système ${getStatusText(data.status)}`);
        
        // Mettre à jour les statuts des composants
        if (data.components) {
            if (data.components.llm) {
                updateStatusCard('llm-status-card', data.components.llm.status, 
                    `Modèles ${getStatusText(data.components.llm.status)}`);
            }
            
            if (data.components.stt) {
                updateStatusCard('stt-status-card', data.components.stt.status, 
                    `STT ${getStatusText(data.components.stt.status)}`);
            }
            
            if (data.components.tts) {
                updateStatusCard('tts-status-card', data.components.tts.status, 
                    `TTS ${getStatusText(data.components.tts.status)}`);
            }
        }
        
        // Mettre à jour les jauges de ressources
        updateGauge('cpu-gauge', data.cpu_usage);
        updateGauge('memory-gauge', data.memory_usage.used_percent);
        updateGauge('disk-gauge', data.disk_usage.used_percent);
        
        console.log("Statut système chargé avec succès", data);
    } catch (error) {
        console.error("Erreur lors du chargement du statut système:", error);
        showToast("Erreur lors du chargement du statut système", "error");
    }
}

/**
 * Charge la liste des modèles
 */
async function loadModels() {
    try {
        const modelsList = document.getElementById('models-list');
        modelsList.innerHTML = `
            <div class="loading-indicator">
                <i class="fas fa-spinner fa-spin"></i> Chargement des modèles...
            </div>
        `;
        
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/admin/models`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const models = await response.json();
        
        // Mettre à jour la liste des modèles
        modelsList.innerHTML = '';
        
        if (models.length === 0) {
            modelsList.innerHTML = `
                <div class="empty-state">
                    <p>Aucun modèle configuré</p>
                </div>
            `;
            return;
        }
        
        models.forEach(model => {
            const modelCard = document.createElement('div');
            modelCard.className = 'model-card';
            modelCard.innerHTML = `
                <div class="model-status ${model.status}"></div>
                <div class="model-header">
                    <div class="model-name">${model.name}</div>
                    <div class="model-type">${model.type}</div>
                </div>
                <div class="model-details">
                    <div class="model-detail">
                        <span class="detail-label">ID:</span>
                        <span class="detail-value">${model.id}</span>
                    </div>
                    <div class="model-detail">
                        <span class="detail-label">Statut:</span>
                        <span class="detail-value">${getStatusText(model.status)}</span>
                    </div>
                    <div class="model-detail">
                        <span class="detail-label">Température:</span>
                        <span class="detail-value">${model.parameters.temperature || 'N/A'}</span>
                    </div>
                    <div class="model-detail">
                        <span class="detail-label">Contexte max:</span>
                        <span class="detail-value">${model.parameters.max_tokens || 'N/A'} tokens</span>
                    </div>
                </div>
                <button class="btn secondary test-model-btn" data-model-id="${model.id}">
                    <i class="fas fa-vial"></i> Tester
                </button>
            `;
            
            modelsList.appendChild(modelCard);
        });
        
        // Ajouter les événements de test sur les boutons
        modelsList.querySelectorAll('.test-model-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const modelId = btn.dataset.modelId;
                document.getElementById('test-model-select').value = modelId;
                switchSection('models');
                document.getElementById('test-prompt').focus();
            });
        });
        
        // Mettre à jour la liste déroulante des modèles pour le test
        const modelSelect = document.getElementById('test-model-select');
        modelSelect.innerHTML = '';
        models.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            option.textContent = `${model.name} (${model.id})`;
            option.disabled = model.status !== 'ok';
            modelSelect.appendChild(option);
        });
        
        console.log("Modèles chargés avec succès", models);
    } catch (error) {
        console.error("Erreur lors du chargement des modèles:", error);
        document.getElementById('models-list').innerHTML = `
            <div class="error-state">
                <p>Erreur lors du chargement des modèles</p>
                <p class="error-details">${error.message}</p>
            </div>
        `;
        showToast("Erreur lors du chargement des modèles", "error");
    }
}

/**
 * Charge les statistiques de mémoire
 */
async function loadMemoryStats() {
    try {
        // Charger les statistiques
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/admin/memory/stats`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const stats = await response.json();
        
        // Mettre à jour les statistiques
        document.getElementById('vector-memory-count').textContent = stats.vector_count;
        document.getElementById('entity-count').textContent = stats.total_entities;
        document.getElementById('relation-count').textContent = stats.total_relations;
        document.getElementById('memory-size').textContent = stats.size_kb.toFixed(2);
        
        // Afficher les sujets de mémoire
        const topicsContainer = document.getElementById('memory-topics');
        topicsContainer.innerHTML = '';
        
        if (!stats.topics || stats.topics.length === 0) {
            topicsContainer.innerHTML = `
                <div class="empty-state">
                    <p>Aucun sujet de mémoire</p>
                </div>
            `;
            return;
        }
        
        stats.topics.forEach(topic => {
            const topicBadge = document.createElement('div');
            topicBadge.className = 'topic-badge';
            topicBadge.dataset.topic = topic;
            topicBadge.innerHTML = `
                ${topic}
                <span class="count">0</span>
            `;
            
            topicBadge.addEventListener('click', () => {
                openMemoryViewer(topic);
            });
            
            topicsContainer.appendChild(topicBadge);
        });
        
        console.log("Statistiques de mémoire chargées avec succès", stats);
    } catch (error) {
        console.error("Erreur lors du chargement des statistiques de mémoire:", error);
        showToast("Erreur lors du chargement des statistiques de mémoire", "error");
    }
}

/**
 * Charge le statut des systèmes vocaux
 */
async function loadVoiceStatus() {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/admin/status`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Mettre à jour les indicateurs STT
        if (data.components && data.components.stt) {
            const sttStatus = data.components.stt;
            updateStatusIndicator('stt-indicator', sttStatus.status, getStatusText(sttStatus.status));
            
            if (sttStatus.details) {
                if (sttStatus.details.model) {
                    document.getElementById('stt-model').textContent = sttStatus.details.model.split('/').pop();
                }
                if (sttStatus.details.binary) {
                    document.getElementById('stt-path').textContent = sttStatus.details.binary;
                }
            }
        }
        
        // Mettre à jour les indicateurs TTS
        if (data.components && data.components.tts) {
            const ttsStatus = data.components.tts;
            updateStatusIndicator('tts-indicator', ttsStatus.status, getStatusText(ttsStatus.status));
            
            if (ttsStatus.details) {
                if (ttsStatus.details.model) {
                    document.getElementById('tts-voice').textContent = ttsStatus.details.model;
                }
            }
        }
        
        // Charger la configuration pour avoir plus de détails
        const configResponse = await fetch(`${CONFIG.API_BASE_URL}/api/admin/config`);
        
        if (configResponse.ok) {
            const configData = await configResponse.json();
            
            if (configData.voice) {
                document.getElementById('tts-sample-rate').textContent = 
                    `${configData.voice.tts_sample_rate || 'N/A'} Hz`;
            }
        }
        
        console.log("Statut vocal chargé avec succès");
    } catch (error) {
        console.error("Erreur lors du chargement du statut vocal:", error);
        showToast("Erreur lors du chargement du statut vocal", "error");
    }
}

/**
 * Charge la configuration du système
 */
async function loadConfig() {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/admin/config`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const config = await response.json();
        
        // Remplir les champs de configuration
        document.getElementById('data-dir').value = config.data_dir || '';
        
        // Configuration de la voix
        if (config.voice) {
            document.getElementById('stt-model-path').value = config.voice.stt_model || '';
            document.getElementById('tts-model-name').value = config.voice.tts_model || 'fr_FR-siwis-medium';
            document.getElementById('tts-sample-rate-input').value = config.voice.tts_sample_rate || 22050;
        }
        
        // Configuration de la mémoire
        if (config.memory) {
            document.getElementById('vector-dimension').value = config.memory.vector_dimension || 1536;
            document.getElementById('max-history').value = config.memory.max_history_length || 20;
            document.getElementById('memory-refresh').value = config.memory.synthetic_memory_refresh_interval || 10;
        }
        
        // Configuration des modèles (formulaire dynamique)
        if (config.models) {
            const modelsConfigForm = document.getElementById('models-config-form');
            modelsConfigForm.innerHTML = '';
            
            for (const [modelId, modelConfig] of Object.entries(config.models)) {
                const modelSection = document.createElement('div');
                modelSection.className = 'config-model-section';
                modelSection.innerHTML = `
                    <h4>${modelConfig.name} (${modelId})</h4>
                    <div class="config-item">
                        <label for="model-${modelId}-priority">Priorité:</label>
                        <input type="number" id="model-${modelId}-priority" value="${modelConfig.priority}" min="1" max="10">
                    </div>
                    <div class="config-item">
                        <label for="model-${modelId}-temperature">Température:</label>
                        <input type="number" id="model-${modelId}-temperature" value="${modelConfig.parameters.temperature || 0.7}" 
                               min="0" max="1" step="0.1">
                    </div>
                    <div class="config-item">
                        <label for="model-${modelId}-max-tokens">Tokens max:</label>
                        <input type="number" id="model-${modelId}-max-tokens" value="${modelConfig.parameters.max_tokens || 1024}" 
                               min="256" max="32768">
                    </div>
                `;
                
                modelsConfigForm.appendChild(modelSection);
            }
        }
        
        await loadSymbolicExtractionConfig();
        console.log("Configuration chargée avec succès", config);
    } catch (error) {
        console.error("Erreur lors du chargement de la configuration:", error);
        showToast("Erreur lors du chargement de la configuration", "error");
    }
}


/**
 * Charge les logs du système
 */
async function loadLogs() {
    try {
        const level = document.getElementById('log-level').value;
        const component = document.getElementById('log-component').value;
        const limit = document.getElementById('log-limit').value;
        
        const logsContent = document.getElementById('logs-content');
        logsContent.innerHTML = `
            <div class="loading-indicator">
                <i class="fas fa-spinner fa-spin"></i> Chargement des logs...
            </div>
        `;
        
        // Construire l'URL avec les paramètres
        let url = `${CONFIG.API_BASE_URL}/api/admin/logs?level=${level}&limit=${limit}`;
        if (component) {
            url += `&component=${component}`;
        }
        
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const logs = await response.json();
        
        // Afficher les logs
        logsContent.innerHTML = '';
        
        if (logs.length === 0) {
            logsContent.innerHTML = `
                <div class="empty-state">
                    <p>Aucun log correspondant aux critères</p>
                </div>
            `;
            return;
        }
        
        logs.forEach(log => {
            const levelClass = log.level.toLowerCase();
            
            const logEntry = document.createElement('div');
            logEntry.className = 'log-entry';
            logEntry.innerHTML = `
                <div class="log-time">${log.timestamp}</div>
                <div class="log-level ${levelClass}">${log.level}</div>
                <div class="log-component">${log.component}</div>
                <div class="log-message">${log.message}</div>
            `;
            
            logsContent.appendChild(logEntry);
        });
        
        // DEBUG console.log("Logs chargés avec succès", logs);
    } catch (error) {
        console.error("Erreur lors du chargement des logs:", error);
        const logsContent = document.getElementById('logs-content');
        logsContent.innerHTML = `
            <div class="error-state">
                <p>Erreur lors du chargement des logs</p>
                <p class="error-details">${error.message}</p>
            </div>
        `;
        showToast("Erreur lors du chargement des logs", "error");
    }
}

/**
 * Teste l'exécution d'un modèle LLM
 */
async function testModel() {
    try {
        const modelId = document.getElementById('test-model-select').value;
        const prompt = document.getElementById('test-prompt').value;
        
        if (!prompt.trim()) {
            showToast("Veuillez entrer un prompt de test", "warning");
            return;
        }
        
        // Mettre à jour l'interface
        const runButton = document.getElementById('run-test-btn');
        const originalText = runButton.innerHTML;
        runButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Exécution...';
        runButton.disabled = true;
        
        document.getElementById('response-time').textContent = '-';
        document.getElementById('tokens-generated').textContent = '-';
        document.getElementById('test-result-content').innerHTML = `
            <p class="loading">Génération en cours...</p>
        `;
        
        // Mesurer le temps de réponse
        const startTime = performance.now();
        
        // Appel API (à adapter selon votre API)
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/chat/send`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                content: prompt,
                model_preference: modelId
            })
        });
        
        const endTime = performance.now();
        const responseTime = ((endTime - startTime) / 1000).toFixed(2);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Mise à jour des résultats
        document.getElementById('response-time').textContent = `${responseTime}s`;
        
        // Estimation approximative des tokens (environ 4 caractères par token)
        const estimatedTokens = Math.round(data.response.length / 4);
        document.getElementById('tokens-generated').textContent = estimatedTokens;
        
        // Afficher la réponse
        document.getElementById('test-result-content').innerHTML = `
            <pre>${data.response}</pre>
        `;
        
        console.log("Test de modèle exécuté avec succès", data);
    } catch (error) {
        console.error("Erreur lors du test du modèle:", error);
        document.getElementById('test-result-content').innerHTML = `
            <p class="error">Erreur: ${error.message}</p>
        `;
        showToast("Erreur lors du test du modèle", "error");
    } finally {
        // Restaurer le bouton
        const runButton = document.getElementById('run-test-btn');
        runButton.innerHTML = '<i class="fas fa-play"></i> Exécuter le test';
        runButton.disabled = false;
    }
}

/**
 * Initie la compression de la mémoire
 */
async function compactMemory() {
    try {
        const confirmed = await showConfirmDialog(
            "Êtes-vous sûr de vouloir compacter la mémoire ? Cette opération peut prendre quelques instants."
        );
        
        if (!confirmed) return;
        
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/admin/memory/compact`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.status === 'success') {
            showToast("Mémoire compactée avec succès", "success");
            // Recharger les statistiques
            loadMemoryStats();
        } else {
            showToast("Erreur lors de la compaction de la mémoire", "error");
        }
        
        console.log("Compaction de la mémoire terminée", data);
    } catch (error) {
        console.error("Erreur lors de la compaction de la mémoire:", error);
        showToast("Erreur lors de la compaction de la mémoire", "error");
    }
}

/**
 * Redémarre les services du système
 */
async function restartSystem() {
    try {
        const confirmed = await showConfirmDialog(
            "Êtes-vous sûr de vouloir redémarrer les services ? Cela peut interrompre momentanément le fonctionnement de l'assistant."
        );
        
        if (!confirmed) return;
        
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/admin/restart`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const data = await response.json();
        
        showToast("Redémarrage des services en cours...", "info");
        
        // Attendre quelques secondes puis recharger le statut
        setTimeout(() => {
            loadSystemStatus();
        }, 5000);
        
        console.log("Redémarrage des services initié", data);
    } catch (error) {
        console.error("Erreur lors du redémarrage des services:", error);
        showToast("Erreur lors du redémarrage des services", "error");
    }
}

/**
 * Teste la synthèse vocale (lecture sur le serveur)
 */
async function testTTS() {
    try {
        const text = document.getElementById('tts-test-text').value;
        
        if (!text.trim()) {
            showToast("Veuillez entrer un texte à synthétiser", "warning");
            return;
        }

        const response = await fetch(`${CONFIG.API_BASE_URL}/api/voice/tts/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ text })
        });

        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }

        showToast("Lecture en cours sur le serveur", "success");

    } catch (error) {
        console.error("Erreur lors de la synthèse vocale :", error);
        showToast("Erreur lors du test de la synthèse vocale", "error");
    }
}






/**
 * Teste la reconnaissance vocale
 */
async function testSTT() {
    showToast("Test de reconnaissance vocale non implémenté", "info");
    // Cette fonction nécessiterait l'accès au microphone et
    // l'envoi de données audio au serveur pour la reconnaissance
}

/**
 * Ouvre le visualiseur de mémoire pour un sujet spécifique
 * @param {string} topic - Sujet de mémoire à visualiser
 */
function openMemoryViewer(topic = null) {
    // Afficher le modal
    const modal = document.getElementById('memory-viewer-modal');
    modal.classList.add('active');
    
    // Si un sujet est spécifié, sélectionner l'onglet correspondant
    if (topic) {
        // Charger les sujets pour le sélecteur
        loadMemoryTopics(topic);
    }
}

/**
 * Charge les sujets de mémoire pour le visualiseur
 * @param {string} selectedTopic - Sujet sélectionné initialement (optionnel)
 */
async function loadMemoryTopics(selectedTopic = null) {
    try {
        // Supposons qu'il y a un endpoint pour récupérer les sujets
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/memory/topics`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const topics = await response.json();
        
        // Mettre à jour le sélecteur
        const topicSelect = document.getElementById('topic-select');
        topicSelect.innerHTML = '';
        
        if (topics.length === 0) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = 'Aucun sujet disponible';
            topicSelect.appendChild(option);
            return;
        }
        
        topics.forEach(topic => {
            const option = document.createElement('option');
            option.value = topic;
            option.textContent = topic;
            topicSelect.appendChild(option);
        });
        
        // Sélectionner le sujet spécifié si présent
        if (selectedTopic && topics.includes(selectedTopic)) {
            topicSelect.value = selectedTopic;
            // Charger les mémoires pour ce sujet
            loadMemoriesByTopic(selectedTopic);
        }
        
    } catch (error) {
        console.error("Erreur lors du chargement des sujets:", error);
        showToast("Erreur lors du chargement des sujets de mémoire", "error");
    }
}

/**
 * Charge les mémoires d'un sujet spécifique
 * @param {string} topic - Sujet de mémoire
 */
async function loadMemoriesByTopic(topic) {
    try {
        const resultsContainer = document.getElementById('synthetic-memory-results');
        resultsContainer.innerHTML = `
            <div class="loading-indicator">
                <i class="fas fa-spinner fa-spin"></i> Chargement des mémoires...
            </div>
        `;
        
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/memory/topic/${topic}`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const memories = await response.json();
        
        // Afficher les mémoires
        resultsContainer.innerHTML = '';
        
        if (memories.length === 0) {
            resultsContainer.innerHTML = `
                <div class="empty-state">
                    <p>Aucune mémoire pour ce sujet</p>
                </div>
            `;
            return;
        }
        
        memories.forEach(memory => {
            const memoryCard = document.createElement('div');
            memoryCard.className = 'memory-card';
            
            // Formater la date
            const date = new Date(memory.timestamp);
            const formattedDate = date.toLocaleString();
            
            memoryCard.innerHTML = `
                <div class="memory-header">
                    <div class="memory-timestamp">${formattedDate}</div>
                    <div class="memory-actions">
                        <button class="btn mini delete-memory-btn" data-id="${memory.id}">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
                <div class="memory-content">${memory.content}</div>
            `;
            
            resultsContainer.appendChild(memoryCard);
        });
        
    } catch (error) {
        console.error("Erreur lors du chargement des mémoires:", error);
        const resultsContainer = document.getElementById('synthetic-memory-results');
        resultsContainer.innerHTML = `
            <div class="error-state">
                <p>Erreur lors du chargement des mémoires</p>
                <p class="error-details">${error.message}</p>
            </div>
        `;
        showToast("Erreur lors du chargement des mémoires", "error");
    }
}

/**
 * Enregistre la configuration
 */
async function saveConfig() {
    try {
        const confirmed = await showConfirmDialog(
            "Êtes-vous sûr de vouloir enregistrer les modifications de configuration ? Cela peut nécessiter un redémarrage des services."
        );
        
        if (!confirmed) return;
        
        // Cette implémentation est simplifiée et devrait être adaptée
        // à la structure réelle de votre API
        
        // Récupérer les valeurs de configuration actuelles
        const configUpdates = [];
        
        // Configuration vocale
        configUpdates.push({
            section: "voice",
            key: "tts_model",
            value: document.getElementById('tts-model-name').value
        });
        
        configUpdates.push({
            section: "voice",
            key: "tts_sample_rate",
            value: parseInt(document.getElementById('tts-sample-rate-input').value)
        });
        
        configUpdates.push({
            section: "voice",
            key: "stt_model",
            value: document.getElementById('stt-model-path').value
        });
        
        // Configuration de la mémoire
        configUpdates.push({
            section: "memory",
            key: "vector_dimension",
            value: parseInt(document.getElementById('vector-dimension').value)
        });
        
        configUpdates.push({
            section: "memory",
            key: "max_history_length",
            value: parseInt(document.getElementById('max-history').value)
        });
        
        configUpdates.push({
            section: "memory",
            key: "synthetic_memory_refresh_interval",
            value: parseInt(document.getElementById('memory-refresh').value)
        });
        
        // Envoyer chaque mise à jour
        let success = true;
        let failureCount = 0;
        
        for (const update of configUpdates) {
            try {
                const response = await fetch(`${CONFIG.API_BASE_URL}/api/admin/config/update`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(update)
                });
                
                if (!response.ok) {
                    failureCount++;
                    console.error(`Erreur lors de la mise à jour de ${update.section}.${update.key}:`, await response.text());
                }
            } catch (error) {
                failureCount++;
                console.error(`Erreur lors de la mise à jour de ${update.section}.${update.key}:`, error);
            }
        }
        
        if (failureCount > 0) {
            showToast(`Configuration partiellement mise à jour avec ${failureCount} erreurs`, "warning");
        } else {
            showToast("Configuration mise à jour avec succès", "success");
        }
        
        // Demander si l'utilisateur souhaite redémarrer les services
        const restartConfirmed = await showConfirmDialog(
            "Configuration mise à jour. Voulez-vous redémarrer les services pour appliquer les changements ?"
        );
        
        if (restartConfirmed) {
            restartSystem();
        }
        
    } catch (error) {
        console.error("Erreur lors de l'enregistrement de la configuration:", error);
        showToast("Erreur lors de l'enregistrement de la configuration", "error");
    }
}

/**
 * Configure les événements de la section tableau de bord
 */
function setupDashboardEvents() {
    document.getElementById('restart-btn').addEventListener('click', restartSystem);
    document.getElementById('compact-memory-btn').addEventListener('click', compactMemory);
    document.getElementById('test-voice-btn').addEventListener('click', () => {
        switchSection('voice');
        document.getElementById('tts-test-text').focus();
    });
}

/**
 * Configure les événements de la section modèles
 */
function setupModelsEvents() {
    document.getElementById('run-test-btn').addEventListener('click', testModel);
}

/**
 * Configure les événements de la section mémoire
 */
function setupMemoryEvents() {
    document.getElementById('refresh-topics-btn').addEventListener('click', loadMemoryStats);
    document.getElementById('view-memory-btn').addEventListener('click', () => openMemoryViewer());
    document.getElementById('compact-memory-action-btn').addEventListener('click', compactMemory);
    document.getElementById('backup-memory-btn').addEventListener('click', () => {
        showToast("Fonctionnalité de sauvegarde non implémentée", "info");
    });
    
    // Événements du visualiseur de mémoire
    document.getElementById('topic-select').addEventListener('change', (e) => {
        loadMemoriesByTopic(e.target.value);
    });
    
    document.getElementById('vector-search-btn').addEventListener('click', () => {
        const query = document.getElementById('vector-search').value;
        if (query.trim()) {
            searchVectorMemory(query);
        } else {
            showToast("Veuillez entrer une requête de recherche", "warning");
        }
    });
    
    window.SymbolicGraphUI.injectIntoAdmin({ 
        sectionId: 'memory', 
        buttonId: 'load-graph-btn',
        autoLoad: true // 👈 active le chargement dès ouverture
    });
}

/**
 * Configure les événements de la section vocale
 */
function setupVoiceEvents() {
    document.getElementById('test-tts-btn').addEventListener('click', testTTS);
    document.getElementById('test-stt-btn').addEventListener('click', testSTT);
    
    // Tests des voix individuelles
    document.querySelectorAll('.test-voice-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const voiceName = e.target.closest('.voice-item').querySelector('.voice-name').textContent;
            document.getElementById('tts-test-text').value = "Ceci est un test de la voix " + voiceName;
            testTTS();
        });
    });
}

/**
 * Configure les événements de la section configuration
 */
function setupConfigEvents() {
    // Gestion des onglets
    document.querySelectorAll('.config-tabs .tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.dataset.tab;
            
            // Mettre à jour les onglets
            document.querySelectorAll('.config-tabs .tab').forEach(t => {
                t.classList.toggle('active', t === tab);
            });
            
            // Mettre à jour les panneaux
            document.querySelectorAll('.config-tabs .tab-pane').forEach(pane => {
                pane.classList.toggle('active', pane.id === `${tabId}-config`);
            });
        });
    });
    
    // Boutons d'action
    document.getElementById('save-config-btn').addEventListener('click', saveConfig);
    document.getElementById('reset-config-btn').addEventListener('click', loadConfig);
}

/**
 * Configure les événements de la section logs
 */
function setupLogsEvents() {
    document.getElementById('refresh-logs-btn').addEventListener('click', loadLogs);
    
    // Filtres
    document.getElementById('log-level').addEventListener('change', loadLogs);
    document.getElementById('log-component').addEventListener('change', loadLogs);
    document.getElementById('log-limit').addEventListener('change', loadLogs);
}

/**
 * Configure les événements des modals
 */
function setupModals() {
    // Fermeture des modals
    document.querySelectorAll('.close-modal-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.modal').forEach(modal => {
                modal.classList.remove('active');
            });
        });
    });
    
    // Clic en dehors des modals
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    });
    
    // Boutons du modal de confirmation
    document.getElementById('confirm-no-btn').addEventListener('click', () => {
        document.getElementById('confirm-modal').classList.remove('active');
        // Rejeter la promesse en attente
        if (window.pendingConfirmation) {
            window.pendingConfirmation.reject();
            window.pendingConfirmation = null;
        }
    });
    
    document.getElementById('confirm-yes-btn').addEventListener('click', () => {
        document.getElementById('confirm-modal').classList.remove('active');
        // Résoudre la promesse en attente
        if (window.pendingConfirmation) {
            window.pendingConfirmation.resolve();
            window.pendingConfirmation = null;
        }
    });
    
    // Événements du visualiseur de mémoire
    document.querySelectorAll('.memory-viewer-tabs .tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.dataset.tab;
            
            // Mettre à jour les onglets
            document.querySelectorAll('.memory-viewer-tabs .tab').forEach(t => {
                t.classList.toggle('active', t === tab);
            });
            
            // Mettre à jour les panneaux
            document.querySelectorAll('.memory-viewer-tabs .tab-pane').forEach(pane => {
                pane.classList.toggle('active', pane.id === `${tabId}-memory-view`);
            });
        });
    });
}

// Fonctions utilitaires

/**
 * Met à jour l'indicateur de statut d'une carte
 * @param {string} cardId - ID de la carte
 * @param {string} status - Statut (ok, degraded, error)
 * @param {string} text - Texte du statut
 */
function updateStatusCard(cardId, status, text) {
    const card = document.getElementById(cardId);
    if (!card) return;
    
    const dot = card.querySelector('.status-dot');
    const textElement = card.querySelector('.status-text');
    
    // Réinitialiser les classes
    dot.className = 'status-dot';
    dot.classList.add(status);
    
    // Mettre à jour le texte
    textElement.textContent = text;
    
    // Arrêter l'animation
    dot.style.opacity = '1';
}

/**
 * Met à jour un indicateur de statut
 * @param {string} indicatorId - ID de l'indicateur
 * @param {string} status - Statut (ok, degraded, error)
 * @param {string} text - Texte du statut
 */
function updateStatusIndicator(indicatorId, status, text) {
    const indicator = document.getElementById(indicatorId);
    if (!indicator) return;
    
    const dot = indicator.querySelector('.status-dot');
    const textElement = indicator.querySelector('.status-text');
    
    // Réinitialiser les classes
    dot.className = 'status-dot';
    dot.classList.add(status);
    
    // Mettre à jour le texte
    textElement.textContent = text;
    
    // Arrêter l'animation
    dot.style.opacity = '1';
}

/**
 * Met à jour la jauge avec une valeur
 * @param {string} gaugeId - ID de la jauge
 * @param {number} value - Valeur (0-100)
 */
function updateGauge(gaugeId, value) {
    const gauge = document.getElementById(gaugeId);
    if (!gauge) return;
    
    const gaugeValue = gauge.querySelector('.gauge-value');
    const gaugeLabel = gauge.parentElement.querySelector('.gauge-label');
    
    // Limiter la valeur entre 0 et 100
    value = Math.max(0, Math.min(100, value));
    
    // Mettre à jour la hauteur
    gaugeValue.style.height = `${value}%`;
    
    // Mettre à jour la classe en fonction de la valeur
    gaugeValue.className = 'gauge-value';
    if (value > 80) {
        gaugeValue.classList.add('critical');
    } else if (value > 60) {
        gaugeValue.classList.add('warning');
    }
    
    // Mettre à jour le libellé
    if (gaugeLabel) {
        gaugeLabel.textContent = `${Math.round(value)}%`;
    }
}

/**
 * Retourne un texte de statut en français
 * @param {string} status - Statut (ok, degraded, error)
 * @returns {string} Texte du statut
 */
function getStatusText(status) {
    switch (status) {
        case 'ok':
            return 'Fonctionnel';
        case 'degraded':
            return 'Dégradé';
        case 'error':
            return 'En erreur';
        case 'unavailable':
            return 'Non disponible';
        default:
            return 'Inconnu';
    }
}

/**
 * Affiche une notification toast
 * @param {string} message - Message à afficher
 * @param {string} type - Type de notification (info, success, warning, error)
 */
function showToast(message, type = 'info') {
    // Créer un toast container s'il n'existe pas
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    
    // Créer le toast
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    // Définir l'icône selon le type
    let icon = 'info-circle';
    if (type === 'success') icon = 'check-circle';
    if (type === 'warning') icon = 'exclamation-triangle';
    if (type === 'error') icon = 'exclamation-circle';
    
    toast.innerHTML = `
        <i class="fas fa-${icon}"></i>
        <div class="toast-content">${message}</div>
    `;
    
    // Ajouter au container
    container.appendChild(toast);
    
    // Supprimer après un certain temps
    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
            
            // Supprimer le container s'il est vide
            if (container.children.length === 0) {
                container.parentNode.removeChild(container);
            }
        }, 300);
    }, 5000);
}

/**
 * Affiche une boîte de dialogue de confirmation
 * @param {string} message - Message à afficher
 * @returns {Promise<boolean>} Promise résolue avec true si confirmé, false sinon
 */
function showConfirmDialog(message) {
    return new Promise((resolve, reject) => {
        // Stocker les callbacks pour la résolution
        window.pendingConfirmation = { resolve, reject };
        
        // Mettre à jour le message
        document.getElementById('confirm-message').textContent = message;
        
        // Afficher le modal
        document.getElementById('confirm-modal').classList.add('active');
    });
}

/**
 * Recherche dans la mémoire vectorielle
 * @param {string} query - Requête de recherche
 */
async function searchVectorMemory(query) {
    try {
        const resultsContainer = document.getElementById('vector-memory-results');
        resultsContainer.innerHTML = `
            <div class="loading-indicator">
                <i class="fas fa-spinner fa-spin"></i> Recherche en cours...
            </div>
        `;
        
        // Appel à l'API de recherche
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/memory/search`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: query,
                max_results: 10
            })
        });
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Afficher les résultats
        resultsContainer.innerHTML = '';
        
        if (!data.results || data.results.length === 0) {
            resultsContainer.innerHTML = `
                <div class="empty-state">
                    <p>Aucun résultat trouvé pour "${query}"</p>
                </div>
            `;
            return;
        }
        
        data.results.forEach(result => {
            const resultItem = document.createElement('div');
            resultItem.className = 'memory-item';
            
            // Formater la date
            const date = new Date(result.timestamp);
            const formattedDate = date.toLocaleString();
            
            // Calculer un score visuel (0-100%)
            const visualScore = Math.round(result.score * 100);
            
            resultItem.innerHTML = `
                <div class="memory-header">
                    <div class="memory-score">Score: ${visualScore}%</div>
                    <div class="memory-timestamp">${formattedDate}</div>
                </div>
                <div class="memory-content">${result.content}</div>
                <div class="memory-topic">Sujet: ${result.topic || 'Non spécifié'}</div>
            `;
            
            resultsContainer.appendChild(resultItem);
        });
        
    } catch (error) {
        console.error("Erreur lors de la recherche dans la mémoire:", error);
        document.getElementById('vector-memory-results').innerHTML = `
            <div class="error-state">
                <p>Erreur lors de la recherche</p>
                <p class="error-details">${error.message}</p>
            </div>
        `;
        showToast("Erreur lors de la recherche dans la mémoire", "error");
    }
}

/**
 * Charge et affiche le graphe symbolique
 */
async function loadSymbolicGraph() {
    try {
        const container = document.getElementById('graph-container');
        container.innerHTML = `
            <div class="loading-indicator">
                <i class="fas fa-spinner fa-spin"></i> Chargement du graphe...
            </div>
        `;
        console.log("loadSymbolicGraph from admin.js appelé");
        // Note: Cette implémentation est un placeholder
        // Une API réelle serait nécessaire pour exposer les données du graphe
        
        // Simuler un délai de chargement
        setTimeout(() => {
            // Pour une véritable implémentation, vous pourriez utiliser une bibliothèque
            // comme D3.js, Cytoscape.js ou Vis.js pour visualiser le graphe
            
            container.innerHTML = `
                <div class="graph-placeholder">
                    <p>Visualisation du graphe symbolique</p>
                    <p>Ce composant nécessite une bibliothèque de visualisation de graphes comme D3.js</p>
                    <p><small>Dans une implémentation complète, vous verriez ici les entités et relations de la mémoire symbolique</small></p>
                </div>
            `;
        }, 1500);
        
    } catch (error) {
        console.error("Erreur lors du chargement du graphe:", error);
        document.getElementById('graph-container').innerHTML = `
            <div class="error-state">
                <p>Erreur lors du chargement du graphe</p>
                <p class="error-details">${error.message}</p>
            </div>
        `;
        showToast("Erreur lors du chargement du graphe", "error");
    }
}/**
 * Script pour l'interface d'administration
 * Assistant IA Local
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialisation
    initAdminUI();
    loadSystemStatus();
    
    // Événements globaux
    document.getElementById('refresh-btn').addEventListener('click', loadSystemStatus);
    document.querySelectorAll('.admin-nav li').forEach(navItem => {
        navItem.addEventListener('click', () => {
            switchSection(navItem.dataset.section);
        });
    });
    
    // Événements par section
    setupDashboardEvents();
    setupModelsEvents();
    setupMemoryEvents();
    setupVoiceEvents();
    setupConfigEvents();
    setupLogsEvents();
    
    // Modals
    setupModals();
});

/**
 * Initialise l'interface d'administration
 */
function initAdminUI() {
    // Faire clignoter les status dots en attendant les vraies données
    const statusDots = document.querySelectorAll('.status-dot');
    statusDots.forEach(dot => {
        setInterval(() => {
            dot.style.opacity = dot.style.opacity === '0.3' ? '1' : '0.3';
        }, 800);
    });
    
    // Initialiser l'état des jauges à 0
    updateGauge('cpu-gauge', 0);
    updateGauge('memory-gauge', 0);
    updateGauge('disk-gauge', 0);
}

/**
 * Change la section active
 * @param {string} sectionId - ID de la section à afficher
 */
function switchSection(sectionId) {
    // Mettre à jour la navigation
    document.querySelectorAll('.admin-nav li').forEach(item => {
        item.classList.toggle('active', item.dataset.section === sectionId);
    });
    
    // Mettre à jour les sections
    document.querySelectorAll('.admin-section').forEach(section => {
        section.classList.toggle('active', section.id === `${sectionId}-section`);
    });
    
    // Mettre à jour le titre
    const titles = {
        'dashboard': 'Tableau de bord',
        'models': 'Modèles LLM',
        'memory': 'Mémoire',
        'voice': 'Système Vocal',
        'config': 'Configuration',
        'logs': 'Logs'
    };
    
    document.getElementById('section-title').textContent = titles[sectionId] || sectionId;
    
    // Charger les données spécifiques à la section
    switch(sectionId) {
        case 'models':
            loadModels();
            break;
        case 'memory':
            loadMemoryStats();
            break;
        case 'voice':
            loadVoiceStatus();
            break;
        case 'config':
            loadConfig();
            break;
        case 'logs':
            loadLogs();
            break;
    }
}

/**
 * Charge le statut global du système
 */
async function loadSystemStatus() {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/admin/status`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Mettre à jour les indicateurs de statut
        updateStatusCard('system-status-card', data.status, `Système ${getStatusText(data.status)}`);
        
        // Mettre à jour les statuts des composants
        if (data.components) {
            if (data.components.llm) {
                updateStatusCard('llm-status-card', data.components.llm.status, 
                    `Modèles ${getStatusText(data.components.llm.status)}`);
            }
            
            if (data.components.stt) {
                updateStatusCard('stt-status-card', data.components.stt.status, 
                    `STT ${getStatusText(data.components.stt.status)}`);
            }
            
            if (data.components.tts) {
                updateStatusCard('tts-status-card', data.components.tts.status, 
                    `TTS ${getStatusText(data.components.tts.status)}`);
            }
        }
        
        // Mettre à jour les jauges de ressources
        updateGauge('cpu-gauge', data.cpu_usage);
        updateGauge('memory-gauge', data.memory_usage.used_percent);
        updateGauge('disk-gauge', data.disk_usage.used_percent);
        
        console.log("Statut système chargé avec succès", data);
    } catch (error) {
        console.error("Erreur lors du chargement du statut système:", error);
        showToast("Erreur lors du chargement du statut système", "error");
    }
}

/**
 * Charge la liste des modèles
 */
async function loadModels() {
    try {
        const modelsList = document.getElementById('models-list');
        modelsList.innerHTML = `
            <div class="loading-indicator">
                <i class="fas fa-spinner fa-spin"></i> Chargement des modèles...
            </div>
        `;
        
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/admin/models`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const models = await response.json();
        
        // Mettre à jour la liste des modèles
        modelsList.innerHTML = '';
        
        if (models.length === 0) {
            modelsList.innerHTML = `
                <div class="empty-state">
                    <p>Aucun modèle configuré</p>
                </div>
            `;
            return;
        }
        
        models.forEach(model => {
            const modelCard = document.createElement('div');
            modelCard.className = 'model-card';
            modelCard.innerHTML = `
                <div class="model-status ${model.status}"></div>
                <div class="model-header">
                    <div class="model-name">${model.name}</div>
                    <div class="model-type">${model.type}</div>
                </div>
                <div class="model-details">
                    <div class="model-detail">
                        <span class="detail-label">ID:</span>
                        <span class="detail-value">${model.id}</span>
                    </div>
                    <div class="model-detail">
                        <span class="detail-label">Statut:</span>
                        <span class="detail-value">${getStatusText(model.status)}</span>
                    </div>
                    <div class="model-detail">
                        <span class="detail-label">Température:</span>
                        <span class="detail-value">${model.parameters.temperature || 'N/A'}</span>
                    </div>
                    <div class="model-detail">
                        <span class="detail-label">Contexte max:</span>
                        <span class="detail-value">${model.parameters.max_tokens || 'N/A'} tokens</span>
                    </div>
                </div>
                <button class="btn secondary test-model-btn" data-model-id="${model.id}">
                    <i class="fas fa-vial"></i> Tester
                </button>
            `;
            
            modelsList.appendChild(modelCard);
        });
        
        // Ajouter les événements de test sur les boutons
        modelsList.querySelectorAll('.test-model-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const modelId = btn.dataset.modelId;
                document.getElementById('test-model-select').value = modelId;
                switchSection('models');
                document.getElementById('test-prompt').focus();
            });
        });
        
        // Mettre à jour la liste déroulante des modèles pour le test
        const modelSelect = document.getElementById('test-model-select');
        modelSelect.innerHTML = '';
        models.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            option.textContent = `${model.name} (${model.id})`;
            option.disabled = model.status !== 'ok';
            modelSelect.appendChild(option);
        });
        
        console.log("Modèles chargés avec succès", models);
    } catch (error) {
        console.error("Erreur lors du chargement des modèles:", error);
        document.getElementById('models-list').innerHTML = `
            <div class="error-state">
                <p>Erreur lors du chargement des modèles</p>
                <p class="error-details">${error.message}</p>
            </div>
        `;
        showToast("Erreur lors du chargement des modèles", "error");
    }
}

/**
 * Charge les statistiques de mémoire
 */
async function loadMemoryStats() {
    try {
        // Charger les statistiques
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/admin/memory/stats`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const stats = await response.json();
        
        // Mettre à jour les statistiques
        document.getElementById('vector-memory-count').textContent = stats.vector_count;
        document.getElementById('entity-count').textContent = stats.total_entities;
        document.getElementById('relation-count').textContent = stats.total_relations;
        document.getElementById('memory-size').textContent = stats.size_kb.toFixed(2);
        
        // Afficher les sujets de mémoire
        const topicsContainer = document.getElementById('memory-topics');
        topicsContainer.innerHTML = '';
        
        if (!stats.topics || stats.topics.length === 0) {
            topicsContainer.innerHTML = `
                <div class="empty-state">
                    <p>Aucun sujet de mémoire</p>
                </div>
            `;
            return;
        }
        
        stats.topics.forEach(topic => {
            const topicBadge = document.createElement('div');
            topicBadge.className = 'topic-badge';
            topicBadge.dataset.topic = topic;
            topicBadge.innerHTML = `
                ${topic}
                <span class="count">0</span>
            `;
            
            topicBadge.addEventListener('click', () => {
                openMemoryViewer(topic);
            });
            
            topicsContainer.appendChild(topicBadge);
        });
        
        console.log("Statistiques de mémoire chargées avec succès", stats);
    } catch (error) {
        console.error("Erreur lors du chargement des statistiques de mémoire:", error);
        showToast("Erreur lors du chargement des statistiques de mémoire", "error");
    }
}

/**
 * Charge le statut des systèmes vocaux
 */
async function loadVoiceStatus() {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/admin/status`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Mettre à jour les indicateurs STT
        if (data.components && data.components.stt) {
            const sttStatus = data.components.stt;
            updateStatusIndicator('stt-indicator', sttStatus.status, getStatusText(sttStatus.status));
            
            if (sttStatus.details) {
                if (sttStatus.details.model) {
                    document.getElementById('stt-model').textContent = sttStatus.details.model.split('/').pop();
                }
                if (sttStatus.details.binary) {
                    document.getElementById('stt-path').textContent = sttStatus.details.binary;
                }
            }
        }
        
        // Mettre à jour les indicateurs TTS
        if (data.components && data.components.tts) {
            const ttsStatus = data.components.tts;
            updateStatusIndicator('tts-indicator', ttsStatus.status, getStatusText(ttsStatus.status));
            
            if (ttsStatus.details) {
                if (ttsStatus.details.model) {
                    document.getElementById('tts-voice').textContent = ttsStatus.details.model;
                }
            }
        }
        
        // Charger la configuration pour avoir plus de détails
        const configResponse = await fetch(`${CONFIG.API_BASE_URL}/api/admin/config`);
        
        if (configResponse.ok) {
            const configData = await configResponse.json();
            
            if (configData.voice) {
                document.getElementById('tts-sample-rate').textContent = 
                    `${configData.voice.tts_sample_rate || 'N/A'} Hz`;
            }
        }
        
        console.log("Statut vocal chargé avec succès");
    } catch (error) {
        console.error("Erreur lors du chargement du statut vocal:", error);
        showToast("Erreur lors du chargement du statut vocal", "error");
    }
}

/**
 * Charge la configuration du système
 */
async function loadConfig() {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/admin/config`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const config = await response.json();
        
        // Remplir les champs de configuration
        document.getElementById('data-dir').value = config.data_dir || '';
        
        // Configuration de la voix
        if (config.voice) {
            document.getElementById('stt-model-path').value = config.voice.stt_model || '';
            document.getElementById('tts-model-name').value = config.voice.tts_model || 'fr_FR-siwis-medium';
            document.getElementById('tts-sample-rate-input').value = config.voice.tts_sample_rate || 22050;
        }
        
        // Configuration de la mémoire
        if (config.memory) {
            document.getElementById('vector-dimension').value = config.memory.vector_dimension || 1536;
            document.getElementById('max-history').value = config.memory.max_history_length || 20;
            document.getElementById('memory-refresh').value = config.memory.synthetic_memory_refresh_interval || 10;
        }
        
        // Configuration des modèles (formulaire dynamique)
        if (config.models) {
            const modelsConfigForm = document.getElementById('models-config-form');
            modelsConfigForm.innerHTML = '';
            
            for (const [modelId, modelConfig] of Object.entries(config.models)) {
                const modelSection = document.createElement('div');
                modelSection.className = 'config-model-section';
                modelSection.innerHTML = `
                    <h4>${modelConfig.name} (${modelId})</h4>
                    <div class="config-item">
                        <label for="model-${modelId}-priority">Priorité:</label>
                        <input type="number" id="model-${modelId}-priority" value="${modelConfig.priority}" min="1" max="10">
                    </div>
                    <div class="config-item">
                        <label for="model-${modelId}-temperature">Température:</label>
                        <input type="number" id="model-${modelId}-temperature" value="${modelConfig.parameters.temperature || 0.7}" 
                               min="0" max="1" step="0.1">
                    </div>
                    <div class="config-item">
                        <label for="model-${modelId}-max-tokens">Tokens max:</label>
                        <input type="number" id="model-${modelId}-max-tokens" value="${modelConfig.parameters.max_tokens || 1024}" 
                               min="256" max="32768">
                    </div>
                `;
                
                models = '';
                
                modelsConfigForm.appendChild(modelSection);
            }
        }
        
        await loadSymbolicExtractionConfig();
        console.log("Configuration chargée avec succès", config);
    } catch (error) {
        console.error("Erreur lors du chargement de la configuration:", error);
        showToast("Erreur lors du chargement de la configuration", "error");
    }
}



/**
 * Charge la configuration de l'extraction symbolique
 */
async function loadSymbolicExtractionConfig() {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/memory/symbolic_extraction_config`);
        
        // Réponse de secours en cas d'erreur
        if (!response.ok) {
            console.warn(`Erreur HTTP: ${response.status}. Utilisation des valeurs par défaut.`);
            // Utiliser des valeurs par défaut
            const toggle = document.getElementById('use-chatgpt-symbolic');
            if (toggle) {
                toggle.checked = false;
            }
            
            // Afficher une note indiquant un problème avec la configuration
            const apiNote = document.getElementById('chatgpt-api-note');
            if (apiNote) {
                apiNote.style.display = 'block';
                apiNote.innerHTML = '<p><i class="fas fa-exclamation-triangle"></i> Impossible de charger la configuration. Vérifiez les logs du serveur.</p>';
            }
            return;
        }
        
        const config = await response.json();
        
        // Mettre à jour l'interface
        const toggle = document.getElementById('use-chatgpt-symbolic');
        if (toggle) {
            toggle.checked = config.use_chatgpt;
        }
        
        // Afficher une note si la clé API n'est pas configurée
        const apiNote = document.getElementById('chatgpt-api-note');
        if (apiNote) {
            apiNote.style.display = config.has_api_key ? 'none' : 'block';
        }
        
    } catch (error) {
        console.error("Erreur lors du chargement de la configuration d'extraction symbolique:", error);
        showToast("Erreur lors du chargement de la configuration. Valeurs par défaut utilisées.", "warning");
        
        // Utiliser des valeurs par défaut
        const toggle = document.getElementById('use-chatgpt-symbolic');
        if (toggle) {
            toggle.checked = false;
        }
    }
}


/**
 * Active ou désactive l'extraction symbolique via ChatGPT
 */
async function toggleChatGPTExtraction(enabled) {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/memory/toggle_chatgpt_extraction`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enable: enabled })
        });
        if (!response.ok) throw new Error(`Erreur HTTP: ${response.status}`);
        const result = await response.json();

        const toggle = document.getElementById('use-chatgpt-symbolic');
        if (result.status === 'success') {
            showToast(result.message, "success");
            if (toggle) toggle.checked = result.current_state;
        } else {
            showToast(result.message, "warning");
            if (toggle) toggle.checked = !enabled;
        }
    } catch (error) {
        console.error("Erreur lors de la modification de la configuration:", error);
        showToast("Erreur lors de la modification de la configuration", "error");
        const toggle = document.getElementById('use-chatgpt-symbolic');
        if (toggle) toggle.checked = !enabled;
    }
}
