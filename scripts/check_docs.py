"""Check repository Markdown relative links without network or third-party dependencies."""

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    files = list(ROOT.glob("*.md"))
    for folder in ("docs", "examples", "ros_bridge", ".github"):
        files.extend((ROOT / folder).rglob("*.md"))
    errors = []
    for path in files:
        text = re.sub(r"```.*?```", "", path.read_text(), flags=re.S)
        for raw in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            target = raw.strip().split(' "')[0].strip("<>")
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path:
                continue
            local = path.parent / unquote(url.path)
            if not local.exists():
                errors.append(f"{path.relative_to(ROOT)}: {target}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Markdown relative links verified in {len(files)} files.")


if __name__ == "__main__":
    main()
