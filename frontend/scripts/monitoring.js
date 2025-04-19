async function fetchSystemStatus() {
    try {
        const res = await fetch(`${CONFIG.API_BASE_URL}/api/admin/status/live`);
        if (!res.ok) throw new Error(`Erreur HTTP: ${res.status}`);
        
        const data = await res.json();
        
        // Mettre à jour l'indicateur dans l'interface principale
        const indicator = document.getElementById("system-status-indicator");
        if (indicator) {
            let symbol = "⏳", color = "gray";
            if (data.status === "ok") { symbol = "🟢"; color = "green"; }
            else if (data.status === "degraded") { symbol = "🟡"; color = "orange"; }
            else if (data.status === "error") { symbol = "🔴"; color = "red"; }
            
            indicator.textContent = symbol;
            indicator.style.color = color;
            indicator.title = `État: ${data.status.toUpperCase()}\nDernier check: ${data.last_check || new Date().toLocaleTimeString()}`;
            
            // Log pour debug
            console.log("✅ Statut système mis à jour:", data.status);
        } else {
            console.warn("⚠️ Élément #system-status-indicator non trouvé dans le DOM");
        }
        
        // Mise à jour des cartes sur la page admin si applicable
        if (document.getElementById("system-status-card")) {
            updateAdminCard("system-status-card", data.status);
            updateAdminCard("llm-status-card", data.components?.llm?.status);
            updateAdminCard("tts-status-card", data.components?.tts?.status);
            updateAdminCard("stt-status-card", data.components?.stt?.status);
        }
    } catch (e) {
        console.warn("❌ Impossible de récupérer l'état système:", e);
        
        // Même en cas d'erreur, mettre à jour l'indicateur
        const indicator = document.getElementById("system-status-indicator");
        if (indicator) {
            indicator.textContent = "🔴";
            indicator.style.color = "red";
            indicator.title = `Erreur de connexion au serveur de monitoring\n${e.message}`;
        }
    }
}

// Ne garder qu'une seule initialisation
document.addEventListener("DOMContentLoaded", () => {
    fetchSystemStatus(); // appel initial
    setInterval(fetchSystemStatus, 30000); // toutes les 30s
});
  
  // Appel initial
  fetchSystemStatus();
  
  // Appel périodique toutes les 30 secondes
  setInterval(fetchSystemStatus, 30000);

  
  function updateAdminCard(cardId, status) {
    const card = document.getElementById(cardId);
    if (!card) return;
  
    const dot = card.querySelector(".status-dot");
    const text = card.querySelector(".status-text");
  
    dot.style.backgroundColor = {
      ok: "green",
      degraded: "orange",
      error: "red"
    }[status] || "gray";
  
    text.textContent = {
      ok: "Fonctionnel",
      degraded: "Dégradé",
      error: "Erreur"
    }[status] || "Inconnu";
  }
  
  // Mise à jour toutes les 30s
  fetchSystemStatus();
  setInterval(fetchSystemStatus, 30000);
  
  document.addEventListener("DOMContentLoaded", () => {
    fetchSystemStatus(); // appel initial
    setInterval(fetchSystemStatus, 30000); // toutes les 30s
  });