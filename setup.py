#!/usr/bin/env python
import os
from setuptools import find_packages, setup

with open(os.path.join(os.path.dirname(__file__), 'README.md')) as readme:
    README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='CATMAID-synapsesuggestor',
    version='0.0.1',
    packages=find_packages(exclude='travis'),
    include_package_data=True,
    license='MIT License',
    description='A django app which acts as a drop-in extension for CATMAID, allowing users to incorporate automatic'
                ' synapse suggestions into their expert neuron annotation workflow.',
    long_description=README,
    url='https://github.com/clbarnes/synapsesuggestor',
    author='Christopher L. Barnes',
    author_email='barnesc@janelia.hhmi.org',
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 1.9',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
)
