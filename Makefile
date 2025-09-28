# Django Project Code Quality Tools
# Usage: make <target>

.PHONY: help format lint type-check test quality-check install-tools

help:
	@echo "Available commands:"
	@echo "  format         - Format code with black and sort imports with isort"
	@echo "  lint           - Run flake8 linter"
	@echo "  type-check     - Run mypy type checker"
	@echo "  test           - Run tests with coverage"
	@echo "  quality-check  - Run all quality checks (lint, type-check)"
	@echo "  install-tools  - Install all code quality tools"

install-tools:
	@echo "Installing code quality tools..."
	pip install black isort flake8 mypy pytest-django pytest-cov

format:
	@echo "Formatting code with black..."
	black apps/ background_tasks/ intelliwiz_config/ --exclude migrations/
	@echo "Sorting imports with isort..."
	isort apps/ background_tasks/ intelliwiz_config/ --skip migrations

lint:
	@echo "Running flake8 linter..."
	flake8 apps/ background_tasks/ intelliwiz_config/

type-check:
	@echo "Running mypy type checker..."
	mypy apps/ background_tasks/ intelliwiz_config/

test:
	@echo "Running tests with coverage..."
	python -m pytest --cov=apps --cov=background_tasks --cov=intelliwiz_config \
		--cov-report=html:coverage_reports/html \
		--cov-report=term \
		--tb=short -v

quality-check: lint type-check
	@echo "All quality checks completed!"

# Security testing
security-test:
	@echo "Running security tests..."
	python -m pytest -m security --tb=short -v

# Run everything
all: format quality-check test
	@echo "All code quality tasks completed successfully!"