/**
 * Main JavaScript - Global initialization and utilities
 * Phase 5 User UI main script
 */

// Global configuration
window.TTRPG = {
    version: '5.0.0',
    phase: 'Phase 5',
    initialized: false,
    components: {}
};

// Initialize application when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
    try {
        await initializeApplication();
    } catch (error) {
        console.error('Failed to initialize application:', error);
        showErrorMessage('Failed to initialize application');
    }
});

async function initializeApplication() {
    console.log('Initializing TTRPG Center User UI...');
    
    // Initialize components in order
    await initializeThemeSystem();
    await initializeErrorHandling();
    await initializeAccessibility();
    await initializePerformanceMonitoring();
    
    // Mark as initialized
    window.TTRPG.initialized = true;
    
    console.log('TTRPG Center User UI initialized successfully');
    
    // Emit initialization event
    document.dispatchEvent(new CustomEvent('ttrpgInitialized', {
        detail: { version: window.TTRPG.version }
    }));
}

// Theme System Integration
async function initializeThemeSystem() {
    // Wait for theme manager to be ready
    if (typeof ThemeManager !== 'undefined') {
        // Theme manager is loaded, wait for initialization
        if (!window.themeManager) {
            await new Promise(resolve => {
                const checkThemeManager = () => {
                    if (window.themeManager) {
                        resolve();
                    } else {
                        setTimeout(checkThemeManager, 100);
                    }
                };
                checkThemeManager();
            });
        }
        
        // Listen for theme changes
        document.addEventListener('themeChanged', (event) => {
            handleThemeChange(event.detail);
        });
        
        console.log('Theme system initialized');
    }
}

function handleThemeChange(themeData) {
    console.log('Theme changed to:', themeData.theme);
    
    // Update any theme-dependent components
    updateComponentsForTheme(themeData.theme);
    
    // Save theme preference
    try {
        localStorage.setItem('ttrpg-theme-preference', themeData.theme);
    } catch (error) {
        console.warn('Could not save theme preference:', error);
    }
}

function updateComponentsForTheme(themeName) {
    // Update syntax highlighting
    updateSyntaxHighlighting(themeName);
    
    // Update dynamic styles
    updateDynamicStyles(themeName);
    
    // Announce theme change for accessibility
    announceThemeChange(themeName);
}

// Error Handling
async function initializeErrorHandling() {
    // Global error handler
    window.addEventListener('error', (event) => {
        console.error('Global error:', event.error);
        handleGlobalError(event.error);
    });
    
    // Unhandled promise rejection handler
    window.addEventListener('unhandledrejection', (event) => {
        console.error('Unhandled promise rejection:', event.reason);
        handleGlobalError(event.reason);
    });
    
    console.log('Error handling initialized');
}

function handleGlobalError(error) {
    // Don't show error notifications for common/expected errors
    if (isIgnorableError(error)) {
        return;
    }
    
    // Show user-friendly error message
    showErrorMessage('An unexpected error occurred. Please try again.');
    
    // Log to analytics/monitoring service if available
    logError(error);
}

function isIgnorableError(error) {
    if (!error) return true;
    
    const ignorableMessages = [
        'Network request failed',
        'Load failed',
        'ResizeObserver loop limit exceeded'
    ];
    
    return ignorableMessages.some(msg => 
        error.message && error.message.includes(msg)
    );
}

// Accessibility
async function initializeAccessibility() {
    // Keyboard navigation
    setupKeyboardNavigation();
    
    // Screen reader announcements
    setupScreenReaderSupport();
    
    // Focus management
    setupFocusManagement();
    
    // High contrast mode detection
    if (window.matchMedia) {
        const highContrastQuery = window.matchMedia('(prefers-contrast: high)');
        handleHighContrast(highContrastQuery.matches);
        highContrastQuery.addListener((e) => handleHighContrast(e.matches));
    }
    
    // Reduced motion detection
    if (window.matchMedia) {
        const reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
        handleReducedMotion(reducedMotionQuery.matches);
        reducedMotionQuery.addListener((e) => handleReducedMotion(e.matches));
    }
    
    console.log('Accessibility features initialized');
}

function setupKeyboardNavigation() {
    // Global keyboard shortcuts
    document.addEventListener('keydown', (event) => {
        // Alt + T: Toggle theme
        if (event.altKey && event.key === 't') {
            event.preventDefault();
            toggleThemeQuickly();
        }
        
        // Alt + M: Toggle memory
        if (event.altKey && event.key === 'm') {
            event.preventDefault();
            if (window.queryInterface) {
                window.queryInterface.toggleMemory();
            }
        }
        
        // Alt + C: Clear session
        if (event.altKey && event.key === 'c') {
            event.preventDefault();
            if (window.queryInterface) {
                window.queryInterface.clearSession();
            }
        }
        
        // Escape: Close modals/panels
        if (event.key === 'Escape') {
            closeActiveModals();
        }
    });
}

function setupScreenReaderSupport() {
    // Create aria-live region for announcements
    const announceRegion = document.createElement('div');
    announceRegion.id = 'aria-announcements';
    announceRegion.setAttribute('aria-live', 'polite');
    announceRegion.setAttribute('aria-atomic', 'true');
    announceRegion.style.position = 'absolute';
    announceRegion.style.left = '-10000px';
    announceRegion.style.width = '1px';
    announceRegion.style.height = '1px';
    announceRegion.style.overflow = 'hidden';
    
    document.body.appendChild(announceRegion);
    
    // Global announce function
    window.announceToScreenReader = function(message) {
        announceRegion.textContent = message;
        setTimeout(() => {
            announceRegion.textContent = '';
        }, 1000);
    };
}

