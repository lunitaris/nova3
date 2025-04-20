// memory-ui.js
// Gère la navigation entre les sous-onglets Synthétique, Symbolique, Vecteurs
// l’activation visuelle du sous-menu
// le déclenchement uniquement de symbolicRulesEditor.initialize() quand l'onglet Symbolique est affiché


function setupMemorySubnavigation() {
    const tabButtons = document.querySelectorAll('.memory-submenu .tab');
    const panes = document.querySelectorAll('.memory-tab-pane');
  
    tabButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.memoryTab;
  
        // Changer l'onglet actif
        tabButtons.forEach(tab => tab.classList.remove('sub-active'));
        btn.classList.add('sub-active');
  
        // Afficher uniquement la section sélectionnée
        panes.forEach(pane => {
          pane.classList.remove('active');
        });
  
        const activePane = document.getElementById(`memory-${target}-section`);
        if (activePane) activePane.classList.add('active');
  
        // Déclencher l'init de l'éditeur symbolique si nécessaire
        if (target === 'symbolic') {
          if (typeof initializeSymbolicRulesEditorIfNeeded === 'function') {
            initializeSymbolicRulesEditorIfNeeded();
          } else {
            console.warn("initializeSymbolicRulesEditorIfNeeded n'est pas défini !");
          }
        }
      });
    });
  }
  





  // Attente du DOM + activation uniquement si la section mémoire est affichée
  document.addEventListener('DOMContentLoaded', () => {
    const memorySection = document.getElementById('memory-section');
    if (memorySection && memorySection.classList.contains('active')) {
      setupMemorySubnavigation();
    }
  
    // Sinon, écouter l’activation de la section mémoire depuis le menu principal
    document.querySelectorAll('.admin-nav li[data-section="memory"]').forEach(item => {
      item.addEventListener('click', () => {
        setTimeout(() => {
          setupMemorySubnavigation();
        }, 100);
      });
    });
  });
  