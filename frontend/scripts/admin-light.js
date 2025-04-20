/**
 * Fonctions pour gérer les lumières dans l'interface admin
 * À ajouter au fichier admin.js
 */

// Configuration des événements de la section lumières
function setupLightsEvents() {
    // Charger les lumières immédiatement
    loadLights();
    document.getElementById('refresh-lights-btn').addEventListener('click', loadLights);
    
    // Événement de changement de pièce
    document.getElementById('filter-room').addEventListener('change', (e) => {
        filterLightsByRoom(e.target.value);
    });
    
    // Gestion des scènes
    document.querySelectorAll('.scene-option').forEach(option => {
        option.addEventListener('click', function() {
            // Désélectionner toutes les options
            document.querySelectorAll('.scene-option').forEach(opt => {
                opt.classList.remove('selected');
            });
            
            // Sélectionner celle-ci
            this.classList.add('selected');
        });
    });
    
    document.getElementById('apply-scene-btn').addEventListener('click', applyScene);
}

/**
 * Charge les lumières depuis l'API
 */
async function loadLights() {
    try {
        // Réinitialiser les conteneurs
        const lightsContainer = document.getElementById('lights-container');
        const roomsContainer = document.getElementById('rooms-container');
        
        lightsContainer.innerHTML = `
            <div class="loading-indicator">
                <i class="fas fa-spinner fa-spin"></i> Chargement des lumières...
            </div>
        `;
        
        roomsContainer.innerHTML = '';
        

        // Charger les pièces ET les lumières en un seul appel
        const fullResponse = await fetch(`${CONFIG.API_BASE_URL}/api/admin/lights/full`);

        if (!fullResponse.ok) {
            throw new Error(`Erreur HTTP: ${fullResponse.status}`);
        }

        const { rooms, lights } = await fullResponse.json();

        // Stocker les données des pièces pour une utilisation ultérieure
        window.lastHueRooms = rooms;

        
        // Mettre à jour le filtre de pièces
        const roomFilter = document.getElementById('filter-room');
        roomFilter.innerHTML = '<option value="all">Toutes les pièces</option>';
        
        if (rooms.length > 0) {
            // Créer les cartes de pièces
            roomsContainer.innerHTML = '<div class="room-card active" data-room="all"><div class="room-icon"><i class="fas fa-home"></i></div><div class="room-name">Toutes les pièces</div></div>';
            
            rooms.forEach(room => {
                // Ajouter au filtre
                const option = document.createElement('option');
                option.value = room.id;
                option.textContent = room.name;
                roomFilter.appendChild(option);
                
                // Créer la carte de pièce
                const roomCard = document.createElement('div');
                roomCard.className = 'room-card';
                roomCard.dataset.room = room.id;
                roomCard.dataset.name = room.name; // Stockez le nom explicitement
                
                roomCard.innerHTML = `
                    <div class="room-icon"><i class="fas fa-door-open"></i></div>
                    <div class="room-name">${room.name}</div>
                    <div class="room-actions">
                        <button class="btn mini toggle-room-btn" data-room="${room.id}" title="Allumer/éteindre toutes les lumières">
                            <i class="fas fa-power-off"></i>
                        </button>
                        <button class="btn mini scene-room-btn" data-room="${room.id}" title="Appliquer une scène">
                            <i class="fas fa-images"></i>
                        </button>
                    </div>
                `;
                
                roomsContainer.appendChild(roomCard);
                
                // Événements de la carte
                roomCard.addEventListener('click', (e) => {
                    if (!e.target.closest('button')) {
                        // Désactiver toutes les cartes
                        document.querySelectorAll('.room-card').forEach(card => {
                            card.classList.remove('active');
                        });
                        
                        // Activer celle-ci
                        roomCard.classList.add('active');
                        
                        // Filtrer les lumières
                        filterLightsByRoom(room.id);
                        
                        // Mettre à jour le sélecteur
                        roomFilter.value = room.id;
                    }
                });
            });
            
            // Ajouter les événements aux boutons de pièces
            document.querySelectorAll('.toggle-room-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    toggleRoom(btn.dataset.room);
                });
            });
            
            document.querySelectorAll('.scene-room-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    openSceneModal('room', btn.dataset.room);
                });
            });
        }
        
    
        // Vérifier s'il y a des lumières
        if (lights.length === 0) {
            lightsContainer.innerHTML = '';
            document.getElementById('no-lights-message').style.display = 'block';
            return;
        }

        // Masquer le message "pas de lumières"
        document.getElementById('no-lights-message').style.display = 'none';
        
        // Générer les cartes de lumières
        lightsContainer.innerHTML = '';
        
        lights.forEach(light => {
            const lightCard = createLightCard(light);
            lightsContainer.appendChild(lightCard);
        });
        
        console.log("Lumières chargées avec succès", lights);
    } catch (error) {
        console.error("Erreur lors du chargement des lumières:", error);
        document.getElementById('lights-container').innerHTML = `
            <div class="error-state">
                <p>Erreur lors du chargement des lumières</p>
                <p class="error-details">${error.message}</p>
            </div>
        `;
        showToast("Erreur lors du chargement des lumières", "error");
    }}

