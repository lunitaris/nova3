async function fetchSystemStatus() {
    try {
      // Utiliser l'URL complète avec le port correct
      const res = await fetch("http://localhost:8000/api/admin/status/live");
      
      if (!res.ok) {
        throw new Error(`Erreur HTTP: ${res.status}`);
      }
      
      const data = await res.json();
      console.log("Données de statut reçues:", data);
    
      // Si on est sur la page chat
      const indicator = document.getElementById("system-status-indicator");
      if (indicator) {
        let symbol = "⏳", color = "gray";
        
        // Définir le symbole et la couleur en fonction du statut
        if (data.status === "ok") { 
          symbol = "🟢"; 
          color = "green"; 
        }
        else if (data.status === "degraded") { 
          symbol = "🟡"; 
          color = "orange"; 
        }
        else if (data.status === "error") { 
          symbol = "🔴"; 
          color = "red"; 
        }
    
        // Mettre à jour l'indicateur
        indicator.textContent = symbol;
        indicator.style.color = color;
        indicator.title = `État : ${data.status.toUpperCase()}\nDernier check : ${data.last_check || new Date().toLocaleTimeString()}`;
      }
    
      // Si on est sur la page admin, mets à jour les cartes
      if (document.getElementById("system-status-card")) {
        updateAdminCard("system-status-card", data.status);
        
        if (data.components) {
          if (data.components.llm) updateAdminCard("llm-status-card", data.components.llm.status);
          if (data.components.tts) updateAdminCard("tts-status-card", data.components.tts.status);
          if (data.components.stt) updateAdminCard("stt-status-card", data.components.stt.status);
        }
      }
    } catch (e) {
      console.warn("Impossible de récupérer l'état système:", e);
      
      // Mettre l'indicateur en état d'erreur en cas d'échec
      const indicator = document.getElementById("system-status-indicator");
      if (indicator) {
        indicator.textContent = "⚠️";
        indicator.style.color = "orange";
        indicator.title = `Erreur de connexion au serveur\nDernière tentative: ${new Date().toLocaleTimeString()}`;
      }
    }
  }
  
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