"""One self-contained HTML page that replays recorded games.

The page never scores anything. Every number it shows was produced by the
engine and written into the records; the page only draws them.
"""

import json
from pathlib import Path

TEMPLATE = Path(__file__).with_name("viewer.html")


def write(path: Path, data: dict) -> None:
    blob = json.dumps(data).replace("</", "<\\/")
    path.write_text(TEMPLATE.read_text().replace("/*DATA*/null/*END*/", blob))
