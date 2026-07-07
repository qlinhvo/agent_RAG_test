
import json
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import os
KB_DIR = Path(os.environ.get("KB_DIR", "knowledge_base"))

PLAINTEXT_SUFFIXES = {".md", ".markdown", ".txt"}


def to_markdown(src: Path) -> str:
    """Convert a single source file to Markdown text."""
    if src.suffix.lower() in PLAINTEXT_SUFFIXES:
        return src.read_text(encoding="utf-8", errors="replace")
    from markitdown import MarkItDown  

    md = MarkItDown()
    return md.convert(str(src)).text_content


def _collect(paths) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files += [c for c in sorted(p.rglob("*")) if c.is_file()]
        elif p.is_file():
            files.append(p)
        else:
            print(f"  skip (not found): {p}")
    return files


def _unique_name(stem: str, manifest: dict) -> str:
    """Make a safe, collision-free '<name>.md' output filename."""
    base = "".join(c if (c.isalnum() or c in "-_ ") else "_" for c in stem).strip()
    base = base.replace(" ", "_") or "doc"
    name, i = f"{base}.md", 1
    while name in manifest:
        name, i = f"{base}-{i}.md", i + 1
    return name


def ingest(paths) -> None:
    KB_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict = {}
    for src in _collect(paths):
        try:
            text = unicodedata.normalize("NFC", to_markdown(src))
        except Exception as exc:  
            print(f"  skip (parse failed): {src.name} -> {exc}")
            continue

        out_name = _unique_name(src.stem, manifest)
        (KB_DIR / out_name).write_text(text, encoding="utf-8")
        manifest[out_name] = {
            "source": str(src),
            "chars": len(text),
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }
        print(f"  {src.name} -> {out_name} ({len(text)} chars)")

    (KB_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Done. {len(manifest)} document(s) in {KB_DIR.resolve()}")


def create_demo() -> list[str]:
    demo = Path("sample_docs")
    demo.mkdir(exist_ok=True)

    (demo / "q3_report.md").write_text(
        "# Q3 Financial Report\n\n"
        "Total revenue in Q3 2026 was 12.4 million USD, up 8% from Q2.\n"
        "Operating costs rose to 7.1 million USD, mainly due to hiring.\n"
        "Net profit for the quarter was 3.2 million USD.\n"
        "The board approved a budget increase for the data platform team.\n",
        encoding="utf-8",
    )
    (demo / "security_policy.md").write_text(
        "# Security Policy\n\n"
        "## Passwords\n"
        "Passwords must be at least 12 characters and rotated every 90 days.\n"
        "Multi-factor authentication is required for all admin accounts.\n\n"
        "## File access\n"
        "Access to customer files is granted on a need-to-know basis only.\n",
        encoding="utf-8",
    )
    (demo / "onboarding_guide.md").write_text(
        "# New Employee Onboarding\n\n"
        "1. Sign the employment contract and NDA.\n"
        "2. Request laptop and building access from IT.\n"
        "3. Complete the security training within the first week.\n"
        "4. Meet your assigned mentor for a project overview.\n",
        encoding="utf-8",
    )
    (demo / "ghi_chu_vn.md").write_text(
        "# Ghi chú nội bộ\n\n"
        "Doanh thu quý 3 tăng trưởng tốt nhờ mảng khách hàng cá nhân.\n"
        "Cần chuẩn bị báo cáo rủi ro hợp đồng trước cuối tháng.\n",
        encoding="utf-8",
    )
    print(f"Created sample documents in {demo.resolve()}")
    return [str(demo)]


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args == ["--demo"]:
        paths = create_demo()
    else:
        paths = args
    ingest(paths)

    (KB_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Done. {len(manifest)} document(s) in {KB_DIR.resolve()}")


def create_demo() -> list[str]:
    demo = Path("sample_docs")
    demo.mkdir(exist_ok=True)

    (demo / "q3_report.md").write_text(
        "# Q3 Financial Report\n\n"
        "Total revenue in Q3 2026 was 12.4 million USD, up 8% from Q2.\n"
        "Operating costs rose to 7.1 million USD, mainly due to hiring.\n"
        "Net profit for the quarter was 3.2 million USD.\n"
        "The board approved a budget increase for the data platform team.\n",
        encoding="utf-8",
    )
    (demo / "security_policy.md").write_text(
        "# Security Policy\n\n"
        "## Passwords\n"
        "Passwords must be at least 12 characters and rotated every 90 days.\n"
        "Multi-factor authentication is required for all admin accounts.\n\n"
        "## File access\n"
        "Access to customer files is granted on a need-to-know basis only.\n",
        encoding="utf-8",
    )
    (demo / "onboarding_guide.md").write_text(
        "# New Employee Onboarding\n\n"
        "1. Sign the employment contract and NDA.\n"
        "2. Request laptop and building access from IT.\n"
        "3. Complete the security training within the first week.\n"
        "4. Meet your assigned mentor for a project overview.\n",
        encoding="utf-8",
    )
    (demo / "ghi_chu_vn.md").write_text(
        "# Ghi chú nội bộ\n\n"
        "Doanh thu quý 3 tăng trưởng tốt nhờ mảng khách hàng cá nhân.\n"
        "Cần chuẩn bị báo cáo rủi ro hợp đồng trước cuối tháng.\n",
        encoding="utf-8",
    )
    print(f"Created sample documents in {demo.resolve()}")
    return [str(demo)]


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args == ["--demo"]:
        paths = create_demo()
    else:
        paths = args
    ingest(paths)
