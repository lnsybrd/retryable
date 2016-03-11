#!/usr/bin/env python
import os

from setuptools import setup
from setuptools.command.develop import develop

class SetupDevelop(develop):

    def finalize_options(self):
        # Check to make sure we are in a virtual environment
        # before we allow this to be run.
        assert os.getenv('VIRTUAL_ENV'), 'You should be in a virtualenv!'
        develop.finalize_options(self)

    def run(self):
        develop.run(self)
        self.spawn(('pip', 'install', '--upgrade', '--requirement', 'requirements/dev.txt'))


# The distribution setup configuration
setup(
    name='retryable',
    version='2016.3.11',
    description='Decorator for retrying python functions',
    author='lnsy.brd',
    author_email='lnsy.brd@gmail.com',
    url='http://github.com/lnsybrd/retryable',
    packages=['retryable'],
    keywords=['retry'],
    cmdclass={
        'develop': SetupDevelop
    }
)
