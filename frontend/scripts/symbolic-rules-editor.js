// frontend/scripts/symbolic-rules-editor.js

/**
 * Gestionnaire des règles de post-traitement du graphe symbolique
 */
class SymbolicRulesEditor {
    constructor() {
        this.rules = {
            entity_aliases: {},
            entity_types: {},
            relation_rewrites: {}
        };
        this.currentTab = 'entity_aliases';
        this.initialized = false;
    }
    
    async initialize() {
        if (this.initialized) return;
        console.log("🧠 symbolicRulesEditor.initialize() appelé !");

        
        try {
            // Charger les règles depuis l'API
            const response = await fetch(`${CONFIG.API_BASE_URL}/api/memory/symbolic_rules`);
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const data = await response.json();
            this.rules = data.rules;
            
            // Construire l'interface
            this.buildInterface();
            
            // Afficher le premier onglet
            this.showTab('entity_aliases');
            
            this.initialized = true;
            console.log("Éditeur de règles symboliques initialisé avec succès");
        } catch (error) {
            console.error("Erreur lors de l'initialisation de l'éditeur de règles:", error);
            showToast("Erreur lors du chargement des règles symboliques", "error");
        }
    }
    
    buildInterface() {
        const container = document.getElementById('symbolic-rules-editor');
        if (!container) {
            console.error("Conteneur d'éditeur de règles non trouvé");
            return;
        }
        
        // Construire les onglets
        const tabsHTML = `
            <div class="rules-tabs">
                <div class="tab" data-tab="entity_aliases">Alias d'entités</div>
                <div class="tab" data-tab="entity_types">Types d'entités</div>
                <div class="tab" data-tab="relation_rewrites">Réécritures de relations</div>
            </div>
        `;
        
        // Construire les contenus des onglets
        const tabsContentHTML = `
            <div class="tab-content">
                <div class="tab-pane" id="entity_aliases-tab">
                    <p class="help-text">Les alias permettent de fusionner des entités similaires (ex: "moi" → "Maël").</p>
                    <div class="rules-table" id="entity_aliases-table"></div>
                    <button class="btn secondary add-rule-btn" data-type="entity_aliases">
                        <i class="fas fa-plus"></i> Ajouter un alias
                    </button>
                </div>
                <div class="tab-pane" id="entity_types-tab">
                    <p class="help-text">Cette table permet d'affiner le type des entités (ex: "chat" → "mode_de_communication").</p>
                    <div class="rules-table" id="entity_types-table"></div>
                    <button class="btn secondary add-rule-btn" data-type="entity_types">
                        <i class="fas fa-plus"></i> Ajouter un type
                    </button>
                </div>
                <div class="tab-pane" id="relation_rewrites-tab">
                    <p class="help-text">Ces règles permettent de réécrire les relations (ex: "est" → "est une instance de").</p>
                    <div class="rules-table" id="relation_rewrites-table"></div>
                    <button class="btn secondary add-rule-btn" data-type="relation_rewrites">
                        <i class="fas fa-plus"></i> Ajouter une réécriture
                    </button>
                </div>
            </div>
        `;
        
        // Construire les actions
        const actionsHTML = `
            <div class="rules-actions">
                <button class="btn primary" id="save-rules-btn">
                    <i class="fas fa-save"></i> Enregistrer les modifications
                </button>
                <button class="btn secondary" id="reset-rules-btn">
                    <i class="fas fa-undo"></i> Réinitialiser
                </button>
            </div>
        `;
        
        // Assembler l'interface
        container.innerHTML = tabsHTML + tabsContentHTML + actionsHTML;
        
        // Ajouter les événements
        this.setupEvents();
        
        // Remplir les tables
        this.renderRulesTables();
    }
    
