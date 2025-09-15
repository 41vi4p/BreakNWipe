#!/usr/bin/env python3
"""
BreakNWipe - Comprehensive Data Wiping CLI Utility
Setup configuration for installation and distribution
"""

from setuptools import setup, find_packages
import os

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

with open(os.path.join(here, 'requirements.txt'), encoding='utf-8') as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name='breaknwipe',
    version='1.0.0',
    description='Comprehensive secure data wiping CLI utility for IT asset recycling',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='CodeBreakers Team',
    author_email='contact@breaknwipe.org',
    url='https://github.com/breaknwipe/breaknwipe',
    license='MIT',

    packages=find_packages(),
    python_requires='>=3.8',
    install_requires=requirements,

    entry_points={
        'console_scripts': [
            'breaknwipe=breaknwipe.cli.main:main',
            'bwipe=breaknwipe.cli.main:main',
        ],
    },

    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Information Technology',
        'Topic :: System :: Systems Administration',
        'Topic :: Security',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Operating System :: POSIX :: Linux',
        'Environment :: Console',
    ],

    keywords='data wiping, secure erase, NIST, DoD, asset recycling, security',

    project_urls={
        'Documentation': 'https://breaknwipe.readthedocs.io/',
        'Source': 'https://github.com/breaknwipe/breaknwipe',
        'Tracker': 'https://github.com/breaknwipe/breaknwipe/issues',
    },

    include_package_data=True,
    package_data={
        'breaknwipe': ['data/*', 'templates/*'],
    },

    extras_require={
        'dev': [
            'pytest>=7.0',
            'pytest-cov>=4.0',
            'black>=22.0',
            'flake8>=5.0',
            'mypy>=1.0',
        ],
        'docs': [
            'sphinx>=5.0',
            'sphinx-rtd-theme>=1.0',
        ],
    },
)