/**
 * Crée une carte pour une lumière
 * @param {Object} light - Données de la lumière
 * @returns {HTMLElement} Élément de carte de lumière
 */
function createLightCard(light) {
    const lightCard = document.createElement('div');
    lightCard.className = `light-card ${light.state.on ? 'on' : 'off'}`;
    lightCard.dataset.id = light.id;
    
    // Récupérer les informations de couleur pour l'affichage
    const colorPreview = getColorPreview(light);
    
    // Créer le HTML de la carte
    lightCard.innerHTML = `
        <div class="light-header">
            <div class="light-info">
                <div class="light-name">${light.name}</div>
                <div class="light-room">${light.room || 'Non assignée'}</div>
            </div>
            <div class="light-toggle">
                <div class="toggle-slider"></div>
            </div>
        </div>
        <div class="light-controls">
            ${light.supports_brightness ? `
                <div class="control-row">
                    <div class="control-label">Luminosité</div>
                    <div class="control-input">
                        <input type="range" class="brightness-slider" min="0" max="254" value="${light.state.brightness || 0}" 
                               ${!light.state.on ? 'disabled' : ''}>
                    </div>
                </div>
            ` : ''}
            ${light.supports_color ? `
                <div class="control-row">
                    <div class="control-label">Couleur</div>
                    <div class="control-input">
                        <div class="color-dropdown">
                            <div class="selected-color">
                                <span class="color-preview" style="background-color: ${colorPreview};"></span>
                                <span class="color-name">Changer</span>
                            </div>
                            <div class="color-options">
                                <div class="color-option color-red" data-color="red" title="Rouge"></div>
                                <div class="color-option color-green" data-color="green" title="Vert"></div>
                                <div class="color-option color-blue" data-color="blue" title="Bleu"></div>
                                <div class="color-option color-yellow" data-color="yellow" title="Jaune"></div>
                                <div class="color-option color-purple" data-color="purple" title="Violet"></div>
                                <div class="color-option color-pink" data-color="pink" title="Rose"></div>
                                <div class="color-option color-white" data-color="white" title="Blanc"></div>
                                <div class="color-option color-orange" data-color="orange" title="Orange"></div>
                                <div class="color-option color-cyan" data-color="cyan" title="Cyan"></div>
                            </div>
                        </div>
                    </div>
                </div>
            ` : ''}
        </div>
        <div class="light-actions">
            <button class="btn mini scene-light-btn" title="Appliquer une scène">
                <i class="fas fa-images"></i> Scène
            </button>
        </div>
    `;
    
    // Ajouter les événements
    
    // Événement d'activation/désactivation
    const toggleSlider = lightCard.querySelector('.toggle-slider');
    toggleSlider.addEventListener('click', () => {
        toggleLight(light.id);
    });
    
    // Événement de luminosité
    const brightnessSlider = lightCard.querySelector('.brightness-slider');
    if (brightnessSlider) {
        brightnessSlider.addEventListener('input', (e) => {
            updateLightBrightness(light.id, parseInt(e.target.value));
        });
    }
    
    // Événements des couleurs
    const colorOptions = lightCard.querySelectorAll('.color-option');
    colorOptions.forEach(option => {
        option.addEventListener('click', (e) => {
            const color = option.dataset.color;
            updateLightColor(light.id, color);
            
            // Mettre à jour le preview
            const preview = lightCard.querySelector('.color-preview');
            if (preview) {
                preview.style.backgroundColor = getColorHex(color);
            }
        });
    });
    
    // Événement de scène
    const sceneBtn = lightCard.querySelector('.scene-light-btn');
    sceneBtn.addEventListener('click', () => {
        openSceneModal('light', light.id);
    });
    
    return lightCard;
}

