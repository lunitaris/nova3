/**
 * Script pour la visualisation du graphe de mémoire symbolique
 * frontend/scripts/memory-graph.js
 */

// Variables globales
let graphData = null;
let graphSimulation = null;

// Ajouter un bouton pour visualiser le graphe symbolique
function addMemoryGraphButton() {
    // Vérifier si le bouton existe déjà
    if (document.getElementById('view-memory-graph-btn')) {
        return;
    }
    
    // Créer le bouton et l'ajouter aux actions de l'en-tête
    const headerActions = document.querySelector('.header-actions');
    
    if (headerActions) {
        const graphButton = document.createElement('button');
        graphButton.id = 'view-memory-graph-btn';
        graphButton.className = 'btn secondary';
        graphButton.innerHTML = '<i class="fas fa-project-diagram"></i> Graph Symbolique de la conv';
        graphButton.addEventListener('click', showMemoryGraph);
        
        // Insérer avant le bouton Effacer
        const clearButton = document.getElementById('clear-conversation-btn');
        if (clearButton) {
            headerActions.insertBefore(graphButton, clearButton);
        } else {
            headerActions.appendChild(graphButton);
        }
    }
}

// Créer et afficher le modal du graphe de mémoire
function showMemoryGraph() {
    // Créer le modal s'il n'existe pas déjà
    let graphModal = document.getElementById('memory-graph-modal');
    
    if (!graphModal) {
        graphModal = document.createElement('div');
        graphModal.id = 'memory-graph-modal';
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
                    <div class="graph-container" id="conversation-graph-container">
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
        
        document.getElementById('refresh-graph-btn').addEventListener('click', loadConversationGraph);
        document.getElementById('include-deleted-graph').addEventListener('change', loadConversationGraph);
        
        // Ajouter les styles si nécessaire
        addMemoryGraphStyles();
    }
    
    // Afficher le modal
    graphModal.classList.add('active');
    
    // Charger le graphe
    loadConversationGraph();
}

