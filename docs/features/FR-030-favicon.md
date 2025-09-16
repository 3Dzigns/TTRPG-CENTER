# Feature Request: FR-030-favicon

## Title

Convert favicon.png to favicon.ico and update DEV environment URL

## Description

The current favicon is stored as `features/favicon.png`. We need to
ensure that the application uses a `.ico` file for compatibility across
browsers and update the development environment URL to use this favicon.

## User Stories

### US-301

**As a** developer\
**I want** to convert the existing `favicon.png` to `favicon.ico`\
**So that** the project has a standard browser-compatible favicon
format.

**Acceptance Criteria** - Conversion process is documented and
repeatable. - `favicon.ico` is generated from `features/favicon.png` and
stored at the project root.

### US-302

**As a** user in the DEV environment\
**I want** the website toolbar to display the TTRPG Center favicon.ico\
**So that** I can easily identify the application tab.

**Acceptance Criteria** - The DEV environment references `/favicon.ico`
in the `<head>` of the HTML. - Browser toolbar shows the icon when
running in DEV (`http://localhost:8000`).

## Technical Notes

-   Use Python or Node-based tooling to automate conversion from PNG to
    ICO.
-   Update base HTML template or framework config to use `/favicon.ico`
    path in DEV.
-   Ensure no cache issues (Phase 0 cache policy respected).

## Test Cases

### Unit Tests

-   Verify that `favicon.ico` exists at project root after build.
-   Validate favicon format is `.ico` with correct resolution (16x16,
    32x32).

### Functional Tests

-   Launch DEV environment → favicon loads in browser tab.
-   Clear cache and refresh → favicon.ico loads consistently.

### Regression Tests

-   No change to favicon references in TEST or PROD environments unless
    explicitly configured.
-   Favicon remains consistent after cache refresh toggle.

### Security Tests

-   Ensure favicon.ico does not expose metadata or unnecessary EXIF
    data.

## Definition of Done

-   `favicon.png` converted to `favicon.ico` stored at root.
-   DEV environment updated to use favicon.ico in the `<head>` link tag.
-   All unit, functional, regression, and security tests pass in CI.
