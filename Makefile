VIRTUAL_ENV=$(shell echo "$${VIRTUAL_ENV:-'.env3'}")

all: $(VIRTUAL_ENV)

.PHONY: help
#(i) help - Show available commands
help:
	@egrep "^#\(i\)" [Mm]akefile

$(VIRTUAL_ENV): requirements.txt
	@[ -d $(VIRTUAL_ENV) ] || virtualenv --no-site-packages --python=python3 $(VIRTUAL_ENV)
	@$(VIRTUAL_ENV)/bin/pip install -r requirements.txt
	@touch $(VIRTUAL_ENV)

$(VIRTUAL_ENV)/bin/py.test: $(VIRTUAL_ENV)
	@$(VIRTUAL_ENV)/bin/pip install pytest
	@touch $(VIRTUAL_ENV)/bin/py.test

#(i)
#(i) ==================
#(i)    Development
#(i) ==================
#(i)

.PHONY: backend-run
#(i) backend-run - Runs backend application
backend-run: $(CURDIR)/backend
	@$(VIRTUAL_ENV)/bin/python -m aiohttp.web -H 0.0.0.0 -P 9000 backend.app:app

.PHONY: br
#(i) br - Short command for run app. Alias for 'backend-run'
br: backend-run

.PHONY: worker-run
#(i) worker-run - Runs worker application
worker-run: $(CURDIR)/worker
	@$(VIRTUAL_ENV)/bin/python -m aiohttp.web -H 0.0.0.0 -P 5000 worker.app:app

.PHONY: wr
#(i) wr - Short command for run app. Alias for 'worker-run'
wr: worker-run

.PHONY: clean
#(i) clean - Cleanup project directories
clean:
	rm -rf build/ dist/ docs/_build *.egg-info
	find $(CURDIR) -name "*.py[co]" -delete
	find $(CURDIR) -name "*.orig" -delete
	find $(CURDIR)/$(MODULE) -name "__pycache__" | xargs rm -rf

#(i)
#(i) ==================
#(i)      Testing
#(i) ==================
#(i)

.PHONY: test
#(i) test - Runs backend all tests
test: $(VIRTUAL_ENV)/bin/py.test
	@$(VIRTUAL_ENV)/bin/py.test -xs all

.PHONY: backend-test
#(i) backend-test - Runs backend tests
backend-test: $(VIRTUAL_ENV)/bin/py.test
	@$(VIRTUAL_ENV)/bin/py.test -xs backend/tests.py

.PHONY: worker-test
#(i) worker-test - Runs worker tests
worker-test: $(VIRTUAL_ENV)/bin/py.test
	@$(VIRTUAL_ENV)/bin/py.test -xs worker/tests.py

.PHONY: bt
#(i) bt - Short command for run all tests. Alias for 'backend-test'
t: backend_test

.PHONY: wt
#(i) wt - Short command for run all tests. Alias for 'worker-test'
t: worker_test

.PHONY: t
#(i) t - Short command for run all tests. Alias for 'test'
t: backend_test
