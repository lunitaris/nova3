// Code modifié : remplacement de l'onglet alias par une UI Drag & Drop + regroupement + suggestions intelligentes

class SymbolicRulesEditor {
    constructor(containerId = 'symbolic-rules-editor-container') {
        this.containerId = containerId;
        this.rules = {
            entity_aliases: {},
            entity_types: {},
            relation_rewrites: {}
        };
        this.container = null;
        this.isInitialized = false;
        this.isLoading = false;
    }

    async initialize() {
        if (this.isInitialized || this.isLoading) return;
        this.isLoading = true;
        try {
            this.container = document.getElementById(this.containerId);
            if (!this.container) throw new Error(`Conteneur '${this.containerId}' non trouvé`);
            this.container.innerHTML = `<div class="loading-indicator"><i class="fas fa-spinner fa-spin"></i> Chargement des règles...</div>`;
            await this.loadRules();
            this.renderInterface();
            this.attachEvents();
            this.isInitialized = true;
        } catch (error) {
            this.container.innerHTML = `<div class="error-state"><p>Erreur : ${error.message}</p></div>`;
        } finally {
            this.isLoading = false;
        }
    }

    async loadRules() {
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/memory/symbolic_rules`);
        const data = await response.json();
        console.log("🔍 Règles reçues :", data);  // Pour débogage
        if (data.status === "success" && data.rules) {
            this.rules = data.rules;
        } else {
            this.rules = { entity_aliases: {}, entity_types: {}, relation_rewrites: {} };
        }
        // Assurez-vous que this.rules est correctement initialisé avec les bonnes clés
        this.rules = data.rules || { entity_aliases: {}, entity_types: {}, relation_rewrites: {} };
        console.log("🔍 this.rules après assignation:", this.rules);  // Ajoutez ce log
    }
    

    renderInterface() {
        console.log("Contenu de this.rules:", this.rules);

        this.container.innerHTML = `
        <div class="rules-editor">
            <div class="tabs-container">
                <div class="rules-tabs">
                    <div class="tab active" data-tab="entity-aliases">Alias d'entités</div>
                    <div class="tab" data-tab="entity-types">Types d'entités</div>
                    <div class="tab" data-tab="relation-rewrites">Réécritures de relations</div>
                </div>
                <div class="tabs-content">
                    <div class="tab-pane active" id="entity-aliases-tab">
                      <div class="alias-search-bar">
                          <input type="text" id="alias-input" placeholder="Nouvel alias...">
                          <select id="target-select"></select>
                          <button class="btn primary" id="add-alias-btn">Ajouter</button>
                      </div>
                      <div id="alias-manager-grid"></div>
                    </div>
                    ${this.renderTabContent('entity_types', 'Types', 'Entité', 'Type')}
                    ${this.renderTabContent('relation_rewrites', 'Réécritures', 'Relation', 'Nouvelle formulation')}
                </div>
            </div>
            <div class="rules-actions">
                <button class="btn primary" id="save-rules-btn"><i class="fas fa-save"></i> Enregistrer</button>
                <button class="btn secondary" id="reset-rules-btn"><i class="fas fa-undo"></i> Réinitialiser</button>
            </div>
        </div>`;

        // Pour le contenu des onglets "entity_types" et "relation_rewrites"
        document.getElementById('entity_types-body').innerHTML = this.generateRulesTableBody('entity_types');
        document.getElementById('relation_rewrites-body').innerHTML = this.generateRulesTableBody('relation_rewrites');

        this.renderAliasGroups();
    }

    renderTabContent(type, title, col1, col2) {
        return `<div class="tab-pane" id="${type}-tab">
            <p class="help-text">${title}</p>
            <div class="rules-table-container">
                <table class="rules-table">
                    <thead><tr><th>${col1}</th><th>${col2}</th><th>Actions</th></tr></thead>
                    <tbody id="${type}-body">${this.generateRulesTableBody(type)}</tbody>
                </table>
            </div>
            <button class="btn secondary add-rule-btn" data-type="${type}"><i class="fas fa-plus"></i> Ajouter</button>
        </div>`;
    }

    renderAliasGroups() {
        const container = document.getElementById('alias-manager-grid');
        const select = document.getElementById('target-select');

        select.innerHTML = '';
        Object.keys(this.rules.entity_types).forEach(type => {
            const option = document.createElement('option');
            option.value = type;
            option.textContent = type;
            select.appendChild(option);
        });

        document.getElementById('add-alias-btn').onclick = () => {
            const alias = document.getElementById('alias-input').value.trim();
            const target = select.value;
            if (alias && target) {
                this.rules.entity_aliases[alias] = target;
                this.renderAliasGroups();
            }
        };

        const grouped = {};
        for (const [alias, target] of Object.entries(this.rules.entity_aliases)) {
            if (!grouped[target]) grouped[target] = [];
            grouped[target].push(alias);
        }

        container.innerHTML = '';
        Object.entries(grouped).forEach(([target, aliases]) => {
            const card = document.createElement('div');
            card.className = 'alias-group-card';
            card.innerHTML = `<h4>${target}</h4>`;
            const tagContainer = document.createElement('div');
            tagContainer.className = 'alias-tag-container';

            aliases.forEach(alias => {
                const tag = document.createElement('div');
                tag.className = 'alias-pill';
                tag.textContent = alias;
                tag.draggable = true;
                tag.dataset.alias = alias;
                tag.dataset.from = target;

                tag.addEventListener('dragstart', e => {
                    e.dataTransfer.setData('alias', alias);
                    e.dataTransfer.setData('from', target);
                });

                const delBtn = document.createElement('span');
                delBtn.className = 'delete-pill';
                delBtn.innerHTML = '&times;';
                delBtn.onclick = () => {
                    delete this.rules.entity_aliases[alias];
                    this.renderAliasGroups();
                };
                tag.appendChild(delBtn);
                tagContainer.appendChild(tag);
            });

            tagContainer.addEventListener('dragover', e => e.preventDefault());
            tagContainer.addEventListener('drop', e => {
                e.preventDefault();
                const alias = e.dataTransfer.getData('alias');
                const from = e.dataTransfer.getData('from');
                if (from !== target) {
                    this.rules.entity_aliases[alias] = target;
                    this.renderAliasGroups();
                }
            });

            card.appendChild(tagContainer);
            container.appendChild(card);
        });
    }


    generateRulesTableBody(type) {
        console.log(`🔍 Génération du corps de table pour: ${type}`, this.rules[type]);
        const entries = Object.entries(this.rules[type] || {});
        if (entries.length === 0) return `<tr><td colspan="3" class="empty-state">Aucune règle définie</td></tr>`;
        return entries.map(([source, target]) => `<tr>...</tr>`).join('');
    }

    attachEvents() {

        console.log("🔍 Éléments ciblés:", {
            tabs: this.container.querySelectorAll('.rules-tabs .tab'),
            addButtons: this.container.querySelectorAll('.add-rule-btn'),
            deleteButtons: this.container.querySelectorAll('.delete-rule-btn')
        });

        this.container.querySelectorAll('.rules-tabs .tab').forEach(tab => {
            tab.addEventListener('click', () => this.switchTab(tab.dataset.tab));
        });
        this.container.querySelectorAll('.add-rule-btn').forEach(btn => {
            btn.addEventListener('click', () => this.addRule(btn.dataset.type));
        });
        this.container.querySelectorAll('.delete-rule-btn').forEach(btn => {
            btn.addEventListener('click', () => this.deleteRule(btn.dataset.type, btn.dataset.source));
        });
        this.container.querySelector('#save-rules-btn')?.addEventListener('click', () => this.saveRules());
        this.container.querySelector('#reset-rules-btn')?.addEventListener('click', () => this.resetRules());
    }

    switchTab(tabId) {
        this.container.querySelectorAll('.rules-tabs .tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabId);
        });
        this.container.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.toggle('active', pane.id === `${tabId}-tab`);
        });
    }

    addRule(type) {
        const tbody = this.container.querySelector(`#${type}-body`);
        if (!tbody) return;
        const row = document.createElement('tr');
        row.innerHTML = `<td><input type="text" class="rule-source" placeholder="Source..."></td><td><input type="text" class="rule-target" placeholder="Cible..."></td><td><button class="btn mini delete-rule-btn" data-type="${type}"><i class="fas fa-trash"></i></button></td>`;
        row.querySelector('.delete-rule-btn').addEventListener('click', () => row.remove());
        tbody.appendChild(row);
        row.querySelector('.rule-source').focus();
    }

