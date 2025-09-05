/**
 * Query Interface - Main user interaction logic
 * Handles query submission, memory management, and response display
 * US-502: Text Response Area, US-503: Image Response Slot, US-504: Session Memory
 */

class QueryInterface {
    constructor() {
        this.sessionId = window.TTRPG_CONFIG?.sessionId || null;
        this.apiBase = window.TTRPG_CONFIG?.apiBase || '/api';
        this.ws = null;
        
        // DOM elements
        this.queryInput = document.getElementById('query-input');
        this.submitButton = document.getElementById('submit-query');
        this.responseContainer = document.getElementById('response-container');
        this.responseTemplate = document.getElementById('response-template');
        this.memoryPanel = document.getElementById('memory-panel');
        this.memoryContent = document.getElementById('memory-content');
        this.memoryCount = document.getElementById('memory-count');
        this.memoryToggle = document.getElementById('memory-toggle');
        this.clearSessionButton = document.getElementById('clear-session');
        this.includeContextCheckbox = document.getElementById('include-context');
        this.responseStatus = document.getElementById('response-status');
        
        // State
        this.isProcessing = false;
        this.memoryEnabled = true;
        this.sessionMemory = [];
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.initializeWebSocket();
        this.loadSessionMemory();
        this.updateMemoryDisplay();
    }
    
