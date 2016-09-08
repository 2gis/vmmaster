VIRTUAL_ENV=$(shell echo "$${VIRTUAL_ENV:-'.env3'}")

all: $(VIRTUAL_ENV)

.PHONY: help
# target: help - Display callable targets
help:
	@egrep "^# target:" [Mm]akefile

.PHONY: clean
# target: clean - Display callable targets
clean:
	rm -rf build/ dist/ docs/_build *.egg-info
	find $(CURDIR) -name "*.py[co]" -delete
	find $(CURDIR) -name "*.orig" -delete
	find $(CURDIR)/$(MODULE) -name "__pycache__" | xargs rm -rf

# =============
#  Development
# =============

$(VIRTUAL_ENV): requirements.txt
	@[ -d $(VIRTUAL_ENV) ] || virtualenv --no-site-packages --python=python3 $(VIRTUAL_ENV)
	@$(VIRTUAL_ENV)/bin/pip install -r requirements.txt
	@touch $(VIRTUAL_ENV)

$(VIRTUAL_ENV)/bin/py.test: $(VIRTUAL_ENV)
	@$(VIRTUAL_ENV)/bin/pip install pytest
	@touch $(VIRTUAL_ENV)/bin/py.test

.PHONY: backend_test
# target: test - Runs tests
backend_test: $(VIRTUAL_ENV)/bin/py.test
	@$(VIRTUAL_ENV)/bin/py.test -xs backend/tests.py

.PHONY: t
t: backend_test

.PHONY: backend-run
backend-run: $(CURDIR)/backend
	@$(VIRTUAL_ENV)/bin/gunicorn backend.app:app --bind=0.0.0.0:9000 --workers=1 --pid=$(CURDIR)/backend_pid --worker-class aiohttp.worker.GunicornWebWorker

.PHONY: frontend-run
frontend-run: $(CURDIR)/frontend
	@$(VIRTUAL_ENV)/bin/gunicorn frontend.app:app --bind=0.0.0.0:8080 --workers=1 --pid=$(CURDIR)/frontend_pid --worker-class aiohttp.worker.GunicornWebWorker

.PHONY: worker-run
worker-run: $(CURDIR)/worker
	@$(VIRTUAL_ENV)/bin/gunicorn worker.app:app --bind=0.0.0.0:5000 --workers=1 --pid=$(CURDIR)/worker_pid --worker-class aiohttp.worker.GunicornWebWorker
