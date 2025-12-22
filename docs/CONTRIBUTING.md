# Contributing to StatementXL

Thank you for your interest in contributing!

## Development Setup

1. Fork and clone the repository
2. Follow [INSTALL.md](./INSTALL.md) for setup
3. Create a feature branch: `git checkout -b feature/your-feature`

## Code Standards

### Python (Backend)
- Format with `black`
- Type hints required
- Docstrings for public functions
- Run `pylint` before committing

### TypeScript (Frontend)
- Format with Prettier
- ESLint rules enforced
- Functional components preferred
- Use TypeScript strict mode

## Pull Request Process

1. Update documentation if needed
2. Add tests for new features
3. Ensure all tests pass
4. Update CHANGELOG.md
5. Request review from maintainers

## Commit Messages

Use conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `refactor:` Code refactoring
- `test:` Tests
- `chore:` Maintenance

Example: `feat: add password reset email template`

## Testing

```bash
# Backend tests
python -m pytest tests/ -v --cov=backend

# Frontend tests
cd frontend && npm test
```

## Reporting Issues

Please include:
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment (OS, Python version, etc.)
- Logs if applicable