// Charge le graphe de la conversation actuelle
async function loadConversationGraph() {
    try {
        const graphContainer = document.getElementById('conversation-graph-container');
        const includeDeleted = document.getElementById('include-deleted-graph').checked;
        
        // Afficher l'indicateur de chargement
        graphContainer.innerHTML = `
            <div class="loading-indicator">
                <i class="fas fa-spinner fa-spin"></i> Chargement du graphe...
            </div>
        `;
        
        // Récupérer l'ID de la conversation active
        const conversationId = window.chatManager?.currentConversationId;
        
        if (!conversationId) {
            graphContainer.innerHTML = `
                <div class="empty-state">
                    <p>Aucune conversation active.</p>
                </div>
            `;
            return;
        }
        
        // Récupérer les données du graphe depuis l'API
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/chat/conversation/${conversationId}/graph?include_deleted=${includeDeleted}`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        graphData = await response.json();
        
        // Vérifier si le graphe est vide
        if (!graphData.nodes || graphData.nodes.length === 0) {
            graphContainer.innerHTML = `
                <div class="empty-state">
                    <p>Aucune mémoire symbolique disponible pour cette conversation.</p>
                    <p>Continuez à discuter pour enrichir la mémoire de l'assistant.</p>
                </div>
            `;
            return;
        }
        
        // Vider le container pour la visualisation
        graphContainer.innerHTML = '';
        
        // Créer la visualisation avec D3.js
        createForceDirectedGraph(graphData, graphContainer);
        
    } catch (error) {
        console.error("Erreur lors du chargement du graphe:", error);
        const graphContainer = document.getElementById('conversation-graph-container');
        
        graphContainer.innerHTML = `
            <div class="error-state">
                <p>Erreur lors du chargement du graphe</p>
                <p class="error-details">${error.message}</p>
            </div>
        `;
    }
}

// Crée le graphe avec D3.js
function createForceDirectedGraph(data, container) {
    // Vider d'abord le conteneur pour éviter les duplications
    container.innerHTML = '';
    // Importer D3.js depuis CDN si nécessaire
    if (!window.d3) {
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js';
        script.onload = () => {
            // Une fois D3 chargé, initialiser le graphe
            initGraph(data, container);
        };
        document.head.appendChild(script);
    } else {
        // D3 est déjà chargé, initialiser directement
        initGraph(data, container);
    }
}

// Initialise le graphe D3.js
function initGraph(data, container) {
    const width = container.clientWidth;
    const height = 500;
    
    // Couleurs pour les groupes d'entités
    const color = d3.scaleOrdinal(d3.schemeCategory10);
    
    // Créer le SVG
    const svg = d3.select(container)
        .append("svg")
        .attr("viewBox", [0, 0, width, height])
        .attr("width", "100%")
        .attr("height", height)
        .attr("class", "memory-graph");
        
    // Ajouter un groupe pour le zoom
    const g = svg.append("g");
    
    // Ajouter le zoom
    svg.call(d3.zoom()
        .extent([[0, 0], [width, height]])
        .scaleExtent([0.1, 8])
        .on("zoom", (event) => {
            g.attr("transform", event.transform);
        }));
    
    // Créer les flèches pour les liens dirigés
    svg.append("defs").selectAll("marker")
        .data(["arrow"])
        .enter().append("marker")
        .attr("id", d => d)
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 15)
        .attr("refY", 0)
        .attr("markerWidth", 6)
        .attr("markerHeight", 6)
        .attr("orient", "auto")
        .append("path")
        .attr("fill", "#999")
        .attr("d", "M0,-5L10,0L0,5");
    
    // Créer la simulation de force
    graphSimulation = d3.forceSimulation(data.nodes)
        .force("link", d3.forceLink(data.links).id(d => d.id).distance(100))
        .force("charge", d3.forceManyBody().strength(-300))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("x", d3.forceX(width / 2).strength(0.1))
        .force("y", d3.forceY(height / 2).strength(0.1));
    
    // Créer les liens
    const link = g.append("g")
        .attr("stroke", "#999")
        .attr("stroke-opacity", 0.6)
        .selectAll("line")
        .data(data.links)
        .enter().append("line")
        .attr("stroke-width", d => Math.max(1, d.value))
        .attr("marker-end", "url(#arrow)")
        .on("mouseover", function(event, d) {
            // Afficher le libellé du lien au survol
            tooltip.transition()
                .duration(200)
                .style("opacity", .9);
            tooltip.html(`Relation: ${d.label}<br>Confiance: ${(d.confidence * 100).toFixed(0)}%`)
                .style("left", (event.pageX + 5) + "px")
                .style("top", (event.pageY - 28) + "px");
        })
        .on("mouseout", function() {
            tooltip.transition()
                .duration(500)
                .style("opacity", 0);
        });
    
    // Créer les nœuds
    const node = g.append("g")
        .attr("stroke", "#fff")
        .attr("stroke-width", 1.5)
        .selectAll("circle")
        .data(data.nodes)
        .enter().append("circle")
        .attr("r", 8)
        .attr("fill", d => color(d.group))
        .call(drag(graphSimulation))
        .on("mouseover", function(event, d) {
            // Afficher les détails du nœud au survol
            tooltip.transition()
                .duration(200)
                .style("opacity", .9);
            tooltip.html(`<strong>${d.name}</strong><br>Type: ${d.type}<br>Confiance: ${(d.confidence * 100).toFixed(0)}%`)
                .style("left", (event.pageX + 5) + "px")
                .style("top", (event.pageY - 28) + "px");
        })
        .on("mouseout", function() {
            tooltip.transition()
                .duration(500)
                .style("opacity", 0);
        })
        .on("click", function(event, d) {
            // Sélectionner/désélectionner un nœud
            const isSelected = d3.select(this).classed("selected");
            
            // Réinitialiser tous les nœuds et liens
            node.classed("selected", false)
                .classed("related", false);
            link.classed("highlighted", false)
                .classed("faded", false);
            
            if (!isSelected) {
                // Sélectionner ce nœud
                d3.select(this).classed("selected", true);
                
                // Mettre en évidence les liens connectés
                link.classed("highlighted", l => l.source.id === d.id || l.target.id === d.id)
                    .classed("faded", l => l.source.id !== d.id && l.target.id !== d.id);
                
                // Mettre en évidence les nœuds connectés
                node.classed("related", n => {
                    if (n.id === d.id) return false;
                    return data.links.some(l => 
                        (l.source.id === d.id && l.target.id === n.id) || 
                        (l.source.id === n.id && l.target.id === d.id)
                    );
                });
            }
        });
    
    // Ajouter les étiquettes des nœuds
    const label = g.append("g")
        .attr("class", "labels")
        .selectAll("text")
        .data(data.nodes)
        .enter().append("text")
        .attr("font-size", 10)
        .attr("dx", 12)
        .attr("dy", ".35em")
        .text(d => d.name);
    
    // Ajouter un infobulle interactive
    const tooltip = d3.select("body").append("div")
        .attr("class", "graph-tooltip")
        .style("opacity", 0);
    
    // Ajouter une légende
    const legend = svg.append("g")
        .attr("class", "legend")
        .attr("transform", "translate(20, 20)");
        
    const legendItems = [
        { label: "Utilisateur", group: 0 },
        { label: "Personne", group: 1 },
        { label: "Lieu", group: 2 },
        { label: "Date", group: 3 },
        { label: "Concept", group: 4 },
        { label: "Préférence", group: 5 }
    ];
    
    const legendEntries = legend.selectAll(".legend-entry")
        .data(legendItems)
        .enter().append("g")
        .attr("class", "legend-entry")
        .attr("transform", (d, i) => `translate(0, ${i * 20})`);
        
    legendEntries.append("circle")
        .attr("r", 6)
        .attr("fill", d => color(d.group));
        
    legendEntries.append("text")
        .attr("x", 15)
        .attr("y", 5)
        .text(d => d.label);
    
    // Mise à jour de la simulation à chaque tick
    graphSimulation.on("tick", () => {
        link
            .attr("x1", d => d.source.x)
            .attr("y1", d => d.source.y)
            .attr("x2", d => d.target.x)
            .attr("y2", d => d.target.y);
            
        node
            .attr("cx", d => d.x = Math.max(10, Math.min(width - 10, d.x)))
            .attr("cy", d => d.y = Math.max(10, Math.min(height - 10, d.y)));
            
        label
            .attr("x", d => d.x)
            .attr("y", d => d.y);
    });
    
    // Fonction pour le glisser-déposer des nœuds
    function drag(simulation) {
        function dragstarted(event) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            event.subject.fx = event.subject.x;
            event.subject.fy = event.subject.y;
        }
        
        function dragged(event) {
            event.subject.fx = event.x;
            event.subject.fy = event.y;
        }
        
        function dragended(event) {
            if (!event.active) simulation.alphaTarget(0);
            event.subject.fx = null;
            event.subject.fy = null;
        }
        
        return d3.drag()
            .on("start", dragstarted)
            .on("drag", dragged)
            .on("end", dragended);
    }
}

// Ajouter les styles CSS pour le graphe
function addMemoryGraphStyles() {
    if (document.getElementById('memory-graph-styles')) return;
    
    const style = document.createElement('style');
    style.id = 'memory-graph-styles';
    style.textContent = `
        .graph-container {
            width: 100%;
            height: 500px;
            border: 1px solid #ddd;
            border-radius: 8px;
            overflow: hidden;
            position: relative;
        }
        
        .memory-graph {
            background-color: #f9f9f9;
            border-radius: 8px;
        }
        
        .graph-tooltip {
            position: absolute;
            padding: 8px;
            background: rgba(0, 0, 0, 0.8);
            color: #fff;
            border-radius: 4px;
            pointer-events: none;
            font-size: 12px;
            z-index: 1000;
        }
        
        .memory-graph circle {
            cursor: pointer;
            transition: r 0.2s;
        }
        
        .memory-graph circle:hover {
            r: 10;
        }
        
        .memory-graph circle.selected {
            stroke: #ff5722;
            stroke-width: 3px;
            r: 12;
        }
        
        .memory-graph circle.related {
            stroke: #ffc107;
            stroke-width: 2px;
            r: 10;
        }
        
        .memory-graph line {
            transition: stroke-opacity 0.3s, stroke-width 0.3s;
        }
        
        .memory-graph line.highlighted {
            stroke: #ff5722;
            stroke-opacity: 1;
            stroke-width: 3;
        }
        
        .memory-graph line.faded {
            stroke-opacity: 0.1;
        }
        
        .legend {
            background-color: rgba(255, 255, 255, 0.8);
            padding: 10px;
            border-radius: 4px;
        }
        
        .legend-entry text {
            font-size: 12px;
        }
        
        .modal-content.large {
            width: 90%;
            max-width: 1000px;
        }
        
        .controls {
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            text-align: center;
            color: #666;
            padding: 20px;
        }
        
        .error-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            text-align: center;
            color: #f44336;
            padding: 20px;
        }
        
        .loading-indicator {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            text-align: center;
        }
        
        [data-theme="dark"] .memory-graph {
            background-color: #2c2c2c;
        }
        
        [data-theme="dark"] .empty-state,
        [data-theme="dark"] .error-state {
            color: #aaa;
        }
        
        [data-theme="dark"] .legend {
            background-color: rgba(50, 50, 50, 0.8);
        }
        
        [data-theme="dark"] .legend-entry text {
            fill: #eee;
        }
    `;
    
    document.head.appendChild(style);
}

// Ajouter l'événement de chargement du document
document.addEventListener('DOMContentLoaded', function() {
    // Ajouter le bouton de visualisation après le chargement
    setTimeout(addMemoryGraphButton, 1000);
});

// Exporter les fonctions pour qu'elles soient accessibles depuis d'autres scripts
window.addMemoryGraphButton = addMemoryGraphButton;
window.showMemoryGraph = showMemoryGraph;
window.loadConversationGraph = loadConversationGraph;