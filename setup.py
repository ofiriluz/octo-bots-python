#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Setup process."""

from io import open
from os import getenv, path

import toml
from setuptools import find_packages, setup


def get_package_requirements(package, version):
    packages = []
    package_name = package
    if isinstance(version, dict):
        for p, v in version.items():
            packages.extend(get_package_requirements(p, v))
    else:
        if isinstance(version, str) and version != "*":
            package_name = f"{package}/${version}"
        packages.append(package_name)
    return packages


def get_install_requirements():
    try:
        # read my pipfile
        with open('Pipfile', 'r') as fh:
            pipfile = fh.read()
        # parse the toml
        pipfile_toml = toml.loads(pipfile)
    except FileNotFoundError:
        return []
    # if the package's key isn't there then just return an empty
    # list
    try:
        required_packages = pipfile_toml['packages'].items()
    except KeyError:
        return []
    # If a version/range is specified in the Pipfile honor it
    # otherwise just list the package
    packages = []
    for package, version in required_packages:
        packages.extend(get_package_requirements(package, version))
    return packages


def get_version():
    version = open("VERSION", 'r').read().strip()
    build_number = getenv("BUILD_NUMBER", 0)
    branch = getenv("BRANCH_NAME", "")
    full_version = f"{version}.{build_number}"
    if branch != "":
        if branch.startswith("rc"):
            full_version = f"{version}.rc{build_number}"
        elif branch != 'master' and not branch.startswith('release'):
            full_version = f"{version}.dev{build_number}"
    return full_version


with open(path.join(path.abspath(path.dirname(__file__)), 'README.md'),
          encoding='utf-8') as f:
    long_description = f.read()

setup(
    # Basic project information
    name='octo-bots-python',
    version=get_version(),
    # Authorship and online reference
    author='Ofir Iluz',
    author_email='iluzofir@gmail.com',
    url='https://github.com/ofiriluz/octo-bots-python',
    # Detailled description
    description='Octo bots management for github checks / bots',
    long_description=long_description,
    long_description_content_type='text/markdown',
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10'
    ],
    # Package configuration
    packages=find_packages(exclude=('tests',)),
    include_package_data=True,
    python_requires='>= 3.6',
    install_requires=get_install_requirements(),
    # Licensing and copyright
    license='Apache 2.0',
    entry_points={
        'console_scripts': ['octo-bots-executor=octo_bots_python.bots_executor:main'],
    })
