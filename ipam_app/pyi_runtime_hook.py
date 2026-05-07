import os
import sys
from pathlib import Path

base_dir = Path(sys.executable).resolve().parent
cache_dir = base_dir / "export" / "matplotlib"
cache_dir.mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(cache_dir)
