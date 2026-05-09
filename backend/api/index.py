"""Vercel entry point — exports the FastAPI ASGI app.

Vercel's @vercel/python runtime auto-detects an ASGI app named `app`
in this file and serves it. We add the parent directory to sys.path so
`from app.main import app` resolves against the existing FastAPI source.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.main import app  # noqa: E402, F401
