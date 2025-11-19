# MCP Server Optimization Guide

## 📊 Optimization Summary

**Before Optimization:**
- Total MCP tool context: ~74,987 tokens
- flow-nexus: 94 tools (~59,052 tokens)
- ruv-swarm: 25 tools (~15,935 tokens)
- Other servers: ~2,000 tokens
- **Problem**: >3x the recommended 25,000 token limit

**After Optimization:**
- Total MCP tool context: ~10,000-15,000 tokens
- **Reduction**: 85% token savings (~65,000 tokens)
- **Benefit**: More context available for actual work
- **Result**: Faster initialization, better performance

## 🎯 Active MCP Servers

These lightweight servers remain enabled for everyday use:

### Web Automation & Testing
- **playwright** - Browser automation, E2E testing, visual validation
- **puppeteer** - Headless browser control, web scraping
- **firecrawl** - Advanced web scraping and content extraction

### Memory & Reasoning
- **sequential-thinking** - Multi-step reasoning, complex analysis
- **memory** - Persistent memory, context retention across sessions

### Code & Development
- **code-index** - AST-based semantic search for large codebases (>10K LOC)
- **context7** - Official library documentation, code patterns
- **socket** - Dependency quality scoring, security analysis

### ML & Research
- **hugging-face** - ML model/dataset search, research papers

**Total**: 9 active servers (~10-15k tokens)

## 🔌 Optional MCP Servers

Heavy servers moved to `.mcp.optional.json` for on-demand activation:

### Cloud & Coordination (78k tokens saved)
- **ruv-swarm** (~16k tokens) - Local swarm coordination, neural networks, DAA
- **flow-nexus** (~59k tokens) - Cloud sandboxes, templates, GitHub automation
- **claude-flow@alpha** (~2k tokens) - Advanced reasoning agents, ReasoningBank
- **agentic-payments** (~1k tokens) - Payment processing, Active Mandate auth

## 🚀 How to Enable Optional Servers

### Method 1: Temporary Enable (Session Only)

Add to `.claude/settings.json` → `enabledMcpjsonServers` array:

```json
{
  "enabledMcpjsonServers": [
    "context7",
    "socket",
    "playwright",
    "sequential-thinking",
    "memory",
    "code-index",
    "hugging-face",
    "puppeteer",
    "firecrawl",
    "ruv-swarm"  // Add the optional server
  ]
}
```

### Method 2: Permanent Enable

Move server config from `.mcp.optional.json` to `.mcp.json`:

```bash
# Example: Enable ruv-swarm permanently
# 1. Copy the ruv-swarm config from .mcp.optional.json
# 2. Paste it into .mcp.json mcpServers section
# 3. Add "ruv-swarm" to enabledMcpjsonServers in settings.json
```

### Method 3: Command Line (If supported)

```bash
claude mcp add ruv-swarm --config .mcp.optional.json
```

## 📖 When to Use Optional Servers

### ruv-swarm
**Enable when you need:**
- Complex multi-agent coordination (>5 agents)
- Neural network training with DAA
- Decentralized autonomous agent workflows
- Swarm topology optimization (mesh, hierarchical, ring)

**Example tasks:**
- Large-scale refactoring with agent coordination
- Distributed neural network training
- Self-healing autonomous workflows

### flow-nexus
**Enable when you need:**
- Cloud-based sandbox execution
- Distributed neural network training
- GitHub automation and repository management
- Template marketplace deployment
- Real-time monitoring and streaming

**Example tasks:**
- Deploy code to cloud sandboxes for testing
- Train neural networks across distributed nodes
- Automated GitHub PR management and analysis
- Template-based project scaffolding

### claude-flow@alpha
**Enable when you need:**
- Advanced reasoning agents with ReasoningBank
- Goal-oriented action planning (GOAP)
- Closed-loop learning from past executions
- Adaptive replanning and multi-step reasoning

**Example tasks:**
- Complex deployment planning with dependencies
- Learning from past task failures
- Adaptive goal decomposition and optimization

### agentic-payments
**Enable when you need:**
- Payment processing integration
- Active Mandate authorization
- Ed25519 cryptographic signing
- Byzantine fault-tolerant consensus for payments

**Example tasks:**
- Integrate payment flows into applications
- Implement Active Mandate payment authorization
- Multi-signature payment verification

