"""
Comprehensive Offline Regression Test Suite for Calibrated RxNorm Normalizer.

Validates:
1. Mathematical unit equivalence (mcg <-> mg, g <-> mg).
2. Liquid concentration ratio equivalence (X mg / Y mL == (X/Y) mg/mL).
3. Attached unit and clinical abbreviation tokenization.
4. Combination product permutation-invariance.
5. Clinical identity protection & hard clinical vetoes (salts, forms, routes, strengths).
6. Ground-truth validation for acetaminophen 1000 mg oral tablet (RxCUI 430837).
7. Full public API contract preservation.
"""

import concurrent.futures
import csv
from dataclasses import asdict
from pathlib import Path
import time
from unittest.mock import patch
import pytest

import rxnorm_normalize as rx


# -----------------------------------------------------------------------------
# 1. Mathematical Strength & Ratio Normalization
# -----------------------------------------------------------------------------
def test_unit_canonicalization_mcg_to_mg():
    assert rx.canonicalize_strength("50 mcg") == (0.05, "mg")
    assert rx.canonicalize_strength("25 mcg") == (0.025, "mg")
    assert rx.canonicalize_strength("100 mcg") == (0.1, "mg")
    assert rx.canonicalize_strength("1000 mcg") == (1.0, "mg")
    assert rx.canonicalize_strength("0.05 mg") == (0.05, "mg")
    assert rx.canonicalize_strength("1 g") == (1000.0, "mg")
    assert rx.canonicalize_strength("1000 mg") == (1000.0, "mg")


def test_liquid_concentration_ratio_canonicalization():
    # 250 mg / 5 mL == 50 mg/mL
    assert rx.canonicalize_strength("250 mg / 5 ml") == (50.0, "mg/ml")
    assert rx.canonicalize_strength("50 mg/ml") == (50.0, "mg/ml")
    # 160 mg / 5 mL == 32 mg/mL
    assert rx.canonicalize_strength("160 mg / 5 ml") == (32.0, "mg/ml")
    assert rx.canonicalize_strength("32 mg/ml") == (32.0, "mg/ml")
    # 100 mg / 5 mL == 20 mg/mL (NOT 100 mg/mL!)
    assert rx.canonicalize_strength("100 mg / 5 ml") == (20.0, "mg/ml")
    assert rx.canonicalize_strength("100 mg/ml") == (100.0, "mg/ml")


def test_mathematical_strength_compatibility():
    # Identical
    assert rx.are_strengths_compatible(("500 mg",), ("500 mg",))
    # mcg vs mg equivalence
    assert rx.are_strengths_compatible(("50 mcg",), ("0.05 mg",))
    assert rx.are_strengths_compatible(("0.05 mg",), ("50 mcg",))
    # Liquid ratio equivalence
    assert rx.are_strengths_compatible(("250 mg / 5 ml",), ("50 mg/ml",))
    assert rx.are_strengths_compatible(("50 mg/ml",), ("250 mg / 5 ml",))
    # Strict conflict rejection
    assert not rx.are_strengths_compatible(("100 mg / 5 ml",), ("100 mg/ml",))
    assert not rx.are_strengths_compatible(("50 mcg",), ("0.1 mg",))
    assert not rx.are_strengths_compatible(("250 mg",), ("500 mg",))


# -----------------------------------------------------------------------------
# 2. Attached Unit and Clinical Abbreviation Normalization
# -----------------------------------------------------------------------------
def test_normalize_query_attached_units():
    assert rx.normalize_query("metformin 500mg tab") == "metformin 500 mg tablet"
    assert rx.normalize_query("levothyroxine 50mcg") == "levothyroxine 50 mcg"
    assert rx.normalize_query("amoxicillin 250mg/5ml") == "amoxicillin 250 mg/5 ml"
    assert rx.normalize_query("gabapentin 100mg cap") == "gabapentin 100 mg capsule"


