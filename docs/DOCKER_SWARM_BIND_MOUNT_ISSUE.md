# Docker Swarm Bind Mount Issue on Windows

**Date**: 2025-10-23
**Status**: ⚠️ BLOCKER IDENTIFIED

## Issue Summary

Docker Swarm services fail to schedule on Windows/Docker Desktop due to bind mount configuration limitations.

## Root Cause

Docker Swarm on Docker Desktop (Windows/WSL2) has **critical limitations with bind mounts** that prevent services from being scheduled to nodes.

### Symptoms

- Services stuck in "New" state indefinitely
- Tasks show "created" status but never progress
- No containers actually start (0/1 replicas)
- No node assignment happens
- Simple services without bind mounts work fine

### Technical Details

```bash
# Test Results:
✅ Docker Swarm active and healthy
✅ Node ready and available (docker-desktop)
✅ Images built successfully
✅ Secrets created correctly
✅ Network overlay created
✅ Simple alpine service schedules and runs
❌ Services with bind mounts stuck in "New" state
❌ No node assignment for stack services
```

### Stack Configuration Issue

The stack uses bind mounts for Transfer Station shared directory:

```yaml
volumes:
  - type: bind
    source: E:/n8n_TTRPG_Transfer_Station
    target: /Transfer_Station
```

**Problem**: Docker Swarm on single-node Windows does not reliably support bind mounts. The scheduler fails to assign tasks to nodes when bind mounts are present.

## Solutions

### Option 1: Use Docker Compose Instead (RECOMMENDED for Windows)

Docker Compose handles bind mounts correctly on Windows. This is the recommended approach for local development.

**Advantages**:
- ✅ Full bind mount support
- ✅ Easier debugging and logs
- ✅ Faster startup
- ✅ No node scheduling issues

**Create**: `docker-compose-ttrpg.yml` (based on stack yml, remove swarm-specific configs)

**Commands**:
```bash
docker compose -f docker-compose-ttrpg.yml up -d
docker compose -f docker-compose-ttrpg.yml down
```

### Option 2: Convert Bind Mounts to Named Volumes

Replace bind mounts with Docker volumes managed by the volume driver.

**Advantages**:
- ✅ Swarm compatible
- ✅ Better portability
- ❌ Loses direct filesystem access

**Change Required**:
```yaml
# Before
volumes:
  - type: bind
    source: E:/n8n_TTRPG_Transfer_Station
    target: /Transfer_Station

# After
volumes:
  - transfer_station:/Transfer_Station

# Add to volumes section
volumes:
  transfer_station:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: E:/n8n_TTRPG_Transfer_Station
```

### Option 3: Multi-Node Swarm with NFS

Deploy on multi-node swarm with shared storage (NFS/SMB).

**Advantages**:
- ✅ True production swarm
- ✅ Shared storage across nodes
- ❌ Complex setup
- ❌ Requires additional infrastructure

### Option 4: Manual Container Deployment

Deploy each service individually with `docker service create` and specify bind mounts.

**Advantages**:
- ✅ Fine-grained control
- ❌ Manual management
- ❌ No stack orchestration

## Recommendation

**For Windows Development**: Use **Docker Compose** (Option 1)
- Best compatibility with Windows paths
- Easier debugging and management
- Identical service definitions (just remove swarm configs)

**For Production**: Use **multi-node swarm with NFS** (Option 3)
- True orchestration and scaling
- High availability
- Proper shared storage

## Current Status

The consolidated `docker-stack-ttrpg.yml` is complete and tested, but **cannot deploy on Windows Docker Desktop** due to bind mount limitations.

## Next Steps

User needs to decide:

1. **Convert to Docker Compose** for Windows development?
2. **Remove bind mounts** and use volumes instead?
3. **Deploy to Linux** or multi-node swarm?

## References

- Docker Swarm Bind Mount Limitations: https://docs.docker.com/engine/swarm/configs/#use-bind-mounts-volumes-or-tmpfs-mounts
- Docker Desktop Windows: https://docs.docker.com/desktop/install/windows-install/

---

**Prepared by**: Claude Code
**Severity**: High - Blocks deployment
**Impact**: All 12 services affected
