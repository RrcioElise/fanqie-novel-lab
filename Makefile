.PHONY: setup app electron test compile check open-source-check clean

setup:
	bash scripts/setup.sh

app:
	bash scripts/run_app.sh

electron:
	bash scripts/run_electron.sh

compile:
	python -m py_compile $$(find src -name '*.py')

test:
	python -m unittest discover -s tests

open-source-check:
	fanqie-lab open-source-check

check: compile test open-source-check

clean:
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist src/*.egg-info
