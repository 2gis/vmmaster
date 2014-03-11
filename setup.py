from setuptools import setup,  find_packages
import os

home = []
for path, subdirs, files in os.walk('vmmaster/home'):
    path = path.replace('vmmaster/', '')
    for name in files:
        home.append(os.path.join(path, name))

setup(
    name='vmmaster',
    version='0.1',
    description='Python KVM-based virtual machine environment system for selenium testing',
    url='https://github.com/nwlunatic/vmmaster',
    packages=find_packages(),
    install_requires=[
        "netifaces>=0.8",
        "graypy==0.2.9",
        "docopt==0.6.1",
        "python-daemon==1.6"
    ],
    scripts=['bin/vmmaster'],
    package_data={
        'vmmaster': home,
    },
    include_package_data=True,
    data_files=[
        # ('/etc/init', ['etc/init/vmmaster.conf']),
        ('/etc/init.d', ['etc/init.d/vmmaster'])
    ]
)
