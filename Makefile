PYTHON = .venv/bin/python
PIP = .venv/bin/pip

.PHONY: setup install colab-install lint test

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
	$(PIP) install -e services/pipeline/

colab-install:
	pip install -q -e shared/
	pip install -q -e services/yt-download/
	pip install -q -e services/clip-extraction/
	pip install -q -e services/db-sync/
	pip install -q -e services/asr-training/
	pip install -q -e services/pipeline/

lint:
	$(PYTHON) -m ruff check .

test:
	$(PYTHON) -m pytest -v
