# Project management tasks.

VENV = .venv
PYTHON = . $(VENV)/bin/activate && python
PYTEST = $(PYTHON) -m pytest


$(VENV)/.make-update: pyproject.toml
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install -U pip  # needs to be updated first
	$(PYTHON) -m pip install -e ".[dev]"
	touch $@


.PHONY: dev
dev: $(VENV)/.make-update


.PHONY: docs
docs: dev
	asciidoc docs/productcomposer.adoc


.PHONY: test-unit
test-unit: dev
	$(PYTEST) tests/unit/


.PHONY: check
check: test-unit
