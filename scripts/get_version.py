# scripts/get_version.py
from pathlib import Path
import tomllib

root = Path(__file__).resolve().parents[1]
pyproject = root / "pyproject.toml"

data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
print(data["project"]["version"])