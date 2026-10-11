import csv
import json
from dataclasses import asdict
from pathlib import Path

import pytest

import rxnorm_normalize as rx

ROOT = Path(__file__).parent
FIXTURE = ROOT / "rxnorm_fixture.csv"
ADVERSARIAL = ROOT / "rxnorm_adversarial.csv"


@pytest.fixture(name="fixture_data")
def load_fixture_data():
    with FIXTURE.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def test_fixture_has_200_plus_documented_cases(fixture_data):
    assert len(fixture_data) >= 200
    assert {row["case_category"] for row in fixture_data} == {"correct", "misspelled"}
    assert sum(row["case_category"] == "correct" for row in fixture_data) >= 100
    assert sum(row["case_category"] == "misspelled" for row in fixture_data) >= 100
    assert all(row["input"] and row["expected_rxcui"] for row in fixture_data)
    assert all(row["verification"] in {"exact", "spelling"} for row in fixture_data)


def test_http_responses_are_mocked_for_deterministic_resolution(monkeypatch):
    responses = {
        ("/rxcui.json", "metformn"): {"idGroup": {"rxnormId": []}},
        ("/spellingsuggestions.json", "metformn"): {
            "suggestionGroup": {"suggestionList": {"suggestion": ["metformin"]}}
        },
        ("/rxcui.json", "metformin"): {"idGroup": {"rxnormId": ["6809"]}},
        ("/approximateTerm.json", "metformn"): {
            "approximateGroup": {"candidate": [{"rxcui": "6809", "name": "metformin"}]}
        },
        ("/rxcui/6809/properties.json", None): {
            "properties": {"name": "metformin", "tty": "IN"}
        },
    }

    def fake_get(path, params):
        key = (path, params.get("name") or params.get("term"))
        if path.startswith("/rxcui/6809/properties"):
            key = (path, None)
        return responses[key]

    monkeypatch.setattr(rx, "_get", fake_get)
    result = rx.RxNormNormalizer().normalize("metformn")
    assert (result.status, result.rxcui, result.matched_name) == (
        "resolved",
        "6809",
        "metformin",
    )


def test_malformed_approximate_candidate_does_not_hide_usable_candidate(monkeypatch):
    responses = {
        "/rxcui.json": {"idGroup": {"rxnormId": []}},
        "/spellingsuggestions.json": {
            "suggestionGroup": {"suggestionList": {"suggestion": []}}
        },
        "/approximateTerm.json": {
            "approximateGroup": {
                "candidate": [
                    {"rxcui": "", "name": "broken"},
                    {"rxcui": "6809", "name": "metformin"},
                ]
            }
        },
        "/rxcui/6809/properties.json": {
            "properties": {"name": "metformin", "tty": "IN"}
        },
    }

    def fake_get(path, _params):
        return responses[path if path == "/approximateTerm.json" else path]

    monkeypatch.setattr(rx, "_get", fake_get)
    normalizer = rx.RxNormNormalizer()
    result = normalizer.normalize("metformin")
    assert (result.status, result.rxcui) == ("resolved", "6809")
    assert normalizer.diagnostics


def test_wholly_malformed_approximate_response_is_an_api_error(monkeypatch):
    def fake_get(path, _params):
        assert isinstance(_params, dict)
        if path == "/rxcui.json":
            return {"idGroup": {"rxnormId": []}}
        if path == "/spellingsuggestions.json":
            return {"suggestionGroup": {"suggestionList": {"suggestion": []}}}
        if path == "/approximateTerm.json":
            return {"approximateGroup": {"candidate": {"rxcui": "6809"}}}
        raise AssertionError(path)

    monkeypatch.setattr(rx, "_get", fake_get)
    result = rx.RxNormNormalizer().normalize("metformin")
    assert result.status == "error"
    assert "malformed candidate" in result.reason


def test_empty_api_results_are_unresolved_not_api_errors(monkeypatch):
    monkeypatch.setattr(
        rx,
        "_get",
        lambda path, params: {
            "/rxcui.json": {"idGroup": {"rxnormId": []}},
            "/spellingsuggestions.json": {
                "suggestionGroup": {"suggestionList": {"suggestion": []}}
            },
            "/approximateTerm.json": {"approximateGroup": {"candidate": []}},
        }[path],
    )
    result = rx.RxNormNormalizer().normalize("notarealmedicine")
    assert (result.status, result.rxcui) == ("unresolved", None)


def test_normalize_caches_successful_results_and_misses(monkeypatch):
    calls = []

    def fake_gather(_normalizer, term):
        calls.append(term)
        return [("6809", term)]

    monkeypatch.setattr(rx.RxNormNormalizer, "gather_candidates", fake_gather)
    normalizer = rx.RxNormNormalizer()
    first = normalizer.normalize("Metformin")
    second = normalizer.normalize(" metformin ")
    assert first is second
    assert calls == ["metformin"]


