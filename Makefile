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
	@$(VIRTUAL_ENV)/bin/pip install -r test_requirements.txt
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
	rm -rf coverage/ build/ dist/ docs/_build .cache/ *.egg-info
	find $(CURDIR) -name "*.py[co]" -delete
	find $(CURDIR) -name "*.orig" -delete
	find $(CURDIR)/$(MODULE) -name "__pycache__" | xargs rm -rf

#(i)
#(i) ==================
#(i)      Testing
#(i) ==================
#(i)

.PHONY: lint
#(i) lint - Runs linting for project
lint: $(VIRTUAL_ENV)/bin/py.test
	@$(CURDIR)/git-hooks/run-10-flake8.sh

.PHONY: l
#(i) l - Short command for lint. Alias for 'lint'
l: lint

.PHONY: test
#(i) test - Runs backend all tests
test: $(VIRTUAL_ENV)/bin/py.test
	@$(VIRTUAL_ENV)/bin/py.test -x tests

.PHONY: ctest
#(i) ctest - Runs backend all tests with coverage
ctest: $(VIRTUAL_ENV)/bin/py.test
	@$(VIRTUAL_ENV)/bin/coverage run tests/run_tests.py
	@$(VIRTUAL_ENV)/bin/coverage html

.PHONY: backend-test
#(i) backend-test - Runs backend tests
backend-test: $(VIRTUAL_ENV)/bin/py.test
	@$(VIRTUAL_ENV)/bin/py.test -x tests/backend/

.PHONY: worker-test
#(i) worker-test - Runs worker tests
worker-test: $(VIRTUAL_ENV)/bin/py.test
	@$(VIRTUAL_ENV)/bin/py.test -x tests/worker/

.PHONY: bt
#(i) bt - Short command for run all tests. Alias for 'backend-test'
bt: backend-test

.PHONY: wt
#(i) wt - Short command for run all tests. Alias for 'worker-test'
wt: worker-test

.PHONY: t
#(i) t - Short command for run all tests. Alias for 'test'
t: test

.PHONY: ct
#(i) ct - Short command for run all tests with coverage. Alias for 'ctest'
ct: ctest
