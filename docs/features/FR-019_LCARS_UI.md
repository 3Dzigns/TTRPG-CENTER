# Feature Request FR-019 — LCARS UI Overhaul & Token/Game/Character Management

## Epic E19.1 — LCARS Themed Interface

### US-1901: Logged-In Status Light
**As a** User  
**I want** the status light to reflect my login state  
**So that** I know if I’m authenticated.  

**Acceptance Criteria**  
- Green = logged in, Red = logged out, Yellow = session expiring.  
- Visible in top-left at all times.  

**Testing**  
- Unit: Simulate login/logout → light changes.  
- Functional: Expiring session shows yellow.  

---

### US-1902: LCARS Theme with Light/Dark Mode
**As a** User  
**I want** LCARS-style interface with theme toggle  
**So that** I can choose light or dark mode.  

**Acceptance Criteria**  
- Theme toggle in settings.  
- Colors/fonts match LCARS design.  

**Testing**  
- Functional: Switching modes updates instantly.  
- Regression: No style breaks in DEV/TEST/PROD.  

---

## Epic E19.2 — Query Input & Submission

### US-1903: Enter or Button Submits Query
**As a** User  
**I want** pressing Enter or clicking the button to send my query  
**So that** it feels natural.  

**Acceptance Criteria**  
- Enter key triggers submission.  
- “Ask” button triggers same submission.  

**Testing**  
- Unit: Keyboard event captured.  
- Functional: Both methods hit `/ask` API.  

---

## Epic E19.3 — Token Indicator

### US-1904: Token Percent Remaining
**As a** User  
**I want** a visual bar showing my token balance  
**So that** I can track usage at a glance.  

**Acceptance Criteria**  
- Bar segmented: Tier tokens (primary), Rollover tokens (secondary), Bonus tokens (accent).  
- Label shows % remaining.  
- Supports up to 6 months rollover.  

**Testing**  
- Unit: 3 data sources map correctly.  
- Functional: Display matches actual balances.  

---

## Epic E19.4 — Game & Character Management

### US-1905: Game Selection Dropdown
**As a** User  
**I want** a game selection dropdown under the token bar on the left  
**So that** I can quickly switch between active game campaigns.  

**Acceptance Criteria**  
- Dropdown lists all games tied to my account.  
- Selecting a game updates context for queries and memory.  
- Default to last active game.  

**Testing**  
- Unit: Dropdown populates correctly.  
- Functional: Game switch updates context.  

---

### US-1906: Character Selection Dropdown
**As a** User  
**I want** a character selection dropdown on the right side of the top bar  
**So that** I can manage or switch characters easily.  

**Acceptance Criteria**  
- Dropdown lists all characters linked to the selected game.  
- Selecting a character sets active persona for queries.  
- Character management options: Add, Edit, Remove.  

**Testing**  
- Unit: Dropdown lists correct characters per game.  
- Functional: Switching updates active character state.  

---

## Epic E19.5 — UI Cleanup

### US-1907: Remove Bottom Bars
**As a** User  
**I want** unnecessary UI clutter removed  
**So that** interface is clean.  

**Acceptance Criteria**  
- Semi-hidden bar gone.  
- Phase indicator gone.  
- Only “Build ###” remains in top bar.  

**Testing**  
- Regression: Build number still shown.  
- Functional: No empty space left behind.  

---

## ✅ Definition of Done (FR-019)
- Logged-in status light working.  
- LCARS theme with light/dark toggle.  
- Query input works with Enter & button.  
- Token bar shows tier + rollover + bonus correctly.  
- Game selection dropdown implemented under token bar.  
- Character selection dropdown implemented on right side.  
- UI clutter removed (no semi-hidden bar, no phase indicator).  
- All unit, functional, regression, and security tests pass.  