function setupFocusManagement() {
    // Track focus for better keyboard navigation
    document.addEventListener('focusin', (event) => {
        document.body.classList.add('using-keyboard');
    });
    
    document.addEventListener('mousedown', (event) => {
        document.body.classList.remove('using-keyboard');
    });
}

function handleHighContrast(enabled) {
    document.body.classList.toggle('high-contrast', enabled);
    console.log('High contrast mode:', enabled ? 'enabled' : 'disabled');
}

function handleReducedMotion(enabled) {
    document.body.classList.toggle('reduced-motion', enabled);
    console.log('Reduced motion:', enabled ? 'enabled' : 'disabled');
}

// Performance Monitoring
async function initializePerformanceMonitoring() {
    // Monitor page load performance
    if (window.performance && window.performance.timing) {
        const loadTime = window.performance.timing.loadEventEnd - window.performance.timing.navigationStart;
        console.log('Page load time:', loadTime + 'ms');
    }
    
    // Monitor memory usage (if available)
    if (window.performance && window.performance.memory) {
        const memoryInfo = window.performance.memory;
        console.log('Memory usage:', {
            used: Math.round(memoryInfo.usedJSHeapSize / 1024 / 1024) + ' MB',
            total: Math.round(memoryInfo.totalJSHeapSize / 1024 / 1024) + ' MB',
            limit: Math.round(memoryInfo.jsHeapSizeLimit / 1024 / 1024) + ' MB'
        });
    }
    
    // Monitor long tasks (if supported)
    if ('PerformanceObserver' in window) {
        try {
            const observer = new PerformanceObserver((list) => {
                list.getEntries().forEach((entry) => {
                    if (entry.duration > 50) { // Log tasks longer than 50ms
                        console.warn('Long task detected:', entry.duration + 'ms');
                    }
                });
            });
            observer.observe({ entryTypes: ['longtask'] });
        } catch (error) {
            console.log('Long task monitoring not supported');
        }
    }
    
    console.log('Performance monitoring initialized');
}

// Utility Functions
function showErrorMessage(message, type = 'error') {
    const notification = document.createElement('div');
    notification.className = `toast ${type}`;
    notification.innerHTML = `
        <div class="toast-title">${type.toUpperCase()}</div>
        <div class="toast-message">${escapeHtml(message)}</div>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after delay
    setTimeout(() => {
        if (notification.parentNode) {
            notification.style.animation = 'slideOut 0.3s ease-out forwards';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }
    }, 5000);
    
    // Announce to screen readers
    if (window.announceToScreenReader) {
        window.announceToScreenReader(`${type}: ${message}`);
    }
}

function toggleThemeQuickly() {
    if (window.themeManager) {
        const themes = Object.keys(window.themeManager.getAllThemes());
        const current = window.themeManager.getCurrentTheme();
        const currentIndex = themes.indexOf(current);
        const nextIndex = (currentIndex + 1) % themes.length;
        window.themeManager.switchTheme(themes[nextIndex]);
    }
}

function closeActiveModals() {
    // Close any open modals
    const modals = document.querySelectorAll('.modal-overlay');
    modals.forEach(modal => {
        modal.style.animation = 'fadeOut 0.3s ease-out forwards';
        setTimeout(() => {
            if (modal.parentNode) {
                modal.parentNode.removeChild(modal);
            }
        }, 300);
    });
}

function updateSyntaxHighlighting(themeName) {
    // Update code block highlighting based on theme
    const codeBlocks = document.querySelectorAll('code, pre');
    codeBlocks.forEach(block => {
        block.classList.remove('theme-lcars', 'theme-terminal', 'theme-classic');
        block.classList.add(`theme-${themeName}`);
    });
}

function updateDynamicStyles(themeName) {
    // Update any dynamic CSS based on theme
    const root = document.documentElement;
    
    // Example: Update scrollbar colors based on theme
    switch (themeName) {
        case 'lcars':
            root.style.setProperty('--scrollbar-color', '#ff9900');
            break;
        case 'terminal':
            root.style.setProperty('--scrollbar-color', '#00ff00');
            break;
        case 'classic':
            root.style.setProperty('--scrollbar-color', '#007acc');
            break;
    }
}

function announceThemeChange(themeName) {
    if (window.announceToScreenReader) {
        const themeName_friendly = window.themeManager?.getThemeData(themeName)?.name || themeName;
        window.announceToScreenReader(`Theme changed to ${themeName_friendly}`);
    }
}

function logError(error) {
    // In a real application, this would send to an analytics service
    console.log('Logging error:', {
        message: error.message,
        stack: error.stack,
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent,
        url: window.location.href
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Cache management for US-507: Fast Retest Behavior
function clearApplicationCache() {
    if ('caches' in window) {
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    console.log('Clearing cache:', cacheName);
                    return caches.delete(cacheName);
                })
            );
        }).then(() => {
            console.log('Application cache cleared');
            showErrorMessage('Cache cleared successfully', 'success');
        });
    } else {
        // Fallback: hard refresh
        window.location.reload(true);
    }
}

// Export global utilities
window.TTRPG.utils = {
    showErrorMessage,
    toggleThemeQuickly,
    closeActiveModals,
    clearApplicationCache,
    escapeHtml
};

// Service worker registration (if available)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => {
                console.log('Service worker registered:', registration);
            })
            .catch(error => {
                console.log('Service worker registration failed:', error);
            });
    });
}