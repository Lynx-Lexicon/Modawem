#!/usr/bin/env python3
"""
Rigorous Clinical Evaluation Dataset Generator with Anti-Leakage Group Split.
Builds a curated, clinically verified evaluation dataset across 10 mandatory categories:
  1. standard_clean
  2. typos_and_formatting
  3. unit_variations
  4. form_and_route_variations
  5. strength_and_concentration
  6. salt_variants
  7. combination_products
  8. look_alike_sound_alike
  9. insufficient_or_ambiguous
 10. conflicting_or_nonexistent

Every resolved case is verified against official RxNorm concepts in drug_reference.sqlite.
Splits are grouped strictly by 'base_ingredient_cluster' (Zero chemical overlap).
"""

import csv
import json
import logging
import random
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT_DIR = Path("D:/modawem")
BASE_DIR = ROOT_DIR / "ai-services" / "normalization"
sys.path.insert(0, str(BASE_DIR))
from rxnorm_normalize import normalize_query

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

EVAL_DIR = ROOT_DIR / "data" / "eval"
EVAL_DIR.mkdir(parents=True, exist_ok=True)
NORM_EVAL_DIR = BASE_DIR / "data" / "eval"
NORM_EVAL_DIR.mkdir(parents=True, exist_ok=True)

SQLITE_PATH = ROOT_DIR / "data" / "reference" / "drug_reference.sqlite"

SEED = 42
random.seed(SEED)


def get_verified_concept(cur: sqlite3.Cursor, name_pattern: str, tty: str) -> tuple[str, str]:
    cur.execute("SELECT rxcui, name FROM rxnorm_concepts WHERE name LIKE ? AND tty = ? ORDER BY length(name) ASC LIMIT 1", (name_pattern, tty))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Concept not found for pattern: '{name_pattern}' with TTY '{tty}'")
    return str(row[0]), str(row[1])


