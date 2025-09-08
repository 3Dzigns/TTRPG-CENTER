/**
 * WebSocket Client - Real-time communication with server
 * Handles connection management and real-time updates
 */

class WebSocketClient {
    constructor(sessionId) {
        this.sessionId = sessionId;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000; // Start with 1 second
        this.maxReconnectDelay = 30000; // Max 30 seconds
        this.isConnecting = false;
        this.isManuallyDisconnected = false;
        
        // Event handlers
        this.eventHandlers = new Map();
        
        // DOM elements
        this.statusIndicator = document.getElementById('ws-status');
        this.statusText = document.getElementById('ws-status-text');
        
        this.init();
    }
    
    init() {
        this.connect();
        
        // Handle page visibility changes
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.handlePageHidden();
            } else {
                this.handlePageVisible();
            }
        });
        
        // Handle page unload
        window.addEventListener('beforeunload', () => {
            this.disconnect();
        });
    }
    
    connect() {
        if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.CONNECTING)) {
            return;
        }
        
        this.isConnecting = true;
        this.updateStatus('connecting', 'CONNECTING...');
        
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/${this.sessionId}`;
            
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = (event) => {
                this.onOpen(event);
            };
            
            this.ws.onmessage = (event) => {
                this.onMessage(event);
            };
            
            this.ws.onclose = (event) => {
                this.onClose(event);
            };
            
            this.ws.onerror = (event) => {
                this.onError(event);
            };
            
        } catch (error) {
            console.error('WebSocket connection error:', error);
            this.onError({ error });
        }
    }
    
    onOpen(event) {
        console.log('WebSocket connected');
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;
        this.updateStatus('connected', 'CONNECTED');
        
        // Send initial message
        this.send({
            type: 'connection',
            sessionId: this.sessionId,
            timestamp: Date.now()
        });
        
        this.emit('connected', { event });
    }
    
    onMessage(event) {
        try {
            const data = JSON.parse(event.data);
            console.log('WebSocket message received:', data);
            
            // Handle different message types
            switch (data.type) {
                case 'echo':
                    this.handleEcho(data);
                    break;
                case 'query_response':
                    this.handleQueryResponse(data);
                    break;
                case 'status_update':
                    this.handleStatusUpdate(data);
                    break;
                case 'error':
                    this.handleError(data);
                    break;
                default:
                    console.log('Unknown message type:', data.type);
            }
            
            this.emit('message', data);
        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
        }
    }
    
    onClose(event) {
        console.log('WebSocket closed:', event.code, event.reason);
        this.isConnecting = false;
        
        if (!this.isManuallyDisconnected) {
            this.updateStatus('disconnected', 'DISCONNECTED');
            this.scheduleReconnect();
        }
        
        this.emit('disconnected', { event });
    }
    
    onError(event) {
        console.error('WebSocket error:', event);
        this.isConnecting = false;
        this.updateStatus('error', 'ERROR');
        this.emit('error', { event });
    }
    
    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            try {
                this.ws.send(JSON.stringify(data));
                return true;
            } catch (error) {
                console.error('Error sending WebSocket message:', error);
                return false;
            }
        }
        return false;
    }
    
    disconnect() {
        this.isManuallyDisconnected = true;
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.updateStatus('disconnected', 'DISCONNECTED');
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('Max reconnection attempts reached');
            this.updateStatus('error', 'CONNECTION FAILED');
            return;
        }
        
        this.reconnectAttempts++;
        console.log(`Reconnecting in ${this.reconnectDelay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        
        this.updateStatus('reconnecting', `RECONNECTING... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        
        setTimeout(() => {
            if (!this.isManuallyDisconnected) {
                this.connect();
            }
        }, this.reconnectDelay);
        
        // Exponential backoff with jitter
        this.reconnectDelay = Math.min(
            this.reconnectDelay * 2 + Math.random() * 1000,
            this.maxReconnectDelay
        );
    }
    
    updateStatus(status, text) {
        if (this.statusIndicator) {
            this.statusIndicator.className = 'status-indicator';
            this.statusIndicator.classList.add(status);
        }
        
        if (this.statusText) {
            this.statusText.textContent = text;
        }
    }
    
    // Message handlers
    handleEcho(data) {
        console.log('Echo received:', data);
    }
    
    handleQueryResponse(data) {
        console.log('Query response received:', data);
        // This would be handled by the query interface
    }
    
    handleStatusUpdate(data) {
        console.log('Status update received:', data);
        // Update UI based on status
    }
    
    handleError(data) {
        console.error('Server error:', data);
        this.showNotification('error', data.message || 'Server error occurred');
    }
    
    // Page visibility handlers
    handlePageHidden() {
        // Reduce activity when page is hidden
        console.log('Page hidden - reducing WebSocket activity');
    }
    
    handlePageVisible() {
        // Resume full activity when page is visible
        console.log('Page visible - resuming WebSocket activity');
        
        // Reconnect if disconnected
        if (!this.ws || this.ws.readyState === WebSocket.CLOSED) {
            this.isManuallyDisconnected = false;
            this.connect();
        }
    }
    
    // Event system
    on(event, handler) {
        if (!this.eventHandlers.has(event)) {
            this.eventHandlers.set(event, []);
        }
        this.eventHandlers.get(event).push(handler);
    }
    
    off(event, handler) {
        if (this.eventHandlers.has(event)) {
            const handlers = this.eventHandlers.get(event);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }
    
    emit(event, data) {
        if (this.eventHandlers.has(event)) {
            this.eventHandlers.get(event).forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error('Error in event handler:', error);
                }
            });
        }
    }
    
    // Utility methods
    showNotification(type, message) {
        // Create and show notification
        const notification = document.createElement('div');
        notification.className = `toast ${type}`;
        notification.innerHTML = `
            <div class="toast-title">${type.toUpperCase()}</div>
            <div class="toast-message">${message}</div>
        `;
        
        document.body.appendChild(notification);
        
        // Remove after delay
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease-out forwards';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }
    
    // Public API
    isConnected() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    }
    
    getConnectionState() {
        if (!this.ws) return 'disconnected';
        
        switch (this.ws.readyState) {
            case WebSocket.CONNECTING: return 'connecting';
            case WebSocket.OPEN: return 'connected';
            case WebSocket.CLOSING: return 'closing';
            case WebSocket.CLOSED: return 'disconnected';
            default: return 'unknown';
        }
    }
    
    sendQuery(query) {
        return this.send({
            type: 'query',
            query: query,
            sessionId: this.sessionId,
            timestamp: Date.now()
        });
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebSocketClient;
}