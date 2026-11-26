"""Shared mutable state for zendriver-tools.

ayder re-imports browser_tools for every func_ref, so every handler holds
its own copy of that module; this module is never a func_ref target and is
imported once, so all handlers and registries share it (D11).
"""