/**
 * Obtient la couleur d'aperçu pour une lumière
 * @param {Object} light - Données de la lumière
 * @returns {string} Couleur CSS
 */
function getColorPreview(light) {
    // Si la lumière a des coordonnées xy, convertir en RGB
    if (light.state.xy && Array.isArray(light.state.xy) && light.state.xy.length === 2) {
        return xyToRgb(light.state.xy[0], light.state.xy[1], light.state.brightness || 254);
    }
    
    // Sinon, renvoyer une couleur blanche ou jaune selon la luminosité
    return light.state.on ? '#ffee99' : '#ffffff';
}

/**
 * Convertit les coordonnées xy en RGB
 * Basé sur la documentation Philips Hue
 */
function xyToRgb(x, y, bri = 254) {
    // Valeurs par défaut basées sur approximation
    if (x === undefined || y === undefined) {
        return '#ffffff';
    }
    
    // Normaliser la luminosité
    const brightness = bri / 254;
    
    // Cette fonction est une approximation simplifiée
    // Pour une conversion précise, il faudrait implémenter l'algorithme complet
    
    // Approximation basée sur des valeurs courantes
    if (x > 0.6) {
        // Rouge
        return `rgb(255, ${Math.round(100 * brightness)}, ${Math.round(50 * brightness)})`;
    } else if (x < 0.3 && y < 0.3) {
        // Bleu
        return `rgb(${Math.round(50 * brightness)}, ${Math.round(100 * brightness)}, 255)`;
    } else if (y > 0.5) {
        // Vert
        return `rgb(${Math.round(50 * brightness)}, 255, ${Math.round(50 * brightness)})`;
    } else if (x > 0.4 && y > 0.4) {
        // Jaune
        return `rgb(255, 255, ${Math.round(50 * brightness)})`;
    } else {
        // Blanc (luminosité variable)
        const val = Math.round(255 * brightness);
        return `rgb(${val}, ${val}, ${val})`;
    }
}

/**
 * Obtient le code hexadécimal pour une couleur nommée
 * @param {string} colorName - Nom de la couleur
 * @returns {string} Code hexadécimal
 */
function getColorHex(colorName) {
    const colors = {
        'red': '#ff5f5f',
        'green': '#5fff7f',
        'blue': '#5f7fff',
        'yellow': '#ffff5f',
        'purple': '#b05fff',
        'pink': '#ff5fb0',
        'white': '#ffffff',
        'orange': '#ffa05f',
        'cyan': '#5fffff'
    };
    
    return colors[colorName] || '#ffffff';
}

/**
 * Active ou désactive une lumière
 * @param {string} lightId - ID de la lumière
 */
