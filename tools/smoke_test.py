# Локальная smoke-проверка структуры проекта.

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from PDFYandexVisionBlock.src import process_pdf
from PDFYandexVisionBlock.src.parser import parse_requisites
from validate_output import validate_output


REQUIRED_BLOCK_FILES = (
    "block.json",
    "meta.json",
    "values.xml",
    "code.value.py",
    "libs.py.json",
    "typeToName.json",
    "requirements.txt",
)


def _ok(message: str) -> None:
    print(f"OK: {message}")


def _info(message: str) -> None:
    print(f"INFO: {message}")


def _failures_for_structure() -> list[str]:
    failures: list[str] = []

    block_dir = ROOT / "PDFYandexVisionBlock"
    for file_name in REQUIRED_BLOCK_FILES:
        path = block_dir / file_name
        if not path.exists():
            failures.append(f"Missing Puzzle RPA block file: {path.relative_to(ROOT)}")

    src_dir = block_dir / "src"
    for file_name in ("__init__.py", "yandex_client.py", "errors.py", "parser.py", "normalizer.py", "schema.py"):
        path = src_dir / file_name
        if not path.exists():
            failures.append(f"Missing source file: {path.relative_to(ROOT)}")

    for path in (
        ROOT / "examples" / "sample_response_yandex.json",
        ROOT / "examples" / "expected_output.json",
        ROOT / "docs" / "DEMO_SCRIPT.md",
        ROOT / "docs" / "ARCHITECTURE.md",
        ROOT / "docs" / "TROUBLESHOOTING.md",
        ROOT / "README.md",
        ROOT / "CHECKPOINTS.md",
        ROOT / "demo_video_link.txt",
    ):
        if not path.exists():
            failures.append(f"Missing handoff file: {path.relative_to(ROOT)}")

    return failures


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    failures = _failures_for_structure()

    if callable(process_pdf):
        _ok("process_pdf import is callable")
    else:
        failures.append("process_pdf import is not callable")

    expected_output = ROOT / "examples" / "expected_output.json"
    if expected_output.exists():
        try:
            expected_data = _load_json(expected_output)
            validation_errors = validate_output(expected_data)
            if validation_errors:
                failures.extend(f"expected_output.json: {error}" for error in validation_errors)
            else:
                _ok("examples/expected_output.json has required fields")
        except json.JSONDecodeError as exc:
            failures.append(f"examples/expected_output.json is invalid JSON: {exc}")

    sample_response = ROOT / "examples" / "sample_response_yandex.json"
    if sample_response.exists():
        try:
            parsed = parse_requisites(_load_json(sample_response))
            if parsed.get("success") is True:
                _ok("sample_response_yandex.json can be parsed offline")
            else:
                failures.append("sample_response_yandex.json parser result is not success=True")
        except Exception as exc:
            failures.append(f"Offline parser check failed: {exc}")

    test_pdf = ROOT / "examples" / "test_input.pdf"
    if test_pdf.exists():
        _info("examples/test_input.pdf exists; live OCR can be checked separately with real credentials")
    else:
        _info("examples/test_input.pdf is not in the repository; live OCR requires a real PDF before demo")

    _info("Live OCR is intentionally skipped: it requires real TOKEN, FOLDER_ID and network access")

    if failures:
        print("Smoke test failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
