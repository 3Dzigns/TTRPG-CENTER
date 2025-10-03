# User UI

## Purpose
Retro terminal/LCARS-themed User application for TTRPG content interaction.

## Responsibilities
- **Query Interface**: Natural language query processing via /ask endpoint
- **Planning Interface**: Complex workflow planning via /plan endpoint
- **Execution Interface**: Workflow execution via /run endpoint
- **Session Management**: User context and conversation history
- **Retro Experience**: Terminal/LCARS aesthetic for immersive TTRPG feel

## Technology Stack
- **Framework**: React + Vite
- **Language**: TypeScript
- **UI Components**: Custom LCARS/Terminal components
- **Styling**: Tailwind CSS with custom retro themes
- **State Management**: React Query + Zustand
- **Testing**: Vitest + Playwright

## Design Themes

### Terminal Theme
- Monospace fonts and command-line aesthetics
- Dark background with green/amber text
- ASCII art and terminal-style prompts
- Command history and tab completion
- Blinking cursor and typing animations

### LCARS Theme (Star Trek)
- Distinctive curved interface elements
- Orange/blue color scheme
- Rounded rectangular buttons
- Status indicators and progress bars
- Futuristic sound effects

## Setup
```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Run tests
npm run test
npm run test:e2e
```

## Environment Configuration
- Development: http://localhost:3010
- Test: http://localhost:3011
- Production: Configured via environment variables

## Key Features

### Query Interface
- Natural language input with autocomplete
- Real-time response streaming
- Context-aware suggestions
- Query history and favorites
- Rich text formatting for TTRPG content

### Planning Interface
- Interactive workflow planning
- Step-by-step guidance
- Resource estimation and validation
- Plan visualization and editing
- Execution scheduling

### Session Management
- Persistent conversation context
- User preferences and settings
- Session history and bookmarks
- Multi-device synchronization
- Privacy controls

### Retro Experience
- Theme switching (Terminal/LCARS)
- Immersive animations and transitions
- Sound effects and audio feedback
- Customizable interface elements
- Easter eggs and hidden features

## Components Structure
```
src/
├── app/          # Main application setup
├── components/   # Reusable UI components
│   ├── terminal/ # Terminal theme components
│   ├── lcars/    # LCARS theme components
│   ├── query/    # Query interface
│   └── session/  # Session management
├── pages/        # Page components
│   ├── chat/
│   ├── plan/
│   ├── history/
│   └── settings/
├── hooks/        # Custom React hooks
├── lib/          # Utility functions and API clients
├── themes/       # Theme definitions and assets
└── test/         # Component tests
```

## API Integration
- **User API**: Primary backend integration (port 8002/8181/8284)
- **Orchestrator**: Direct query processing
- **Session Storage**: Context persistence
- **WebSocket**: Real-time streaming

## Accessibility
- Keyboard navigation support
- Screen reader compatibility
- High contrast mode
- Font size customization
- Motion reduction options

## Performance
- Code splitting and lazy loading
- Optimized bundle size
- Service worker for offline capability
- Progressive web app features
- Mobile responsiveness

## Status
🚧 **Planned** - Phase 5 implementation

## Next Steps
1. Design terminal and LCARS component libraries
2. Implement query interface with streaming
3. Create session management system
4. Build responsive retro themes
5. Add accessibility features