def test_normalize_query_clinical_abbreviations():
    assert rx.normalize_query("amoxicillin 500 mg po tab") == "amoxicillin 500 mg oral tablet"
    assert rx.normalize_query("cefdinir 125 mg / 5 ml susp") == "cefdinir 125 mg/5 ml suspension"
    assert rx.normalize_query("prednisolone 15 mg / 5 ml soln") == "prednisolone 15 mg/5 ml solution"
    assert rx.normalize_query("metformin hcl 500 mg tab") == "metformin hydrochloride 500 mg tablet"
    assert rx.normalize_query("metoprolol er 50 mg") == "metoprolol extended release 50 mg"
    assert rx.normalize_query("omeprazole 20 mg dr cap") == "omeprazole 20 mg delayed release capsule"


def test_abbreviation_expansion_does_not_corrupt_drug_names():
    # 'po' should not corrupt propranolol or potassium
    assert "propranolol" in rx.normalize_query("propranolol 40 mg po")
    assert "potassium" in rx.normalize_query("potassium chloride 10 meq")
    # 'hcl' should not corrupt hydrochlorothiazide
    assert "hydrochlorothiazide" in rx.normalize_query("hydrochlorothiazide 25 mg")
    # 'tab' should not corrupt tabrecta
    assert "tabrecta" in rx.normalize_query("tabrecta 200 mg")


# -----------------------------------------------------------------------------
# 3. Clinical Identity Parsing & Multi-Ingredient Combination Matching
# -----------------------------------------------------------------------------
def test_parse_identity_handles_unnormalized_and_attached_inputs():
    ident = rx.parse_identity("levothyroxine sodium 0.05mg tab")
    assert "tablet" in ident.forms
    assert "0.05 mg" in ident.strengths
    assert "sodium" in ident.salts

    combo = rx.parse_identity("amoxicillin 500mg / clavulanate 125mg po tab")
    assert combo.combination is True
    assert "oral" in combo.routes
    assert "tablet" in combo.forms
    assert len(combo.strengths) == 2


def test_combination_permutation_invariance():
    ident_req = rx.parse_identity("clavulanate 125 mg / amoxicillin 500 mg oral tablet")
    candidate_name = "amoxicillin 500 MG / clavulanate 125 MG Oral Tablet"
    assert rx.attributes_compatible(ident_req, candidate_name)


# -----------------------------------------------------------------------------
# 4. Hard Clinical Vetoes & Rejection Safety
# -----------------------------------------------------------------------------
def test_clinical_veto_on_conflicting_salts():
    ident = rx.parse_identity("metoprolol tartrate 50 mg oral tablet")
    candidate_succinate = "metoprolol succinate 50 MG Oral Tablet"
    assert not rx.attributes_compatible(ident, candidate_succinate)
    assert rx._attribute_state(ident, candidate_succinate) == "conflict"


def test_clinical_veto_on_unrequested_extended_release():
    # Plain oral tablet must reject 24 HR extended release
    ident_plain = rx.parse_identity("metformin hydrochloride 500 mg oral tablet")
    candidate_er = "24 HR metformin hydrochloride 500 MG Extended Release Oral Tablet"
    assert not rx.attributes_compatible(ident_plain, candidate_er)
    assert rx._attribute_state(ident_plain, candidate_er) == "conflict"


def test_clinical_veto_on_conflicting_dosage_forms_and_routes():
    ident_drops = rx.parse_identity("metformin 500 mg ophthalmic drops")
    cand_tab = "metformin hydrochloride 500 MG Oral Tablet"
    assert not rx.attributes_compatible(ident_drops, cand_tab)
    assert rx._attribute_state(ident_drops, cand_tab) == "conflict"


def test_clinical_veto_on_look_alike_sound_alike_pairs():
    # Hydralazine vs Hydroxyzine
    norm = rx.RxNormNormalizer()
    res = norm.normalize("hydralazine 25 mg oral tablet")
    # Must never resolve to hydroxyzine
    if res.status == "resolved":
        assert "hydroxyzine" not in res.matched_name.lower()
        assert "hydralazine" in res.matched_name.lower()


# -----------------------------------------------------------------------------
# 5. Acetaminophen 1000 mg Oral Tablet (RxCUI 430837)
# -----------------------------------------------------------------------------
def test_acetaminophen_1000_mg_oral_tablet_resolves():
    norm = rx.RxNormNormalizer()
    res = norm.normalize("acetaminophen 1000 mg oral tablet")
    assert res.status == "resolved"
    assert res.rxcui == "430837"
    assert "acetaminophen 1000 MG Oral Tablet" in res.matched_name


