# FR-016 LCARS UI System Design

## Overview

This document provides a comprehensive design specification for the LCARS (Library Computer Access/Retrieval System) themed UI implementation for the TTRPG Center application. The design focuses on creating an authentic Star Trek-inspired interface while maintaining usability and implementing the feature requirements from FR-019.

## 1. Design Analysis

### Current State Assessment

Based on analysis of the existing codebase:

**Existing Components:**
- **Templates:** User interface with main.html, base.html structure
- **Theme System:** Already includes lcars.css theme with comprehensive styling
- **Query Interface:** Two-panel layout (left: input, right: response)
- **Authentication:** OAuth integration with Google login
- **Session Management:** WebSocket-based real-time communication

**Current LCARS Implementation Status:**
- ✅ Basic LCARS color palette defined
- ✅ Typography system (Orbitron, Source Code Pro)
- ✅ Two-panel interface layout
- ❌ Status light system missing
- ❌ Token management system missing
- ❌ Game/Character dropdowns missing
- ❌ Theme toggle functionality incomplete
- ❌ UI cleanup items not addressed

## 2. LCARS Design System

### 2.1 Color System Enhancement

```css
/* Enhanced LCARS Color Palette */
:root {
    /* Primary LCARS Colors */
    --lcars-orange: #ff9900;      /* Primary accent, buttons, highlights */
    --lcars-red: #cc6666;         /* Status error, alerts */
    --lcars-blue: #9999cc;        /* Information, secondary actions */
    --lcars-purple: #cc99cc;      /* Data displays, metadata */
    --lcars-yellow: #ffcc99;      /* Warnings, tier tokens */
    --lcars-green: #99cc99;       /* Status success, active states */
    --lcars-teal: #99cccc;        /* Tertiary data, sources */

    /* Status Light Colors */
    --status-logged-in: #00ff00;   /* Bright green for active login */
    --status-logged-out: #ff0000;  /* Bright red for logged out */
    --status-session-expiring: #ffff00; /* Bright yellow for expiring */

    /* Token Bar Colors */
    --token-tier: var(--lcars-orange);     /* Primary tier tokens */
    --token-rollover: var(--lcars-blue);   /* Rollover tokens */
    --token-bonus: var(--lcars-purple);    /* Bonus tokens */

    /* Theme Variants */
    --theme-light-bg: #f0f0f0;
    --theme-light-text: #1a1a1a;
    --theme-dark-bg: #000000;
    --theme-dark-text: #ffffff;
}
```

### 2.2 Typography System

```css
/* LCARS Typography Hierarchy */
.typography-system {
    /* Headers */
    --font-system-title: 2.5rem;    /* TTRPG CENTER */
    --font-panel-title: 1.25rem;    /* QUERY INTERFACE */
    --font-section-header: 0.875rem; /* SESSION MEMORY */

    /* Interactive Elements */
    --font-button-primary: 1rem;     /* EXECUTE QUERY */
    --font-button-secondary: 0.75rem; /* LOGOUT, MEMORY */
    --font-dropdown: 0.875rem;       /* Game/Character selectors */

    /* Data Display */
    --font-input: 0.95rem;           /* Query input field */
    --font-response: 0.95rem;        /* Response content */
    --font-metadata: 0.75rem;        /* Timestamps, tokens */
    --font-status: 0.75rem;          /* Status indicators */

    /* Font Families */
    --font-primary: 'Orbitron', monospace;     /* Headers, buttons */
    --font-secondary: 'Source Code Pro', monospace; /* Content, data */
}
```

### 2.3 Component Hierarchy

```
LCARS Interface Structure
├── Header Bar
│   ├── System Title ("TTRPG CENTER")
│   ├── Build Number Display
│   ├── Status Light (Login State)
│   └── Theme Toggle (Light/Dark)
├── Main Interface
│   ├── Left Panel
│   │   ├── Panel Header ("QUERY INTERFACE")
│   │   ├── Token Status Bar
│   │   ├── Game Selection Dropdown
│   │   ├── Query Input Section
│   │   │   ├── Input Field
│   │   │   ├── Submit Button (Enter key enabled)
│   │   │   └── Context Options
│   │   └── Session Memory Panel
│   └── Right Panel
│       ├── Panel Header ("RESPONSE OUTPUT")
│       ├── Character Selection Dropdown
│       ├── Response Display Area
│       └── Sources/Metadata Section
└── Session Status Bar
    ├── Session ID
    └── WebSocket Connection Status
```

## 3. Component Specifications

### 3.1 Status Light System (US-1901)

**Location:** Top-left of header bar
**States:**
- **Green (`--status-logged-in`):** User authenticated, session valid
- **Red (`--status-logged-out`):** User not authenticated
- **Yellow (`--status-session-expiring`):** Session expires in <15 minutes

