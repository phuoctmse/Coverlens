"""Writes the full report as JSON, the machine-readable copy of the Excel file."""

from pathlib import Path

from coverlens.core.report import Report

FILE_NAME = "coverage_report.json"


class JsonWriter:
    def write(self, report: Report, out_dir: Path) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / FILE_NAME
        path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path
