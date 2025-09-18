PYTHON ?= python3
VENV_DIR := venvs/five9
ACTIVATE := source $(VENV_DIR)/bin/activate
REQ := requirements.txt
TEST_PATTERN ?= test*.py
FAIL_UNDER ?= 0
HTML_DIR := htmlcov
OPEN_HTML ?= 1

.PHONY: help venv install dev test testcov unit coverage clean dist tox

help:
	@echo "Targets:"
	@echo "  venv        Create virtual environment (if missing)"
	@echo "  install     Install dependencies into venv"
	@echo "  dev         venv + install editable package"
	@echo "  test        Run unit tests (unittest)"
	@echo "  coverage    Run coverage with HTML report"
	@echo "  tox         Run tox (multi-env) if tox.ini present"
	@echo "  clean       Remove build, cache, coverage artifacts"

venv:
	@test -d $(VENV_DIR) || ($(PYTHON) -m venv $(VENV_DIR) && echo "Created venv at $(VENV_DIR)")

install: venv
	$(ACTIVATE) && pip install -q -r $(REQ) && pip install -q -e .

dev: install

# Basic unittest run
test: install
	# Full test suite (integration + unit) with coverage + HTML report
	$(ACTIVATE) && F9_INTEGRATION=1 coverage run -m unittest discover -s five9/tests -p '$(TEST_PATTERN)' -v
	$(ACTIVATE) && coverage report || true
	$(ACTIVATE) && coverage html -d $(HTML_DIR)
	@if [ "$(OPEN_HTML)" = "1" ]; then \
		command -v open >/dev/null 2>&1 && open $(HTML_DIR)/index.html || echo "Open $(HTML_DIR)/index.html manually" ; \
	fi
	@echo "Full coverage report: $(HTML_DIR)/index.html"

# Alias identical to test (explicit name)
testcov: test

# Fast unit tests only (no live API) - default
unit: install
	# Run fast unit tests that avoid live API calls (utils + five9_session)
	$(ACTIVATE) && python -m unittest five9.tests.test_five9_session_unit -v
	$(ACTIVATE) && python -m unittest discover -s five9/tests -p 'test_utils_*.py' -v

# Coverage run with fail-under threshold optional (export FAIL_UNDER=80)
coverage: install
	# Fast unit coverage only (utils)
	$(ACTIVATE) && coverage run -m unittest discover -s five9/tests -p 'test_utils_*.py'
	$(ACTIVATE) && coverage report --fail-under=$(FAIL_UNDER) || true
	$(ACTIVATE) && coverage html -d $(HTML_DIR)
	@if [ "$(OPEN_HTML)" = "1" ]; then \
		command -v open >/dev/null 2>&1 && open $(HTML_DIR)/index.html || echo "Open $(HTML_DIR)/index.html manually" ; \
	fi
	@echo "Unit coverage report: $(HTML_DIR)/index.html"

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache five9/htmlcov .coverage
	find . -name '__pycache__' -type d -exec rm -rf {} + || true

# Optional tox target
tox: install
	$(ACTIVATE) && pip install -q tox && tox
