#!/usr/bin/env python
import os.path
from setuptools import setup, find_packages
import hsreplayparser

README = open(os.path.join(os.path.dirname(__file__), "README.md")).read()

CLASSIFIERS = [
	"Intended Audience :: Developers",
	"Programming Language :: Python",
	"Programming Language :: Python :: 3",
	"Programming Language :: Python :: 3.4",
	"Topic :: Games/Entertainment :: Simulation",
]

setup(
	name="hsreplayparser",
	version=hsreplayparser.__version__,
	packages=find_packages(exclude=["tests"]),
	author=hsreplayparser.__author__,
	author_email=hsreplayparser.__email__,
	description="A replay parsing module for the HSReplay specification.",
	classifiers=CLASSIFIERS,
	download_url="https://github.com/amw2104/HSReplayParser/tarball/master",
	long_description=README,
	url="https://github.com/amw2104/HSReplayParser",
)