**Implementation:**
```html
<div class="status-light-container">
    <div class="status-light" id="auth-status-light"></div>
    <span class="status-label" id="auth-status-text">LOGGED OUT</span>
</div>
```

**Behavior:**
- Pulsing animation for all states
- Automatic updates based on session monitoring
- Click to show auth status details

### 3.2 Theme Toggle System (US-1902)

**Location:** Top-right of header bar
**States:**
- **Light Mode:** Light backgrounds, dark text
- **Dark Mode:** Dark backgrounds, light text (default LCARS)

**Implementation:**
```html
<div class="theme-controls">
    <button class="theme-btn" data-theme="light">LIGHT</button>
    <button class="theme-btn active" data-theme="dark">DARK</button>
</div>
```

**CSS Variable System:**
```css
[data-theme="light"] {
    --primary-bg: var(--theme-light-bg);
    --primary-text: var(--theme-light-text);
    /* Maintain LCARS accent colors in both modes */
}

[data-theme="dark"] {
    --primary-bg: var(--theme-dark-bg);
    --primary-text: var(--theme-dark-text);
}
```

### 3.3 Token Status Bar (US-1904)

**Location:** Left panel, below panel header
**Design:** Segmented horizontal bar with percentage labels

```html
<div class="token-status-bar">
    <div class="token-bar-container">
        <div class="token-segment tier" style="width: 45%;">
            <span class="token-label">TIER: 450</span>
        </div>
        <div class="token-segment rollover" style="width: 30%;">
            <span class="token-label">ROLLOVER: 300</span>
        </div>
        <div class="token-segment bonus" style="width: 15%;">
            <span class="token-label">BONUS: 150</span>
        </div>
    </div>
    <div class="token-summary">
        <span class="token-total">900 TOKENS (75% REMAINING)</span>
    </div>
</div>
```

**Features:**
- Visual segmentation by token type
- Color-coded segments (orange/blue/purple)
- Percentage calculation display
- Responsive width adjustment
- Hover tooltips for detailed breakdown

### 3.4 Game Selection Dropdown (US-1905)

**Location:** Left panel, below token status bar
**Functionality:** Context switching for queries and memory

```html
<div class="game-selection">
    <label class="selection-label">ACTIVE CAMPAIGN</label>
    <select class="lcars-dropdown" id="game-selector">
        <option value="">Select Game...</option>
        <option value="dnd5e-campaign1">D&D 5E - Dragon Heist</option>
        <option value="pathfinder-ap1">Pathfinder - Age of Ashes</option>
        <option value="call-of-cthulhu-1">Call of Cthulhu - Masks</option>
    </select>
</div>
```

**Behavior:**
- Persistence of last selected game
- Context updates for query processing
- Memory filtering by game context
- API integration for game list retrieval

### 3.5 Character Selection Dropdown (US-1906)

**Location:** Right panel header, aligned right
**Functionality:** Character context and management

```html
<div class="character-selection">
    <select class="lcars-dropdown compact" id="character-selector">
        <option value="">Select Character...</option>
        <option value="char1">Thorin Ironforge (Fighter)</option>
        <option value="char2">Lyralei Moonwhisper (Ranger)</option>
        <option value="char3">Zara Shadowstep (Rogue)</option>
    </select>
    <button class="control-btn character-manage" title="Manage Characters">
        <span class="btn-text">MANAGE</span>
    </button>
</div>
```

**Character Management Features:**
- Character sheet access
- Add/Edit/Remove character workflows
- Character-specific query context
- Integration with game selection

### 3.6 Enhanced Query Input (US-1903)

**Current:** Basic textarea with submit button
**Enhancement:** Enter key submission, improved accessibility

```javascript
// Enhanced input handling
document.getElementById('query-input').addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitQuery();
    }
});

// Button and Enter key trigger same function
function submitQuery() {
    // Unified submission logic
    // Supports both button click and Enter key
}
```

### 3.7 UI Cleanup (US-1907)

**Removals:**
- Semi-hidden bottom bars
- Phase indicators
- Unnecessary status displays

**Retained:**
- Build number display in header
- Essential session information
- Core functionality indicators

## 4. Token Management System Architecture

### 4.1 Data Model

```typescript
interface TokenBalance {
    tier: {
        current: number;
        maximum: number;
        refreshDate: Date;
    };
    rollover: {
        current: number;
        maximum: number;
        expiryDate: Date;
    };
    bonus: {
        current: number;
        source: string;
        expiryDate?: Date;
    };
    total: number;
    percentageRemaining: number;
}
```

### 4.2 API Integration

```typescript
// Token balance retrieval
GET /api/user/tokens
Response: TokenBalance

// Token usage tracking
POST /api/query/submit
Request: { query: string, useTokens: number }
Response: { response: string, tokensUsed: number, remainingBalance: TokenBalance }
```

