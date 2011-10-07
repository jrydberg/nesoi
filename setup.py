from setuptools import setup, find_packages
setup(name='nesoi',
      version='0.0.2',
      description='a coordination and configuration manager',
      author='Johan Rydberg',
      author_email='johan.rydberg@gmail.com',
      url='http://github.com/jrydberg/nesoi',
      packages=find_packages() + ['twisted.plugins']
)
