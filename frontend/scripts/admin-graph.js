/**
 * Module de visualisation du graphe de mémoire symbolique
 * À ajouter au fichier frontend/scripts/admin.js
 */

// Ajoutez cette fonction après les autres fonctions dans admin.js
async function loadSymbolicGraph() {
    try {
        const container = document.getElementById('graph-container');
        container.innerHTML = `
            <div class="loading-indicator">
                <i class="fas fa-spinner fa-spin"></i> Chargement du graphe...
            </div>
        `;
        console.log("loadSymbolicGraph from admin-graph.js appelé");
        
        // Charger les données du graphe
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/memory/graph?format=d3`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const graphData = await response.json();
        
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
        
        // Vider le container pour la visualisation
        container.innerHTML = '';
        
        // Créer la visualisation avec D3.js
        createForceDirectedGraph(graphData, container);
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
}

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
    const simulation = d3.forceSimulation(data.nodes)
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
        .call(drag(simulation))
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
    
    // Mise à jour de la simulation à chaque tick
    simulation.on("tick", () => {
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
    
    // Ajouter des contrôles pour la visualisation
    const controls = svg.append("g")
        .attr("class", "controls")
        .attr("transform", `translate(${width - 100}, 20)`);
        
    // Bouton de réinitialisation du zoom
    controls.append("rect")
        .attr("width", 80)
        .attr("height", 25)
        .attr("rx", 5)
        .attr("class", "control-button");
        
    controls.append("text")
        .attr("x", 40)
        .attr("y", 16)
        .attr("text-anchor", "middle")
        .text("Recentrer")
        .attr("class", "control-text");
        
    controls.on("click", function() {
        // Réinitialiser le zoom
        svg.transition().duration(750).call(
            d3.zoom().transform,
            d3.zoomIdentity
        );
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

// Ajouter du CSS pour le graphe (dans un élément style)
function addGraphStyles() {
    if (document.getElementById('graph-styles')) return;
    
    const style = document.createElement('style');
    style.id = 'graph-styles';
    style.textContent = `
        .memory-graph {
            background-color: #f9f9f9;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.12);
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
        
        .control-button {
            fill: rgba(255, 255, 255, 0.8);
            stroke: #ccc;
            cursor: pointer;
        }
        
        .control-button:hover {
            fill: rgba(255, 255, 255, 1);
            stroke: #999;
        }
        
        .control-text {
            font-size: 12px;
            pointer-events: none;
            user-select: none;
        }
    `;
    
    document.head.appendChild(style);
}

// Modifier la fonction existante pour utiliser notre nouvelle implémentation
document.getElementById('load-graph-btn').addEventListener('click', function() {
    // Ajouter les styles
    addGraphStyles();
    // Charger le graphe
    loadSymbolicGraph();
});