def test_unavailable_results_are_errors_and_are_not_cached(monkeypatch):
    calls = []

    def unavailable(_normalizer, term):
        calls.append(term)
        raise rx.RxNormUnavailable("offline")

    monkeypatch.setattr(rx.RxNormNormalizer, "gather_candidates", unavailable)
    normalizer = rx.RxNormNormalizer()
    first = normalizer.normalize("metformin")
    second = normalizer.normalize("metformin")
    assert first.status == second.status == "error"
    assert first.reason.startswith("RxNorm API unavailable:")
    assert calls == ["metformin", "metformin"]


def test_result_and_json_output_contracts(monkeypatch, capsys):
    monkeypatch.setattr(
        rx.RxNormNormalizer,
        "gather_candidates",
        lambda self, term: [("6809", term)],
    )
    normalizer = rx.RxNormNormalizer()
    result = normalizer.normalize("metformin")
    data = asdict(result)
    assert set(data) == {
        "input",
        "rxcui",
        "matched_name",
        "score",
        "status",
        "reason",
        "closest",
    }
    assert data["status"] == "resolved"
    assert isinstance(data["score"], float)
    assert isinstance(data["closest"], list)
    rx.show(result)
    output = capsys.readouterr().out
    assert "[MATCH]" in output
    assert json.loads(output[output.index("{") :])["rxcui"] == "6809"


def test_adversarial_cases_document_rejection_categories():
    with ADVERSARIAL.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    categories = {row["case_category"] for row in rows}
    assert categories >= {
        "unknown",
        "ambiguous",
        "similar_drug_name",
        "salt_variant",
        "combination_product",
        "strength_difference",
    }
    assert any(row["expected_acceptance"] == "true" for row in rows)
    assert any(row["expected_acceptance"] == "false" for row in rows)
    for row in rows:
        if row["expected_acceptance"] == "true":
            assert row["expected_status"] == "resolved"
            assert row["expected_rxcui"]
        else:
            assert row["expected_status"] == "unresolved"


def test_evaluate_requires_positive_fixture_categories(tmp_path):
    path = tmp_path / "incomplete.csv"
    path.write_text(
        "input,expected_rxcui,case_category\n"
        + "\n".join(f"metformin-{index},6809,correct" for index in range(100))
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="at least 100 correct and 100 misspelled"):
        rx.evaluate(str(path))


def test_evaluate_uses_exact_rxcui_and_reports_outcomes(tmp_path, monkeypatch, capsys):
    path = tmp_path / "evaluation.csv"
    rows = [f"metformin-{index},6809,correct" for index in range(100)] + [
        f"metformn-{index},6809,misspelled" for index in range(100)
    ]
    path.write_text(
        "input,expected_rxcui,case_category\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )

    def fake_normalize(_self, name):
        if name.startswith("metformin-"):
            return rx.Result(name, "68090", "metformin", 1.0, "resolved", None)
        if name.startswith("metformn-"):
            return rx.Result(name, "6809", "metformin", 1.0, "resolved", None)
        return rx.Result(name, None, None, 0.0, "unresolved", "unknown")

    monkeypatch.setattr(rx.RxNormNormalizer, "normalize", fake_normalize)
    assert rx.evaluate(str(path)) == 1
    output = capsys.readouterr().out
    assert "correct_name_accuracy=0/100" in output
    assert "misspelled_name_accuracy=100/100" in output
    assert "false_positive_resolutions=0" in output


def test_adversarial_fixture_requires_status_and_acceptance_columns(tmp_path):
    path = tmp_path / "adversarial.csv"
    path.write_text(
        "input,expected_rxcui,case_category\nnotreal,,unknown\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="expected_status and expected_acceptance"):
        rx.evaluate(str(path))


def test_adversarial_fixture_rejects_invalid_status_and_malformed_row(tmp_path):
    path = tmp_path / "adversarial.csv"
    path.write_text(
        "input,expected_rxcui,case_category,expected_status,expected_acceptance\n"
        "notreal,,unknown,maybe,false\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="malformed fixture row"):
        rx.evaluate(str(path))


def test_fixture_rejects_conflicting_duplicate_labels(tmp_path):
    path = tmp_path / "duplicates.csv"
    path.write_text(
        "input,expected_rxcui,case_category\n"
        "metformin,6809,correct\n"
        "metformin,1234,misspelled\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="malformed fixture row"):
        rx.evaluate(str(path))


def test_adversarial_api_error_is_not_a_passing_rejection(
    tmp_path, monkeypatch, capsys
):
    path = tmp_path / "adversarial.csv"
    path.write_text(
        "input,expected_rxcui,case_category,expected_status,expected_acceptance\n"
        "notreal,,unknown,unresolved,false\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        rx.RxNormNormalizer,
        "normalize",
        lambda _self, name: rx.Result(name, None, None, 0.0, "error", "offline"),
    )
    assert rx.evaluate(str(path)) == 1
    assert "api_errors=1" in capsys.readouterr().out
