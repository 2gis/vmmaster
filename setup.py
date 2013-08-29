from setuptools import setup


# .gitignore is included for directory creation
home_directory_skeleton = [
    ('/var/lib/vmmaster', ['config.py']),
    ('/var/lib/vmmaster/clones', ['clones/.gitignore']),
    ('/var/lib/vmmaster/origins', ['origins/.gitignore']),
    ('/var/lib/vmmaster/session', ['session/.gitignore']),
]

init_script = ('/etc/init.d', '')

setup(
    name='vmmaster',
    version='0.1',
    description='Python KVM-based virtual machine environment system for selenium testing',
    url='https://github.com/nwlunatic/vmmaster',
    packages=[
        'vmmaster',
        'vmmaster.core',
        'vmmaster.core.dumpxml',
        'vmmaster.core.network',
        'vmmaster.utils',
        'vmmaster.core.server',
    ],
    package_dir={
        'vmmaster': 'vmmaster',
        'vmmaster.core': 'vmmaster/core',
        'vmmaster.core.dumpxml': 'vmmaster/core/dumpxml',
        'vmmaster.core.network': 'vmmaster/core/network',
        'vmmaster.utils': 'vmmaster/utils',
        'vmmaster.core.server': 'vmmaster/core/server',
    },
    install_requires=[
        "netifaces>=0.8",
    ],
    data_files=home_directory_skeleton
)