async function toggleLight(lightId) {
    try {
        const lightCard = document.querySelector(`.light-card[data-id="${lightId}"]`);
        const isCurrentlyOn = lightCard.classList.contains('on');
        
        // Optimistic UI update
        lightCard.classList.toggle('on');
        lightCard.classList.toggle('off');
        
        // Activer/désactiver le slider de luminosité
        const brightnessSlider = lightCard.querySelector('.brightness-slider');
        if (brightnessSlider) {
            brightnessSlider.disabled = isCurrentlyOn;
        }
        
        // Appel à l'API
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/admin/lights/${lightId}/control`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action: isCurrentlyOn ? 'off' : 'on',
                parameters: {}
            })
        });
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.message || "Échec de l'opération");
        }
        
        showToast(result.message, "success");
    } catch (error) {
        console.error(`Erreur lors du basculement de la lumière ${lightId}:`, error);
        
        // Rollback en cas d'erreur
        const lightCard = document.querySelector(`.light-card[data-id="${lightId}"]`);
        if (lightCard) {
            lightCard.classList.toggle('on');
            lightCard.classList.toggle('off');
            
            const brightnessSlider = lightCard.querySelector('.brightness-slider');
            if (brightnessSlider) {
                brightnessSlider.disabled = !brightnessSlider.disabled;
            }
        }
        
        showToast(`Erreur: ${error.message}`, "error");
    }
}

/**
 * Met à jour la luminosité d'une lumière
 * @param {string} lightId - ID de la lumière
 * @param {number} brightness - Valeur de luminosité (0-254)
 */
async function updateLightBrightness(lightId, brightness) {
    try {
        // Optimistic UI update
        // (pas d'update visuel immédiat pour le slider)
        
        // Appel à l'API avec debounce
        if (window.brightnessTimeout) {
            clearTimeout(window.brightnessTimeout);
        }
        
        window.brightnessTimeout = setTimeout(async () => {
            const response = await fetch(`${CONFIG.API_BASE_URL}/api/admin/lights/${lightId}/control`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    action: 'brightness',
                    parameters: {
                        value: brightness
                    }
                })
            });
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const result = await response.json();
            
            if (!result.success) {
                throw new Error(result.message || "Échec de l'opération");
            }
            
            // Message de succès uniquement à la fin du debounce
            showToast(result.message, "success");
        }, 300);
    } catch (error) {
        console.error(`Erreur lors de la mise à jour de la luminosité de ${lightId}:`, error);
        showToast(`Erreur: ${error.message}`, "error");
    }
}

/**
 * Met à jour la couleur d'une lumière
 * @param {string} lightId - ID de la lumière
 * @param {string} color - Nom de la couleur
 */
async function updateLightColor(lightId, color) {
    try {
        // Appel à l'API
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/admin/lights/${lightId}/control`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action: 'color',
                parameters: {
                    color: color
                }
            })
        });
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.message || "Échec de l'opération");
        }
        
        showToast(result.message, "success");
    } catch (error) {
        console.error(`Erreur lors de la mise à jour de la couleur de ${lightId}:`, error);
        showToast(`Erreur: ${error.message}`, "error");
    }
}

/**
 * Filtre les lumières par pièce
 * @param {string} roomId - ID de la pièce, ou "all" pour toutes
 */
