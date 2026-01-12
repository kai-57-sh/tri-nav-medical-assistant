#!/usr/bin/env python
"""Launch script for TriNav server."""
import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import and run
if __name__ == "__main__":
    from server import main
    main()
