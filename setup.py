from setuptools import setup,  find_packages
import os
from pip.req import parse_requirements

# parse_requirements() returns generator of pip.req.InstallRequirement objects
install_reqs = parse_requirements("requirements.txt")
reqs = [str(ir.req) for ir in install_reqs]

home = []
for path, subdirs, files in os.walk('vmmaster/home'):
    path = path.replace('vmmaster/', '')
    for name in files:
        home.append(os.path.join(path, name))

alembic = []
for path, subdirs, files in os.walk('vmmaster/alembic'):
    path = path.replace('vmmaster/', '')
    for name in files:
        home.append(os.path.join(path, name))
alembic.append('alembic.ini')

setup(
    name='vmmaster',
    version='0.1',
    description='Python KVM-based virtual machine environment system for selenium testing',
    url='https://github.com/nwlunatic/vmmaster',
    packages=find_packages(),
    install_requires=reqs,
    scripts=[
        'bin/vmmaster',
        'bin/vmmaster_cleanup'
    ],
    package_data={
        'vmmaster': home,
        'vmmaster': alembic,
    },
    include_package_data=True,
    data_files=[
        ('/etc/init.d', ['etc/init.d/vmmaster'])
    ]
)
