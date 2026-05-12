from __future__ import annotations

from app import csv_writer


def test_csv_writer_columns_and_values(tmp_path):
    jobs = [
        {
            "title": "Engineer",
            "company": "Acme",
            "work_mode": "Remote",
            "location": "Remote",
            "salary": None,
            "posted": None,
            "url": "https://example.com/job",
            "source": "Example",
            "is_nonprofit_or_h1b_cap_exempt": True,
            "why_match": "Strong backend fit.",
        }
    ]
    path = csv_writer.write_csv(jobs, results_dir=tmp_path)
    text = path.read_text(encoding="utf-8")
    assert text.splitlines()[0].split(",") == csv_writer.CSV_FIELDS
    assert "True" in text
    assert ",," in text
