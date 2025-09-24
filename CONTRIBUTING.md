# Contributing to TTRPG Center

Thank you for your interest in contributing to TTRPG Center! This document provides guidelines for contributing to the MVP v2 implementation.

## Development Setup

### Prerequisites

- Python 3.12+
- Docker and Docker Compose
- Git

### Environment Setup

```bash
# Clone the repository
git clone <repository-url>
cd TTRPG_Center

# Initialize development environment
./scripts/init-environments.sh dev

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-test.txt

# Run development setup
./scripts/run-local.sh -Env dev
```

## Development Workflow

### 1. Create Feature Branch

```bash
git checkout -b feat/your-feature-name
```

### 2. Make Changes

Follow the coding standards defined in `MVP-Version-2/Coding-Standards-TTRPG-Center.md`:

- Python 3.12+ with type hints
- Black formatting (88 character line limit)
- Ruff linting
- Structured JSON logging
- Environment isolation

### 3. Testing

```bash
# Run unit tests
pytest tests/unit

# Run functional tests
pytest tests/functional

# Run security tests
bandit -r src_common

# Run all tests
pytest tests/unit tests/functional
```

### 4. Quality Checks

```bash
# Format code
black src_common services tests

# Lint code
ruff check src_common services tests

# Type checking
mypy src_common services
```

### 5. Commit Changes

Use conventional commit format:

```bash
git add .
git commit -m "feat: add user authentication system"
```

Commit types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Test additions or modifications
- `chore`: Maintenance tasks

### 6. Push and Create Pull Request

```bash
git push -u origin feat/your-feature-name
```

Create a pull request with:
- Clear title and description
- Link to relevant issues
- Test results and validation
- Breaking change notes (if any)

## Code Standards

### Architecture Principles

- **Environment Isolation**: All environments (dev/test/prod) must be completely isolated
- **Microservices**: Follow MVP v2 microservices architecture
- **Pass 0→G Pipeline**: Implement complete ingestion pipeline
- **Structured Logging**: Use MVP v2 JSON logging schema

### Code Quality

- **Type Safety**: All functions must have type hints
- **Error Handling**: Comprehensive error handling with logging
- **Testing**: Unit tests for all functions, functional tests for APIs
- **Documentation**: Docstrings for all public functions and classes

### File Organization

```
/
├── src_common/           # Shared libraries
├── services/            # Microservices
│   ├── ingest/         # Ingestion service
│   ├── orchestrator/   # Orchestration service
│   ├── admin_api/      # Admin API service
│   └── user_api/       # User API service
├── env/                # Environment isolation
│   ├── dev/           # Development environment
│   ├── test/          # Testing environment
│   └── prod/          # Production environment
└── tests/             # Test suites
```

### Environment Variables

Never commit secrets or API keys. Use environment variables:

```bash
# .env file (gitignored)
OPENAI_API_KEY=your_key_here
ASTRADB_APPLICATION_TOKEN=your_token_here
```

## Pull Request Process

### Review Criteria

1. **Code Quality**
   - Follows coding standards
   - Has appropriate tests
   - Includes type hints
   - Has proper error handling

2. **Architecture Compliance**
   - Maintains environment isolation
   - Follows microservices patterns
   - Uses structured logging
   - Implements proper security measures

3. **Testing**
   - All tests pass
   - Coverage meets requirements
   - Security tests pass
   - Integration tests validate end-to-end functionality

### Review Process

1. **Automated Checks**: CI pipeline runs tests and quality checks
2. **Code Review**: Maintainer reviews code for quality and architecture
3. **Testing**: Feature is tested in development environment
4. **Approval**: Two approvals required for merge
5. **Merge**: Squash and merge to main branch

## Issue Reporting

### Bug Reports

Use the bug report template and include:
- Environment details (dev/test/prod)
- Steps to reproduce
- Expected vs actual behavior
- Error logs and stack traces
- Screenshots (if UI related)

### Feature Requests

Use the feature request template and include:
- Problem statement
- Proposed solution
- Alternative solutions considered
- Acceptance criteria

## Security

- Report security vulnerabilities to security@ttrpg-center.local
- Do not open public issues for security vulnerabilities
- Follow secure coding practices
- Run security linting before submitting PRs

## Communication

- Use GitHub Discussions for questions and ideas
- Use GitHub Issues for bugs and feature requests
- Follow the code of conduct in all interactions

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

## Questions?

Feel free to open a GitHub Discussion or reach out to the maintainers for any questions about contributing.