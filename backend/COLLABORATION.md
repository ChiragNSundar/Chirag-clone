# Backend Collaboration Guidelines

## Coding Standards
- **Type Hints**: All functions must have type hints.
- **Docstrings**: Google-style docstrings for all modules and functions.
- **Error Handling**: Use `try/except` blocks in Service layers; let Routes handle HTTP exceptions.

## Git Workflow
1. Create a feature branch: `feature/your-feature-name`
2. Commit changes with conventional commits (e.g., `feat: add ollama support`).
3. Open a PR and request review.

## Testing
- **Unit Tests**: Required for all new services.
- **Integration Tests**: Required for new API endpoints.
- **Visual Tests**: Run `npm run test:e2e` in frontend for UI changes.

## Service Pattern
We use a Singleton pattern for services.
```python
_service = None
def get_service():
    if _service is None:
        _service = Service()
    return _service
```
Always access services via their `get_` accessor.
