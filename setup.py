from setuptools import setup,  find_packages
import os

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
    install_requires=[
        "twisted==13.2.0",
        "sqlalchemy==0.9.4",
        "netifaces>=0.8",
        "graypy==0.2.9",
        "docopt==0.6.1",
        "alembic==0.6.5",
        "PyDispatcher==2.0.3"
    ],
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
