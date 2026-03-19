import sys
from pathlib import Path

# Add src and common/src to path for monorepo imports
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "common" / "src"))
