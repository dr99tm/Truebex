"""Operator scripts, run from server/ as `python -m scripts.<name>`."""

# First, before any script imports SQLAlchemy: app/__init__.py keeps
# `platform` off WMI on Windows.
import app  # noqa: F401
