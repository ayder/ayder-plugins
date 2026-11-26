"""Shared mutable state for zendriver-tools.

ayder re-imports browser_tools for every func_ref, so every handler holds
its own copy of that module; this module is never a func_ref target and is
imported once, so all handlers and registries share it (D11).
"""

browser = None          # the zendriver Browser, once started
handle = None           # recorded Popen handle of the Chrome child we launched
profile_dir = None      # active profile directory (Path)
profile_kind = None     # "throwaway" | "persistent:<name>"
headless_setting = None
tab = None              # the single current tab (MVP)
