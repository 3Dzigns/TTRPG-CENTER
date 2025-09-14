/**
 * Theme Manager - US-501: Theme toggle and management
 * Handles LCARS, Terminal, and Classic themes with persistent storage
 */

class ThemeManager {
    constructor() {
        this.themes = {
            lcars: {
                name: 'LCARS',
                description: 'Star Trek LCARS-inspired interface',
                // Correct path: user theme CSS lives under /static/user/css/themes
                cssFile: '/static/user/css/themes/lcars.css'
            },
            terminal: {
                name: 'Terminal',
                description: 'Classic retro terminal interface',
                cssFile: '/static/user/css/themes/terminal.css'
            },
            classic: {
                name: 'Classic',
                description: 'Clean modern interface',
                cssFile: '/static/user/css/themes/classic.css'
            }
        };
        
        this.currentTheme = this.getStoredTheme() || 'lcars';
        this.themeStylesheet = document.getElementById('theme-stylesheet');
        
        this.init();
    }
    
    init() {
        // Apply stored theme
        this.applyTheme(this.currentTheme);
        
        // Set up theme buttons
        this.setupThemeButtons();
        
        // Listen for theme changes from other tabs
        window.addEventListener('storage', (e) => {
            if (e.key === 'ttrpg-theme') {
                this.applyTheme(e.newValue);
            }
        });
    }
    
    setupThemeButtons() {
        const themeButtons = document.querySelectorAll('.theme-btn');
        
        themeButtons.forEach(button => {
            button.addEventListener('click', () => {
                const theme = button.getAttribute('data-theme');
                this.switchTheme(theme);
            });
        });
        
        // Update button states
        this.updateButtonStates();
    }
    
    switchTheme(themeName) {
        if (this.themes[themeName]) {
            this.currentTheme = themeName;
            this.applyTheme(themeName);
            this.storeTheme(themeName);
            this.updateButtonStates();
            
            // Emit theme change event
            this.emitThemeChange(themeName);
            
            console.log(`Theme switched to: ${this.themes[themeName].name}`);
        }
    }
    
    applyTheme(themeName) {
        const theme = this.themes[themeName];
        if (!theme) return;
        
        // Update theme stylesheet
        this.themeStylesheet.href = theme.cssFile;
        
        // Update body class
        document.body.className = document.body.className.replace(/theme-\w+/g, '');
        document.body.classList.add(`theme-${themeName}`);
        
        // Update data attribute
        document.body.setAttribute('data-theme', themeName);
        
        // Update CSS custom properties for dynamic theming
        this.updateCSSProperties(themeName);
    }
    
    updateCSSProperties(themeName) {
        const root = document.documentElement;
        
        // Theme-specific CSS custom properties
        switch (themeName) {
            case 'lcars':
                root.style.setProperty('--theme-primary', '#ff9900');
                root.style.setProperty('--theme-secondary', '#cc6666');
                root.style.setProperty('--theme-accent', '#9999cc');
                break;
            case 'terminal':
                root.style.setProperty('--theme-primary', '#00ff00');
                root.style.setProperty('--theme-secondary', '#ffff00');
                root.style.setProperty('--theme-accent', '#ff00ff');
                break;
            case 'classic':
                root.style.setProperty('--theme-primary', '#007acc');
                root.style.setProperty('--theme-secondary', '#666666');
                root.style.setProperty('--theme-accent', '#333333');
                break;
        }
    }
    
    updateButtonStates() {
        const themeButtons = document.querySelectorAll('.theme-btn');
        
        themeButtons.forEach(button => {
            const theme = button.getAttribute('data-theme');
            if (theme === this.currentTheme) {
                button.classList.add('active');
            } else {
                button.classList.remove('active');
            }
        });
    }
    
    getStoredTheme() {
        try {
            return localStorage.getItem('ttrpg-theme');
        } catch (e) {
            console.warn('Could not access localStorage for theme:', e);
            return null;
        }
    }
    
    storeTheme(themeName) {
        try {
            localStorage.setItem('ttrpg-theme', themeName);
        } catch (e) {
            console.warn('Could not save theme to localStorage:', e);
        }
    }
    
    emitThemeChange(themeName) {
        const event = new CustomEvent('themeChanged', {
            detail: {
                theme: themeName,
                themeData: this.themes[themeName]
            }
        });
        document.dispatchEvent(event);
    }
    
    // Public API
    getCurrentTheme() {
        return this.currentTheme;
    }
    
    getThemeData(themeName = null) {
        const theme = themeName || this.currentTheme;
        return this.themes[theme];
    }
    
    getAllThemes() {
        return this.themes;
    }
    
    // Accessibility
    announceThemeChange(themeName) {
        const announcement = document.createElement('div');
        announcement.setAttribute('aria-live', 'polite');
        announcement.setAttribute('aria-atomic', 'true');
        announcement.style.position = 'absolute';
        announcement.style.left = '-10000px';
        announcement.style.width = '1px';
        announcement.style.height = '1px';
        announcement.style.overflow = 'hidden';
        
        const theme = this.themes[themeName];
        announcement.textContent = `Theme changed to ${theme.name}`;
        
        document.body.appendChild(announcement);
        
        // Remove after announcement
        setTimeout(() => {
            document.body.removeChild(announcement);
        }, 1000);
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.themeManager = new ThemeManager();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ThemeManager;
}
