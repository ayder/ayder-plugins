import sys
from pathlib import Path

import pytest

# Make plugin root importable in tests (mirrors mcp-tool/tests/conftest.py).
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def reset_plugin_status():
    """Clear the shared plugin_status badge registry around each test."""
    try:
        from ayder_cli.tools import plugin_status

        plugin_status.clear()
    except ImportError:
        pass
    yield
    try:
        from ayder_cli.tools import plugin_status

        plugin_status.clear()
    except ImportError:
        pass
