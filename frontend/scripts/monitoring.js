async function fetchSystemStatus() {
    try {
      const res = await fetch("http://localhost:8000/api/admin/status/live");
      const data = await res.json();
  
      // Si on est sur la page chat
      const indicator = document.getElementById("system-status-indicator");
      if (indicator) {
        let symbol = "⏳", color = "gray";
        if (data.status === "ok") { symbol = "🟢"; color = "green"; }
        else if (data.status === "degraded") { symbol = "🟡"; color = "orange"; }
        else if (data.status === "error") { symbol = "🔴"; color = "red"; }
  
        indicator.textContent = symbol;
        indicator.style.color = color;
        indicator.title = `État : ${data.status.toUpperCase()}\nDernier check : ${data.last_check}`;
      }
  
      // Si on est sur la page admin, mets à jour les cartes
      if (document.getElementById("system-status-card")) {
        updateAdminCard("system-status-card", data.status);
        updateAdminCard("llm-status-card", data.components.llm?.status);
        updateAdminCard("tts-status-card", data.components.tts?.status);
        updateAdminCard("stt-status-card", data.components.stt?.status);
      }
  
    } catch (e) {
      console.warn("Impossible de récupérer l'état système", e);
    }
  }
  
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