# Documentation Index

Detailed reference documentation for the n8n TTRPG Center project.

## Documentation Structure

The documentation has been split into focused reference guides to optimize AI context loading while maintaining comprehensive coverage.

### Main Documentation

**[../CLAUDE.md](../CLAUDE.md)** - Essential context for AI assistants
- Project overview and architecture
- Quick reference commands
- Port mappings and service access
- Common workflows
- Pointers to detailed documentation

**Size:** ~8.6 KB (optimized for AI context)

### Detailed Reference Guides

**[ingestion-pipeline.md](ingestion-pipeline.md)** - Complete pipeline documentation
- Gate 0: File validation and hashing
- Pass A: TOC extraction and metadata
- Pass B: Document splitting
- Pass C: Full document processing
- Pass D: Vector embeddings
- Pass E: Knowledge graph construction
- Configuration system reference

**Size:** ~17.7 KB

**[scripts-reference.md](scripts-reference.md)** - Script usage examples
- Document splitter tool (doc_splitter)
- Database manager (db_manager.py)
- Complete workflow examples
- Integration patterns

**Size:** ~11.2 KB

**[docker-commands.md](docker-commands.md)** - Docker operations reference
- Stack management commands
- Service control
- Container access patterns
- Database operations
- Logging and debugging
- Cleanup and maintenance
- Backup and restore procedures

**Size:** ~13.4 KB

**[troubleshooting.md](troubleshooting.md)** - Problem-solving guide
- Docker and container issues
- Custom n8n node problems
- Database connection errors
- Transfer Station issues
- LangFlow troubleshooting
- Configuration problems
- General debugging techniques

**Size:** ~11.8 KB

## Usage for AI Assistants

### Primary Context (Always Loaded)
- **CLAUDE.md** - Core context with essential information

### On-Demand References (Load as Needed)
When working on specific tasks, AI assistants can read the relevant detailed documentation:

- **Pipeline development** → Read `ingestion-pipeline.md`
- **Docker operations** → Read `docker-commands.md`
- **Script usage** → Read `scripts-reference.md`
- **Debugging issues** → Read `troubleshooting.md`

### Benefits of This Structure

**Memory Efficiency:**
- Primary context reduced from 48 KB → 8.6 KB (82% reduction)
- Detailed docs only loaded when needed
- Faster context loading and processing

**Maintainability:**
- Each document has a single, focused purpose
- Easier to update specific sections
- No duplication across files

**Accessibility:**
- All information still available
- Clear organization and navigation
- Comprehensive coverage maintained

## Quick Navigation

### By Task Type

**Setting up the project:**
- CLAUDE.md → Project Overview
- docker-commands.md → Stack Management

**Running the ingestion pipeline:**
- CLAUDE.md → Ingestion Pipeline Overview
- ingestion-pipeline.md → Detailed pass documentation
- scripts-reference.md → Complete workflow examples

**Troubleshooting issues:**
- troubleshooting.md → Issue-specific solutions
- docker-commands.md → Logging and Debugging

**Custom node development:**
- CLAUDE.md → Custom n8n Node section
- docker-commands.md → Custom Node Development
- troubleshooting.md → Custom n8n Node problems

**Database operations:**
- CLAUDE.md → Database Access (quick reference)
- docker-commands.md → Database Operations (comprehensive)
- scripts-reference.md → Database Manager tool

## Contributing to Documentation

When updating documentation:

1. **CLAUDE.md** - Only essential context and quick references
2. **Detailed guides** - Comprehensive examples and explanations
3. **Keep consistent** - Cross-reference between documents
4. **Test accessibility** - Verify AI assistants can find information easily

## File Sizes Summary

| File | Size | Purpose |
|------|------|---------|
| CLAUDE.md | 8.6 KB | AI context (always loaded) |
| ingestion-pipeline.md | 17.7 KB | Pipeline reference |
| scripts-reference.md | 11.2 KB | Script examples |
| docker-commands.md | 13.4 KB | Docker operations |
| troubleshooting.md | 11.8 KB | Problem solving |
| **Total** | **62.7 KB** | Complete documentation |

**Context Optimization:** 82% reduction in primary context size while maintaining 100% information coverage.
