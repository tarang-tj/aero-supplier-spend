PY := .venv/bin/python -I
.PHONY: pull load crosswalk metrics outputs reconcile test lint probe gate all

pull:        ## download all slices (slow, networked)
	$(PY) -m src.pull --all --workers 3
load:
	$(PY) -m src.load
crosswalk:
	$(PY) -m src.crosswalk
metrics: crosswalk
	$(PY) -m src.metrics
	$(PY) -m src.memo_numbers
outputs: metrics
	$(PY) -m src.charts
	$(PY) -m src.export_xlsx
	$(PY) -m src.page
reconcile:   ## the one networked check: every slice equals the USAspending aggregate
	$(PY) -m src.reconcile
lint:
	.venv/bin/ruff check src tests
test:
	$(PY) -m pytest -q
probe:
	$(PY) -m src.probe docs/index.html
gate: lint test reconcile probe
all: load outputs gate
