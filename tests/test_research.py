import csv
import json

from redteam_memory.models import Attempt, Case, Evidence
from redteam_memory.research import research_summary, write_case_csv, write_summary_json, write_summary_svg
from redteam_memory.store import MemoryStore


def test_cross_case_research_summary_and_exports(tmp_path):
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        first = store.save_case(Case(title="one", target="model-a", carrier="chat", tags=["lang:en"]))
        second = store.save_case(Case(title="two", target="model-b", carrier="document", tags=["lang:zh"]))
        store.add_attempt(Attempt(case_id=first.case_id, mechanism="baseline", input_text="a", outcome="refused"))
        store.add_attempt(Attempt(case_id=second.case_id, mechanism="carrier", input_text="b", outcome="unknown"))
        store.add_evidence(Evidence(
            case_id=second.case_id, kind="runtime", description="confirmed", source="test",
            verified=True, metadata={"confirms_impact": True},
        ))
        summary = research_summary(store)
        csv_path = tmp_path / "cases.csv"
        json_path = tmp_path / "summary.json"
        svg_path = tmp_path / "targets.svg"
        write_case_csv(store, csv_path)
        write_summary_json(store, json_path)
        write_summary_svg(store, metric="cases-by-target", path=svg_path)

    assert summary["totals"]["cases"] == 2
    assert summary["totals"]["confirmed_cases"] == 1
    assert summary["cases_by_language"] == {"en": 1, "zh": 1}
    with csv_path.open(encoding="utf-8", newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 2
    assert json.loads(json_path.read_text(encoding="utf-8"))["totals"]["attempts"] == 2
    assert "<svg" in svg_path.read_text(encoding="utf-8")
