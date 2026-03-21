import sys
from pathlib import Path

import pytest

# Make plugin root importable in tests
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def reset_mcp_state():
    """Reset mcp_state singleton between tests to prevent cross-test pollution."""
    yield
    try:
        from mcp_state import state
        state.handlers.clear()
        state.sessions.clear()
    except ImportError:
        pass
