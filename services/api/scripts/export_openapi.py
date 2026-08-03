import json
from pathlib import Path
from typing import Any

from app.main import app


def main() -> None:
    output_path = Path(__file__).resolve().parents[1] / "openapi.json"
    document: dict[str, Any] = app.openapi()
    output_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(output_path)


if __name__ == "__main__":
    main()
