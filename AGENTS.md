# AGENTS.md - Development Guidelines for News Reader Project

This document provides guidelines for agentic coding assistants working on the news reader project. It covers build/lint/test commands and code style conventions.

## Project Overview

This is a Python-based RSS feed reader and web scraper that summarizes articles using various AI models. It processes RSS feeds, websites, and YouTube content, generating consolidated news overviews.

### Key Files
- `nwsreader.py`: Main application with modular architecture
- `sources.txt`: RSS feeds and website URLs (simple text format, preferred)
- `sources.json`: Structured JSON format (advanced features)
- `settings.json`: Configuration file
- `requirements.txt`: Python dependencies

### Sources Format
The application supports both sources formats for maximum flexibility:

- **`sources.txt`** (recommended): Simple text format, easy to edit
- **`sources.json`**: Advanced JSON format with groups, channels, and prompts

Priority order: JSON → TXT (whichever exists first is used)

### Migration
To convert `sources.txt` to `sources.json` format:
```bash
python3 migrate_sources.py
```

### Error Handling
The application provides clear error messages when issues occur:
- **JSON parsing errors**: Specific error messages with troubleshooting tips
- **Ollama connection errors**: "Cannot connect to Ollama server at [host]:11434"
- **Model not found**: "Model '[model]' not found" with installation instructions
- **Timeout errors**: Clear timeout messages with duration
- **Graceful degradation**: Articles are skipped but not marked complete for retry

## Code Style Guidelines

### General Principles
- Write readable, maintainable code
- Follow PEP 8 style guide
- Use 4 spaces for indentation (never tabs)
- Keep lines under 88 characters (Black default)
- Use docstrings for all public functions
- Add comments for complex logic

## Testing Commands

### Setup Testing Environment
```bash
# Install testing dependencies
pip install pytest pytest-cov pytest-mock

# Create basic test structure if not exists
mkdir -p tests
touch tests/__init__.py
```

### Running Tests
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_nwsreader.py

# Run single test function
pytest tests/test_nwsreader.py::test_summarize_text -v

# Run tests with coverage
pytest --cov=nwsreader --cov-report=html

# Run tests in verbose mode
pytest -v

# Run tests with specific marker
pytest -m "integration"
```

### Test Structure Guidelines
- Unit tests in `tests/` directory
- Test files named `test_*.py`
- Test functions named `test_*`
- Use pytest fixtures for common setup
- Mock external dependencies (requests, feedparser)

## Build and Development Commands

### Environment Setup
```bash
pip install -r requirements.txt
```

### Running the Application
```bash
# Single run - process sources and generate overview
python3 nwsreader.py --file sources.json --overview

# Continuous mode - process every N minutes
python3 nwsreader.py --file sources.json --overview --interval 60

# Process single URL
python3 nwsreader.py --url "https://example.com/article"
```

### Docker Usage
The Docker container runs in continuous mode by default:
- Uses `sources.json` for structured source groups
- Processes feeds every 60 minutes
- Shows database status and processing logs
- Requires Ollama server for summarization

### File Structure

```
news-reader/
├── nwsreader.py          # Main application
├── sources.txt           # RSS feeds and URLs
├── settings.json         # Configuration
├── news_reader.db        # SQLite database
├── requirements.txt      # Python dependencies
├── tests/                # Test files
└── AGENTS.md            # This file
```

## Testing Commands

### Setup Testing Environment
```bash
# Install testing dependencies
pip install pytest pytest-cov pytest-mock

# Create basic test structure if not exists
mkdir -p tests
touch tests/__init__.py
```

### Running Tests
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_nwsreader.py

# Run single test function
pytest tests/test_nwsreader.py::test_summarize_text -v

# Run tests with coverage
pytest --cov=nwsreader --cov-report=html

# Run tests in verbose mode
pytest -v

# Run tests with specific marker
pytest -m "integration"
```

### Test Structure Guidelines
- Unit tests in `tests/` directory
- Test files named `test_*.py`
- Test functions named `test_*`
- Use pytest fixtures for common setup
- Mock external dependencies (requests, feedparser)

## Linting and Code Quality

### Ruff (Recommended Linter)
```bash
# Install ruff
pip install ruff

# Lint all files
ruff check .

# Lint specific file
ruff check nwsreader.py

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

## Code Style Guidelines

### General Principles
- Write readable, maintainable code
- Follow PEP 8 style guide
- Use 4 spaces for indentation (never tabs)
- Keep lines under 88 characters (Black default)
- Use docstrings for all public functions
- Add comments for complex logic

### Function Structure
```python
def function_name(param1: Type, param2: Type) -> ReturnType:
    """Brief description of what function does."""
    pass
```

### Naming Conventions
- Use `snake_case` for variables and functions
- Use `PascalCase` for class names
- Use `UPPER_SNAKE_CASE` for constants
- Use descriptive names: `feed_url` not `url`

### Import Organization
1. Standard library imports
2. Blank line
3. Third-party imports
4. Blank line
5. Local imports

