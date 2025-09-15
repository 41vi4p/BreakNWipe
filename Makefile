# BreakNWipe Development Makefile

.PHONY: help install dev-install test lint format clean build package

help:
	@echo "BreakNWipe Development Commands:"
	@echo "  install      - Install package for production use"
	@echo "  dev-install  - Install package in development mode"
	@echo "  test         - Run test suite"
	@echo "  lint         - Run code linting"
	@echo "  format       - Format code with black"
	@echo "  clean        - Clean build artifacts"
	@echo "  build        - Build distribution packages"
	@echo "  package      - Create installable packages (.deb, .rpm)"

install:
	pip install -r requirements.txt
	pip install .

dev-install:
	pip install -r requirements.txt
	pip install -e ".[dev]"

test:
	pytest tests/ -v --cov=breaknwipe --cov-report=html

lint:
	flake8 breaknwipe tests
	mypy breaknwipe

format:
	black breaknwipe tests
	isort breaknwipe tests

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
	# Create .deb package
	python setup.py --command-packages=stdeb.command bdist_deb

	# Create .rpm package
	python setup.py bdist_rpm

# Development shortcuts
run-interactive:
	sudo python -m breaknwipe.cli.main --interactive

run-list:
	sudo python -m breaknwipe.cli.main --list-devices

install-deps:
	sudo apt-get update
	sudo apt-get install -y python3-dev python3-pip build-essential
	sudo apt-get install -y smartmontools hdparm nvme-cli
	sudo apt-get install -y python3-stdeb rpm