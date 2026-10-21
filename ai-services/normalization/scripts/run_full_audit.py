#!/usr/bin/env python3
"""
Full PR Revision Audit Runner.
Executes both Baseline and Post-Fix evaluations on the newly partitioned,
zero-leakage, deduplicated datasets:
- calibration.csv
- dev.csv
- held_out_test.csv
- full_evaluation_dataset.csv
- rxnorm_fixture.csv
- rxnorm_adversarial.csv
"""

import csv
import json
import logging
from pathlib import Path
from unittest.mock import patch
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import rxnorm_normalize as rx
from scripts.run_evaluation import evaluate_dataset

REPORTS_DIR = BASE_DIR / "reports"
ROOT_EVAL_DIR = Path("D:/modawem/data/eval")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def run_post_fix_evaluations() -> dict:
    logging.info("=== Running Post-Fix Evaluations ===")
    datasets = {
        "calibration": ROOT_EVAL_DIR / "calibration.csv",
        "dev": ROOT_EVAL_DIR / "dev.csv",
        "held_out_test": ROOT_EVAL_DIR / "held_out_test.csv",
        "full_evaluation_dataset": ROOT_EVAL_DIR / "full_evaluation_dataset.csv",
        "rxnorm_fixture": BASE_DIR / "tests" / "rxnorm_fixture.csv",
        "rxnorm_adversarial": BASE_DIR / "tests" / "rxnorm_adversarial.csv",
    }

    results = {}
    for name, path in datasets.items():
        if path.exists():
            summary, records = evaluate_dataset(path)
            results[name] = summary

            # Save JSON
            with open(REPORTS_DIR / f"postfix_eval_{name}.json", "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)

            # Save CSV
            with open(REPORTS_DIR / f"postfix_eval_{name}.csv", "w", newline="", encoding="utf-8") as f:
                if records:
                    fieldnames = [k for k in records[0].keys() if k != "top_candidates"]
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for r in records:
                        writer.writerow({k: v for k, v in r.items() if k != "top_candidates"})

    return results


def run_baseline_evaluations() -> dict:
    logging.info("=== Running Baseline Evaluations (Simulating Original Unmodified Logic) ===")

    # Baseline query cleaner: only lowercase and remove non-word chars except / . -
    def baseline_normalize_query(text: str) -> str:
        import re
        t = text.lower().strip()
        t = re.sub(r"[^\w\s/.-]", " ", t)
        return re.sub(r"\s+", " ", t).strip()

    # Baseline strength equality: direct string equality only
    def baseline_are_strengths_compatible(requested, available):
        if not requested:
            return True
        if not available:
            return False
        avail_list = list(available)
        for req in requested:
            if req in avail_list:
                avail_list.remove(req)
            else:
                return False
        return True

    # Baseline canonicalize strength: None
    def baseline_canonicalize_strength(st: str):
        return None

    # Baseline attribute state: without structured pairs or unit canonicalization
    def baseline_attribute_state(query: rx.Identity, candidate_name: str) -> str:
        cand = rx.parse_identity(candidate_name)
        if query.strengths and not cand.strengths:
            return "missing"
        if query.strengths and not baseline_are_strengths_compatible(query.strengths, cand.strengths):
            return "conflict"
        if query.forms and not cand.forms:
            return "missing"
        if query.forms and cand.forms and not set(query.forms).issubset(cand.forms):
            return "conflict"
        cand_special = set(cand.forms) & rx._SPECIAL_FORMS
        query_special = set(query.forms) & rx._SPECIAL_FORMS
        if cand_special and not cand_special.issubset(query_special):
            return "conflict"
        if query.routes and not cand.routes:
            return "missing"
        if query.routes and cand.routes and not set(query.routes).issubset(cand.routes):
            return "conflict"
        if query.salts and not cand.salts:
            return "missing"
        if query.salts and cand.salts and not set(query.salts).issubset(cand.salts):
            return "conflict"
        if query.combination and not cand.combination:
            return "conflict"
        return "compatible"

    datasets = {
        "calibration": ROOT_EVAL_DIR / "calibration.csv",
        "dev": ROOT_EVAL_DIR / "dev.csv",
        "held_out_test": ROOT_EVAL_DIR / "held_out_test.csv",
        "full_evaluation_dataset": ROOT_EVAL_DIR / "full_evaluation_dataset.csv",
        "rxnorm_fixture": BASE_DIR / "tests" / "rxnorm_fixture.csv",
        "rxnorm_adversarial": BASE_DIR / "tests" / "rxnorm_adversarial.csv",
    }

    results = {}
    with patch.object(rx, "normalize_query", side_effect=baseline_normalize_query), \
         patch.object(rx, "are_strengths_compatible", side_effect=baseline_are_strengths_compatible), \
         patch.object(rx, "canonicalize_strength", side_effect=baseline_canonicalize_strength), \
         patch.object(rx, "_attribute_state", side_effect=baseline_attribute_state):

        for name, path in datasets.items():
            if path.exists():
                summary, records = evaluate_dataset(path)
                results[name] = summary

                # Save JSON
                with open(REPORTS_DIR / f"baseline_eval_{name}.json", "w", encoding="utf-8") as f:
                    json.dump(summary, f, indent=2)

                # Save CSV
                with open(REPORTS_DIR / f"baseline_eval_{name}.csv", "w", newline="", encoding="utf-8") as f:
                    if records:
                        fieldnames = [k for k in records[0].keys() if k != "top_candidates"]
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        for r in records:
                            writer.writerow({k: v for k, v in r.items() if k != "top_candidates"})

    return results


def main():
    post_fix_results = run_post_fix_evaluations()
    baseline_results = run_baseline_evaluations()

    print("\n" + "="*80)
    print("COMPARATIVE SUMMARY TABLE (Baseline vs Post-Fix)")
    print("="*80)
    print(f"{'Dataset Split':<24} | {'Metric':<10} | {'Baseline':<12} | {'Post-Fix':<12} | {'Delta':<10}")
    print("-" * 80)

    for split in ["calibration", "dev", "held_out_test", "full_evaluation_dataset"]:
        b = baseline_results[split]
        p = post_fix_results[split]

        b_acc = b["accuracy"] * 100
        p_acc = p["accuracy"] * 100
        b_prec = b["precision"] * 100
        p_prec = p["precision"] * 100
        b_rec = b["recall"] * 100
        p_rec = p["recall"] * 100
        b_f1 = b["f1_score"] * 100
        p_f1 = p["f1_score"] * 100

        print(f"{split:<24} | Accuracy   | {b_acc:>10.2f}% | {p_acc:>10.2f}% | {p_acc - b_acc:>+9.2f}%")
        print(f"{'':<24} | Precision  | {b_prec:>10.2f}% | {p_prec:>10.2f}% | {p_prec - b_prec:>+9.2f}%")
        print(f"{'':<24} | Recall     | {b_rec:>10.2f}% | {p_rec:>10.2f}% | {p_rec - b_rec:>+9.2f}%")
        print(f"{'':<24} | F1 Score   | {b_f1:>10.2f}% | {p_f1:>10.2f}% | {p_f1 - b_f1:>+9.2f}%")
        print(f"{'':<24} | FP Count   | {b['false_positives']:>11} | {p['false_positives']:>11} | {p['false_positives'] - b['false_positives']:>+10}")
        print("-" * 80)


if __name__ == "__main__":
    main()