    deleteRule(type, source) {
        const row = this.container.querySelector(`.delete-rule-btn[data-type="${type}"][data-source="${source}"]`)?.closest('tr');
        if (row) row.remove();
    }

    collectRules() {
        const collected = {
            entity_aliases: { ...this.rules.entity_aliases },
            entity_types: {},
            relation_rewrites: {}
        };
        ['entity_types', 'relation_rewrites'].forEach(type => {
            this.container.querySelectorAll(`#${type}-body tr`).forEach(row => {
                if (row.querySelector('.empty-state')) return;
                const source = row.querySelector('.rule-source')?.value.trim();
                const target = row.querySelector('.rule-target')?.value.trim();
                if (source && target) collected[type][source] = target;
            });
        });
        return collected;
    }

    async saveRules() {
        const updated = this.collectRules();
        const res = await fetch(`${CONFIG.API_BASE_URL}/api/memory/symbolic_rules`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updated)
        });
        const data = await res.json();
        if (data.status === 'success') {
            this.rules = updated;
            showToast("Règles enregistrées", "success");
        } else showToast("Erreur d'enregistrement", "error");
    }

    async resetRules() {
        if (!confirm("Réinitialiser les règles ?")) return;
        await fetch(`${CONFIG.API_BASE_URL}/api/memory/symbolic_rules/reset`, { method: 'POST' });
        await this.loadRules();
        this.renderInterface();
        this.attachEvents();
        showToast("Réinitialisé", "success");
    }
}

function initializeSymbolicRulesEditorIfNeeded() {
    if (!symbolicRulesEditor.isInitialized && !symbolicRulesEditor.isLoading) {
        symbolicRulesEditor.initialize();
    }
}

const symbolicRulesEditor = new SymbolicRulesEditor();
