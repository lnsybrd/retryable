#!/usr/bin/env python
import os
import sys
import subprocess
import shutil
import contextlib

from setuptools import setup, find_packages
from setuptools.command.develop import develop as DevelopCommand
from setuptools.command.test import test as TestCommand


class SetupDevelop(DevelopCommand):
    pip_args = ''

    def finalize_options(self):
        # Check to make sure we are in a virtual environment
        # before we allow this to be run.
        if not os.getenv('VIRTUAL_ENV'):
            print >>sys.stderr, 'ERROR: You are not in a virtual environment'
            sys.exit(1)

        DevelopCommand.finalize_options(self)

    def run(self):
        self.install_git_hooks("tools/devtools/hooks")
        self.install_requirements(filepath="requirements.txt", label="runtime")
        self.install_requirements(filepath="dev-requirements.txt", label="development")
        self.install_development_egg()

    def install_development_egg(self):
        with label_operation("Installing development egg:"):
            # old-style super call
            DevelopCommand.run(self)

    @classmethod
    def install_requirements(cls, filepath, label, pip_bin=None):
        pip_bin = pip_bin or 'pip'
        with label_operation('Install {} PIP dependencies:'.format(label)):
            cmd = '{pip_bin} install {pip_args} -r {filepath}'.format(
                pip_bin=pip_bin, filepath=filepath, pip_args=cls.pip_args)
            subprocess.check_call(cmd, shell=True)

    @classmethod
    def install_git_hooks(cls, hooks_dir):
        repo_hooks_dir = ".git/hooks"
        with label_operation("Copy git hooks:"):
            if not os.path.exists(repo_hooks_dir):
                shutil.copytree(hooks_dir, repo_hooks_dir)
            else:
                print("Hooks folder already exists. Step skipped")


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)

        self.test_args = ['-v']
        self.test_suite = True

    def run_tests(self):
        #import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.test_args)
        sys.exit(errno)


@contextlib.contextmanager
def label_operation(msg, after=' ---- DONE'):
    """
        Context manager which display string ``msg``, yields to caller,
        then displays string ``after`` when complete.
    """
    print(msg)
    yield
    print(after)


if __name__ == '__main__':
    # The distribution setup configuration
    setup(name='retryable',
          version='0.0.1',
          description='Retryable Decorator',
          author='d3vz3r0',
          author_email='lin.salisbury@gmail.com',
          url='http://github.com/d3vz3r0/retryable',
          packages=find_packages(),
          cmdclass={'develop': SetupDevelop,
                    'test': PyTest})