    setupEventListeners() {
        // Query submission
        this.submitButton?.addEventListener('click', () => this.submitQuery());
        this.queryInput?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                this.submitQuery();
            }
        });
        
        // Memory controls
        this.memoryToggle?.addEventListener('click', () => this.toggleMemory());
        this.clearSessionButton?.addEventListener('click', () => this.clearSession());
        
        // Auto-resize textarea
        this.queryInput?.addEventListener('input', () => this.autoResizeTextarea());
    }
    
    initializeWebSocket() {
        if (this.sessionId && typeof WebSocketClient !== 'undefined') {
            this.ws = new WebSocketClient(this.sessionId);
            
            this.ws.on('connected', () => {
                console.log('WebSocket connected for query interface');
            });
            
            this.ws.on('message', (data) => {
                this.handleWebSocketMessage(data);
            });
        }
    }
    
    async submitQuery() {
        const query = this.queryInput?.value?.trim();
        if (!query || this.isProcessing) return;
        
        this.setProcessing(true);
        this.updateStatus('Processing query...');
        
        try {
            const requestData = {
                query: query,
                session_id: this.sessionId,
                memory_mode: this.memoryEnabled ? 'session' : 'none',
                theme: window.themeManager?.getCurrentTheme() || 'lcars'
            };
            
            const response = await fetch(`${this.apiBase}/query`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            this.displayResponse(result, query);
            
            // Update session memory
            if (this.memoryEnabled) {
                this.addToSessionMemory(query, result.answer);
            }
            
            // Clear input
            this.queryInput.value = '';
            this.autoResizeTextarea();
            
            this.updateStatus('Query completed');
            
        } catch (error) {
            console.error('Query submission error:', error);
            this.displayError('Failed to process query: ' + error.message);
            this.updateStatus('Query failed');
        } finally {
            this.setProcessing(false);
        }
    }
    
    displayResponse(result, originalQuery) {
        // Hide placeholder
        const placeholder = this.responseContainer?.querySelector('.response-placeholder');
        if (placeholder) {
            placeholder.style.display = 'none';
        }
        
        // Clone response template
        const responseElement = this.responseTemplate?.cloneNode(true);
        if (!responseElement) return;
        
        responseElement.id = `response-${Date.now()}`;
        responseElement.style.display = 'block';
        responseElement.classList.add('response-active');
        
        // Update metadata
        this.updateResponseMetadata(responseElement, result);
        
        // Update text response
        this.updateTextResponse(responseElement, result.answer);
        
        // Update image response (if available)
        this.updateImageResponse(responseElement, result.image_url);
        
        // Update sources (if available)
        this.updateSourcesSection(responseElement, result.retrieved_chunks);
        
        // Clear existing responses and add new one
        const existingResponses = this.responseContainer?.querySelectorAll('.response-template:not(#response-template)');
        existingResponses?.forEach(el => el.remove());
        
        this.responseContainer?.appendChild(responseElement);
        
        // Scroll to response
        responseElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
        
        // Add to WebSocket if available
        if (this.ws && this.ws.isConnected()) {
            this.ws.send({
                type: 'query_processed',
                query: originalQuery,
                response: result.answer,
                sessionId: this.sessionId,
                timestamp: result.timestamp
            });
        }
    }
    
    updateResponseMetadata(element, result) {
        const metaModel = element.querySelector('#meta-model');
        const metaTime = element.querySelector('#meta-time');
        const metaTokens = element.querySelector('#meta-tokens');
        const timestamp = element.querySelector('#response-timestamp');
        
        if (metaModel) metaModel.textContent = `MODEL: ${result.metadata?.model || 'unknown'}`;
        if (metaTime) metaTime.textContent = `TIME: ${result.metadata?.processing_time_ms || '0'}ms`;
        if (metaTokens) metaTokens.textContent = `TOKENS: ${result.metadata?.tokens || '0'}`;
        if (timestamp) timestamp.textContent = new Date(result.timestamp * 1000).toISOString();
    }
    
    updateTextResponse(element, answer) {
        const textContent = element.querySelector('#response-text-content');
        if (textContent) {
            // Process markdown-like formatting
            const formattedText = this.formatText(answer);
            textContent.innerHTML = formattedText;
        }
    }
    
    updateImageResponse(element, imageUrl) {
        const imageResponse = element.querySelector('#image-response');
        const responseImage = element.querySelector('#response-image');
        const imagePlaceholder = element.querySelector('.image-placeholder');
        
        if (imageUrl && responseImage) {
            responseImage.src = imageUrl;
            responseImage.style.display = 'block';
            if (imagePlaceholder) imagePlaceholder.style.display = 'none';
            imageResponse.style.display = 'block';
            
            responseImage.onload = () => {
                console.log('Response image loaded successfully');
            };
            
            responseImage.onerror = () => {
                console.error('Failed to load response image');
                responseImage.style.display = 'none';
                if (imagePlaceholder) {
                    imagePlaceholder.style.display = 'block';
                    imagePlaceholder.textContent = 'Failed to load image';
                }
            };
        } else {
            // Hide image section for text-only responses
            imageResponse.style.display = 'none';
        }
    }
    
    updateSourcesSection(element, sources) {
        const sourcesSection = element.querySelector('#sources-section');
        const sourcesContent = element.querySelector('#sources-content');
        
        if (sources && sources.length > 0 && sourcesContent) {
            sourcesContent.innerHTML = '';
            
            sources.forEach((source, index) => {
                const sourceElement = document.createElement('div');
                sourceElement.className = 'source-item';
                sourceElement.innerHTML = `
                    <div class="source-meta">
                        <div class="source-name">${this.escapeHtml(source.source || `Source ${index + 1}`)}</div>
                        <div class="source-score">SCORE: ${source.score?.toFixed(3) || 'N/A'}</div>
                    </div>
                    <div class="source-text">${this.escapeHtml(source.text || '')}</div>
                `;
                sourcesContent.appendChild(sourceElement);
            });
            
            sourcesSection.style.display = 'block';
        } else {
            sourcesSection.style.display = 'none';
        }
    }
    
    displayError(message) {
        const errorElement = document.createElement('div');
        errorElement.className = 'response-template response-error';
        errorElement.innerHTML = `
            <div class="response-header">
                <div class="response-meta">
                    <span class="meta-item">ERROR</span>
                </div>
                <div class="response-timestamp">${new Date().toISOString()}</div>
            </div>
            <div class="response-content">
                <div class="text-response error">
                    <div class="response-text-content">${this.escapeHtml(message)}</div>
                </div>
            </div>
        `;
        
        // Clear existing responses
        const placeholder = this.responseContainer?.querySelector('.response-placeholder');
        if (placeholder) placeholder.style.display = 'none';
        
        const existingResponses = this.responseContainer?.querySelectorAll('.response-template:not(#response-template)');
        existingResponses?.forEach(el => el.remove());
        
        this.responseContainer?.appendChild(errorElement);
    }
    
    // Memory Management (US-504: Session Memory)
    addToSessionMemory(query, response) {
        const entry = {
            id: Date.now(),
            timestamp: new Date().toISOString(),
            query: query,
            response: response,
            type: 'qa_pair'
        };
        
        this.sessionMemory.unshift(entry); // Add to beginning
        
        // Limit memory size
        if (this.sessionMemory.length > 50) {
            this.sessionMemory = this.sessionMemory.slice(0, 50);
        }
        
        this.updateMemoryDisplay();
        this.saveSessionMemory();
    }
    
    updateMemoryDisplay() {
        if (!this.memoryContent || !this.memoryCount) return;
        
        this.memoryCount.textContent = `${this.sessionMemory.length} ENTRIES`;
        
        if (this.sessionMemory.length === 0) {
            this.memoryContent.innerHTML = '<div class="memory-empty">NO PREVIOUS QUERIES</div>';
            return;
        }
        
        this.memoryContent.innerHTML = '';
        
        // Show last 10 entries
        const recentEntries = this.sessionMemory.slice(0, 10);
        recentEntries.forEach(entry => {
            const memoryItem = document.createElement('div');
            memoryItem.className = 'memory-item';
            memoryItem.innerHTML = `
                <div class="memory-query">${this.escapeHtml(this.truncateText(entry.query, 100))}</div>
                <div class="memory-response">${this.escapeHtml(this.truncateText(entry.response, 150))}</div>
            `;
            
            // Click to reuse query
            memoryItem.addEventListener('click', () => {
                if (this.queryInput) {
                    this.queryInput.value = entry.query;
                    this.autoResizeTextarea();
                    this.queryInput.focus();
                }
            });
            
            this.memoryContent.appendChild(memoryItem);
        });
    }
    
    toggleMemory() {
        this.memoryEnabled = !this.memoryEnabled;
        
        const indicator = this.memoryToggle?.querySelector('.btn-indicator');
        if (indicator) {
            if (this.memoryEnabled) {
                indicator.classList.add('active');
            } else {
                indicator.classList.remove('active');
            }
        }
        
        // Update memory panel visibility
        if (this.memoryPanel) {
            this.memoryPanel.style.display = this.memoryEnabled ? 'flex' : 'none';
        }
        
        console.log(`Memory ${this.memoryEnabled ? 'enabled' : 'disabled'}`);
    }
    
    async clearSession() {
        if (!confirm('Clear session memory? This cannot be undone.')) {
            return;
        }
        
        try {
            if (this.sessionId) {
                const response = await fetch(`${this.apiBase}/session/${this.sessionId}/memory`, {
                    method: 'DELETE'
                });
                
                if (!response.ok) {
                    throw new Error('Failed to clear server memory');
                }
            }
            
            this.sessionMemory = [];
            this.updateMemoryDisplay();
            this.saveSessionMemory();
            
            // Clear response display
            const placeholder = this.responseContainer?.querySelector('.response-placeholder');
            if (placeholder) placeholder.style.display = 'flex';
            
            const responses = this.responseContainer?.querySelectorAll('.response-template:not(#response-template)');
            responses?.forEach(el => el.remove());
            
            this.updateStatus('Session cleared');
            
        } catch (error) {
            console.error('Clear session error:', error);
            alert('Failed to clear session: ' + error.message);
        }
    }
    
    loadSessionMemory() {
        try {
            const stored = localStorage.getItem(`ttrpg-memory-${this.sessionId}`);
            if (stored) {
                this.sessionMemory = JSON.parse(stored);
            }
        } catch (error) {
            console.warn('Could not load session memory:', error);
        }
    }
    
    saveSessionMemory() {
        try {
            localStorage.setItem(`ttrpg-memory-${this.sessionId}`, JSON.stringify(this.sessionMemory));
        } catch (error) {
            console.warn('Could not save session memory:', error);
        }
    }
    
    // Utility methods
    setProcessing(processing) {
        this.isProcessing = processing;
        
        if (this.submitButton) {
            this.submitButton.disabled = processing;
            const btnText = this.submitButton.querySelector('.btn-text');
            const btnLoading = this.submitButton.querySelector('.btn-loading');
            
            if (btnText && btnLoading) {
                if (processing) {
                    btnText.style.display = 'none';
                    btnLoading.style.display = 'inline';
                } else {
                    btnText.style.display = 'inline';
                    btnLoading.style.display = 'none';
                }
            }
        }
        
        if (this.queryInput) {
            this.queryInput.disabled = processing;
        }
    }
    
    updateStatus(status) {
        const statusElement = this.responseStatus?.querySelector('.status-text');
        if (statusElement) {
            statusElement.textContent = status;
        }
        console.log('Status:', status);
    }
    
    autoResizeTextarea() {
        if (this.queryInput) {
            this.queryInput.style.height = 'auto';
            this.queryInput.style.height = this.queryInput.scrollHeight + 'px';
        }
    }
    
    formatText(text) {
        if (!text) return '';
        
        // Basic markdown-like formatting
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }
    
    escapeHtml(text) {
        if (!text) return '';
        
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    truncateText(text, maxLength) {
        if (!text || text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'query_response':
                // Handle real-time query updates
                console.log('Real-time query response:', data);
                break;
            case 'status_update':
                this.updateStatus(data.status);
                break;
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.queryInterface = new QueryInterface();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = QueryInterface;
}