# Docker Swarm Secrets Management

## Overview

This directory contains utilities for managing Docker Swarm secrets for the n8n TTRPG Center stack. Secrets provide secure storage for sensitive credentials like API keys, database passwords, and authentication tokens.

## Why Docker Secrets?

**Security Benefits:**
- **Encrypted at rest** - Secrets are encrypted in the Swarm cluster
- **Encrypted in transit** - TLS encryption when secrets are delivered to containers
- **Access control** - Only authorized services can access specific secrets
- **Audit trail** - Secret creation/deletion is logged
- **No plaintext files** - Eliminates `.env` files in version control

**Operational Benefits:**
- **Centralized management** - Single source of truth for credentials
- **Easy rotation** - Update secrets without rebuilding images
- **Service isolation** - Each service only sees its required secrets
- **Multi-node ready** - Secrets replicated across Swarm nodes

## Quick Start

### 1. Initialize Secrets

```bash
# From existing .env file
cd secrets
./create_secrets.sh --from-env-file ../.env

# Interactive mode (prompts for each secret)
./create_secrets.sh
```

### 2. Verify Secrets

```bash
# List all secrets
docker secret ls

# Inspect secret metadata (cannot view actual value)
docker secret inspect openai_api_key
```

### 3. Deploy Stack with Secrets

```bash
cd ..
docker stack deploy -c docker-stack-n8n_TTRPG.yml ttrpg
```

## Secret Definitions

| Secret Name | Description | Used By | Format |
|------------|-------------|---------|--------|
| `openai_api_key` | OpenAI API key for embeddings | pass_d_hayhooks.py, gate_1_* scripts | `sk-proj-...` |
| `neo4j_user` | Neo4j username | neo4j service, ingestion scripts | String |
| `neo4j_password` | Neo4j password | neo4j service, ingestion scripts | String |
| `postgres_user` | PostgreSQL username | postgres service | String |
| `postgres_password` | PostgreSQL password | postgres service | String |
| `postgres_db` | PostgreSQL database name | postgres service | String |

## Scripts

### create_secrets.sh

Initializes Docker secrets from environment variables or interactive prompts.

**Usage:**
```bash
./create_secrets.sh [--from-env-file FILE] [--force]
```

**Options:**
- `--from-env-file FILE` - Load secrets from .env file (default: `../.env`)
- `--force` - Recreate existing secrets (requires manual removal first)
- `-h, --help` - Show help message

**Examples:**
```bash
# Create from .env file
./create_secrets.sh --from-env-file ../.env

# Interactive mode
./create_secrets.sh

# From custom location
./create_secrets.sh --from-env-file /secure/location/.env
```

### rotate_secrets.sh

Safely rotates secrets by creating new versions and updating services.

**Usage:**
```bash
./rotate_secrets.sh <secret_name> [--new-value VALUE] [--from-stdin]
```

**Options:**
- `--new-value VALUE` - New secret value (prompts if not provided)
- `--from-stdin` - Read new value from stdin
- `--stack-name NAME` - Stack name (default: `ttrpg`)
- `-h, --help` - Show help message

**Examples:**
```bash
# Interactive rotation
./rotate_secrets.sh openai_api_key

# With new value
./rotate_secrets.sh neo4j_password --new-value "new-secure-password-here"

# From stdin (for automation)
echo "new-api-key" | ./rotate_secrets.sh openai_api_key --from-stdin
```

## Secret Rotation Procedures

### Quarterly Rotation (Recommended)

1. **Generate new credentials**
   ```bash
   # Generate secure password
   NEW_PASSWORD=$(openssl rand -base64 32)
   echo $NEW_PASSWORD  # Save securely before rotating
   ```

2. **Rotate secret**
   ```bash
   ./rotate_secrets.sh <secret_name> --new-value "$NEW_PASSWORD"
   ```

3. **Update external services**
   - For OpenAI: Generate new key in OpenAI dashboard, rotate
   - For databases: Update passwords in database after rotation
   - For internal secrets: Rotation handles all updates

4. **Verify services**
   ```bash
   docker service ls
   docker service logs ttrpg_ingestion_engine
   ```

### Emergency Rotation (Security Incident)

If a secret is compromised:

1. **Immediate removal**
   ```bash
   docker secret rm <compromised_secret>
   ```

2. **Service update**
   ```bash
   # Services will restart and fail (expected)
   docker service ls
   ```

3. **Create new secret**
   ```bash
   echo -n "new-secure-value" | docker secret create <secret_name> -
   ```

4. **Redeploy stack**
   ```bash
   docker stack deploy -c docker-stack-n8n_TTRPG.yml ttrpg
   ```

