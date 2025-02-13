"""
Sanic-Redis
"""

import sys

from setuptools import find_packages, setup
from setuptools.command.test import test as TestCommand

from sanic_redis import __version__ as version


class PyTest(TestCommand):
    """
    Provide a Test runner to be used from setup.py to run unit tests
    """

    user_options = [("pytest-args=", "a", "Arguments to pass to pytest")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = ""

    def run_tests(self):
        import shlex

        import pytest

        errno = pytest.main(shlex.split(self.pytest_args))
        sys.exit(errno)


setup_kwargs = {
    "name": "sanic-redis",
    "version": version,
    "url": "https://github.com/strahe/sanic-redis",
    "license": "MIT",
    "author": "octal",
    "author_email": "octalgah@gmail.com",
    "description": (
        'Adds redis support to Sanic'
    ),
    "long_description": 'sanic-redis is a Sanic framework extension which adds support for the redis.',
    "packages": find_packages(exclude=("tests", "tests.*")),
    "platforms": "any",
    "python_requires": ">=3.7",
    "keywords": ['sanic', 'redis', 'hiredis'],
    "zip_safe": False,
    "classifiers": [
        "Development Status :: 4 - Beta",
        "Environment :: Web Environment",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Internet :: WWW/HTTP :: Session',
    ],
}

env_dependency = (
    '; sys_platform != "win32" ' 'and implementation_name == "cpython"'
)
ujson = "ujson>=1.35" + env_dependency
uvloop = "uvloop>=0.15.0" + env_dependency
types_ujson = "types-ujson" + env_dependency

requirements = [
    "sanic",
    "redis>=5.0.0,<6.0",
    "hiredis>=2.3.2,<3.0"
]

tests_require = [
    "sanic-testing>=22.9.0",
    "pytest==8.0.*",
    "coverage",
    "beautifulsoup4",
    "pytest-sanic",
    "pytest-benchmark",
    "chardet==3.*",
    "flake8",
    "black",
    "isort>=5.0.0",
    "bandit",
    "mypy>=0.901,<0.910",
    "docutils",
    "pygments",
    "uvicorn<0.15.0",
    "slotscheck>=0.8.0,<1",
    types_ujson,
]

setup_kwargs["install_requires"] = requirements
setup_kwargs["tests_require"] = tests_require
setup_kwargs["cmdclass"] = {"test": PyTest}
setup(**setup_kwargs)
