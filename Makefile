# BreakNWipe Development Makefile

.PHONY: help install dev-install test lint format clean build package install-system uninstall-system demo

help:
	@echo "BreakNWipe Development Commands:"
	@echo "  install          - Install package for production use"
	@echo "  dev-install      - Install package in development mode"
	@echo "  test             - Run test suite"
	@echo "  lint             - Run code linting"
	@echo "  format           - Format code with black"
	@echo "  clean            - Clean build artifacts"
	@echo "  build            - Build distribution packages"
	@echo "  package          - Create installable packages (.deb, .rpm)"
	@echo "  install-system   - Install BreakNWipe system-wide"
	@echo "  uninstall-system - Remove BreakNWipe from system"
	@echo "  demo             - Run demonstration"

install:
	uv sync --no-dev

dev-install:
	uv sync

test:
	uv run pytest tests/ -v --cov=breaknwipe --cov-report=html

lint:
	uv run flake8 breaknwipe tests
	uv run mypy breaknwipe

format:
	uv run black breaknwipe tests
	uv run isort breaknwipe tests

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf htmlcov/
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +

build: clean
	python setup.py sdist bdist_wheel

package: build
	@echo "Building distribution packages..."
	chmod +x scripts/build_packages.sh
	sudo ./scripts/build_packages.sh

install-system:
	@echo "Installing BreakNWipe system-wide..."
	chmod +x scripts/install.sh scripts/install_dependencies.sh
	sudo ./scripts/install.sh

uninstall-system:
	@echo "Removing BreakNWipe from system..."
	chmod +x scripts/uninstall.sh
	sudo ./scripts/uninstall.sh

# Development shortcuts
run-interactive:
	sudo uv run python -m breaknwipe.cli.main --interactive

run-list:
	sudo uv run python -m breaknwipe.cli.main --list-devices

run-help:
	uv run python -m breaknwipe.cli.main --help

demo:
	@echo "Running BreakNWipe demonstration..."
	chmod +x scripts/demo.sh
	sudo ./scripts/demo.sh

install-deps:
	sudo apt-get update
	sudo apt-get install -y python3-dev python3-pip build-essential
	sudo apt-get install -y smartmontools hdparm nvme-cli
	sudo apt-get install -y python3-stdeb rpm ruby ruby-dev rubygems
	sudo gem install --no-document fpm

# Testing shortcuts
test-algorithms:
	uv run python -c "from breaknwipe.wipe_engine.algorithms import list_available_algorithms; import json; print(json.dumps(list_available_algorithms(), indent=2))"

test-device-detection:
	sudo uv run python -c "from breaknwipe.device.detector import DeviceDetector; d = DeviceDetector(); [print(f'{dev.path}: {dev.model} ({dev.capacity_human})') for dev in d.list_devices()]"

# Documentation
docs:
	@echo "Documentation available:"
	@echo "  - README.md: Main documentation"
	@echo "  - docs/DESIGN.md: Architecture and design"
	@echo "  - docs/BLOCKCHAIN_INTEGRATION.md: Blockchain integration guide"
	@echo "  - CLI help: make run-help"

# Security check
security-check:
	@echo "Running security checks..."
	uv run python -c "import os; print('Root check:', os.geteuid() == 0)"
	uv run python -c "from breaknwipe.certificate.signature import DigitalSigner; print('Crypto available:', bool(DigitalSigner()))"