5. **Verify recovery**
   ```bash
   docker service ls  # All services should be running
   ```

## Security Best Practices

### Secret Creation

1. **Use strong passwords**
   ```bash
   # Generate 32-character password
   openssl rand -base64 32

   # Generate 64-character password
   openssl rand -base64 48
   ```

2. **Never commit .env files**
   ```bash
   # Verify .gitignore
   cat ../.gitignore | grep ".env"

   # Check for accidental commits
   git log --all --full-history -- ../.env
   ```

3. **Secure .env file permissions**
   ```bash
   chmod 600 ../.env
   ls -la ../.env  # Should show -rw-------
   ```

### Secret Storage

1. **Backup secrets securely**
   - Use password manager (1Password, LastPass, Bitwarden)
   - Encrypted vault (GPG, age)
   - Secure cloud storage (AWS Secrets Manager, HashiCorp Vault)

2. **Never store secrets in:**
   - Version control (Git)
   - Unencrypted files
   - Shared drives
   - Chat applications
   - Documentation

### Access Control

1. **Limit secret visibility**
   ```yaml
   # In docker-stack.yml
   services:
     service_name:
       secrets:
         - openai_api_key  # Only secrets needed
   ```

2. **Use service-specific secrets**
   - Create separate secrets for different services when possible
   - Example: `n8n_postgres_password` vs `ingestion_postgres_password`

3. **Audit secret access**
   ```bash
   # View which services use a secret
   docker service inspect <service_name> | grep SecretName

   # View secret metadata
   docker secret inspect <secret_name>
   ```

## Troubleshooting

### Secret Not Found

**Symptoms:** Service fails with "secret not found" error

**Solution:**
```bash
# Check if secret exists
docker secret ls | grep <secret_name>

# Create missing secret
./create_secrets.sh

# Redeploy service
docker service update --force ttrpg_<service_name>
```

### Secret Cannot Be Updated

**Symptoms:** `docker secret create` fails with "already exists"

**Solution:**
```bash
# Secrets are immutable - must remove and recreate
docker secret rm <secret_name>
docker secret create <secret_name> -

# Or use rotation script
./rotate_secrets.sh <secret_name>
```

### Service Cannot Access Secret

**Symptoms:** Application logs show "permission denied" or "secret file not found"

**Solution:**
```bash
# Verify secret is mounted in service
docker service inspect ttrpg_<service_name> | grep -A 5 Secrets

# Check secret exists
docker secret ls | grep <secret_name>

# Update service with correct secret
docker service update --secret-add <secret_name> ttrpg_<service_name>
```

### Secrets Not Persisting After Swarm Restart

**Symptoms:** Secrets disappear after `docker swarm leave`

**Solution:**
```bash
# Secrets are Swarm-specific - backup before leaving Swarm
docker secret ls --format '{{.Name}}' > secret_names.txt

# After rejoining Swarm, recreate secrets
./create_secrets.sh --from-env-file ../.env
```

## Migration from .env to Secrets

### Step-by-Step Migration

1. **Backup existing .env**
   ```bash
   cp ../.env ../.env.backup
   chmod 600 ../.env.backup
   ```

2. **Initialize Swarm** (if not already done)
   ```bash
   docker swarm init
   ```

3. **Create secrets**
   ```bash
   ./create_secrets.sh --from-env-file ../.env
   ```

4. **Update Python scripts** (already done in this migration)
   - Scripts now read from `/run/secrets/<secret_name>`
   - Fallback to environment variables for backward compatibility

5. **Deploy with Swarm stack**
   ```bash
   docker stack deploy -c docker-stack-n8n_TTRPG.yml ttrpg
   ```

6. **Verify services**
   ```bash
   docker service ls
   docker service logs ttrpg_ingestion_engine
   ```

7. **Secure .env file**
   ```bash
   # Move to secure location
   mv ../.env /secure/location/.env.ttrpg_backup

   # Or securely delete
   shred -u ../.env  # Linux
   # rm -P ../.env     # macOS
   ```

## Additional Resources

- [Docker Secrets Documentation](https://docs.docker.com/engine/swarm/secrets/)
- [Docker Swarm Security Best Practices](https://docs.docker.com/engine/swarm/secrets/#security)
- [OpenAI API Key Best Practices](https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety)

## Support

For issues with secrets management:
1. Check service logs: `docker service logs ttrpg_<service_name>`
2. Review secret permissions: `docker secret inspect <secret_name>`
3. Verify Swarm status: `docker info | grep Swarm`
4. See troubleshooting section above

For security incidents:
1. Immediately rotate compromised secrets
2. Review service logs for unauthorized access
3. Update access controls
4. Document incident for audit trail