def build_evaluation_dataset() -> list[dict]:
    conn = sqlite3.connect(SQLITE_PATH)
    cur = conn.cursor()

    cases = []
    case_counter = 1
    seen_norm_queries = set()

    def add(raw_input, category, expected_status, expected_rxcui, expected_name,
            expected_reason, rationale, base_ingredient_cluster):
        nonlocal case_counter
        norm_q = normalize_query(raw_input)
        if norm_q in seen_norm_queries:
            return
        seen_norm_queries.add(norm_q)
        cases.append({
            "case_id": f"CASE_{case_counter:04d}",
            "raw_input": raw_input,
            "category": category,
            "expected_status": expected_status,
            "expected_rxcui": expected_rxcui if expected_status == "resolved" else "",
            "expected_name": expected_name,
            "expected_reason": expected_reason,
            "rationale": rationale,
            "base_ingredient_cluster": base_ingredient_cluster.lower().strip(),
            "split": "",
        })
        case_counter += 1

    logging.info("Harvesting verified concepts from SQLite...")

    # 1. Standard Clean Cases
    clean_items = [
        ("lisinopril % oral tablet", "SCD", "lisinopril", ["10 MG", "20 MG", "5 MG", "40 MG"]),
        ("atorvastatin % oral tablet", "SCD", "atorvastatin", ["10 MG", "20 MG", "40 MG", "80 MG"]),
        ("metformin hydrochloride % oral tablet", "SCD", "metformin", ["500 MG", "850 MG", "1000 MG"]),
        ("amoxicillin % oral capsule", "SCD", "amoxicillin", ["250 MG", "500 MG"]),
        ("amoxicillin % oral tablet", "SCD", "amoxicillin", ["875 MG"]),
        ("omeprazole % delayed release oral capsule", "SCD", "omeprazole", ["10 MG", "20 MG", "40 MG"]),
        ("losartan potassium % oral tablet", "SCD", "losartan", ["25 MG", "50 MG", "100 MG"]),
        ("gabapentin % oral capsule", "SCD", "gabapentin", ["100 MG", "300 MG", "400 MG"]),
        ("gabapentin % oral tablet", "SCD", "gabapentin", ["600 MG", "800 MG"]),
        ("amlodipine % oral tablet", "SCD", "amlodipine", ["2.5 MG", "5 MG", "10 MG"]),
        ("sertraline % oral tablet", "SCD", "sertraline", ["25 MG", "50 MG", "100 MG"]),
        ("simvastatin % oral tablet", "SCD", "simvastatin", ["10 MG", "20 MG", "40 MG"]),
        ("levothyroxine sodium % oral tablet", "SCD", "levothyroxine", ["0.025 MG", "0.05 MG", "0.1 MG", "0.125 MG"]),
        ("furosemide % oral tablet", "SCD", "furosemide", ["20 MG", "40 MG", "80 MG"]),
        ("pantoprazole % delayed release oral tablet", "SCD", "pantoprazole", ["20 MG", "40 MG"]),
        ("prednisone % oral tablet", "SCD", "prednisone", ["5 MG", "10 MG", "20 MG"]),
        ("citalopram % oral tablet", "SCD", "citalopram", ["10 MG", "20 MG", "40 MG"]),
        ("fluoxetine % oral capsule", "SCD", "fluoxetine", ["10 MG", "20 MG", "40 MG"]),
        ("escitalopram % oral tablet", "SCD", "escitalopram", ["5 MG", "10 MG", "20 MG"]),
        ("rosuvastatin calcium % oral tablet", "SCD", "rosuvastatin", ["5 MG", "10 MG", "20 MG", "40 MG"]),
        ("bupropion hydrochloride % oral tablet", "SCD", "bupropion", ["75 MG", "100 MG"]),
        ("cetirizine hydrochloride % oral tablet", "SCD", "cetirizine", ["5 MG", "10 MG"]),
        ("loratadine % oral tablet", "SCD", "loratadine", ["10 MG"]),
        ("tramadol hydrochloride % oral tablet", "SCD", "tramadol", ["50 MG"]),
        ("clopidogrel % oral tablet", "SCD", "clopidogrel", ["75 MG"]),
        ("tamsulosin hydrochloride % oral capsule", "SCD", "tamsulosin", ["0.4 MG"]),
        ("duloxetine % delayed release oral capsule", "SCD", "duloxetine", ["20 MG", "30 MG", "60 MG"]),
        ("carvedilol % oral tablet", "SCD", "carvedilol", ["3.125 MG", "6.25 MG", "12.5 MG", "25 MG"]),
        ("acetaminophen % oral tablet", "SCD", "acetaminophen", ["325 MG", "500 MG", "1000 MG"]),
        ("ibuprofen % oral tablet", "SCD", "ibuprofen", ["400 MG", "600 MG", "800 MG"]),
        ("warfarin sodium % oral tablet", "SCD", "warfarin", ["1 MG", "2 MG", "2.5 MG", "5 MG", "10 MG"]),
        ("spironolactone % oral tablet", "SCD", "spironolactone", ["25 MG", "50 MG", "100 MG"]),
        ("pravastatin sodium % oral tablet", "SCD", "pravastatin", ["10 MG", "20 MG", "40 MG", "80 MG"]),
        ("meloxicam % oral tablet", "SCD", "meloxicam", ["7.5 MG", "15 MG"]),
        ("cyclobenzaprine hydrochloride % oral tablet", "SCD", "cyclobenzaprine", ["5 MG", "7.5 MG", "10 MG"]),
        ("baclofen % oral tablet", "SCD", "baclofen", ["10 MG", "20 MG"]),
        ("celecoxib % oral capsule", "SCD", "celecoxib", ["50 MG", "100 MG", "200 MG"]),
    ]

    for pat, tty, cluster, strengths in clean_items:
        for st in strengths:
            full_pat = pat.replace("%", st)
            try:
                rxcui, name = get_verified_concept(cur, full_pat, tty)
                # Raw input in lowercase standard formatting
                raw_in = name.lower()
                add(raw_in, "standard_clean", "resolved", rxcui, name, "",
                    "Standard clean clinical drug query matching exact RxNorm concept.", cluster)
            except Exception as e:
                logging.warning(f"Could not find clean concept: {full_pat}: {e}")

    # 2. Typos & Formatting Cases (Misspellings, attached units, casing)
    for pat, tty, cluster, strengths in clean_items[:20]:
        for st in strengths[:2]:
            full_pat = pat.replace("%", st)
            try:
                rxcui, name = get_verified_concept(cur, full_pat, tty)
                # 1. Attached unit
                att_unit = name.lower().replace(" mg", "mg").replace(" oral tablet", " tab").replace(" oral capsule", " cap")
                add(att_unit, "typos_and_formatting", "resolved", rxcui, name, "",
                    "Attached units and common clinical abbreviations.", cluster)

                # 2. Typo in name
                words = name.lower().split()
                drug_w = words[0]
                if len(drug_w) > 5:
                    typo_w = drug_w[:-2] + drug_w[-1]  # drop penultimate char
                    typo_input = " ".join([typo_w] + words[1:])
                    add(typo_input, "typos_and_formatting", "resolved", rxcui, name, "",
                        "Recoverable single-edit typo in active ingredient name.", cluster)
            except Exception:
                pass

    # 3. Unit Variations (mcg vs mg, etc.)
    unit_concepts = [
        ("levothyroxine sodium % oral tablet", "levothyroxine", [
            ("0.025 MG", "25 mcg", "0.025 mg"),
            ("0.05 MG", "50 mcg", "0.05 mg"),
            ("0.075 MG", "75 mcg", "0.075 mg"),
            ("0.088 MG", "88 mcg", "0.088 mg"),
            ("0.1 MG", "100 mcg", "0.1 mg"),
            ("0.112 MG", "112 mcg", "0.112 mg"),
            ("0.125 MG", "125 mcg", "0.125 mg"),
            ("0.137 MG", "137 mcg", "0.137 mg"),
            ("0.15 MG", "150 mcg", "0.15 mg"),
            ("0.175 MG", "175 mcg", "0.175 mg"),
            ("0.2 MG", "200 mcg", "0.2 mg"),
            ("0.3 MG", "300 mcg", "0.3 mg"),
        ]),
        ("digoxin % oral tablet", "digoxin", [
            ("0.0625 MG", "62.5 mcg", "0.0625 mg"),
            ("0.125 MG", "125 mcg", "0.125 mg"),
            ("0.25 MG", "250 mcg", "0.25 mg"),
        ]),
        ("clonidine hydrochloride % oral tablet", "clonidine", [
            ("0.1 MG", "100 mcg", "0.1 mg"),
            ("0.2 MG", "200 mcg", "0.2 mg"),
            ("0.3 MG", "300 mcg", "0.3 mg"),
        ]),
        ("tamsulosin hydrochloride % oral capsule", "tamsulosin", [
            ("0.4 MG", "400 mcg", "0.4 mg"),
        ]),
        ("alprazolam % oral tablet", "alprazolam", [
            ("0.25 MG", "250 mcg", "0.25 mg"),
            ("0.5 MG", "500 mcg", "0.5 mg"),
            ("1 MG", "1000 mcg", "1 mg"),
        ]),
    ]
    for pat, cluster, specs in unit_concepts:
        for rx_st, mcg_st, mg_st in specs:
            full_pat = pat.replace("%", rx_st)
            try:
                rxcui, name = get_verified_concept(cur, full_pat, "SCD")
                # Add mcg variation
                inp_mcg = name.lower().replace(rx_st.lower(), mcg_st)
                add(inp_mcg, "unit_variations", "resolved", rxcui, name, "",
                    "Clinically equivalent representation using mcg unit.", cluster)
                # Add mg variation with attached unit
                inp_mg = name.lower().replace(rx_st.lower(), mg_st.replace(" ", ""))
                add(inp_mg, "unit_variations", "resolved", rxcui, name, "",
                    "Clinically equivalent representation using mg unit.", cluster)
            except Exception as e:
                logging.warning(f"Unit concept failed: {full_pat}: {e}")

    # 4. Form and Route Variations (ER vs IR, capsules, disintegrating tablets)
    form_items = [
        ("24 HR metoprolol succinate % extended release oral tablet", "metoprolol", ["25 MG", "50 MG", "100 MG", "200 MG"]),
        ("metoprolol tartrate % oral tablet", "metoprolol", ["25 MG", "50 MG", "100 MG"]),
        ("12 HR bupropion hydrochloride % extended release oral tablet", "bupropion", ["100 MG", "150 MG", "200 MG"]),
        ("bupropion hydrochloride % oral tablet", "bupropion", ["75 MG", "100 MG"]),
        ("24 HR venlafaxine % extended release oral capsule", "venlafaxine", ["37.5 MG", "75 MG", "150 MG"]),
        ("venlafaxine % oral tablet", "venlafaxine", ["25 MG", "37.5 MG", "50 MG", "75 MG"]),
        ("potassium chloride % extended release oral tablet", "potassium chloride", ["10 MEQ", "20 MEQ"]),
        ("potassium chloride % extended release oral capsule", "potassium chloride", ["10 MEQ"]),
        ("ondansetron % disintegrating oral tablet", "ondansetron", ["4 MG", "8 MG"]),
        ("ondansetron % oral tablet", "ondansetron", ["4 MG", "8 MG"]),
        ("morphine sulfate % extended release oral tablet", "morphine", ["15 MG", "30 MG", "60 MG"]),
        ("morphine sulfate % oral tablet", "morphine", ["15 MG", "30 MG"]),
        ("oxycodone hydrochloride % oral capsule", "oxycodone", ["5 MG"]),
        ("oxycodone hydrochloride % oral tablet", "oxycodone", ["5 MG", "10 MG", "20 MG"]),
        ("12 HR oxycodone hydrochloride % extended release oral tablet", "oxycodone", ["10 MG", "20 MG", "40 MG"]),
    ]
    for pat, cluster, strengths in form_items:
        for st in strengths:
            full_pat = pat.replace("%", st)
            try:
                rxcui, name = get_verified_concept(cur, full_pat, "SCD")
                add(name.lower(), "form_and_route_variations", "resolved", rxcui, name, "",
                    "Differentiating dosage release mechanisms and specific oral delivery forms.", cluster)
            except Exception as e:
                logging.warning(f"Form concept failed: {full_pat}: {e}")

    # 5. Strength and Concentration (Liquid suspensions & solutions)
    liquid_items = [
        ("amoxicillin 25 MG/ML Oral Suspension", "amoxicillin", "125 mg/5 ml"),
        ("amoxicillin 50 MG/ML Oral Suspension", "amoxicillin", "250 mg/5 ml"),
        ("amoxicillin 40 MG/ML Oral Suspension", "amoxicillin", "200 mg/5 ml"),
        ("amoxicillin 80 MG/ML Oral Suspension", "amoxicillin", "400 mg/5 ml"),
        ("ibuprofen 20 MG/ML Oral Suspension", "ibuprofen", "100 mg/5 ml"),
        ("prednisolone 3 MG/ML Oral Solution", "prednisolone", "15 mg/5 ml"),
        ("acetaminophen 32 MG/ML Oral Solution", "acetaminophen", "160 mg/5 ml"),
        ("diphenhydramine hydrochloride 2.5 MG/ML Oral Solution", "diphenhydramine", "12.5 mg/5 ml"),
        ("furosemide 10 MG/ML Oral Solution", "furosemide", "10 mg/ml"),
        ("azithromycin 40 MG/ML Oral Suspension", "azithromycin", "200 mg/5 ml"),
        ("azithromycin 20 MG/ML Oral Suspension", "azithromycin", "100 mg/5 ml"),
        ("cephalexin 25 MG/ML Oral Suspension", "cephalexin", "125 mg/5 ml"),
        ("cephalexin 50 MG/ML Oral Suspension", "cephalexin", "250 mg/5 ml"),
    ]
    for canon_name, cluster, ratio_input in liquid_items:
        try:
            rxcui, name = get_verified_concept(cur, canon_name, "SCD")
            # 1. Base ML form
            add(name.lower(), "strength_and_concentration", "resolved", rxcui, name, "",
                "Normalized standard per-mL liquid concentration.", cluster)
            # 2. Ratio input (e.g. 250 mg/5 mL)
            drug_name_prefix = name.lower().split()[0]
            form_suffix = "oral suspension" if "suspension" in name.lower() else "oral solution"
            user_query = f"{drug_name_prefix} {ratio_input} {form_suffix}"
            add(user_query, "strength_and_concentration", "resolved", rxcui, name, "",
                f"Clinical liquid dose ratio ({ratio_input}) mathematically equivalent to {name}.", cluster)
        except Exception as e:
            logging.warning(f"Liquid concept failed: {canon_name}: {e}")

    # 6. Salt Variants (PIN vs IN concepts)
    salt_items = [
        ("metoprolol succinate", "PIN", "metoprolol"),
        ("metoprolol tartrate", "PIN", "metoprolol"),
        ("metoprolol", "IN", "metoprolol"),
        ("amlodipine besylate", "PIN", "amlodipine"),
        ("amlodipine", "IN", "amlodipine"),
        ("losartan potassium", "PIN", "losartan"),
        ("losartan", "IN", "losartan"),
        ("diltiazem hydrochloride", "PIN", "diltiazem"),
        ("diltiazem", "IN", "diltiazem"),
        ("diclofenac sodium", "PIN", "diclofenac"),
        ("diclofenac potassium", "PIN", "diclofenac"),
        ("diclofenac", "IN", "diclofenac"),
        ("hydroxyzine hydrochloride", "PIN", "hydroxyzine"),
        ("hydroxyzine pamoate", "PIN", "hydroxyzine"),
        ("hydroxyzine", "IN", "hydroxyzine"),
        ("ciprofloxacin hydrochloride", "PIN", "ciprofloxacin"),
        ("ciprofloxacin", "IN", "ciprofloxacin"),
        ("doxycycline hyclate", "PIN", "doxycycline"),
        ("doxycycline monohydrate", "PIN", "doxycycline"),
        ("doxycycline", "IN", "doxycycline"),
        ("erythromycin", "IN", "erythromycin"),
        ("erythromycin ethylsuccinate", "PIN", "erythromycin"),
        ("erythromycin stearate", "PIN", "erythromycin"),
    ]
    for pat, tty, cluster in salt_items:
        try:
            rxcui, name = get_verified_concept(cur, pat, tty)
            add(pat.lower(), "salt_variants", "resolved", rxcui, name, "",
                f"Distinguishing specific salt/base chemical concept ({tty}).", cluster)
        except Exception as e:
            logging.warning(f"Salt concept failed: {pat}: {e}")

    # 7. Combination Products (Multi-ingredient drugs & reordering)
    combo_items = [
        ("amoxicillin 500 MG / clavulanate 125 MG Oral Tablet", "amoxicillin-clavulanate"),
        ("amoxicillin 875 MG / clavulanate 125 MG Oral Tablet", "amoxicillin-clavulanate"),
        ("amoxicillin 250 MG / clavulanate 125 MG Oral Tablet", "amoxicillin-clavulanate"),
        ("hydrochlorothiazide 12.5 MG / lisinopril 10 MG Oral Tablet", "lisinopril-hctz"),
        ("hydrochlorothiazide 12.5 MG / lisinopril 20 MG Oral Tablet", "lisinopril-hctz"),
        ("hydrochlorothiazide 25 MG / lisinopril 20 MG Oral Tablet", "lisinopril-hctz"),
        ("hydrochlorothiazide 12.5 MG / losartan potassium 50 MG Oral Tablet", "losartan-hctz"),
        ("hydrochlorothiazide 12.5 MG / losartan potassium 100 MG Oral Tablet", "losartan-hctz"),
        ("hydrochlorothiazide 25 MG / losartan potassium 100 MG Oral Tablet", "losartan-hctz"),
        ("amlodipine 5 MG / atorvastatin 10 MG Oral Tablet", "amlodipine-atorvastatin"),
        ("amlodipine 5 MG / atorvastatin 20 MG Oral Tablet", "amlodipine-atorvastatin"),
        ("amlodipine 10 MG / atorvastatin 20 MG Oral Tablet", "amlodipine-atorvastatin"),
        ("metformin hydrochloride 500 MG / sitagliptin 50 MG Oral Tablet", "metformin-sitagliptin"),
        ("metformin hydrochloride 1000 MG / sitagliptin 50 MG Oral Tablet", "metformin-sitagliptin"),
        ("acetaminophen 300 MG / codeine phosphate 30 MG Oral Tablet", "acetaminophen-codeine"),
        ("acetaminophen 325 MG / hydrocodone bitartrate 5 MG Oral Tablet", "acetaminophen-hydrocodone"),
        ("acetaminophen 325 MG / tramadol hydrochloride 37.5 MG Oral Tablet", "acetaminophen-tramadol"),
    ]
    for canon_name, cluster in combo_items:
        try:
            rxcui, name = get_verified_concept(cur, canon_name, "SCD")
            # 1. Standard name
            add(name.lower(), "combination_products", "resolved", rxcui, name, "",
                "Multi-ingredient combination clinical drug.", cluster)
            # 2. Reordered components
            parts = name.lower().split(" / ")
            if len(parts) == 2:
                reordered = f"{parts[1]} / {parts[0]}"
                add(reordered, "combination_products", "resolved", rxcui, name, "",
                    "Multi-ingredient combination with reordered components.", cluster)
        except Exception as e:
            logging.warning(f"Combo concept failed: {canon_name}: {e}")


    # 8. Look-Alike Sound-Alike (LASA) Confusable Pairs
    lasa_pairs = [
        ("hydralazine hydrochloride 25 MG Oral Tablet", "hydralazine"),
        ("hydralazine hydrochloride 50 MG Oral Tablet", "hydralazine"),
        ("hydroxyzine hydrochloride 25 MG Oral Tablet", "hydroxyzine"),
        ("hydroxyzine hydrochloride 50 MG Oral Tablet", "hydroxyzine"),
        ("celecoxib 100 MG Oral Capsule", "celecoxib"),
        ("celecoxib 200 MG Oral Capsule", "celecoxib"),
        ("citalopram 20 MG Oral Tablet", "citalopram"),
        ("citalopram 40 MG Oral Tablet", "citalopram"),
        ("prednisone 5 MG Oral Tablet", "prednisone"),
        ("prednisolone 5 MG Oral Tablet", "prednisolone"),
        ("clonidine hydrochloride 0.1 MG Oral Tablet", "clonidine"),
        ("clonazepam 0.5 MG Oral Tablet", "clonazepam"),
        ("clonazepam 1 MG Oral Tablet", "clonazepam"),
        ("clozapine 25 MG Oral Tablet", "clozapine"),
        ("olanzapine 5 MG Oral Tablet", "olanzapine"),
        ("tramadol hydrochloride 50 MG Oral Tablet", "tramadol"),
        ("trazodone hydrochloride 50 MG Oral Tablet", "trazodone"),
        ("metformin hydrochloride 500 MG Oral Tablet", "metformin"),
        ("metronidazole 500 MG Oral Tablet", "metronidazole"),
        ("fluoxetine 20 MG Oral Capsule", "fluoxetine"),
        ("duloxetine 20 MG Delayed Release Oral Capsule", "duloxetine"),
        ("vinblastine sulfate 1 MG/ML Injectable Solution", "vinblastine"),
        ("1 ML vincristine sulfate 1 MG/ML Injection", "vincristine"),
        ("hydroxychloroquine sulfate 200 MG Oral Tablet", "hydroxychloroquine"),
        ("glipizide 5 MG Oral Tablet", "glipizide"),
        ("glyburide 5 MG Oral Tablet", "glyburide"),
        ("risperidone 1 MG Oral Tablet", "risperidone"),
        ("ropinirole 1 MG Oral Tablet", "ropinirole"),
        ("buspirone hydrochloride 10 MG Oral Tablet", "buspirone"),
        ("amitriptyline hydrochloride 25 MG Oral Tablet", "amitriptyline"),
    ]
    for pat, cluster in lasa_pairs:
        try:
            rxcui, name = get_verified_concept(cur, pat, "SCD")
            add(name.lower(), "look_alike_sound_alike", "resolved", rxcui, name, "",
                "Look-alike / sound-alike high risk confusable drug requiring strict discrimination.", cluster)
        except Exception as e:
            logging.warning(f"LASA concept failed: {pat}: {e}")

    # 9. Insufficient or Ambiguous (Under-specified -> MUST REJECT)
    ambiguous_inputs = [
        ("amoxicillin tablet", "amoxicillin", "Missing strength (250 mg, 500 mg, 875 mg available)"),
        ("amoxicillin capsule", "amoxicillin", "Missing strength (250 mg, 500 mg available)"),
        ("amoxicillin oral suspension", "amoxicillin", "Missing concentration (125mg/5mL, 250mg/5mL, etc.)"),
        ("lisinopril oral tablet", "lisinopril", "Missing strength (2.5 mg, 5 mg, 10 mg, 20 mg, 40 mg available)"),
        ("atorvastatin oral tablet", "atorvastatin", "Missing strength (10 mg, 20 mg, 40 mg, 80 mg available)"),
        ("metformin oral tablet", "metformin", "Missing strength (500 mg, 850 mg, 1000 mg available)"),
        ("metformin 500 mg immediate or extended release tablet", "metformin", "Ambiguous release mechanism (IR vs ER)"),
        ("metoprolol 50 mg tartrate or succinate tablet", "metoprolol", "Ambiguous salt (tartrate vs succinate ER)"),
        ("metoprolol 100 mg tartrate or succinate tablet", "metoprolol", "Ambiguous salt (tartrate vs succinate ER)"),
        ("metoprolol tartrate or succinate", "metoprolol", "Explicitly disjunctive/ambiguous salt input"),
        ("omeprazole capsule", "omeprazole", "Missing strength (10 mg, 20 mg, 40 mg available)"),
        ("losartan oral tablet", "losartan", "Missing strength (25 mg, 50 mg, 100 mg available)"),
        ("gabapentin capsule", "gabapentin", "Missing strength (100 mg, 300 mg, 400 mg available)"),
        ("gabapentin tablet", "gabapentin", "Missing strength (600 mg, 800 mg available)"),
        ("amlodipine oral tablet", "amlodipine", "Missing strength (2.5 mg, 5 mg, 10 mg available)"),
        ("sertraline tablet", "sertraline", "Missing strength (25 mg, 50 mg, 100 mg available)"),
        ("simvastatin tablet", "simvastatin", "Missing strength (10 mg, 20 mg, 40 mg, 80 mg available)"),
        ("furosemide tablet", "furosemide", "Missing strength (20 mg, 40 mg, 80 mg available)"),
        ("pantoprazole tablet", "pantoprazole", "Missing strength (20 mg, 40 mg available)"),
        ("prednisone oral tablet", "prednisone", "Missing strength (1 mg, 2.5 mg, 5 mg, 10 mg, 20 mg, 50 mg available)"),
        ("citalopram oral tablet", "citalopram", "Missing strength (10 mg, 20 mg, 40 mg available)"),
        ("fluoxetine capsule", "fluoxetine", "Missing strength (10 mg, 20 mg, 40 mg available)"),
        ("escitalopram oral tablet", "escitalopram", "Missing strength (5 mg, 10 mg, 20 mg available)"),
        ("rosuvastatin oral tablet", "rosuvastatin", "Missing strength (5 mg, 10 mg, 20 mg, 40 mg available)"),
        ("cetirizine tablet", "cetirizine", "Missing strength (5 mg, 10 mg available)"),
        ("loratadine tablet", "loratadine", "Missing strength (5 mg, 10 mg available)"),
        ("tramadol tablet", "tramadol", "Missing strength (50 mg, 100 mg, 200 mg, 300 mg available)"),
        ("duloxetine capsule", "duloxetine", "Missing strength (20 mg, 30 mg, 40 mg, 60 mg available)"),
        ("carvedilol oral tablet", "carvedilol", "Missing strength (3.125 mg, 6.25 mg, 12.5 mg, 25 mg available)"),
        ("ibuprofen oral tablet", "ibuprofen", "Missing strength (100 mg, 200 mg, 400 mg, 600 mg, 800 mg available)"),
        ("acetaminophen oral tablet", "acetaminophen", "Missing strength (325 mg, 500 mg, 650 mg available)"),
        ("albuterol inhaler", "albuterol", "Missing formulation and dose details"),
        ("insulin glargine injection", "insulin glargine", "Missing delivery system (vial, solostar, etc.)"),
        ("warfarin tablet", "warfarin", "Missing strength (1, 2, 2.5, 3, 4, 5, 6, 7.5, 10 mg available)"),
        ("clonidine tablet", "clonidine", "Missing strength (0.1, 0.2, 0.3 mg available)"),
        ("hydroxyzine tablet", "hydroxyzine", "Missing salt and strength (10, 25, 50 mg available)"),
        ("diltiazem capsule", "diltiazem", "Missing release mechanism and strength"),
        ("potassium chloride tablet", "potassium chloride", "Missing strength (8, 10, 15, 20 mEq available)"),
        ("oxycodone tablet", "oxycodone", "Missing strength and release mechanism"),
        ("morphine tablet", "morphine", "Missing release mechanism and strength"),
        ("alprazolam tablet", "alprazolam", "Missing strength (0.25, 0.5, 1, 2 mg available)"),
        ("bupropion tablet", "bupropion", "Missing release mechanism (IR, SR, XL)"),
        ("doxycycline capsule", "doxycycline", "Missing salt and strength (50, 75, 100 mg available)"),
        ("ciprofloxacin tablet", "ciprofloxacin", "Missing strength (250, 500, 750 mg available)"),
        ("azithromycin tablet", "azithromycin", "Missing strength (250, 500, 600 mg available)"),
        ("cephalexin capsule", "cephalexin", "Missing strength (250, 500, 750 mg available)"),
        ("clopidogrel tablet", "clopidogrel", "Missing strength (75, 300 mg available)"),
        ("venlafaxine capsule", "venlafaxine", "Missing strength (37.5, 75, 150 mg available)"),
        ("ondansetron tablet", "ondansetron", "Missing strength (4, 8, 24 mg available)"),
        ("tamsulosin capsule", "tamsulosin", "Missing strength specification"),
    ]
    for raw_in, cluster, reason in ambiguous_inputs:
        add(raw_in, "insufficient_or_ambiguous", "unresolved", "", "", reason,
            "Under-specified medication input lacking necessary clinical identity attributes.", cluster)

    # 10. Conflicting or Nonexistent (Impossible strengths, fake drugs, conflicting routes -> MUST REJECT)
    conflict_inputs = [
        ("lisinopril 999 mg oral tablet", "lisinopril", "Nonexistent strength (max 40 mg)"),
        ("lisinopril 0.01 mg oral tablet", "lisinopril", "Nonexistent sub-microscopic dose"),
        ("atorvastatin 5000 mg tablet", "atorvastatin", "Lethal impossible strength (max 80 mg)"),
        ("atorvastatin 1 mg oral tablet", "atorvastatin", "Nonexistent strength"),
        ("metformin 10 mg oral tablet", "metformin", "Nonexistent subtherapeutic dose"),
        ("metformin 50000 mg oral tablet", "metformin", "Physically impossible tablet mass"),
        ("amoxicillin 10000 mg oral capsule", "amoxicillin", "Impossible single capsule strength"),
        ("amoxicillin 0.1 mg oral tablet", "amoxicillin", "Nonexistent micro-dose"),
        ("acetaminophen 0.5 mg tablet", "acetaminophen", "Nonexistent homeopathic-like dose"),
        ("acetaminophen 9999 mg oral tablet", "acetaminophen", "Fatal toxic dose in single unit"),
        ("gabapentin 1 mg oral capsule", "gabapentin", "Nonexistent subtherapeutic strength"),
        ("gabapentin 10000 mg oral tablet", "gabapentin", "Impossible tablet weight"),
        ("amlodipine 500 mg oral tablet", "amlodipine", "Fatal overdose strength (max 10 mg)"),
        ("sertraline 5000 mg tablet", "sertraline", "Fatal overdose strength"),
        ("simvastatin 500 mg oral tablet", "simvastatin", "Lethal rhabdomyolysis strength (max 40/80 mg)"),
        ("levothyroxine sodium 500 mg oral tablet", "levothyroxine", "10,000x fatal thyrotoxic overdose (dosed in mcg)"),
        ("levothyroxine 1000 mg oral tablet", "levothyroxine", "Impossible strength; prescriber confused mg with mcg"),
        ("digoxin 100 mg oral tablet", "digoxin", "Massive lethal cardiac glycoside overdose (dosed in 0.125-0.25 mg)"),
        ("furosemide 10000 mg tablet", "furosemide", "Impossible diuretic strength"),
        ("pantoprazole 1000 mg tablet", "pantoprazole", "Nonexistent strength (max 40 mg)"),
        ("prednisone 500 mg oral tablet", "prednisone", "Nonexistent solid oral tablet strength"),
        ("citalopram 500 mg oral tablet", "citalopram", "Fatal QT prolongation overdose strength"),
        ("clopidogrel 1000 mg oral tablet", "clopidogrel", "Nonexistent antiplatelet strength"),
        ("tramadol 2000 mg oral tablet", "tramadol", "Lethal seizure-inducing dose"),
        ("carvedilol 500 mg oral tablet", "carvedilol", "Massive fatal beta blocker dose"),
        ("ibuprofen 50000 mg tablet", "ibuprofen", "Physically impossible tablet mass"),
        ("notarealmedicine 50 mg tablet", "notarealmedicine", "Fabricated non-existent drug name"),
        ("supercillin 500 mg capsule", "supercillin", "Invented antibiotic name"),
        ("fakemed 100 mg tablet", "fakemed", "Nonsense drug name"),
        ("cureall 20 mg oral solution", "cureall", "Fictitious drug"),
        ("placebex 10 mg tablet", "placebex", "Nonsense drug name"),
        ("invalidsaltinil 50 mg oral tablet", "invalidsaltinil", "Fictitious synthetic chemical name"),
        ("amoxicillin 500 mg inhalation powder", "amoxicillin", "Conflicting/nonexistent route for amoxicillin"),
        ("metformin 500 mg ophthalmic drops", "metformin", "Nonsensical ophthalmic route for oral antidiabetic"),
        ("lisinopril 10 mg topical ointment", "lisinopril", "Nonexistent topical route for ACE inhibitor"),
        ("atorvastatin 20 mg nasal spray", "atorvastatin", "Nonexistent nasal formulation for statin"),
        ("digoxin 0.25 mg shampoo", "digoxin", "Absurd conflicting route for cardiac glycoside"),
        ("warfarin 500 mg oral tablet", "warfarin", "Fatal hemorrhagic overdose strength (max 10 mg)"),
        ("fluoxetine 1000 mg capsule", "fluoxetine", "Fatal serotonin syndrome dose"),
        ("duloxetine 1000 mg capsule", "duloxetine", "Fatal overdose strength"),
        ("escitalopram 200 mg tablet", "escitalopram", "Fatal overdose strength (max 20 mg)"),
        ("rosuvastatin 500 mg tablet", "rosuvastatin", "Fatal rhabdomyolysis dose (max 40 mg)"),
        ("bupropion 3000 mg tablet", "bupropion", "Fatal status epilepticus dose (max 450 mg)"),
        ("venlafaxine 2000 mg capsule", "venlafaxine", "Fatal cardiac toxicity dose"),
        ("clonazepam 100 mg tablet", "clonazepam", "Massive central nervous system depression overdose"),
        ("clonidine 50 mg tablet", "clonidine", "Fatal bradycardia/hypotension dose (max 0.3 mg)"),
        ("tamsulosin 40 mg capsule", "tamsulosin", "Severe hypotension dose (normal 0.4 mg)"),
        ("losartan 1000 mg tablet", "losartan", "Dangerous hypotension dose (max 100 mg)"),
        ("cetirizine 200 mg tablet", "cetirizine", "Massive antihistamine overdose (normal 10 mg)"),
        ("loratadine 200 mg tablet", "loratadine", "Massive antihistamine overdose (normal 10 mg)"),
    ]
    for raw_in, cluster, reason in conflict_inputs:
        add(raw_in, "conflicting_or_nonexistent", "unresolved", "", "", reason,
            "Conflicting strength, impossible route, or fictitious entity requiring strict clinical rejection.", cluster)

    conn.close()
    return cases


