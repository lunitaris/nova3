/**
 * Module commun pour la visualisation de graphes de mémoire symbolique
 * Ce fichier centralise toutes les fonctions de visualisation utilisées dans l'application
 */

// Variables globales
let graphData = null;
let graphSimulation = null;

/**
 * Charge et affiche un graphe symbolique
 * @param {string} endpoint - Endpoint API à appeler
 * @param {HTMLElement} container - Conteneur où afficher le graphe
 * @param {Object} params - Paramètres additionnels pour l'API
 * @param {Function} onSuccess - Fonction à appeler en cas de succès (optionnel)
 */
function loadSymbolicGraph(endpoint, container, params = {}, onSuccess = null) {
    try {
        console.log(`Chargement du graphe depuis ${endpoint}`, params);
        
        // Vider le conteneur et afficher l'indicateur de chargement
        container.innerHTML = `
            <div class="loading-indicator">
                <i class="fas fa-spinner fa-spin"></i> Chargement du graphe...
            </div>
        `;
        
        // Construire l'URL avec les paramètres
        const url = new URL(endpoint, CONFIG.API_BASE_URL);
        Object.keys(params).forEach(key => {
            url.searchParams.append(key, params[key]);
        });
        
        // Charger les données du graphe
        fetch(url)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Erreur HTTP: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                graphData = data;
                
                // Vérifier si le graphe est vide
                if (!graphData.nodes || graphData.nodes.length === 0) {
                    container.innerHTML = `
                        <div class="empty-state">
                            <p>Le graphe de mémoire symbolique est vide</p>
                            <p>Ajoutez des informations en mémoire pour voir apparaître le graphe</p>
                        </div>
                    `;
                    return;
                }
                
                // Créer la visualisation
                createForceDirectedGraph(graphData, container);
                
                // Appeler le callback de succès si fourni
                if (onSuccess && typeof onSuccess === 'function') {
                    onSuccess(graphData);
                }
            })
            .catch(error => {
                console.error("Erreur lors du chargement du graphe:", error);
                container.innerHTML = `
                    <div class="error-state">
                        <p>Erreur lors du chargement du graphe</p>
                        <p class="error-details">${error.message}</p>
                    </div>
                `;
            });
            
    } catch (error) {
        console.error("Erreur:", error);
        container.innerHTML = `
            <div class="error-state">
                <p>Erreur inattendue</p>
                <p class="error-details">${error.message}</p>
            </div>
        `;
    }
}

/**
 * Crée un graphe orienté force avec D3.js
 * @param {Object} data - Données du graphe (nodes et links)
 * @param {HTMLElement} container - Conteneur où afficher le graphe
 */
function createForceDirectedGraph(data, container) {
    // Vider d'abord le conteneur pour éviter les duplications
    container.innerHTML = '';
    
    // Importer D3.js depuis CDN si nécessaire
    if (!window.d3) {
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js';
        document.head.appendChild(script);
        
        script.onload = () => {
            // Une fois D3 chargé, initialiser le graphe
            initGraph(data, container);
        };
    } else {
        // D3 est déjà chargé, initialiser directement
        initGraph(data, container);
    }
}

/**
 * Initialise la visualisation du graphe avec D3.js
 * @param {Object} data - Données du graphe
 * @param {HTMLElement} container - Conteneur
 */
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

/**
 * Ajoute les styles CSS nécessaires pour le graphe
 */
function addGraphStyles() {
    if (document.getElementById('graph-visualization-styles')) return;
    
    const style = document.createElement('style');
    style.id = 'graph-visualization-styles';
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

// Exporter les fonctions pour les rendre accessibles
window.GraphVisualization = {
    loadSymbolicGraph,
    createForceDirectedGraph,
    initGraph,
    addGraphStyles
};