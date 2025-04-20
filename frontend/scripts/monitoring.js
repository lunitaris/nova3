function allStatusesAvailable(components) {
    const keys = ["llm", "tts", "stt", "hue", "memory_vector", "memory_symbolic", "memory_synthetic"];
    return keys.every(k => components[k] && components[k].status);
  }

  



async function fetchSystemStatus() {
    try {
        // Appel direct à l'endpoint de diagnostic qui fonctionne
        const res = await fetch(`${CONFIG.API_BASE_URL}/api/admin/status/details`);
        
        if (!res.ok) {
            console.error("Erreur HTTP:", res.status);
            updateIndicator("error", "Erreur de connexion");
            return;
        }
        
        const data = await res.json();
        console.log("Données de statut reçues:", data);
        
        // Mise à jour de l'indicateur avec le statut reçu
        const statusFinal = allStatusesAvailable(data.components) ? data.status : "unknown";
        updateIndicator(statusFinal, data);

        updateMiniIndicators(data);
        
    } catch (error) {
        console.error("Erreur lors de la récupération du statut:", error);
        updateIndicator("error", "Erreur: " + error.message);
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
  



// Fonction pour mettre à jour l'indicateur
function updateIndicator(status, data) {
    const indicator = document.getElementById("system-status-indicator");
    if (!indicator) return;
    
    let symbol, color;
    
    switch(status) {
        case "ok":
            symbol = "🟢";
            color = "green";
            break;
        case "degraded":
            symbol = "🟡";
            color = "orange";
            break;
        case "error":
            symbol = "🔴";
            color = "red";
            break;
        case "unknown":
            symbol = "⏳";
            color = "gray";
            break;
        default:
            symbol = "⚠️";
            color = "gray";
    }
    
    indicator.textContent = symbol;
    indicator.style.color = color;
    
    // Créer un titre détaillé pour le survol
    let title = `État système: ${status.toUpperCase()}`;
    title += `\nMis à jour: ${new Date().toLocaleTimeString()}`;
    
    // Si des données détaillées sont disponibles, les ajouter
    if (data && data.components) {
        if (data.components.llm) title += `\nLLM: ${data.components.llm.status}`;
        if (data.components.tts) title += `\nTTS: ${data.components.tts.status}`;
        if (data.components.stt) title += `\nSTT: ${data.components.stt.status}`;
    }
    
    indicator.title = title;
}

// Initialisation
document.addEventListener("DOMContentLoaded", () => {
    // Premier appel immédiat
    fetchSystemStatus();
    
    // Puis toutes les 30 secondes
    setInterval(fetchSystemStatus, 30000);
});