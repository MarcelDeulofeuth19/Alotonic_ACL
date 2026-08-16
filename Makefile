# Todos los targets pesados corren con nice/ionice: esta instancia es PROD en vivo.
PY := .venv/bin/python
NICE := nice -n 15 ionice -c3

.PHONY: venv test lint run

venv:
	python3.12 -m venv .venv
	$(NICE) $(PY) -m pip install --no-cache-dir -r requirements-dev.txt

test:
	$(NICE) $(PY) -m pytest

lint:
	$(NICE) $(PY) -m flake8 .

# Solo para desarrollo local; en prod el servicio corre en Docker (ver runbook).
run:
	$(PY) -m uvicorn app.main:app --host 127.0.0.1 --port 8090
