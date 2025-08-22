# Makefile for IC2V development

.PHONY: help install test lint format clean build docs

# Default target
help:
	@echo "Available targets:"
	@echo "  install     Install package in development mode"
	@echo "  test        Run test suite"
	@echo "  lint        Run linting checks"
	@echo "  format      Format code with black"
	@echo "  type-check  Run type checking with mypy"
	@echo "  clean       Clean build artifacts"
	@echo "  build       Build package"
	@echo "  docs        Generate documentation"
	@echo "  all         Run format, lint, type-check, and test"

install:
	pip install -e .[dev]

test:
	pytest tests/ -v --cov=ic2v --cov-report=term-missing --cov-report=html

lint:
	flake8 src tests --count --statistics

format:
	black src tests

type-check:
	mypy src/ic2v

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean
	python -m build

docs:
	@echo "Documentation is in README.md and docstrings"

all: format lint type-check test

# Development shortcuts
dev-setup: install
	@echo "Development environment ready!"

ci: all
	@echo "CI checks completed successfully!"