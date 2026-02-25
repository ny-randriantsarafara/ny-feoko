PYTHON = .venv/bin/python
PIP = .venv/bin/pip

.PHONY: setup install lint test

setup:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(MAKE) install

install:
	$(PIP) install -e shared/
	$(PIP) install -e services/yt-download/
	$(PIP) install -e services/clip-extraction/
	$(PIP) install -e services/db-sync/
	$(PIP) install -e services/asr-training/
	$(PIP) install -e services/mt-training/

lint:
	$(PYTHON) -m ruff check .

test:
	$(PYTHON) -m pytest -v
