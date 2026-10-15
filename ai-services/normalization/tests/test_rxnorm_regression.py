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

from dataclasses import asdict
from pathlib import Path
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
