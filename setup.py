from distutils.core import setup


setup(name='vmmaster',
      version='0.1',
      description='Python KVM-based virtual machine environment system for selenium testing',
      ext_modules=[mongoose],
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
      requires=[
          "netifaces==0.8",
      ]
)