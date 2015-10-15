Development
***********

Environment
===========
::

    pip install -r requirements-dev.txt
    ./install-hooks.sh

Linting
=======
::

    .tox/bin/flake8 vmmaster/ tests/

Unittests with coverage
=======================
::

    .tox/bin/coverage run --source=vmmaster run_unittests.py
    .tox/bin/coverage html
    look for coverage/index.html
