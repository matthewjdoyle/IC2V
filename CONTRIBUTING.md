## Contributing to IC2V

We welcome contributions to IC2V! This document will help you get started.

### Development Setup

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/IC2V.git
   cd IC2V
   ```

3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. Install in development mode:
   ```bash
   pip install -e .[dev]
   ```

### Development Workflow

1. Create a new branch for your feature:
   ```bash
   git checkout -b feature/amazing-feature
   ```

2. Make your changes and add tests

3. Run the test suite:
   ```bash
   pytest tests/ -v --cov=ic2v
   ```

4. Check code formatting:
   ```bash
   black src tests
   flake8 src tests
   mypy src/ic2v
   ```

5. Commit your changes:
   ```bash
   git commit -m "Add amazing feature"
   ```

6. Push to your fork and create a Pull Request

### Code Style

- We use [Black](https://github.com/psf/black) for code formatting
- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guide
- Use type hints where appropriate
- Write docstrings for all public functions and classes

### Testing

- All new code should have tests
- Tests are written using pytest
- Aim for high code coverage (>80%)
- Use mocking for external dependencies like ffmpeg

### Reporting Issues

- Use the GitHub issue tracker
- Include steps to reproduce the issue
- Provide system information (OS, Python version, ffmpeg version)
- Include sample images if relevant (but keep them small)

### Feature Requests

- Open an issue with the "enhancement" label
- Describe the use case and expected behavior
- Be open to discussion about implementation

Thank you for contributing! 🎉