### 4.3 Visual Calculation Logic

```javascript
function calculateTokenBarSegments(balance: TokenBalance) {
    const total = balance.total;
    const tierWidth = (balance.tier.current / total) * 100;
    const rolloverWidth = (balance.rollover.current / total) * 100;
    const bonusWidth = (balance.bonus.current / total) * 100;

    return {
        tier: `${tierWidth}%`,
        rollover: `${rolloverWidth}%`,
        bonus: `${bonusWidth}%`
    };
}
```

## 5. Testing Framework Integration

### 5.1 Component Testing Structure

```typescript
// Status Light Component Tests
describe('StatusLight', () => {
    test('shows green when user logged in', () => {
        // Test implementation
    });

    test('shows red when user logged out', () => {
        // Test implementation
    });

    test('shows yellow when session expiring', () => {
        // Test implementation
    });
});

// Theme Toggle Tests
describe('ThemeToggle', () => {
    test('switches between light and dark modes', () => {
        // Test implementation
    });

    test('persists theme selection', () => {
        // Test implementation
    });
});

// Token Bar Tests
describe('TokenStatusBar', () => {
    test('displays correct token percentages', () => {
        // Test implementation
    });

    test('updates when tokens consumed', () => {
        // Test implementation
    });
});
```

### 5.2 Integration Testing

**Functional Tests:**
- Complete user workflows
- Cross-component interactions
- API integration verification
- Theme persistence across sessions

**Regression Tests:**
- Component rendering across environments
- Theme switching reliability
- Token calculation accuracy
- Dropdown functionality consistency

## 6. Implementation Specifications

### 6.1 File Structure

```
static/user/
├── css/
│   ├── components/
│   │   ├── status-light.css
│   │   ├── token-bar.css
│   │   ├── dropdowns.css
│   │   └── theme-toggle.css
│   └── themes/
│       ├── lcars.css (enhanced)
│       └── lcars-light.css (new)
├── js/
│   ├── components/
│   │   ├── status-light.js
│   │   ├── token-manager.js
│   │   ├── game-selector.js
│   │   ├── character-manager.js
│   │   └── theme-controller.js
│   └── main.js (updated)
└── templates/user/
    ├── main.html (updated)
    └── components/ (new modular templates)
```

### 6.2 API Endpoints Required

```
GET  /api/user/tokens - Token balance retrieval
GET  /api/user/games - Available games for user
GET  /api/user/characters?game_id={id} - Characters for game
POST /api/user/characters - Create/update character
GET  /api/auth/status - Current authentication status
POST /api/auth/refresh - Refresh session token
```

### 6.3 JavaScript Module Structure

```javascript
// Main application initialization
class LCARSInterface {
    constructor() {
        this.statusLight = new StatusLight();
        this.tokenManager = new TokenManager();
        this.gameSelector = new GameSelector();
        this.characterManager = new CharacterManager();
        this.themeController = new ThemeController();
    }

    initialize() {
        // Component initialization and event binding
    }
}

// Individual component classes
class StatusLight {
    updateStatus(authState) { /* implementation */ }
}

class TokenManager {
    updateDisplay(balance) { /* implementation */ }
    calculateUsage(query) { /* implementation */ }
}
```

## 7. Security Considerations

### 7.1 Authentication Integration

- JWT token management for API calls
- Session expiration monitoring
- Automatic token refresh handling
- Secure credential storage

### 7.2 Data Privacy

- Token balance caching with expiration
- Game/character data encryption
- Session-based memory isolation
- XSS prevention in dynamic content

## 8. Performance Specifications

### 8.1 Load Time Targets

- Initial page load: <2 seconds
- Theme switching: <200ms
- Dropdown population: <500ms
- Token balance update: <300ms

### 8.2 Memory Management

- Component cleanup on navigation
- Event listener removal
- WebSocket connection management
- CSS-in-JS optimization for themes

## 9. Accessibility Requirements

### 9.1 WCAG 2.1 Compliance

- Color contrast ratios ≥4.5:1 for text
- Keyboard navigation for all interactive elements
- Screen reader compatibility
- Focus indication for all controls

### 9.2 LCARS-Specific Accessibility

- High contrast mode support
- Font size scaling compatibility
- Color-blind friendly status indicators
- Alternative text for visual elements

## 10. Browser Compatibility

### 10.1 Supported Browsers

- Chrome/Chromium 90+
- Firefox 88+
- Safari 14+
- Edge 90+

### 10.2 Progressive Enhancement

- CSS Grid fallbacks for older browsers
- WebSocket fallback to polling
- Local storage fallback for theme persistence
- Basic functionality without JavaScript

This design specification provides a comprehensive foundation for implementing the LCARS UI system while maintaining the authentic Star Trek aesthetic and ensuring robust functionality across all specified requirements.