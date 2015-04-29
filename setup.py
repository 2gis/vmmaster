from setuptools import setup,  find_packages
import os
import versioneer

versioneer.VCS = 'git'
versioneer.versionfile_source = 'vmmaster/_version.py'
versioneer.versionfile_build = 'vmmaster/_version.py'
versioneer.tag_prefix = ''  # tags are like 0.1.0
versioneer.parentdir_prefix = 'vmmaster-'  # dirname like 'myproject-0.1.0'

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
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description='Python KVM-based virtual machine environment system for selenium testing',
    url='https://github.com/2gis/vmmaster',
    packages=find_packages(),
    install_requires=[
        'Flask==0.10.1',
        'twisted==14.0.0',
        'sqlalchemy==0.9.4',
        'netifaces>=0.8',
        'graypy==0.2.9',
        'docopt==0.6.1',
        'alembic==0.6.5',
        'PyDispatcher==2.0.3',
        'requests==2.3.0',
        'python-glanceclient==0.16.1',
        'python-keystoneclient==1.2.0',
        'python-neutronclient==2.3.11',
        'python-novaclient==2.22.0',
        'pysubnettree==0.23',
        'Flask-HTTPAuth==2.4.0'
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