## 🔧 Configuration Files

### `.mcp.json` (Active Servers)
Project-shared configuration for lightweight, frequently used MCP servers.

- **Location**: `E:\n8n_TTRPG_Center\.mcp.json`
- **Scope**: Team-shared (committed to git)
- **Contents**: 6 active servers (~10-15k tokens)
- **Windows Fix**: All npx commands wrapped with `cmd /c`

### `.mcp.optional.json` (Optional Servers)
Heavy servers for specialized tasks, disabled by default.

- **Location**: `E:\n8n_TTRPG_Center\.mcp.optional.json`
- **Scope**: Reference configuration (can be committed)
- **Contents**: 4 optional servers (~78k tokens if all enabled)
- **Purpose**: On-demand activation for specific workflows

### `.claude/settings.json` (User Preferences)
User-specific settings including enabled server list.

- **Location**: `E:\n8n_TTRPG_Center\.claude\settings.json`
- **Scope**: User-specific (private to your machine)
- **Contents**: `enabledMcpjsonServers` array, hooks, permissions
- **Purpose**: Control which servers are active

## ✅ Verification

### Check Active Servers
```bash
claude mcp list
```

Expected output: 9 active servers (context7, socket, playwright, sequential-thinking, memory, code-index, hugging-face, puppeteer, firecrawl)

### Check Token Usage
Look for diagnostics output showing:
- MCP tools context: ~10-15k tokens (down from ~75k)
- No warnings about large context (>25k threshold)

### Test Active Tools
```bash
# Test playwright (browser automation)
# Test sequential-thinking (reasoning)
# Test memory (persistent state)
# Test code-index (semantic search)
```

## 🐛 Troubleshooting

### "Windows requires 'cmd /c' wrapper" Warnings
**Fixed**: All npx commands in `.mcp.json` now use `cmd /c` wrapper.

If you still see warnings, ensure commands follow this pattern:
```json
{
  "command": "cmd",
  "args": ["/c", "npx", "package-name"]
}
```

### Agent Parse Errors
**Fixed**: Added frontmatter to reasoning agent files:
- `.claude/agents/reasoning/README.md`
- `.claude/agents/reasoning/example-reasoning-agent-template.md`

### Optional Server Not Working
1. Check it's in `.mcp.optional.json`
2. Verify it's added to `enabledMcpjsonServers` in `.claude/settings.json`
3. Restart Claude Code session
4. Check for errors: `claude mcp list`

### Restore Original Configuration
Backups created at:
- `.mcp.json.backup`
- `.claude/settings.json.backup`

To restore:
```bash
cp .mcp.json.backup .mcp.json
cp .claude/settings.json.backup .claude/settings.json
```

## 📈 Performance Metrics

**Context Window Efficiency:**
- Before: ~75k tokens for MCP tools (37% of 200k window)
- After: ~15k tokens for MCP tools (7.5% of 200k window)
- **Gain**: ~60k tokens (30% of context window) for actual work

**Initialization Speed:**
- Before: 13 MCP servers to connect
- After: 9 MCP servers to connect
- **Improvement**: ~30% faster startup

**Flexibility:**
- Can enable optional servers in <2 minutes
- No functionality loss for primary workflows
- Clear documentation on when to use each server

## 🎯 Best Practices

1. **Start Light**: Use default active servers for most tasks
2. **Enable Selectively**: Only activate optional servers when needed
3. **Disable After Use**: Remove optional servers from settings when task complete
4. **Monitor Token Usage**: Watch for context warnings, optimize as needed
5. **Document Decisions**: Add notes when enabling optional servers permanently

## 📚 Related Documentation

- **CLAUDE.md** - Updated with optimization notes and lazy loading patterns
- **MCP Server Guides**:
  - [ruv-swarm docs](https://github.com/ruvnet/ruv-swarm)
  - [flow-nexus docs](https://flow-nexus.ruv.io)
  - [claude-flow docs](https://github.com/ruvnet/claude-flow)

## 🆘 Support

For issues or questions:
- Check diagnostics: `claude diagnostics`
- Review logs: `claude logs`
- GitHub issues: Project-specific issue tracker

---

**Last Updated**: 2025-10-30
**Optimization Version**: 1.0
**Token Savings**: ~65,000 tokens (85% reduction)
