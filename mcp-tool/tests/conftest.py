import sys
from pathlib import Path

# Make plugin root importable in tests
sys.path.insert(0, str(Path(__file__).parent.parent))