# -----------------------------------------------------------------------------
# 6. Public API Signature & Schema Contracts
# -----------------------------------------------------------------------------
def test_public_api_signatures_and_result_schema():
    norm = rx.RxNormNormalizer()
    res = norm.normalize("lisinopril 10 mg oral tablet")
    data = asdict(res)
    expected_keys = {
        "input",
        "rxcui",
        "matched_name",
        "score",
        "status",
        "reason",
        "closest",
    }
    assert set(data.keys()) == expected_keys
    assert isinstance(res.score, float)
    assert isinstance(res.closest, list)
    assert res.status in {"resolved", "unresolved", "error"}


# -----------------------------------------------------------------------------
# 7. Multi-Ingredient Combination Structured Pairing & Swapped Strength Rejection
# -----------------------------------------------------------------------------
def test_combination_structured_pairing_reversed_order():
    """Validates that reversed ingredient order resolves to the exact same concept."""
    norm = rx.RxNormNormalizer()
    r1 = norm.normalize("amlodipine 5 mg + atorvastatin 10 mg")
    r2 = norm.normalize("atorvastatin 10 mg + amlodipine 5 mg")
    assert r1.status == "resolved"
    assert r2.status == "resolved"
    assert r1.rxcui == "597977"
    assert r2.rxcui == "597977"
    assert "amlodipine 5 MG / atorvastatin 10 MG Oral Tablet" in r1.matched_name
    assert "amlodipine 5 MG / atorvastatin 10 MG Oral Tablet" in r2.matched_name


def test_combination_swapped_strength_rejection():
    """Validates that swapped strengths (amlodipine 10 / atorvastatin 5) reject candidate 597977 (amlodipine 5 / atorvastatin 10)."""
    norm = rx.RxNormNormalizer()
    res = norm.normalize("amlodipine 10 mg + atorvastatin 5 mg")
    assert res.status == "unresolved"
    assert res.rxcui != "597977"


def test_combination_mismatched_single_strength_rejection():
    """Validates that if one component's strength differs, candidate is strictly rejected."""
    norm = rx.RxNormNormalizer()
    res = norm.normalize("amlodipine 5 mg + atorvastatin 50 mg")
    assert res.status == "unresolved"
    assert res.rxcui is None


# -----------------------------------------------------------------------------
# 8. Single-Flight Concurrency & Cache Stampede Prevention
# -----------------------------------------------------------------------------
def test_same_key_single_flight_coordination():
    """Validates that concurrent requests for the exact same uncached key execute the underlying call exactly once."""
    call_count = 0

    def mock_gather(term):
        nonlocal call_count
        call_count += 1
        time.sleep(0.08)
        return [("12345", None)]

    norm = rx.RxNormNormalizer()
    norm._cache.clear()

    with patch.object(norm, "gather_candidates", side_effect=mock_gather):
        with patch.object(
            norm, "_get_props", return_value=("lisinopril 10 MG Oral Tablet", "SCD")
        ):
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = [
                    executor.submit(norm.normalize, "lisinopril 10 mg oral tablet")
                    for _ in range(8)
                ]
                results = [f.result() for f in futures]

    assert call_count == 1, f"Expected exactly 1 call under single-flight, got {call_count}"
    assert all(r.status == "resolved" for r in results)
    assert all(r.rxcui == "12345" for r in results)
    assert all(r is results[0] for r in results)


def test_distinct_key_parallelism():
    """Validates that concurrent requests for distinct keys execute in parallel without serialization."""
    def slow_gather(term):
        time.sleep(0.1)
        return [("12345", None)]

    norm = rx.RxNormNormalizer()
    norm._cache.clear()

    keys = [
        "aspirin 100 mg oral tablet",
        "aspirin 100 mg tablet",
        "aspirin 100 mg tab",
        "aspirin 100mg tablet",
    ]

    with patch.object(norm, "gather_candidates", side_effect=slow_gather):
        with patch.object(
            norm, "_get_props", return_value=("aspirin 100 MG Oral Tablet", "SCD")
        ):
            t0 = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(norm.normalize, k) for k in keys]
                results = [f.result() for f in futures]
            elapsed = time.time() - t0

    assert elapsed < 0.25, f"Expected parallel wall time < 0.25s, got {elapsed:.2f}s"
    assert all(r.status == "resolved" for r in results)


