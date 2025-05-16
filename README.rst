product-composer
================

This is the successor of product-builder. A tool to create rpm product
repositories inside of Open Build Service based on a larger pool
of packages.

It is used by any SLFO based product during product creation and
also during maintenance time.

Currently it supports:
 - processing based on a list of rpm package names
 - optional filters for architectures, versions and flavors can be defined
 - it can either just take a single rpm of a given name or all of them
 - it can post process updateinfo data
 - post processing like rpm meta data generation
 - modify pre-generated installer images to put a package set for 
   off-line installation on it.

Development
===========

Create the development environment:

.. code-block:: console

    $ python -m venv .venv
    $ .venv/bin/python -m pip install -e ".[dev]"


Run tests:

.. code-block::

    $ .venv/bin/python -m pytest -v tests/


Build documentation:

.. code-block::

    $ make docs



Installation
============

Packaging and distributing a Python application is dependent on the target
operating system(s) and execution environment, which could be a Python virtual
environment, Linux container, or native application.

Install the application to a self-contained Python virtual environment:

    $ python -m venv .venv
    $ .venv/bin/python -m pip install <project source>
    $ cp -r <project source>/etc .venv/
    $ .venv/bin/productcomposer --help



Execution
=========

The installed application includes a wrapper script for command line execution.
The location of this scripts depends on how the application was installed.


Configuration
-------------

The application uses `TOML`_ files for configuration. Configuration supports
runtime parameter substitution via a shell-like variable syntax, *i.e.*
``var = ${VALUE}``. CLI invocation will use the current environment for
parameter substitution, which makes it simple to pass host-specific values
to the application without needing to change the config file for every
installation.

.. code-block:: toml

    mailhost = $SENDMAIL_HOST


Logging
-------

The application uses standard `Python logging`_. All loggins is to ``STDERR``,
nd the logging level can be set via the config file or on the command line.


.. _TOML: https://toml.io
.. _Python logging: https://docs.python.org/3/library/logging.html
.. _mdklatt/cookiecutter-python-app: https://github.com/mdklatt/cookiecutter-python-app
