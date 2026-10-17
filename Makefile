.PHONY: help install lock frontend backend db-init db-start db-stop db-status migrate migration lint test test-db check

# Optional Unix convenience wrapper. Native Windows users can call scripts/dev.py directly.
PYTHON ?= python3

help install lock frontend backend db-init db-start db-stop db-status migrate lint test test-db check:
	$(PYTHON) scripts/dev.py $@

migration:
	$(PYTHON) scripts/dev.py migration --message "$(message)"