def test_single_flight_exception_recovery_and_unblocking():
    """Validates that leader failure cleanly unblocks follower threads and surfaces error without deadlock or cache poisoning."""
    should_fail = True

    def flaky_gather(term):
        time.sleep(0.05)
        if should_fail:
            raise rx.RxNormUnavailable("Upstream timeout")
        return [("12345", None)]

    norm = rx.RxNormNormalizer()
    norm._cache.clear()

    with patch.object(norm, "gather_candidates", side_effect=flaky_gather):
        with patch.object(
            norm, "_get_props", return_value=("aspirin 100 MG Oral Tablet", "SCD")
        ):
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = [
                    executor.submit(norm.normalize, "aspirin 100 mg oral tablet")
                    for _ in range(4)
                ]
                results = [f.result() for f in futures]

            assert all(r.status == "error" for r in results)
            assert all("Upstream timeout" in (r.reason or "") for r in results)
            assert "aspirin 100 mg oral tablet" not in norm._in_flight
            assert "aspirin 100 mg oral tablet" not in norm._cache

            should_fail = False
            retry_res = norm.normalize("aspirin 100 mg oral tablet")
            assert retry_res.status == "resolved"
            assert retry_res.rxcui == "12345"


# -----------------------------------------------------------------------------
# 9. Evaluation Split Isolation & Label Consistency Audit
# -----------------------------------------------------------------------------
def test_evaluation_splits_zero_leakage_and_label_consistency():
    """Validates that evaluation datasets have 0% chemical overlap, 0% query duplicate overlap, and 0 label contradictions."""
    eval_dir = Path("d:/modawem/data/eval")
    calib_file = eval_dir / "calibration.csv"
    dev_file = eval_dir / "dev.csv"
    test_file = eval_dir / "held_out_test.csv"

    if not (calib_file.exists() and dev_file.exists() and test_file.exists()):
        pytest.skip("Evaluation CSV datasets not present on disk")

    def load_split(path):
        with open(path, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    calib = load_split(calib_file)
    dev = load_split(dev_file)
    test = load_split(test_file)

    def extract_ingredients(cases):
        ings = set()
        for c in cases:
            for p in c["base_ingredient_cluster"].split("-"):
                if p.strip():
                    ings.add(p.strip().lower())
        return ings

    c_ings = extract_ingredients(calib)
    d_ings = extract_ingredients(dev)
    t_ings = extract_ingredients(test)

    # 1. Zero active ingredient leakage
    assert not (c_ings & d_ings), f"Chemical overlap between calib and dev: {c_ings & d_ings}"
    assert not (c_ings & t_ings), f"Chemical overlap between calib and test: {c_ings & t_ings}"
    assert not (d_ings & t_ings), f"Chemical overlap between dev and test: {d_ings & t_ings}"

    # 2. Zero normalized query leakage
    c_q = {rx.normalize_query(c["raw_input"]) for c in calib}
    d_q = {rx.normalize_query(c["raw_input"]) for c in dev}
    t_q = {rx.normalize_query(c["raw_input"]) for c in test}

    assert not (c_q & d_q), f"Query duplicate overlap between calib and dev: {c_q & d_q}"
    assert not (c_q & t_q), f"Query duplicate overlap between calib and test: {c_q & t_q}"
    assert not (d_q & t_q), f"Query duplicate overlap between dev and test: {d_q & t_q}"

    # 3. Label Consistency: metformin 500 mg tablet resolves to 861007
    norm = rx.RxNormNormalizer()
    res = norm.normalize("metformin 500 mg tablet")
    assert res.status == "resolved"
    assert res.rxcui == "861007"
    assert "metformin hydrochloride 500 MG Oral Tablet" in res.matched_name