    setupEvents() {
        // Événements des onglets
        document.querySelectorAll('.rules-tabs .tab').forEach(tab => {
            tab.addEventListener('click', () => {
                this.showTab(tab.dataset.tab);
            });
        });
        
        // Événement d'ajout de règle
        document.querySelectorAll('.add-rule-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.addNewRule(btn.dataset.type);
            });
        });
        
        // Événement de sauvegarde
        document.getElementById('save-rules-btn').addEventListener('click', () => {
            this.saveRules();
        });
        
        // Événement de réinitialisation
        document.getElementById('reset-rules-btn').addEventListener('click', () => {
            this.resetRules();
        });
    }
    
    showTab(tabName) {
        // Mettre à jour l'onglet actif
        document.querySelectorAll('.rules-tabs .tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });
        
        // Mettre à jour le contenu actif
        document.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.toggle('active', pane.id === `${tabName}-tab`);
        });
        
        this.currentTab = tabName;
    }
    
    renderRulesTables() {
        // Rendre chaque table de règles
        this.renderRulesTable('entity_aliases');
        this.renderRulesTable('entity_types');
        this.renderRulesTable('relation_rewrites');
    }
    
    renderRulesTable(ruleType) {
        const tableContainer = document.getElementById(`${ruleType}-table`);
        if (!tableContainer) return;
        
        const rules = this.rules[ruleType] || {};
        
        // Créer l'en-tête de la table
        let tableHTML = `
            <table class="rules-table-content">
                <thead>
                    <tr>
                        <th>Source</th>
                        <th>Cible</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        // Remplir le corps de la table
        if (Object.keys(rules).length === 0) {
            tableHTML += `
                <tr>
                    <td colspan="3" class="empty-state">Aucune règle définie</td>
                </tr>
            `;
        } else {
            for (const [source, target] of Object.entries(rules)) {
                tableHTML += `
                    <tr>
                        <td>
                            <input type="text" class="rule-source" value="${source}" data-original="${source}">
                        </td>
                        <td>
                            <input type="text" class="rule-target" value="${target}">
                        </td>
                        <td>
                            <button class="btn mini delete-rule-btn" data-type="${ruleType}" data-source="${source}">
                                <i class="fas fa-trash"></i>
                            </button>
                        </td>
                    </tr>
                `;
            }
        }
        
        // Fermer la table
        tableHTML += `
                </tbody>
            </table>
        `;
        
        // Mettre à jour le contenu
        tableContainer.innerHTML = tableHTML;
        
        // Ajouter les événements de suppression
        tableContainer.querySelectorAll('.delete-rule-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.deleteRule(btn.dataset.type, btn.dataset.source);
            });
        });
    }
    
    addNewRule(ruleType) {
        // Ajouter une nouvelle ligne vide dans la table
        const tableBody = document.querySelector(`#${ruleType}-table table tbody`);
        
        // Supprimer la ligne "aucune règle" si elle existe
        const emptyRow = tableBody.querySelector('.empty-state');
        if (emptyRow) {
            emptyRow.closest('tr').remove();
        }
        
        // Créer une nouvelle ligne
        const newRow = document.createElement('tr');
        newRow.innerHTML = `
            <td>
                <input type="text" class="rule-source" value="" placeholder="Source">
            </td>
            <td>
                <input type="text" class="rule-target" value="" placeholder="Cible">
            </td>
            <td>
                <button class="btn mini delete-rule-btn" data-type="${ruleType}">
                    <i class="fas fa-trash"></i>
                </button>
            </td>
        `;
        
        // Ajouter la ligne
        tableBody.appendChild(newRow);
        
        // Donner le focus au premier champ
        newRow.querySelector('.rule-source').focus();
        
        // Ajouter l'événement de suppression
        const deleteBtn = newRow.querySelector('.delete-rule-btn');
        deleteBtn.addEventListener('click', () => {
            newRow.remove();
        });
    }
    
    deleteRule(ruleType, source) {
        // Demander confirmation
        if (confirm(`Êtes-vous sûr de vouloir supprimer cette règle : "${source}" ?`)) {
            // Supprimer la règle
            delete this.rules[ruleType][source];
            
            // Mettre à jour l'affichage
            this.renderRulesTable(ruleType);
        }
    }
    
    collectRules() {
        // Collecter toutes les règles des tables
        const updatedRules = {
            entity_aliases: {},
            entity_types: {},
            relation_rewrites: {}
        };
        
        // Parcourir chaque type de règle
        ['entity_aliases', 'entity_types', 'relation_rewrites'].forEach(ruleType => {
            const table = document.querySelector(`#${ruleType}-table table tbody`);
            if (!table) return;
            
            // Parcourir chaque ligne
            table.querySelectorAll('tr').forEach(row => {
                const sourceInput = row.querySelector('.rule-source');
                const targetInput = row.querySelector('.rule-target');
                
                if (sourceInput && targetInput) {
                    const source = sourceInput.value.trim();
                    const target = targetInput.value.trim();
                    
                    // Ignorer les lignes vides
                    if (source && target) {
                        // Si la source a été modifiée, supprimer l'ancienne entrée
                        const originalSource = sourceInput.dataset.original;
                        if (originalSource && originalSource !== source) {
                            delete this.rules[ruleType][originalSource];
                        }
                        
                        // Ajouter la nouvelle règle
                        updatedRules[ruleType][source] = target;
                    }
                }
            });
        });
        
        return updatedRules;
    }
    
    async saveRules() {
        try {
            // Collecter les règles
            const updatedRules = this.collectRules();
            
            // Envoyer à l'API
            const response = await fetch(`${CONFIG.API_BASE_URL}/api/memory/symbolic_rules`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updatedRules)
            });
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const result = await response.json();
            
            if (result.status === 'success') {
                showToast("Règles symboliques enregistrées avec succès", "success");
                
                // Mettre à jour les règles locales
                this.rules = updatedRules;
                
                // Rafraîchir l'interface
                this.renderRulesTables();
            } else {
                throw new Error(result.message || "Échec de la sauvegarde");
            }
            
        } catch (error) {
            console.error("Erreur lors de la sauvegarde des règles:", error);
            showToast(`Erreur lors de la sauvegarde: ${error.message}`, "error");
        }
    }
    
    async resetRules() {
        try {
            // Demander confirmation
            if (!confirm("Êtes-vous sûr de vouloir réinitialiser toutes les règles aux valeurs par défaut ?")) {
                return;
            }
            
            // Appeler l'API de réinitialisation
            const response = await fetch(`${CONFIG.API_BASE_URL}/api/memory/symbolic_rules/reset`, {
                method: 'POST'
            });
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const result = await response.json();
            
            if (result.status === 'success') {
                showToast("Règles symboliques réinitialisées avec succès", "success");
                
                // Recharger les règles
                const rulesResponse = await fetch(`${CONFIG.API_BASE_URL}/api/memory/symbolic_rules`);
                if (rulesResponse.ok) {
                    const data = await rulesResponse.json();
                    this.rules = data.rules;
                    
                    // Rafraîchir l'interface
                    this.renderRulesTables();
                }
            } else {
                throw new Error(result.message || "Échec de la réinitialisation");
            }
            
        } catch (error) {
            console.error("Erreur lors de la réinitialisation des règles:", error);
            showToast(`Erreur lors de la réinitialisation: ${error.message}`, "error");
        }
    }
}

// Instance globale
const symbolicRulesEditor = new SymbolicRulesEditor();

document.addEventListener('DOMContentLoaded', function () {
    // Délai pour s’assurer que la modale est dans le DOM
    setTimeout(() => {
        const rulesTab = document.querySelector('.memory-viewer-tabs .tab[data-tab="rules"]');

        if (rulesTab) {
            console.log("🧠 Onglet 'Règles' détecté");

            rulesTab.addEventListener('click', () => {
                console.log("🧠 Onglet 'Règles' cliqué → init forcé");
                symbolicRulesEditor.initialize();
            });

            // Si déjà actif (onglet par défaut)
            if (rulesTab.classList.contains('active')) {
                console.log("🧠 Onglet 'Règles' actif au chargement → init direct");
                symbolicRulesEditor.initialize();
            }
        } else {
            console.warn("❌ Onglet 'Règles' introuvable !");
        }
    }, 500); // assez long pour que la modale soit injectée
});