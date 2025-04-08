/**
 * Configuration de l'application Assistant IA
 */

const CONFIG = {
    // Configuration du backend
    API_BASE_URL: "http://localhost:8000",
    WEBSOCKET_BASE_URL: "ws://localhost:8000",
    
    // Chemins d'API
    API: {
        CHAT: "/api/chat",
        VOICE: "/api/voice",
        MEMORY: "/api/memory",
        HEALTH: "/health"
    },
    
    // Préférences par défaut
    DEFAULTS: {
        // Préférences générales
        THEME: "light", // "light", "dark", "system"
        
        // Préférences des modèles
        MODEL_PREFERENCE: "auto", // "auto", "fast", "balanced", "cloud"
        
        // Préférences vocales
        TTS_VOICE: "fr_FR-siwis-medium",
        SPEECH_RATE: 1.0,
        
        // Délais et timeouts
        TYPING_DELAY: 30, // ms par caractère pour simuler la frappe
        RESPONSE_TIMEOUT: 60000, // 60 secondes
        
        // Historique de conversation
        MAX_MESSAGES_DISPLAY: 50,
        
        // Mode de conversation
        CONVERSATION_MODE: "chat", // "chat" ou "voice"
    }
};

/**
 * Gestionnaire des préférences utilisateur
 */
class UserPreferences {
    constructor() {
        this.prefs = this.loadPreferences();
        this.applyTheme();
    }
    
    /**
     * Charge les préférences depuis le stockage local
     */
    loadPreferences() {
        try {
            const savedPrefs = localStorage.getItem('assistant_preferences');
            return savedPrefs ? JSON.parse(savedPrefs) : CONFIG.DEFAULTS;
        } catch (error) {
            console.error("Erreur lors du chargement des préférences:", error);
            return CONFIG.DEFAULTS;
        }
    }
    
    /**
     * Sauvegarde les préférences dans le stockage local
     */
    savePreferences() {
        try {
            localStorage.setItem('assistant_preferences', JSON.stringify(this.prefs));
        } catch (error) {
            console.error("Erreur lors de la sauvegarde des préférences:", error);
        }
    }
    
    /**
     * Récupère une préférence
     * @param {string} key - Clé de la préférence
     * @param {any} defaultValue - Valeur par défaut si non trouvée
     * @returns {any} La valeur de la préférence
     */
    get(key, defaultValue = null) {
        return this.prefs[key] !== undefined ? this.prefs[key] : 
               (defaultValue !== null ? defaultValue : CONFIG.DEFAULTS[key]);
    }
    
    /**
     * Définit une préférence
     * @param {string} key - Clé de la préférence
     * @param {any} value - Valeur à définir
     */
    set(key, value) {
        this.prefs[key] = value;
        this.savePreferences();
        
        // Actions spéciales selon la préférence
        if (key === 'THEME') {
            this.applyTheme();
        }
    }
    
    /**
     * Applique le thème selon les préférences
     */
    applyTheme() {
        let theme = this.get('THEME');
        
        // Si thème système, détecter la préférence du système
        if (theme === 'system') {
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            theme = prefersDark ? 'dark' : 'light';
        }
        
        // Appliquer le thème au document
        document.documentElement.setAttribute('data-theme', theme);
    }
}

// Instance globale des préférences
const userPreferences = new UserPreferences();