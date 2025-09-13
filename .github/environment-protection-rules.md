# GitHub Environment Protection Rules Configuration

This document describes the required GitHub environment protection rules for the TTRPG Center CI/CD pipeline.

## Environment Configuration

### 1. `dev` Environment

**Purpose**: Development environment for continuous deployment from main branch.

**Protection Rules**:
- **Deployment branches**: `main` only
- **Required reviewers**: None (automatic deployment)
- **Wait timer**: None
- **Environment variables**:
  - `CONTAINER_IMAGE`: Set by workflow
  - `DATABASE_URL`: Development database connection
  - `LOG_LEVEL`: `DEBUG`

**Configuration Steps**:
1. Go to repository Settings → Environments
2. Create environment named `dev`
3. Set deployment branches to `main` only
4. No additional protection rules needed

### 2. `test` Environment

**Purpose**: Testing environment for manual promotions with approval.

**Protection Rules**:
- **Deployment branches**: `main` only
- **Required reviewers**: 1 reviewer (team lead or senior developer)
- **Wait timer**: None
- **Environment variables**:
  - `CONTAINER_IMAGE`: Set by workflow
  - `DATABASE_URL`: Test database connection
  - `LOG_LEVEL`: `INFO`

**Configuration Steps**:
1. Go to repository Settings → Environments
2. Create environment named `test`
3. Set deployment branches to `main` only
4. Enable "Required reviewers" and add 1 reviewer
5. Add team members who can approve TEST deployments

### 3. `test-promotion` Environment

**Purpose**: Approval gate for promotions to TEST environment.

**Protection Rules**:
- **Deployment branches**: `main` only
- **Required reviewers**: 1 reviewer (different from deployer)
- **Wait timer**: None
- **Prevent self-review**: Enabled

**Configuration Steps**:
1. Go to repository Settings → Environments
2. Create environment named `test-promotion`
3. Set deployment branches to `main` only
4. Enable "Required reviewers" and add 1 reviewer
5. Enable "Prevent self-review"

### 4. `rollback-approval` Environment

**Purpose**: Approval gate for rollback operations.

**Protection Rules**:
- **Deployment branches**: Any branch
- **Required reviewers**: 1 reviewer (ops team member)
- **Wait timer**: None
- **Environment variables**:
  - Emergency contact information
  - Escalation procedures

**Configuration Steps**:
1. Go to repository Settings → Environments
2. Create environment named `rollback-approval`
3. Allow deployments from any branch
4. Enable "Required reviewers" and add ops team members
5. Add environment variables for emergency procedures

### 5. `prod` Environment (Future)

**Purpose**: Production environment (not yet implemented).

**Protection Rules**:
- **Deployment branches**: `main` only
- **Required reviewers**: 2 reviewers (ops team + tech lead)
- **Wait timer**: 30 minutes (business hours only)
- **Prevent self-review**: Enabled
- **Environment variables**:
  - Production database connections
  - API keys for production services
  - Monitoring and alerting configuration

**Configuration Steps** (when ready):
1. Go to repository Settings → Environments
2. Create environment named `prod`
3. Set deployment branches to `main` only
4. Enable "Required reviewers" and add 2 reviewers
5. Set wait timer to 30 minutes
6. Enable "Prevent self-review"
7. Configure production environment variables

## Reviewer Assignment

### Recommended Reviewer Groups

1. **Development Team**
   - Senior developers
   - Team leads
   - Can approve: `test-promotion`

2. **Operations Team**
   - DevOps engineers
   - Site reliability engineers
   - Can approve: `rollback-approval`, `prod`

3. **Security Team**
   - Security engineers
   - Can approve: `prod` (for security-sensitive deployments)

### Best Practices

1. **No Self-Approval**: Deployer cannot approve their own deployment
2. **Cross-Team Review**: Different teams review different environments
3. **Emergency Procedures**: Clear escalation path for urgent rollbacks
4. **Documentation**: All approvals should include justification comments

## Environment Variables Configuration

### Security Considerations

1. **Secrets Management**
   - Use GitHub Secrets for sensitive values
   - Environment-specific secrets (e.g., `DEV_DATABASE_PASSWORD`)
   - Never store secrets in environment variables visible in logs

2. **Variable Naming Convention**
   ```
   Environment-specific: {ENV}_{SERVICE}_{SETTING}
   Examples:
   - DEV_POSTGRES_PASSWORD
   - TEST_REDIS_URL
   - PROD_API_KEY
   ```

3. **Required Variables by Environment**

   **DEV Environment**:
   - `POSTGRES_PASSWORD`
   - `MONGO_URI`
   - `NEO4J_PASSWORD`
   - `REDIS_URL`
   - `OPENAI_API_KEY`
   - `ANTHROPIC_API_KEY`

   **TEST Environment**:
   - `TEST_POSTGRES_PASSWORD`
   - `TEST_MONGO_URI`
   - `TEST_NEO4J_PASSWORD`
   - `TEST_REDIS_URL`
   - `OPENAI_API_KEY` (shared or separate)
   - `ANTHROPIC_API_KEY` (shared or separate)

## Workflow Integration

### Environment Usage in Workflows

1. **CI Workflow (`ci.yml`)**
   - No environment protection (runs on all PRs)
   - Uses repository secrets only

2. **Release Workflow (`release.yml`)**
   - Uses `dev` environment for automatic deployment
   - No manual approval required

3. **Promote Workflow (`promote.yml`)**
   - Uses `test-promotion` environment for approval gate
   - Uses `test` environment for actual deployment

4. **Rollback Workflow (`rollback.yml`)**
   - Uses `rollback-approval` environment for approval gate
   - Uses target environment (`dev` or `test`) for execution

### Environment Protection Benefits

1. **Controlled Deployments**: Prevents unauthorized deployments
2. **Audit Trail**: All deployments tracked with approver information
3. **Risk Mitigation**: Human oversight for critical operations
4. **Compliance**: Meets regulatory requirements for change control

## Setup Instructions

### Step 1: Create Environments

1. Navigate to repository Settings
2. Click on "Environments" in the left sidebar
3. Click "New environment"
4. Create each environment listed above

### Step 2: Configure Protection Rules

For each environment:

1. Click on the environment name
2. Configure deployment branches
3. Add required reviewers
4. Set wait timers if needed
5. Enable additional protection rules

### Step 3: Add Environment Variables

1. In each environment configuration
2. Click "Add secret" or "Add variable"
3. Add necessary configuration values
4. Use GitHub Secrets for sensitive data

### Step 4: Assign Reviewers

1. Add team members as reviewers
2. Ensure proper access levels
3. Test approval workflows

### Step 5: Test Configuration

1. Create test deployment
2. Verify approval requirements work
3. Test rollback procedures
4. Validate environment isolation

## Troubleshooting

### Common Issues

1. **Missing Reviewers**: Ensure reviewers have repository access
2. **Branch Restrictions**: Verify deployment branch settings
3. **Variable Access**: Check environment variable visibility
4. **Approval Delays**: Set up proper notification preferences

### Emergency Procedures

1. **Bypass Protection**: Repository admins can force deployments
2. **Emergency Contacts**: Maintain up-to-date contact information
3. **Escalation Path**: Clear procedures for urgent approvals
4. **Rollback Authority**: Designated emergency rollback approvers

---

**Last Updated**: 2025-09-12
**Document Version**: 1.0
**Next Review**: 2025-10-12