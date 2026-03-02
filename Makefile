PYTHON = .venv/bin/python
PIP = .venv/bin/pip

.PHONY: setup install lint test api editor

setup:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(MAKE) install

install:
	$(PIP) install -e apps/api/

colab-install:
	pip install -q -e apps/api/

lint:
	$(PYTHON) -m ruff check apps/api/src apps/api/tests --ignore B008

test:
	PYTHONPATH=apps/api/src $(PYTHON) -m pytest apps/api/tests -v

api:
	PYTHONPATH=apps/api/src $(PYTHON) -m uvicorn ports.rest.app:create_app --factory --host 0.0.0.0 --port 8000

editor:
	cd apps/web && npx next dev
