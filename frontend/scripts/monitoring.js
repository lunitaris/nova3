function allStatusesAvailable(components) {
    const keys = ["llm", "tts", "stt", "hue", "memory_vector", "memory_symbolic", "memory_synthetic"];
    return keys.every(k => components[k] && components[k].status);
  }

  

  async function fetchSystemStatus() {
    try {
        const res = await fetch(`${CONFIG.API_BASE_URL}/api/admin/status`);
        
        if (!res.ok) {
            console.error("Erreur HTTP:", res.status);
            updateIndicator("error", "Erreur de connexion");
            return;
        }
        
        const data = await res.json();
        console.log("Données de statut reçues:", data);
        
        // Mise à jour des jauges de ressources système
        if (data.cpu_usage !== undefined) {
            setGaugeValue('cpu-gauge', data.cpu_usage);
        }
        
        if (data.memory_usage && data.memory_usage.used_percent !== undefined) {
            setGaugeValue('memory-gauge', data.memory_usage.used_percent);
        }
        
        if (data.disk_usage && data.disk_usage.used_percent !== undefined) {
            setGaugeValue('disk-gauge', data.disk_usage.used_percent);
        }
        
        // Mise à jour des statuts des composants
        if (data.components) {
            for (const [component, status] of Object.entries(data.components)) {
                const card = document.getElementById(`${component}-status-card`);
                if (card) {
                    const statusDot = card.querySelector('.status-dot');
                    const statusText = card.querySelector('.status-text');
                    
                    if (statusDot) {
                        statusDot.className = `status-dot ${status.status}`;
                    }
                    
                    if (statusText) {
                        statusText.textContent = getStatusText(status.status);
                    }
                }
                
                // Mise à jour des mini-indicateurs
                const miniIndicator = document.getElementById(`status-${component}`);
                if (miniIndicator) {
                    const statusIcon = status.status === 'ok' ? '🟢' : 
                                     status.status === 'degraded' ? '🟡' : 
                                     status.status === 'error' ? '🔴' : '⏳';
                    miniIndicator.textContent = statusIcon;
                }
            }
        }
        
        // Mise à jour de l'indicateur principal
        updateIndicator(data.status || "unknown", data);
        
    } catch (error) {
        console.error("Erreur lors de la récupération du statut:", error);
        updateIndicator("error", "Erreur: " + error.message);
    }
}


function getStatusText(status) {
    switch(status) {
        case 'ok':
            return 'Opérationnel';
        case 'degraded':
            return 'Dégradé';
        case 'error':
            return 'Erreur';
        default:
            return 'Inconnu';
    }
}

function setGaugeValue(gaugeId, value) {
    const gauge = document.getElementById(gaugeId);
    if (gauge) {
        const gaugeValue = gauge.querySelector('.gauge-value');
        const gaugeLabel = gauge.parentElement.querySelector('.gauge-label');
        
        if (gaugeValue) {
            gaugeValue.style.height = `${value}%`;
            
            // Changer la couleur en fonction de la valeur
            if (value > 90) {
                gaugeValue.className = 'gauge-value critical';
            } else if (value > 75) {
                gaugeValue.className = 'gauge-value warning';
            } else {
                gaugeValue.className = 'gauge-value';
            }
        }
        
        if (gaugeLabel) {
            gaugeLabel.textContent = `${Math.round(value)}%`;
        }
    }
}

function updateMiniIndicators(data) {
    const statusMap = {
      ok: "🟢",
      degraded: "🟡",
      error: "🔴",
      unknown: "⏳"
    };
  
    const set = (id, status) => {
      const el = document.getElementById(`status-${id}`);
      if (el) el.textContent = statusMap[status] || "⏳";
    };
  
    set("llm", data.components.llm?.status || "unknown");
    set("tts", data.components.tts?.status || "unknown");
    set("stt", data.components.stt?.status || "unknown");
    set("hue", data.components.hue?.status || "unknown");
    set("memory-vector", data.components.memory_vector?.status || "unknown");
    set("memory-symbolic", data.components.memory_symbolic ? "ok" : "unknown");
    set("memory-synthetic", data.components.memory_synthetic ? "ok" : "unknown");
  }
  



  function updateIndicator(status, data) {
    // Mise à jour de la carte système principale
    const systemCard = document.getElementById("system-status-card");
    if (systemCard) {
        const statusDot = systemCard.querySelector(".status-dot");
        const statusText = systemCard.querySelector(".status-text");
        
        if (statusDot) {
            statusDot.className = `status-dot ${status}`;
        }
        
        if (statusText) {
            statusText.textContent = status === "ok" ? "Opérationnel" :
                                    status === "degraded" ? "Dégradé" :
                                    status === "error" ? "Erreur" : "Inconnu";
        }
    }
    
    // Mise à jour des cartes de composants
    if (data && data.components) {
        for (const [component, compStatus] of Object.entries(data.components)) {
            const card = document.getElementById(`${component}-status-card`);
            if (card) {
                const statusDot = card.querySelector(".status-dot");
                const statusText = card.querySelector(".status-text");
                
                if (statusDot) {
                    statusDot.className = `status-dot ${compStatus.status}`;
                }
                
                if (statusText) {
                    statusText.textContent = compStatus.status === "ok" ? "Opérationnel" :
                                            compStatus.status === "error" ? "Erreur" : "Inconnu";
                }
            }
        }
    }
}

// Initialisation
document.addEventListener("DOMContentLoaded", () => {
    // Premier appel immédiat
    fetchSystemStatus();
    
    // Puis toutes les 30 secondes
    setInterval(fetchSystemStatus, 30000);
});