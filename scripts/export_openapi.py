"""Export the deterministic FastAPI contract for TypeScript generation."""

import json
from pathlib import Path

from app.config.settings import Settings
from app.main import create_app

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPOSITORY_ROOT / "packages" / "shared-types" / "openapi.json"


def main() -> None:
    schema = create_app(Settings(_env_file=None, APP_ENV="test")).openapi()
    OUTPUT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
