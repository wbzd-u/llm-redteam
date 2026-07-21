import csv
import json

from redteam_memory.models import Attempt, Case, Evidence
from redteam_memory.mechanisms import import_mechanisms
from redteam_memory.research import mechanism_research_matrix, paper_packet, research_summary, write_case_csv, write_paper_packet, write_summary_json, write_summary_svg
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
        packet_path = tmp_path / "paper-packet.md"
        write_paper_packet(store, packet_path)

    assert summary["totals"]["cases"] == 2
    assert summary["totals"]["confirmed_cases"] == 1
    assert summary["totals"]["historical_confirmed_cases"] == 0
    assert summary["cases_by_language"] == {"en": 1, "zh": 1}
    with csv_path.open(encoding="utf-8", newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 2
    assert json.loads(json_path.read_text(encoding="utf-8"))["totals"]["attempts"] == 2
    assert "<svg" in svg_path.read_text(encoding="utf-8")
    assert "方法部分" in packet_path.read_text(encoding="utf-8")


def test_mechanism_matrix_and_paper_packet_keep_unlinked_cases_visible(tmp_path):
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        case = store.save_case(Case(title="one", mechanism="historical mechanism", tags=["source:user-kb"]))
        import_mechanisms(store, [{
            "mechanism_id": "mechanism-test", "name": "Test mechanism", "category": "Testing",
            "summary": "A safe test card.", "match_terms": ["test"], "tags": ["test"],
            "applicability_signals": ["signal"], "preconditions": ["control"],
            "negative_signals": ["negative"], "confidence": "hypothesis", "notes": "notes",
        }])
        store.link_mechanism_case("mechanism-test", case.case_id, relation="observed")
        matrix = mechanism_research_matrix(store, source="user-kb")
        packet = paper_packet(store, source="user-kb")
    assert matrix[0]["name"] == "Test mechanism"
    assert matrix[0]["case_count"] == 1
    assert packet["data_dictionary"]
