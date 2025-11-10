.PHONY: install install-dev test run-local clean build-docker deploy-lambda help

help:
	@echo "AI Weekly Report - Makefile Commands"
	@echo "===================================="
	@echo "install        - Install production dependencies"
	@echo "install-dev    - Install development dependencies"
	@echo "test          - Run tests"
	@echo "run-local     - Generate weekly report locally"
	@echo "clean         - Remove temporary files"
	@echo "build-docker  - Build Docker image for Lambda"
	@echo "deploy-lambda - Deploy to AWS Lambda (requires AWS CLI)"
	@echo ""

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

test:
	pytest tests/ -v --cov=src --cov-report=html

run-local:
	python -m src.main

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage

build-docker:
	docker build -t ai-weekly-report:latest -f deployment/Dockerfile .

deploy-lambda:
	@echo "Building and deploying to AWS Lambda..."
	cd deployment && ./deploy.sh

lint:
	black src/ tests/
	flake8 src/ tests/

type-check:
	mypy src/