def perform_anti_leakage_split(cases: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    # 1. Union-Find on active ingredients
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: str, y: str) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for c in cases:
        ings = [p.strip().lower() for p in c["base_ingredient_cluster"].split("-") if p.strip()]
        c["active_ingredients"] = set(ings)
        for i in range(1, len(ings)):
            union(ings[0], ings[i])

    comp_cases = defaultdict(list)
    for c in cases:
        root = find(list(c["active_ingredients"])[0])
        comp_cases[root].append(c)

    # 2. Balanced partition of components
    comps = list(comp_cases.values())
    rng = random.Random(SEED)
    rng.shuffle(comps)

    total_cases = len(cases)
    targets = {
        "calibration": total_cases * 0.40,
        "dev": total_cases * 0.30,
        "held_out_test": total_cases * 0.30,
    }

    splits: dict[str, list[dict]] = {
        "calibration": [],
        "dev": [],
        "held_out_test": [],
    }

    for comp in comps:
        best_split = min(splits.keys(), key=lambda s: len(splits[s]) / targets[s])
        for item in comp:
            item["split"] = best_split
        splits[best_split].extend(comp)

    return splits["calibration"], splits["dev"], splits["held_out_test"]


def save_datasets(cases: list[dict], calib: list[dict], dev: list[dict], test: list[dict]) -> dict:
    fieldnames = [
        "case_id", "raw_input", "category", "expected_status", "expected_rxcui",
        "expected_name", "expected_reason", "rationale", "base_ingredient_cluster", "split"
    ]

    files_to_save = [
        (EVAL_DIR / "full_evaluation_dataset.csv", cases),
        (EVAL_DIR / "calibration.csv", calib),
        (EVAL_DIR / "dev.csv", dev),
        (EVAL_DIR / "held_out_test.csv", test),
        (NORM_EVAL_DIR / "full_evaluation_dataset.csv", cases),
        (NORM_EVAL_DIR / "calibration.csv", calib),
        (NORM_EVAL_DIR / "dev.csv", dev),
        (NORM_EVAL_DIR / "held_out_test.csv", test),
    ]

    for path, data in files_to_save:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in data:
                # Save only expected fields (strip auxiliary fields like active_ingredients)
                writer.writerow({k: row.get(k, "") for k in fieldnames})

    manifest = {
        "dataset_name": "Clinical RxNorm Normalizer Comprehensive Benchmark",
        "total_cases": len(cases),
        "split_counts": {
            "calibration": len(calib),
            "dev": len(dev),
            "held_out_test": len(test),
        },
        "split_percentages": {
            "calibration": round(len(calib) / len(cases) * 100, 1),
            "dev": round(len(dev) / len(cases) * 100, 1),
            "held_out_test": round(len(test) / len(cases) * 100, 1),
        },
        "category_distribution": dict(Counter(c["category"] for c in cases)),
        "status_distribution": dict(Counter(c["expected_status"] for c in cases)),
        "unique_ingredient_clusters": len({c["base_ingredient_cluster"] for c in cases}),
        "anti_leakage_guarantee": "Zero active chemical ingredient overlap and zero normalized query overlap between calibration, dev, and held_out_test.",
    }

    with open(EVAL_DIR / "dataset_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    with open(NORM_EVAL_DIR / "dataset_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest


def main() -> None:
    logging.info("Starting Clinical Evaluation Dataset Generation...")
    cases = build_evaluation_dataset()
    logging.info(f"Total benchmark cases generated: {len(cases)}")

    calib, dev, test = perform_anti_leakage_split(cases)

    # 1. Strict Active Ingredient Zero-Leakage Assertion
    c_ings = set.union(*(c["active_ingredients"] for c in calib))
    d_ings = set.union(*(c["active_ingredients"] for c in dev))
    t_ings = set.union(*(c["active_ingredients"] for c in test))

    assert not (c_ings & d_ings), f"Ingredient leakage between calibration and dev: {c_ings & d_ings}"
    assert not (c_ings & t_ings), f"Ingredient leakage between calibration and test: {c_ings & t_ings}"
    assert not (d_ings & t_ings), f"Ingredient leakage between dev and test: {d_ings & t_ings}"
    logging.info("Strict Active Ingredient Anti-Leakage Gate PASSED (0% chemical overlap).")

    # 2. Strict Normalized Query Zero-Leakage Assertion
    c_q = {normalize_query(c["raw_input"]) for c in calib}
    d_q = {normalize_query(c["raw_input"]) for c in dev}
    t_q = {normalize_query(c["raw_input"]) for c in test}

    assert not (c_q & d_q), f"Query leakage between calibration and dev: {c_q & d_q}"
    assert not (c_q & t_q), f"Query leakage between calibration and test: {c_q & t_q}"
    assert not (d_q & t_q), f"Query leakage between dev and test: {d_q & t_q}"
    logging.info("Strict Query Anti-Leakage Gate PASSED (0% duplicate query overlap).")

    # 3. All 10 categories present in all splits
    for s_name, s_cases in [("calibration", calib), ("dev", dev), ("held_out_test", test)]:
        cats = {c["category"] for c in s_cases}
        assert len(cats) == 10, f"Split {s_name} is missing categories: {10 - len(cats)}"
    logging.info("Category Coverage Gate PASSED (All 10 categories present in all 3 splits).")

    manifest = save_datasets(cases, calib, dev, test)
    logging.info("Datasets successfully generated and saved to data/eval/!")
    logging.info(f"Manifest:\n{json.dumps(manifest, indent=2)}")


if __name__ == "__main__":
    main()