function filterLightsByRoom(roomId) {
    const lightCards = document.querySelectorAll('.light-card');
    
    if (roomId === 'all') {
        // Afficher toutes les lumières
        lightCards.forEach(card => {
            card.style.display = 'flex';
        });
        return;
    }
    
    // Récupérer le nom de la pièce à partir de son ID
    let roomName = roomId;
    const roomCard = document.querySelector(`.room-card[data-room="${roomId}"]`);
    if (roomCard) {
        const roomNameElement = roomCard.querySelector('.room-name');
        if (roomNameElement) {
            roomName = roomNameElement.textContent.trim();
        }
    }
    
    //DEBUG console.log(`Filtrage des lumières pour la pièce: ${roomId} (nom: ${roomName})`);
    

    // Récupérer les IDs des lumières qui appartiennent à cette pièce
    // Ces informations devraient être disponibles dans la réponse de l'API des pièces
    // Mais comme elles ne sont pas correctement associées, nous devons les trouver
    
    // Vérifier si c'est une pièce Hue
    const rooms = window.lastHueRooms || [];
    const hueRoom = rooms.find(r => r.id == roomId);
    
    if (hueRoom && hueRoom.lights && hueRoom.lights.length > 0) {
        //DEBUG console.log(`Pièce Hue trouvée avec ${hueRoom.lights.length} lumières`);
        // Utiliser les IDs de lumières directement depuis la pièce Hue
        const roomLightIds = hueRoom.lights.map(id => id.toString());
        
        // Afficher uniquement les lumières de cette pièce
        lightCards.forEach(card => {
            const lightId = card.dataset.id;
            card.style.display = roomLightIds.includes(lightId) ? 'flex' : 'none';
        });
        return;
    }
    

    // Filtrer les lumières par pièce
    let matchFound = false;
    lightCards.forEach(card => {
        const lightElement = card.querySelector('.light-room');
        const lightRoom = lightElement ? lightElement.textContent.trim() : '';
        
        // Journaliser chaque lumière pour débogage
        //DEBUG: console.log(`Lumière: ${card.dataset.id}, pièce: "${lightRoom}"`);
        
        // Vérifier la correspondance avec plus de souplesse
        const isMatch = 
            lightRoom.toLowerCase() === roomName.toLowerCase() ||
            roomId.includes(lightRoom.toLowerCase()) ||
            lightRoom.toLowerCase().includes(roomName.toLowerCase()) ||
            (roomId.startsWith('simulated_') && lightRoom.toLowerCase() === roomId.replace('simulated_', '').toLowerCase());
        
        card.style.display = isMatch ? 'flex' : 'none';
        if (isMatch) matchFound = true;
    });
    
    // Si aucune correspondance n'est trouvée, afficher toutes les lumières
    if (!matchFound) {
        console.warn(`Aucune lumière trouvée pour la pièce ${roomName}, affichage de toutes les lumières`);
        lightCards.forEach(card => {
            card.style.display = 'flex';
        });
    }
}

/**
 * Active/désactive toutes les lumières d'une pièce
 * @param {string} roomId - ID de la pièce
 */
