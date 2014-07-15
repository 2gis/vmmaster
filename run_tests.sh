pip install mock
pip install git+https://github.com/nwlunatic/lode_runner
PYTHONPATH=`pwd` lode_runner tests/ $@
