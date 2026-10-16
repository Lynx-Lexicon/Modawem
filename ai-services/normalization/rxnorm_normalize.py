"""
RxNorm drug-name normalizer.

Usage:
    pip install requests rapidfuzz
    python rxnorm_normalize.py                      # interactive: type names one by one
    python rxnorm_normalize.py paracetmol "metformin 500 mg"
    python rxnorm_normalize.py --debug paracetmol   # print what each stage returned
    python rxnorm_normalize.py --eval data/drug_names_sample.csv

Pipeline:
    1. normalize_query()    -> harmless text cleanup; identity-bearing details are kept
    2. gather_candidates()  -> exact lookup + spelling suggestions + approximate search
    3. rank_candidates()    -> score and order remaining concepts (full-precision similarity)
    4. accept()             -> verify TTY, clinical attributes, threshold, and ambiguity

Lexical similarity ranks strings only. It is not a probability of clinical
correctness. Acceptance also requires parsed strength / form / salt / route /
combination attributes to agree with the candidate, and an allowed RxNorm TTY.

If not confident the status is "unresolved", but the closest guesses are still shown
in `closest` (clearly NOT confirmed) so a human can look at them.

The service may return only these RxNorm term types (TTY): IN (ingredient), PIN
 (precise ingredient), MIN (multiple ingredient), BN (brand name), SCD (clinical
 drug), and SBD (branded drug). Related concepts are used only to establish that
 two candidates are the same RxNorm medication family; a product is never silently
 replaced by one of its ingredients.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field as dataclass_field
from pathlib import Path
import sqlite3
from threading import Lock, Event
from typing import Optional
from urllib.parse import urlencode

import requests
from rapidfuzz import fuzz

BASE_DIR = Path(__file__).resolve().parent
CACHE_DB_PATH = BASE_DIR / "data" / "cache" / "rxnorm_http_cache.sqlite"
if not CACHE_DB_PATH.exists():
    ROOT_CACHE = Path("D:/modawem/data/cache/rxnorm_http_cache.sqlite")
    if ROOT_CACHE.exists():
        CACHE_DB_PATH = ROOT_CACHE

BASE_URL = os.environ.get("RXNORM_BASE_URL", "https://rxnav.nlm.nih.gov/REST")
TIMEOUT_SEC = 5
RETRIES = 2
BACKOFF_BASE_SEC = 0.25
MAX_CACHE_ENTRIES = 1024
AMBIGUITY_MARGIN = 0.05  # if 2 different drugs score this close -> reject
# The public result is always one of these concepts.  SCD/SBD are products;
# the other types are ingredient or brand concepts.
ALLOWED_TTY = {"IN", "PIN", "MIN", "BN", "SCD", "SBD"}
PRODUCT_TTY = {"SCD", "SBD"}
INGREDIENT_TTY = {"IN", "PIN", "MIN"}

_STRENGTH = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|µg|ug|g|ml|iu|units?|%)"
    r"(?:\s*/\s*\d*(?:\.\d+)?\s*(?:ml|l|actuat|puff))?\b",
    re.I,
)
_FORMS = re.compile(
    r"\b(tablets?|tabs?|capsules?|caps?|syrup|suspension|cream|ointment|"
    r"solution|drops?|gel|patch|chewable|chewables|er|xr|sr|film[- ]coated|"
    r"extended[- ]release|delayed[- ]release|immediate[- ]release|"
    r"modified[- ]release|disintegrating(?: oral tablet)?|odt)\b",
    re.I,
)
_ROUTES = re.compile(
    r"\b(oral|injection|topical|inhalation|rectal|vaginal|ophthalmic|otic)\b", re.I
)
_SALT = re.compile(
    r"\b(hydrochloride|hcl|sodium|sulfate|sulphate|maleate|tartrate|succinate|"
    r"acetate|phosphate|citrate|fumarate|besylate|mesylate|bitartrate|potassium|calcium)\b",
    re.I,
)
# Kept as a separate pattern so salts are interpreted wherever they occur in a
# name; salts are identity attributes, not harmless trailing text.
_TRAILING_SALT = re.compile(
    r"\b(?:hydrochloride|hcl|sodium|sulfate|sulphate|maleate|tartrate|succinate|"
    r"acetate|phosphate|citrate|fumarate|besylate|mesylate|bitartrate|potassium|calcium)\b",
    re.I,
)

_FORM_CANON = {
    "tablet": "tablet",
    "tablets": "tablet",
    "tab": "tablet",
    "tabs": "tablet",
    "capsule": "capsule",
    "capsules": "capsule",
    "cap": "capsule",
    "caps": "capsule",
    "syrup": "syrup",
    "suspension": "suspension",
    "cream": "cream",
    "ointment": "ointment",
    "solution": "solution",
    "drop": "drops",
    "drops": "drops",
    "gel": "gel",
    "patch": "patch",
    "chewable": "chewable",
    "chewables": "chewable",
    "er": "extended-release",
    "xr": "extended-release",
    "sr": "extended-release",
    "film-coated": "film-coated",
    "film coated": "film-coated",
    "extended-release": "extended-release",
    "extended release": "extended-release",
    "delayed-release": "delayed-release",
    "delayed release": "delayed-release",
    "immediate-release": "immediate-release",
    "immediate release": "immediate-release",
    "modified-release": "modified-release",
    "modified release": "modified-release",
    "disintegrating oral tablet": "disintegrating oral tablet",
    "disintegrating": "disintegrating oral tablet",
    "odt": "disintegrating oral tablet",
}
_SPECIAL_FORMS = {
    "extended-release",
    "delayed-release",
    "modified-release",
    "disintegrating oral tablet",
}
_SALT_CANON = {
    "hcl": "hydrochloride",
    "hydrochloride": "hydrochloride",
    "sulphate": "sulfate",
    "sulfate": "sulfate",
    "sodium": "sodium",
    "maleate": "maleate",
    "tartrate": "tartrate",
    "succinate": "succinate",
    "acetate": "acetate",
    "phosphate": "phosphate",
    "citrate": "citrate",
    "fumarate": "fumarate",
    "besylate": "besylate",
    "mesylate": "mesylate",
    "bitartrate": "bitartrate",
    "potassium": "potassium",
    "calcium": "calcium",
}
_FILLER = {"salt", "and", "with", "the", "of", "for", "a", "an"}


@dataclass(frozen=True)
class Identity:
    strengths: tuple[str, ...] = ()
    forms: tuple[str, ...] = ()
    routes: tuple[str, ...] = ()
    salts: tuple[str, ...] = ()
    combination: bool = False
    ingredient_tokens: tuple[str, ...] = ()
    ingredient_strength_pairs: tuple[tuple[str, str], ...] = ()

    def has_modifier(self) -> bool:
        return bool(
            self.strengths
            or self.forms
            or self.routes
            or self.salts
            or self.combination
            or self.ingredient_strength_pairs
        )

    def requests_product(self) -> bool:
        return bool(self.strengths or self.forms or self.ingredient_strength_pairs)


@dataclass
class Result:
    input: str
    rxcui: Optional[str]
    matched_name: Optional[str]
    score: float
    status: str  # "resolved" | "unresolved" | "error"
    reason: Optional[str]
    closest: list = dataclass_field(
        default_factory=list
    )  # top guesses, NOT confirmed unless resolved


class RxNormUnavailable(Exception):
    pass


def normalize_query(text: str) -> str:
    """Harmless lookup cleanup: case, punctuation, whitespace, unit separation, clinical abbreviations."""
    t = text.lower().strip()
    # 0. Normalize '+' to ' / ' when used as combination separator
    t = re.sub(r"\s*\+\s*", " / ", t)
    # 1. Normalize combination slashes to have spaces: " / "
    t = re.sub(r"\s*/\s*", " / ", t)
    # 2. Slashes in concentrations/strengths should have NO spaces: e.g. "100 mg / 5 ml" -> "100 mg/5 ml"
    t = re.sub(r"\s*/\s*(?=(?:\d+(?:\.\d+)?\s*)?(?:ml|l|actuat|puff)\b)", "/", t, flags=re.I)
    # 3. Separate attached numbers and units: e.g. 500mg -> 500 mg, 10mcg -> 10 mcg, 5ml -> 5 ml
    t = re.sub(r"(?<=\d)(mg|mcg|µg|ug|g|ml|l|meq|iu|units?|%)\b", r" \1", t, flags=re.I)
    # 4. Separate attached numbers and dosage forms: e.g. 10tab -> 10 tab
    t = re.sub(r"(?<=\d)(tabs?|caps?)\b", r" \1", t, flags=re.I)
    # 5. Safe clinical abbreviations at word boundaries (preserves drug names)
    abbrev_map = [
        (r"\btabs?\b", "tablet"),
        (r"\bcaps?\b", "capsule"),
        (r"\bsusp\b", "suspension"),
        (r"\bsoln\b", "solution"),
        (r"\bpo\b", "oral"),
        (r"\bhcl\b", "hydrochloride"),
        (r"\bodt\b", "disintegrating oral tablet"),
        (r"\bdr\b", "delayed release"),
        (r"\b(?:xr|er|sr)\b", "extended release"),
    ]
    for pattern, repl in abbrev_map:
        t = re.sub(pattern, repl, t, flags=re.I)
    # 6. Punctuation cleanup (keeping / % . -)
    t = re.sub(r"[^\w\s/%.-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def clean(text: str) -> str:
    """Alias of normalize_query; does not strip strength, form, salt, or route."""
    return normalize_query(text)


def _canon_number(match: re.Match) -> str:
    return format(float(match.group(0)), "g")


def _canon_strength(raw: str) -> str:
    s = raw.lower().replace("µg", "mcg").replace("µ", "u")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s*/\s*", "/", s)
    s = re.sub(r"\d+(?:\.\d+)?", _canon_number, s)
    s = re.sub(r"units?\b", "unit", s)
    return s


def canonicalize_strength(st: str) -> Optional[tuple[float, str]]:
    """Convert strength string into canonical (value, unit) tuple.

    Mass units (mcg, mg, g) -> (mg_value, 'mg')
    Liquid concentration ratios (X mg / Y mL) -> (mg_per_ml, 'mg/ml')
    Other units -> (value, 'unit')
    """
    st = st.lower().strip()
    if "/" in st:
        parts = st.split("/", 1)
        num_str, denom_str = parts[0].strip(), parts[1].strip()
        num_m = re.match(
            r"^(\d+(?:\.\d+)?)\s*(mg|mcg|µg|ug|g|meq|iu|units?|%)?$", num_str
        )
        denom_m = re.match(r"^(\d+(?:\.\d+)?\s*)?(ml|l|mg|g)?$", denom_str)
        if num_m and denom_m:
            num_val = float(num_m.group(1))
            num_unit = (num_m.group(2) or "mg").lower()
            denom_val_str = denom_m.group(1)
            denom_val = (
                float(denom_val_str.strip())
                if denom_val_str and denom_val_str.strip()
                else 1.0
            )
            denom_unit = (denom_m.group(2) or "ml").lower()

            if num_unit in ("mcg", "µg", "ug"):
                num_mg = num_val / 1000.0
            elif num_unit == "mg":
                num_mg = num_val
            elif num_unit == "g":
                num_mg = num_val * 1000.0
            else:
                num_mg = None

            if denom_unit == "ml":
                denom_ml = denom_val
            elif denom_unit == "l":
                denom_ml = denom_val * 1000.0
            else:
                denom_ml = None

            if num_mg is not None and denom_ml is not None and denom_ml > 0:
                return (round(num_mg / denom_ml, 6), "mg/ml")

    m = re.match(r"^(\d+(?:\.\d+)?)\s*(mg|mcg|µg|ug|g|ml|l|meq|iu|units?|%)$", st)
    if m:
        val = float(m.group(1))
        unit = m.group(2).lower()
        if unit in ("mcg", "µg", "ug"):
            return (round(val / 1000.0, 6), "mg")
        elif unit == "mg":
            return (round(val, 6), "mg")
        elif unit == "g":
            return (round(val * 1000.0, 6), "mg")
        elif unit in ("units", "unit"):
            return (round(val, 6), "unit")
        else:
            return (round(val, 6), unit)
    return None


def are_strengths_compatible(
    requested: tuple[str, ...], available: tuple[str, ...]
) -> bool:
    """Check if every requested strength has a mathematically compatible available strength."""
    if not requested:
        return True
    if not available:
        return False
    avail_canon = [canonicalize_strength(s) for s in available]
    avail_raw = list(available)
    for req in requested:
        r_c = canonicalize_strength(req)
        match_idx = None
        for idx, a_c in enumerate(avail_canon):
            if r_c is not None and a_c is not None:
                if abs(r_c[0] - a_c[0]) < 1e-5 and r_c[1] == a_c[1]:
                    match_idx = idx
                    break
            elif req == avail_raw[idx]:
                match_idx = idx
                break
        if match_idx is None:
            return False
        avail_canon.pop(match_idx)
        avail_raw.pop(match_idx)
    return True


def _extract_ingredient_strength_pairs(text: str) -> tuple[tuple[str, str], ...]:
    """Extract structured (ingredient, strength) pairs from prescription or candidate text."""
    t = normalize_query(text)
    t_clean = re.sub(r"\[.*?\]", " ", t)
    s_all = list(_STRENGTH.finditer(t_clean))
    parts = re.split(
        r"\s*(?:[/+]|\b(?:and|with)\b)\s*(?!\d*\s*(?:ml|l)\b)", t_clean, flags=re.I
    )
    pairs = []
    if len(parts) > 1:
        for p in parts:
            s_matches = list(_STRENGTH.finditer(p))
            stripped = _STRENGTH.sub(" ", p)
            stripped = _FORMS.sub(" ", stripped)
            stripped = _ROUTES.sub(" ", stripped)
            stripped = _TRAILING_SALT.sub(" ", stripped)
            tokens = [
                w.lower()
                for w in re.findall(r"[a-z0-9]+", stripped)
                if w.lower() not in _FILLER
            ]
            ing = " ".join(tokens)
            if s_matches and ing:
                pairs.append((ing, _canon_strength(s_matches[0].group(0))))
    if len(pairs) != len(s_all) and len(s_all) > 1:
        clean_no_strength = _STRENGTH.sub(" ", t_clean)
        clean_no_strength = _FORMS.sub(" ", clean_no_strength)
        clean_no_strength = _ROUTES.sub(" ", clean_no_strength)
        clean_no_strength = _TRAILING_SALT.sub(" ", clean_no_strength)
        ing_parts = re.split(
            r"\s*[/+]\s*|\s+(?:and|with)\s+", clean_no_strength, flags=re.I
        )
        clean_ings = []
        for ip in ing_parts:
            toks = [
                w.lower()
                for w in re.findall(r"[a-z0-9]+", ip)
                if w.lower() not in _FILLER
            ]
            if toks:
                clean_ings.append(" ".join(toks))
        if len(clean_ings) == len(s_all):
            pairs = list(
                zip(clean_ings, [_canon_strength(sm.group(0)) for sm in s_all])
            )
        else:
            seg_pairs = []
            last_end = 0
            for sm in s_all:
                segment = t_clean[last_end : sm.start()]
                last_end = sm.end()
                stripped = _FORMS.sub(" ", segment)
                stripped = _ROUTES.sub(" ", stripped)
                stripped = _TRAILING_SALT.sub(" ", stripped)
                toks = [
                    w.lower()
                    for w in re.findall(r"[a-z0-9]+", stripped)
                    if w.lower() not in _FILLER
                ]
                if toks:
                    seg_pairs.append((" ".join(toks), _canon_strength(sm.group(0))))
            if len(seg_pairs) == len(s_all):
                pairs = seg_pairs
    elif len(pairs) == 0 and len(s_all) == 1:
        stripped = _STRENGTH.sub(" ", t_clean)
        stripped = _FORMS.sub(" ", stripped)
        stripped = _ROUTES.sub(" ", stripped)
        stripped = _TRAILING_SALT.sub(" ", stripped)
        tokens = [
            w.lower()
            for w in re.findall(r"[a-z0-9]+", stripped)
            if w.lower() not in _FILLER
        ]
        ing = " ".join(tokens)
        if ing:
            pairs.append((ing, _canon_strength(s_all[0].group(0))))
    return tuple(pairs)


def are_ingredient_strength_pairs_compatible(
    query_pairs: tuple[tuple[str, str], ...],
    cand_pairs: tuple[tuple[str, str], ...],
) -> bool:
    """True when each query (ingredient, strength) pair matches a compatible candidate pair."""
    if not query_pairs:
        return True
    if not cand_pairs:
        return False
    if len(query_pairs) != len(cand_pairs):
        return False

    matched_cand_indices = set()
    for q_ing, q_str in query_pairs:
        found = False
        q_words = set(q_ing.split())
        for idx, (c_ing, c_str) in enumerate(cand_pairs):
            if idx in matched_cand_indices:
                continue
            c_words = set(c_ing.split())
            ing_match = bool(
                (q_ing in c_ing)
                or (c_ing in q_ing)
                or (q_words & c_words)
                or (fuzz.ratio(q_ing, c_ing) >= 80)
            )
            if ing_match:
                if are_strengths_compatible((q_str,), (c_str,)):
                    matched_cand_indices.add(idx)
                    found = True
                    break
        if not found:
            return False
    return True


def _canonicalize_query_strengths(text: str) -> str:
    """Replace liquid ratios (e.g. 250 mg/5 ml) and mcg with their RxNorm canonical forms (50 mg/ml, 0.05 mg)."""
    t = text

    def repl_ratio(m: re.Match) -> str:
        num = float(m.group(1))
        denom_str = m.group(2)
        denom = float(denom_str) if denom_str and denom_str.strip() else 1.0
        if denom > 0:
            ratio = num / denom
            return f"{format(ratio, 'g')} mg/ml"
        return m.group(0)

    t = re.sub(
        r"\b(\d+(?:\.\d+)?)\s*mg\s*/\s*(\d+(?:\.\d+)?)?\s*ml\b",
        repl_ratio,
        t,
        flags=re.I,
    )

    def repl_mcg(m: re.Match) -> str:
        val = float(m.group(1))
        mg = val / 1000.0
        return f"{format(mg, 'g')} mg"

    t = re.sub(r"\b(\d+(?:\.\d+)?)\s*(?:mcg|µg|ug)\b", repl_mcg, t, flags=re.I)
    return t


def parse_identity(text: str) -> Identity:
    """Interpret medication attributes. Does not remove them from the lookup string."""
    t = normalize_query(text)
    strength_matches = tuple(_STRENGTH.finditer(t))
    strength_spans = tuple(match.span() for match in strength_matches)
    explicit_combination = any(
        character == "/"
        and not any(start <= index < end for start, end in strength_spans)
        for index, character in enumerate(t)
    )
    strengths = tuple(
        dict.fromkeys(_canon_strength(match.group(0)) for match in strength_matches)
    )
    forms = tuple(
        dict.fromkeys(
            _FORM_CANON[m.group(0).lower().replace("  ", " ")]
            for m in _FORMS.finditer(t)
            if m.group(0).lower().replace("  ", " ") in _FORM_CANON
        )
    )
    routes = tuple(dict.fromkeys(m.group(0).lower() for m in _ROUTES.finditer(t)))
    salts = tuple(
        dict.fromkeys(
            _SALT_CANON[m.group(0).lower()]
            for m in _SALT.finditer(t)
            if m.group(0).lower() in _SALT_CANON
        )
    )
    stripped = _STRENGTH.sub(" ", t)
    stripped = _FORMS.sub(" ", stripped)
    stripped = _ROUTES.sub(" ", stripped)
    stripped = _TRAILING_SALT.sub(" ", stripped)
    stripped = stripped.replace("/", " ")
    leftover = [w for w in re.findall(r"[a-z0-9]+", stripped) if w not in _FILLER]
    combination = explicit_combination
    ingredient_strength_pairs = _extract_ingredient_strength_pairs(t)
    return Identity(
        strengths,
        forms,
        routes,
        salts,
        combination=combination,
        ingredient_tokens=tuple(leftover),
        ingredient_strength_pairs=ingredient_strength_pairs,
    )


def attributes_compatible(query: Identity, candidate_name: str) -> bool:
    """True when candidate attributes confirm the requested attributes."""
    return _attribute_state(query, candidate_name) == "compatible"


def _attribute_state(query: Identity, candidate_name: str) -> str:
    """Classify candidate attributes as compatible, missing, or conflicting."""
    cand = parse_identity(candidate_name)

    # 1. Strengths: mathematical compatibility
    if query.strengths and not cand.strengths:
        return "missing"
    if query.strengths and not are_strengths_compatible(
        query.strengths, cand.strengths
    ):
        return "conflict"

    # 1b. Structured ingredient-strength pairing (order-invariant matching & swapped strength rejection)
    if query.ingredient_strength_pairs and cand.ingredient_strength_pairs:
        if len(query.ingredient_strength_pairs) > 1 or len(cand.ingredient_strength_pairs) > 1:
            if not are_ingredient_strength_pairs_compatible(
                query.ingredient_strength_pairs, cand.ingredient_strength_pairs
            ):
                return "conflict"

    # 2. Forms: subset plus unrequested special forms
    if query.forms and not cand.forms:
        return "missing"
    if query.forms and cand.forms and not set(query.forms).issubset(cand.forms):
        return "conflict"
    cand_special = set(cand.forms) & _SPECIAL_FORMS
    query_special = set(query.forms) & _SPECIAL_FORMS
    if cand_special and not cand_special.issubset(query_special):
        return "conflict"

    # 3. Routes
    if query.routes and not cand.routes:
        return "missing"
    if query.routes and cand.routes and not set(query.routes).issubset(cand.routes):
        return "conflict"

    # 4. Salts
    if query.salts and not cand.salts:
        return "missing"
    if query.salts and cand.salts and not set(query.salts).issubset(cand.salts):
        return "conflict"

    # 5. Combinations
    if query.combination and not cand.combination:
        return "conflict"
    if not query.combination and cand.combination:
        candidate_parts = [part for part in candidate_name.lower().split("/") if part]
        query_tokens = set(query.ingredient_tokens)
        if len(candidate_parts) < 2 or not all(
            set(re.findall(r"[a-z0-9]+", part)) & query_tokens
            for part in candidate_parts[:2]
        ):
            return "conflict"
    return "compatible"


def _lexical_score(term: str, name: str) -> float:
    """Full-precision string similarity in [0, 1]. Not a probability of correctness."""
    other = name.lower()
    return max(fuzz.ratio(term, other), fuzz.token_set_ratio(term, other)) / 100.0


_CALIBRATION_EXAMPLES = (
    ("metformn", "metformin", True),
    ("aspirn", "aspirin", True),
    ("naproxn", "naproxen", True),
    ("etodlac", "etodolac", True),
    ("sulndac", "sulindac", True),
    ("inslin", "insulin", True),
    ("cefdnir", "cefdinir", True),
    ("azithromyc", "azithromycin", True),
    ("clarithromyc", "clarithromycin", True),
    ("erythromyc", "erythromycin", True),
    ("clindamyc", "clindamycin", True),
    ("ramiprl", "ramipril", True),
    ("losartn", "losartan", True),
    ("atenlol", "atenolol", True),
    ("metoprol", "metoprolol", True),
    ("carvediloll", "carvedilol", True),
    ("acetaminophen 500 mg tablet", "acetaminophen 500 MG Oral Tablet", True),
    (
        "amoxicillin 100 mg/5 ml suspension",
        "amoxicillin 100 MG/5 ML Oral Suspension",
        True,
    ),
    ("amoxicillin clavulanate", "amoxicillin / clavulanate", True),
    ("metoprolol tartrate", "metoprolol tartrate", True),
    ("paracetmol", "acetaminophen", True),
    ("metformin 500 mg tablet", "metformin 1000 MG Oral Tablet", False),
    ("acetaminophen 0.5 mg tablet", "acetaminophen 5 MG Oral Tablet", False),
    ("amoxicillin 100 mg/5 ml", "amoxicillin 5 MG/ML Oral Solution", False),
    ("metoprolol tartrate", "metoprolol succinate", False),
    ("amoxicillin 250 mg tablet", "amoxicillin 250 MG Oral Capsule", False),
    ("metformin", "metoprolol", False),
    ("metforman", "metformin", False),
    ("aspirn", "aspirin 325 MG Oral Tablet", False),
    ("naproxn", "naproxen sodium", False),
    ("etodlac", "etodolol", False),
    ("sulndac", "sulfamethoxazole", False),
    ("inslin", "inulin", False),
    ("azithromyc", "clarithromycin", False),
    ("clindamyc", "clindamax", False),
    ("ramiprl", "ramelteon", False),
    ("losartn", "losartan potassium", False),
    ("atenlol", "atenolol 100 MG Oral Tablet", False),
    ("metoprol", "metoprolol succinate", False),
    ("carvediloll", "carvedilol phosphate", False),
)


def _calibrate_accept_threshold() -> float:
    """Set the lexical floor from reviewed same-concept fixture scores.

    Similarity is only a string-ranking signal, never a probability of
    correctness. Clinical attribute compatibility remains mandatory.
    """
    positives = [
        _lexical_score(query, candidate)
        for query, candidate, label in _CALIBRATION_EXAMPLES
        if label
    ]
    negatives = [
        _lexical_score(query, candidate)
        for query, candidate, label in _CALIBRATION_EXAMPLES
        if not label
    ]
    thresholds = sorted({0.0, *positives, *negatives})

    def balanced_accuracy(threshold: float) -> float:
        sensitivity = sum(score >= threshold for score in positives) / len(positives)
        specificity = sum(score < threshold for score in negatives) / len(negatives)
        return (sensitivity + specificity) / 2

    # Prefer the stricter threshold when evidence produces a tie. This is a
    # lexical floor only; attributes and TTY still decide clinical eligibility.
    return max(
        thresholds, key=lambda threshold: (balanced_accuracy(threshold), threshold)
    )


ACCEPT_THRESHOLD = _calibrate_accept_threshold()


_http_lock = Lock()
_http_in_flight: dict[str, Event] = {}
_http_last_error: dict[str, str] = {}


def _get(path: str, params: dict) -> dict:
    param_str = urlencode(sorted((k, str(v)) for k, v in params.items()))
    cache_key = f"{path}?{param_str}" if param_str else path

    while True:
        leader = False
        with _http_lock:
            if CACHE_DB_PATH and CACHE_DB_PATH.exists():
                try:
                    with sqlite3.connect(CACHE_DB_PATH) as conn:
                        cur = conn.cursor()
                        cur.execute(
                            "SELECT response_json FROM http_cache WHERE cache_key = ?",
                            (cache_key,),
                        )
                        row = cur.fetchone()
                        if row:
                            payload = json.loads(row[0])
                            if isinstance(payload, dict):
                                return payload
                except Exception:
                    pass

            if cache_key in _http_in_flight:
                event = _http_in_flight[cache_key]
            else:
                event = Event()
                _http_in_flight[cache_key] = event
                leader = True

        if not leader:
            event.wait()
            with _http_lock:
                if CACHE_DB_PATH and CACHE_DB_PATH.exists():
                    try:
                        with sqlite3.connect(CACHE_DB_PATH) as conn:
                            cur = conn.cursor()
                            cur.execute(
                                "SELECT response_json FROM http_cache WHERE cache_key = ?",
                                (cache_key,),
                            )
                            row = cur.fetchone()
                            if row:
                                payload = json.loads(row[0])
                                if isinstance(payload, dict):
                                    return payload
                    except Exception:
                        pass
                err_msg = _http_last_error.get(cache_key)
                if err_msg is not None:
                    raise RxNormUnavailable(f"{path}: {err_msg}")
            continue

        last: Exception | None = None
        try:
            for attempt in range(RETRIES + 1):
                try:
                    r = requests.get(
                        f"{BASE_URL}{path}", params=params, timeout=TIMEOUT_SEC
                    )
                    r.raise_for_status()
                    payload = r.json()
                    if not isinstance(payload, dict):
                        raise ValueError("response JSON must be an object")
                    if CACHE_DB_PATH and CACHE_DB_PATH.exists():
                        try:
                            with sqlite3.connect(CACHE_DB_PATH) as conn:
                                conn.execute(
                                    "INSERT OR REPLACE INTO http_cache (cache_key, path, params, response_json) VALUES (?, ?, ?, ?)",
                                    (
                                        cache_key,
                                        path,
                                        json.dumps(params),
                                        json.dumps(payload, ensure_ascii=False),
                                    ),
                                )
                                conn.commit()
                        except Exception:
                            pass
                    with _http_lock:
                        _http_last_error.pop(cache_key, None)
                    return payload
                except requests.HTTPError as e:
                    last = e
                    status = getattr(getattr(e, "response", None), "status_code", None)
                    if status is None:
                        status = getattr(r, "status_code", None)
                    retryable = status == 429 or (
                        status is not None and 500 <= status <= 599
                    )
                    if not retryable:
                        break
                except (requests.RequestException, ValueError) as e:
                    last = e
                if attempt < RETRIES:
                    time.sleep(BACKOFF_BASE_SEC * (2**attempt))
            raise RxNormUnavailable(f"{path}: {last or 'request failed'}")
        except Exception as e:
            with _http_lock:
                _http_last_error[cache_key] = str(e)
            raise
        finally:
            with _http_lock:
                _http_in_flight.pop(cache_key, None)
                event.set()


def _mapping(value, path: str, field_name: str) -> dict:
    if not isinstance(value, dict):
        raise RxNormUnavailable(f"{path}: missing or malformed {field_name}")
    return value


def _string_list(value, path: str, field_name: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise RxNormUnavailable(f"{path}: missing or malformed {field_name}")
    return value


def _exact(term: str) -> list[str]:
    d = _get("/rxcui.json", {"name": term, "search": 2})
    group = _mapping(d.get("idGroup"), "/rxcui.json", "idGroup")
    return _string_list(group.get("rxnormId", []), "/rxcui.json", "rxnormId")


def _spelling(term: str) -> list[str]:
    d = _get("/spellingsuggestions.json", {"name": term})
    group = _mapping(
        d.get("suggestionGroup"), "/spellingsuggestions.json", "suggestionGroup"
    )
    suggestions = _mapping(
        group.get("suggestionList"), "/spellingsuggestions.json", "suggestionList"
    )
    return _string_list(
        suggestions.get("suggestion", []), "/spellingsuggestions.json", "suggestion"
    )


class ApproximateCandidates(list):
    """Usable approximate candidates plus diagnostics for discarded entries."""

    def __init__(self, candidates: list[dict], diagnostics: list[str]) -> None:
        super().__init__(candidates)
        self.diagnostics = diagnostics


def _approx(term: str) -> ApproximateCandidates:
    d = _get("/approximateTerm.json", {"term": term, "maxEntries": 10})
    group = _mapping(
        d.get("approximateGroup"), "/approximateTerm.json", "approximateGroup"
    )
    candidates = group.get("candidate", [])
    if not isinstance(candidates, list):
        raise RxNormUnavailable("/approximateTerm.json: missing or malformed candidate")
    usable = []
    diagnostics = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            diagnostics.append("discarded non-object approximate candidate")
            continue
        if (
            not isinstance(candidate.get("rxcui"), str)
            or not candidate["rxcui"].strip()
        ):
            diagnostics.append("discarded approximate candidate with malformed rxcui")
            continue
        if not isinstance(candidate.get("name"), str) or not candidate["name"].strip():
            diagnostics.append("discarded approximate candidate with malformed name")
            continue
        usable.append(candidate)
    return ApproximateCandidates(usable, diagnostics)


def _props(rxcui: str) -> tuple[Optional[str], Optional[str]]:
    d = _get(f"/rxcui/{rxcui}/properties.json", {})
    p = _mapping(d.get("properties"), f"/rxcui/{rxcui}/properties.json", "properties")
    name = p.get("name")
    tty = p.get("tty")
    if (
        not isinstance(name, str)
        or not name.strip()
        or not isinstance(tty, str)
        or not tty.strip()
    ):
        raise RxNormUnavailable(f"/rxcui/{rxcui}/properties.json: missing name or tty")
    return name, tty


def _related(rxcui: str) -> list[tuple[str, str, str]]:
    """Map any concept (e.g. a tablet product) to its ingredient / brand concepts."""
    d = _get(f"/rxcui/{rxcui}/related.json", {"tty": "IN MIN PIN BN"})
    out = []
    group = _mapping(
        d.get("relatedGroup"), f"/rxcui/{rxcui}/related.json", "relatedGroup"
    )
    concept_groups = group.get("conceptGroup", [])
    if not isinstance(concept_groups, list) or any(
        not isinstance(item, dict) for item in concept_groups
    ):
        raise RxNormUnavailable(f"/rxcui/{rxcui}/related.json: malformed conceptGroup")
    for concept_group in concept_groups:
        properties = concept_group.get("conceptProperties", [])
        if not isinstance(properties, list) or any(
            not isinstance(item, dict) for item in properties
        ):
            raise RxNormUnavailable(
                f"/rxcui/{rxcui}/related.json: malformed conceptProperties"
            )
        for prop in properties:
            if any(
                not isinstance(prop.get(key), str) or not prop[key].strip()
                for key in ("rxcui", "name", "tty")
            ):
                raise RxNormUnavailable(
                    f"/rxcui/{rxcui}/related.json: malformed concept property"
                )
            out.append((prop["rxcui"], prop["name"], prop["tty"]))
    return out


# ---------------------------------------------------------------- Normalizer
class RxNormNormalizer:
    def __init__(self, debug: bool = False) -> None:
        self.debug = debug
        self._cache: dict[str, Result] = {}
        self._props_cache: dict[str, tuple] = {}
        self._related_cache: dict[str, list] = {}
        self._cache_lock = Lock()
        self._props_lock = Lock()
        self._related_lock = Lock()
        self._in_flight: dict[str, Event] = {}
        self._props_in_flight: dict[str, Event] = {}
        self._related_in_flight: dict[str, Event] = {}
        self._last_error: dict[str, str] = {}
        self.diagnostics: list[str] = []

    @staticmethod
    def _remember(cache: dict, key: str, value) -> None:
        if key in cache:
            cache.pop(key)
        cache[key] = value
        while len(cache) > MAX_CACHE_ENTRIES:
            cache.pop(next(iter(cache)))

    def _log(self, *a) -> None:
        if self.debug:
            print("[debug]", *a, file=sys.stderr)

    def _get_props(self, rxcui: str):
        while True:
            leader = False
            with self._props_lock:
                cached = self._props_cache.get(rxcui)
                if cached is not None:
                    return cached
                if rxcui in self._props_in_flight:
                    event = self._props_in_flight[rxcui]
                else:
                    event = Event()
                    self._props_in_flight[rxcui] = event
                    leader = True

            if not leader:
                event.wait()
                with self._props_lock:
                    cached = self._props_cache.get(rxcui)
                    if cached is not None:
                        return cached
                continue

            try:
                value = _props(rxcui)
                with self._props_lock:
                    self._remember(self._props_cache, rxcui, value)
                return value
            finally:
                with self._props_lock:
                    self._props_in_flight.pop(rxcui, None)
                    event.set()

    def _get_related(self, rxcui: str):
        while True:
            leader = False
            with self._related_lock:
                cached = self._related_cache.get(rxcui)
                if cached is not None:
                    return cached
                if rxcui in self._related_in_flight:
                    event = self._related_in_flight[rxcui]
                else:
                    event = Event()
                    self._related_in_flight[rxcui] = event
                    leader = True

            if not leader:
                event.wait()
                with self._related_lock:
                    cached = self._related_cache.get(rxcui)
                    if cached is not None:
                        return cached
                continue

            try:
                value = _related(rxcui)
                with self._related_lock:
                    self._remember(self._related_cache, rxcui, value)
                return value
            finally:
                with self._related_lock:
                    self._related_in_flight.pop(rxcui, None)
                    event.set()

    def gather_candidates(self, term: str) -> list[tuple[str, Optional[str]]]:
        """Exact, spelling, and approximate hits, deduplicated by rxcui (exact first)."""
        ordered: list[tuple[str, Optional[str]]] = []
        seen: set[str] = set()

        def add(rxcui: Optional[str], text: Optional[str]) -> None:
            if not rxcui or rxcui in seen:
                if rxcui and text:
                    for index, (known_rxcui, known_text) in enumerate(ordered):
                        if known_rxcui == rxcui and not known_text:
                            ordered[index] = (rxcui, text)
                            break
                return
            seen.add(rxcui)
            ordered.append((rxcui, text))

        def collect(lookup_term: str) -> None:
            exact = _exact(lookup_term)
            self._log("exact:", exact)
            for rx in exact:
                add(rx, None)

            sugg = _spelling(lookup_term)[:5]
            self._log("spelling suggestions:", sugg)
            for s in sugg:
                for rx in _exact(s):
                    add(rx, s.lower())

            approx = _approx(lookup_term)
            diagnostics = getattr(approx, "diagnostics", [])
            self.diagnostics.extend(diagnostics)
            for diagnostic in diagnostics:
                self._log("approximate:", diagnostic)
            self._log("approximate:", approx[:5])
            for c in approx:
                add(c.get("rxcui"), None)

        collect(term)

        canon_term = _canonicalize_query_strengths(term)
        if canon_term != term:
            try:
                collect(canon_term)
            except RxNormUnavailable:
                pass

        if not ordered and " / " in term:
            try:
                parts = term.split(" / ")
                if len(parts) == 2:
                    reordered = f"{parts[1].strip()} / {parts[0].strip()}"
                    collect(reordered)
                    canon_reordered = _canonicalize_query_strengths(reordered)
                    if canon_reordered != reordered:
                        collect(canon_reordered)
            except RxNormUnavailable:
                pass

        return ordered

    @staticmethod
    def _normalize_candidates(
        cands: list[tuple[str, Optional[str]]],
    ) -> list[tuple[str, Optional[str]]]:
        """Deduplicate RxCUIs while retaining the first source spelling."""
        unique: dict[str, Optional[str]] = {}
        for rxcui, text in cands:
            if rxcui not in unique or (unique[rxcui] is None and text):
                unique[rxcui] = text
        return list(unique.items())

    @staticmethod
    def _canonical_tty(tty: Optional[str]) -> str:
        return (tty or "").strip().upper()

    def rank_candidates(
        self,
        term: str,
        cands: list[tuple[str, Optional[str]]],
        identity: Identity | None = None,
    ) -> list[tuple[str, float, str, str]]:
        """Return (rxcui, score, name, tty) sorted by score desc, then rxcui, name.

        Filters disallowed TTY and concept types that would drop requested
        specificity. Ranking does not accept or reject a match.
        """
        identity = identity or parse_identity(term)
        scored: list[tuple[str, float, str, str]] = []
        for rxcui, text in self._normalize_candidates(cands):
            try:
                name, raw_tty = self._get_props(rxcui)
            except RxNormUnavailable as exc:
                self.diagnostics.append(f"discarded candidate {rxcui}: {exc}")
                self._log("discarded candidate:", rxcui, exc)
                continue
            tty = self._canonical_tty(raw_tty)
            if not name or tty not in ALLOWED_TTY:
                continue
            if identity.requests_product() and tty not in PRODUCT_TTY:
                continue
            if identity.combination and tty == "IN":
                continue
            score = _lexical_score(term, name)
            canon_term = _canonicalize_query_strengths(term)
            if canon_term != term:
                score = max(score, _lexical_score(canon_term, name))
            if text and not identity.has_modifier():
                score = max(score, _lexical_score(term, normalize_query(text)))
            scored.append((rxcui, score, name, tty))
        scored.sort(
            key=lambda row: (
                -row[1],
                0 if row[3] == "SCD" else 1,
                row[0],
                row[2],
            )
        )
        return scored

    def accept(
        self,
        original: str,
        ranked: list[tuple[str, float, str, str]],
        identity: Identity,
        had_candidates: bool,
    ) -> Result:
        """Accept or reject the already-ranked list. Does not re-order candidates."""
        closest = [
            {"rxcui": rx, "name": nm, "score": sc, "tty": tty}
            for rx, sc, nm, tty in ranked[:3]
        ]
        self._log("ranked:", closest)

        if not had_candidates:
            return Result(
                original,
                None,
                None,
                0.0,
                "unresolved",
                "RxNorm returned no candidates for this name",
            )
        if not ranked:
            return Result(
                original,
                None,
                None,
                0.0,
                "unresolved",
                "Candidates found but none maps to an ingredient or brand",
            )

        compatible = [
            candidate
            for candidate in ranked
            if (
                _attribute_state(identity, candidate[2]) == "compatible"
                or (
                    not identity.has_modifier()
                    and candidate[3] in INGREDIENT_TTY
                    and _attribute_state(identity, candidate[2]) == "conflict"
                    and not identity.combination
                )
            )
        ]
        if not compatible:
            state = _attribute_state(identity, ranked[0][2])
            reason = (
                "Top candidate conflicts with requested medication attributes"
                if state == "conflict"
                else "Candidates do not provide enough medication attribute information"
            )
            return Result(
                original,
                None,
                None,
                ranked[0][1],
                "unresolved",
                reason,
                closest,
            )
        top_rxcui, top_score, top_name, _top_tty = compatible[0]
        if top_score < ACCEPT_THRESHOLD:
            return Result(
                original,
                None,
                None,
                top_score,
                "unresolved",
                "No sufficiently reliable match",
                closest,
            )

        rivals = []
        top_ident = parse_identity(top_name)
        top_ing_str = " ".join(top_ident.ingredient_tokens)
        query_ing_str = " ".join(identity.ingredient_tokens)
        top_ing_score = (
            max(
                fuzz.ratio(query_ing_str, top_ing_str),
                fuzz.token_sort_ratio(query_ing_str, top_ing_str),
            )
            / 100.0
            if query_ing_str and top_ing_str
            else 1.0
        )

        top_name_clean = normalize_query(top_name)
        canon_top = _canonicalize_query_strengths(top_name_clean)
        term_clean = normalize_query(original)
        canon_term = _canonicalize_query_strengths(term_clean)
        top_is_exact = (
            fuzz.ratio(term_clean, top_name_clean) == 100
            or fuzz.ratio(canon_term, canon_top) == 100
            or fuzz.token_sort_ratio(term_clean, top_name_clean) == 100
            or fuzz.token_sort_ratio(canon_term, canon_top) == 100
        )

        for rxcui, score, name, _tty in compatible[1:]:
            if self._same_concept_family(top_rxcui, rxcui):
                continue
            if top_is_exact:
                name_clean = normalize_query(name)
                canon_name = _canonicalize_query_strengths(name_clean)
                rival_is_exact = (
                    fuzz.ratio(term_clean, name_clean) == 100
                    or fuzz.ratio(canon_term, canon_name) == 100
                    or fuzz.token_sort_ratio(term_clean, name_clean) == 100
                    or fuzz.token_sort_ratio(canon_term, canon_name) == 100
                )
                if not rival_is_exact:
                    continue
            if query_ing_str:
                rival_ident = parse_identity(name)
                rival_ing_str = " ".join(rival_ident.ingredient_tokens)
                if rival_ing_str:
                    rival_ing_score = (
                        max(
                            fuzz.ratio(query_ing_str, rival_ing_str),
                            fuzz.token_sort_ratio(query_ing_str, rival_ing_str),
                        )
                        / 100.0
                    )
                    if top_ing_score >= ACCEPT_THRESHOLD and (
                        rival_ing_score < ACCEPT_THRESHOLD
                        or (top_ing_score - rival_ing_score > AMBIGUITY_MARGIN)
                    ):
                        continue
            rivals.append((score, name))
        if (
            rivals
            and rivals[0][0] >= ACCEPT_THRESHOLD
            and top_score - rivals[0][0] <= AMBIGUITY_MARGIN
        ):
            return Result(
                original,
                None,
                None,
                top_score,
                "unresolved",
                f"Ambiguous: close candidates '{top_name}' and '{rivals[0][1]}'",
                closest,
            )
        return Result(
            original, top_rxcui, top_name, top_score, "resolved", None, closest[:1]
        )

    def decide(self, original: str, term: str, cands) -> Result:
        identity = parse_identity(term)
        if not identity.combination and self._verified_query_combination(term, cands):
            identity = Identity(
                identity.strengths,
                identity.forms,
                identity.routes,
                identity.salts,
                combination=True,
            )
        ranked = self.rank_candidates(term, cands, identity)
        return self.accept(original, ranked, identity, had_candidates=bool(cands))

    def _verified_query_combination(
        self, term: str, cands: list[tuple[str, Optional[str]]]
    ) -> bool:
        """Recognize space-separated combinations only from verified RxNorm data."""
        query_tokens = set(re.findall(r"[a-z0-9]+", term.lower()))
        for rxcui, _ in self._normalize_candidates(cands):
            try:
                name, tty = self._get_props(rxcui)
            except RxNormUnavailable:
                continue
            if self._canonical_tty(tty) != "MIN":
                continue
            related = self._get_related(rxcui)
            ingredients = [
                ingredient_name.lower()
                for _, ingredient_name, ingredient_tty in related
                if self._canonical_tty(ingredient_tty) in {"IN", "PIN"}
            ]
            if len(ingredients) < 2:
                ingredients = [part.strip().lower() for part in name.split("/")]
            if len(ingredients) >= 2 and all(
                set(re.findall(r"[a-z0-9]+", ingredient)) & query_tokens
                for ingredient in ingredients[:2]
            ):
                return True
        return False

    def _same_concept_family(self, first: str, second: str) -> bool:
        """Allow explicit brand/ingredient relationship or SCD/SBD brand product relationship."""
        if first == second:
            return True
        first_name, first_tty = self._get_props(first)
        second_name, second_tty = self._get_props(second)
        first_tty = self._canonical_tty(first_tty)
        second_tty = self._canonical_tty(second_tty)

        # 1. SCD <-> SBD relationship: SBD name in RxNorm is always "<SCD Name> [<Brand Name>]"
        if (first_tty == "SCD" and second_tty == "SBD") or (
            first_tty == "SBD" and second_tty == "SCD"
        ):
            scd_name = first_name if first_tty == "SCD" else second_name
            sbd_name = second_name if first_tty == "SCD" else first_name
            if sbd_name.strip().lower().startswith(f"{scd_name.strip().lower()} ["):
                return True

        # 2. Brand / Ingredient relationship
        if first_tty == second_tty:
            return False
        brand_ingredient = (first_tty == "BN" and second_tty in INGREDIENT_TTY) or (
            second_tty == "BN" and first_tty in INGREDIENT_TTY
        )
        if not brand_ingredient:
            return False
        first_related = {rx for rx, _, _ in self._get_related(first)}
        second_related = {rx for rx, _, _ in self._get_related(second)}
        return second in first_related or first in second_related

    def normalize(self, name: str) -> Result:
        if not isinstance(name, str) or not name.strip():
            return Result(str(name), None, None, 0.0, "unresolved", "Empty input")
        term = normalize_query(name)
        self._log("cleaned:", repr(term))
        if not term:
            return Result(
                name, None, None, 0.0, "unresolved", "Nothing left after cleaning"
            )
        key = term
        while True:
            leader = False
            with self._cache_lock:
                cached = self._cache.get(key)
                if cached is not None:
                    return cached
                if key in self._in_flight:
                    event = self._in_flight[key]
                else:
                    event = Event()
                    self._in_flight[key] = event
                    leader = True

            if not leader:
                event.wait()
                with self._cache_lock:
                    cached = self._cache.get(key)
                    if cached is not None:
                        return cached
                    err_msg = self._last_error.get(key)
                    if err_msg is not None:
                        return Result(
                            name,
                            None,
                            None,
                            0.0,
                            "error",
                            f"RxNorm API unavailable: {err_msg}",
                        )
                continue

            result: Optional[Result] = None
            err_msg: Optional[str] = None
            try:
                cands = self.gather_candidates(term)
                result = self.decide(name, term, cands)
                return result
            except RxNormUnavailable as e:
                err_msg = str(e)
                return Result(
                    name, None, None, 0.0, "error", f"RxNorm API unavailable: {e}"
                )
            except Exception as e:
                err_msg = str(e)
                return Result(
                    name,
                    None,
                    None,
                    0.0,
                    "error",
                    f"Unexpected normalization error: {e}",
                )
            finally:
                with self._cache_lock:
                    if result is not None and result.status != "error":
                        self._remember(self._cache, key, result)
                    if err_msg is not None:
                        self._last_error[key] = err_msg
                    else:
                        self._last_error.pop(key, None)
                    self._in_flight.pop(key, None)
                    event.set()


# ---------------------------------------------------------------- Output / CLI
def show(res: Result) -> None:
    if res.status == "resolved":
        print(
            f"[MATCH] {res.input!r} -> {res.matched_name} (RxCUI {res.rxcui}) score={res.score:.0%}"
        )
    else:
        print(f"[{res.status.upper()}] {res.input!r}: {res.reason}")
        for c in res.closest:
            print(
                f"   closest guess (NOT confirmed): {c['name']} (RxCUI {c['rxcui']}) {c['score']:.0%}"
            )
    print(json.dumps(asdict(res), indent=2, ensure_ascii=False))
    print()


def _read_evaluation_rows(path: str) -> list[dict[str, str]]:
    required = {"input", "expected_rxcui", "case_category"}
    with open(path, newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        columns = set(reader.fieldnames or [])
        missing = required - columns
        if missing:
            raise ValueError(
                f"{path}: missing CSV columns: {', '.join(sorted(missing))}"
            )
        rows = list(reader)

    allowed = {"correct", "misspelled"}
    adversarial = {
        "unknown",
        "ambiguous",
        "similar_drug_name",
        "salt_variant",
        "combination_product",
        "strength_difference",
    }
    categories = {row.get("case_category", "").strip() for row in rows}
    invalid = categories - allowed - adversarial
    if invalid:
        raise ValueError(
            f"{path}: unsupported case categories: {', '.join(sorted(invalid))}"
        )
    if not rows:
        raise ValueError(f"{path}: fixture must contain at least one row")

    positive = categories & allowed
    adversarial_categories = categories & adversarial
    if positive and adversarial_categories:
        raise ValueError(
            f"{path}: positive and adversarial rows must use separate fixtures"
        )
    if adversarial_categories and not {
        "expected_status",
        "expected_acceptance",
    }.issubset(columns):
        raise ValueError(
            f"{path}: adversarial fixtures require expected_status and expected_acceptance columns"
        )

    seen: dict[str, tuple[str, str, str, str, str]] = {}

    malformed = []
    for number, row in enumerate(rows, start=2):
        category = (row.get("case_category") or "").strip()
        name = (row.get("input") or "").strip()
        expected = (row.get("expected_rxcui") or "").strip()
        if not name or not category:
            malformed.append(str(number))
        if category in allowed and not expected:
            malformed.append(str(number))
        if category in adversarial:
            status = (row.get("expected_status") or "").strip()
            if status not in {"resolved", "unresolved"}:
                malformed.append(str(number))
            if (row.get("expected_acceptance") or "").strip().lower() not in {
                "true",
                "false",
            }:
                malformed.append(str(number))
            accepted = (row.get("expected_acceptance") or "").strip().lower() == "true"
            if accepted != (status == "resolved" and bool(expected)):
                malformed.append(str(number))
        if name:
            label = (
                category,
                expected,
                (row.get("expected_status") or "").strip(),
                (row.get("expected_acceptance") or "").strip().lower(),
                (row.get("verification") or "").strip(),
            )
            prior = seen.get(name.casefold())
            if prior is not None:
                malformed.append(str(number))
            seen[name.casefold()] = label
        if None in row:
            malformed.append(str(number))
    if malformed:
        raise ValueError(
            f"{path}: malformed fixture row(s): {', '.join(sorted(set(malformed)))}"
        )

    if positive:
        counts = {
            category: sum(row["case_category"].strip() == category for row in rows)
            for category in allowed
        }
        missing_categories = allowed - positive
        if missing_categories or any(counts[category] < 100 for category in allowed):
            raise ValueError(
                f"{path}: fixture requires at least 100 correct and 100 misspelled rows; "
                f"counts={counts}"
            )

    return rows


def evaluate(path: str, debug: bool = False) -> int:
    """Evaluate a positive fixture or an adversarial rejection fixture.

    Positive rows must use ``case_category`` values ``correct`` or
    ``misspelled`` and are checked against their exact expected RxCUI. An
    adversarial row has a blank expected RxCUI and counts any resolution as a
    false positive.
    """
    targets = {"correct": 0.95, "misspelled": 0.85}
    rows = _read_evaluation_rows(path)
    norm = RxNormNormalizer(debug)
    stats = {
        category: {
            "correct": 0,
            "false_positive": 0,
            "expected_failure": 0,
            "unresolved": 0,
            "api_error": 0,
            "total": 0,
        }
        for category in {row["case_category"].strip() for row in rows}
    }
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = executor.map(norm.normalize, (row["input"].strip() for row in rows))

    for row, result in zip(rows, results):
        category = row["case_category"].strip()
        expected = row["expected_rxcui"].strip()
        current = stats[category]
        current["total"] += 1
        expected_acceptance = (row.get("expected_acceptance") or "").strip().lower()
        expected_status = (row.get("expected_status") or "").strip()
        if category in targets:
            passed = result.status == "resolved" and result.rxcui == expected
        elif expected_acceptance == "true":
            passed = (
                result.status == "resolved"
                and result.rxcui == expected
                and result.status == expected_status
            )
        else:
            passed = result.status == expected_status and result.status != "error"

        if category in targets and passed:
            current["correct"] += 1
        elif category not in targets and expected_acceptance == "true" and passed:
            current["correct"] += 1
        elif category not in targets and expected_acceptance == "true":
            current["expected_failure"] += 1
        elif category not in targets and result.status == "resolved":
            current["false_positive"] += 1
        elif result.status == "error":
            current["api_error"] += 1
        else:
            current["unresolved"] += 1
        if not passed:
            print(
                f"MISS [{category}] {row['input']!r} -> {result.rxcui} "
                f"({result.status}: {result.reason}) expected {expected or '<none>'}"
            )

    failed = False
    for category, current in stats.items():
        total = current["total"]
        accuracy = current["correct"] / total if category in targets else 0.0
        target = targets.get(category)
        if target is not None:
            passed = accuracy >= target
            failed |= not passed
            print(
                f"{category}: accuracy={current['correct']}/{total} = {accuracy:.1%} "
                f"(target {target:.0%}) {'PASS' if passed else 'FAIL'}; "
                f"unresolved={current['unresolved']}; api_errors={current['api_error']}"
            )
        else:
            failed |= (
                current["false_positive"] > 0
                or current["expected_failure"] > 0
                or current["api_error"] > 0
            )
            print(
                f"{category}: false_positive_resolutions={current['false_positive']}; "
                f"expected_control_failures={current['expected_failure']}; "
                f"unresolved={current['unresolved']}; api_errors={current['api_error']} "
                f"({'PASS' if not current['false_positive'] and not current['expected_failure'] and not current['api_error'] else 'FAIL'})"
            )
    total_correct = sum(
        current["correct"] for category, current in stats.items() if category in targets
    )
    total_unresolved = sum(current["unresolved"] for current in stats.values())
    total_errors = sum(current["api_error"] for current in stats.values())
    total_false_positives = sum(current["false_positive"] for current in stats.values())
    print(
        "summary: "
        f"correct_name_accuracy={stats.get('correct', {}).get('correct', 0)}/"
        f"{stats.get('correct', {}).get('total', 0)}; "
        f"misspelled_name_accuracy={stats.get('misspelled', {}).get('correct', 0)}/"
        f"{stats.get('misspelled', {}).get('total', 0)}; "
        f"false_positive_resolutions={total_false_positives}; "
        f"unresolved_cases={total_unresolved}; api_errors={total_errors}; "
        f"positive_matches={total_correct}"
    )
    return 1 if failed else 0


def main() -> None:
    ap = argparse.ArgumentParser(description="RxNorm drug name normalizer")
    ap.add_argument("names", nargs="*", help="drug names to resolve")
    ap.add_argument(
        "--eval", metavar="CSV", help="run accuracy evaluation on a fixture"
    )
    ap.add_argument(
        "--debug", action="store_true", help="print what each stage returned"
    )
    args = ap.parse_args()
    if args.eval:
        sys.exit(evaluate(args.eval, args.debug))
    norm = RxNormNormalizer(args.debug)
    if args.names:
        for n in args.names:
            show(norm.normalize(n))
        return
    print("Type a drug name (blank line to quit).")
    while True:
        try:
            name = input("drug> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not name:
            break
        show(norm.normalize(name))


if __name__ == "__main__":
    main()
