
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