async function toggleRoom(roomId) {
    try {
        // Déterminer l'état actuel (on ou off)
        const lightsInRoom = Array.from(document.querySelectorAll('.light-card'))
            .filter(card => {
                const roomElement = card.querySelector('.light-room');
                const cardRoom = roomElement ? roomElement.textContent.trim() : '';
                return cardRoom.toLowerCase() === roomId.toLowerCase() ||
                       cardRoom.includes(roomId) ||
                       roomId.includes(cardRoom);
            });
        
        // Déterminer si on doit allumer ou éteindre
        const anyOn = lightsInRoom.some(card => card.classList.contains('on'));
        const action = anyOn ? 'off' : 'on';
        
        // Optimistic UI update
        lightsInRoom.forEach(card => {
            if (action === 'on') {
                card.classList.add('on');
                card.classList.remove('off');
                
                const brightnessSlider = card.querySelector('.brightness-slider');
                if (brightnessSlider) {
                    brightnessSlider.disabled = false;
                }
            } else {
                card.classList.remove('on');
                card.classList.add('off');
                
                const brightnessSlider = card.querySelector('.brightness-slider');
                if (brightnessSlider) {
                    brightnessSlider.disabled = true;
                }
            }
        });
        
        // Appel à l'API
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/admin/lights/rooms/${roomId}/control`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action: action,
                parameters: {}
            })
        });
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.message || "Échec de l'opération");
        }
        
        showToast(result.message, "success");
    } catch (error) {
        console.error(`Erreur lors de la bascule de la pièce ${roomId}:`, error);
        showToast(`Erreur: ${error.message}`, "error");
        
        // Recharger les lumières en cas d'erreur pour rétablir l'état correct
        loadLights();
    }
}

/**
 * Ouvre le modal de scène
 * @param {string} targetType - Type de cible ('light' ou 'room')
 * @param {string} targetId - ID de la cible
 */
function openSceneModal(targetType, targetId) {
    // Stocker les informations de la cible
    document.getElementById('scene-target-id').value = targetId;
    document.getElementById('scene-target-type').value = targetType;
    
    // Réinitialiser la sélection
    document.querySelectorAll('.scene-option').forEach(opt => {
        opt.classList.remove('selected');
    });
    
    // Sélectionner la première scène par défaut
    document.querySelector('.scene-option').classList.add('selected');
    
    // Afficher le modal
    document.getElementById('scenes-modal').classList.add('active');
}

/**
 * Applique une scène
 */
async function applyScene() {
    try {
        // Récupérer les informations
        const targetType = document.getElementById('scene-target-type').value;
        const targetId = document.getElementById('scene-target-id').value;
        const selectedScene = document.querySelector('.scene-option.selected');
        
        if (!selectedScene) {
            showToast("Veuillez sélectionner une scène", "warning");
            return;
        }
        
        const sceneName = selectedScene.dataset.scene;
        
        // Fermer le modal
        document.getElementById('scenes-modal').classList.remove('active');
        
        // URL de l'API selon le type de cible
        const url = targetType === 'room' 
            ? `${CONFIG.API_BASE_URL}/api/admin/lights/rooms/${targetId}/control`
            : `${CONFIG.API_BASE_URL}/api/admin/lights/${targetId}/control`;
        
        // Appel à l'API
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action: 'scene',
                parameters: {
                    scene: sceneName
                }
            })
        });
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.message || "Échec de l'opération");
        }
        
        showToast(result.message, "success");
        
        // Recharger les lumières pour mettre à jour l'interface
        setTimeout(loadLights, 500);
    } catch (error) {
        console.error("Erreur lors de l'application de la scène:", error);
        showToast(`Erreur: ${error.message}`, "error");
    }
}




/////////////////////////// LOGS AND DEBUG //////////////



// Fonction pour récupérer et afficher les erreurs d'API
function handleApiError(error, endpoint) {
    console.error(`Erreur lors de l'appel à ${endpoint}:`, error);
    
    // Si l'erreur contient une réponse, tenter de lire le corps
    if (error.response) {
        error.response.text().then(text => {
            try {
                // Tenter de parser en JSON
                const errorData = JSON.parse(text);
                console.error("Détails de l'erreur:", errorData);
                showToast(`Erreur: ${errorData.detail || errorData.message || "Erreur inconnue"}`, "error");
            } catch (e) {
                // Afficher le texte brut si ce n'est pas du JSON
                console.error("Réponse d'erreur:", text);
                showToast(`Erreur: ${text || error.message}`, "error");
            }
        }).catch(e => {
            // Si impossible de lire la réponse
            console.error("Impossible de lire les détails de l'erreur:", e);
            showToast(`Erreur: ${error.message || "Erreur inconnue"}`, "error");
        });
    } else {
        // Pas de réponse disponible
        showToast(`Erreur: ${error.message || "Erreur de connexion"}`, "error");
    }
}





function debugRooms() {
    console.log("=== DÉBOGAGE DES PIÈCES ET LUMIÈRES ===");
    
    // Récupérer toutes les pièces
    const rooms = document.querySelectorAll('.room-card');
    console.log(`Nombre de pièces: ${rooms.length}`);
    
    rooms.forEach(room => {
        const roomId = room.dataset.room;
        const roomName = room.querySelector('.room-name').textContent;
        console.log(`Pièce: "${roomName}" (ID: ${roomId})`);
    });
    
    // Récupérer toutes les lumières
    const lights = document.querySelectorAll('.light-card');
    console.log(`Nombre de lumières: ${lights.length}`);
    
    lights.forEach(light => {
        const lightId = light.dataset.id;
        const lightName = light.querySelector('.light-name').textContent;
        const lightRoom = light.querySelector('.light-room').textContent;
        console.log(`Lumière: "${lightName}" (ID: ${lightId}), Pièce: "${lightRoom}"`);
    });
    
    console.log("=====================================");
}