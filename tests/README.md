# Test Suite

This directory contains the test suite for the OptionsKit Backend API.

## Test Structure

- `conftest.py` - Shared fixtures and test configuration
- `test_health.py` - Health check endpoints
- `test_version.py` - Version API endpoint
- `test_chain.py` - Options chain endpoint
- `test_expirations.py` - Options expirations endpoint
- `test_occ_symbols.py` - OCC symbols endpoints
- `test_integration.py` - Integration tests

## Running Tests

### Install Test Dependencies

```bash
pip install -r requirements-dev.txt
```

### Run All Tests

```bash
pytest tests/ -v
```

### Run Specific Test File

```bash
pytest tests/test_health.py -v
```

### Run with Coverage

```bash
pytest tests/ -v --cov=app --cov-report=html
```

This will generate an HTML coverage report in `htmlcov/index.html`.

### Run Specific Test

```bash
pytest tests/test_health.py::test_healthz -v
```

## Test Strategy

- **Unit Tests**: Test individual endpoints with mocked external APIs
- **Integration Tests**: Test critical paths and workflows
- **Mocking**: External APIs (Tradier, OCC) are mocked to avoid rate limits and external dependencies

## CI/CD

Tests run automatically on:
- Every push to `master` or `main`
- Every pull request
- Manual trigger via GitHub Actions

Tests must pass before deployment to AWS App Runner.

