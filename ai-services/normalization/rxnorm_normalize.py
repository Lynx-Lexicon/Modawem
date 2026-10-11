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
from threading import Lock
from typing import Optional

import requests
from rapidfuzz import fuzz

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
    r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|µg|g|ml|iu|units?|%)"
    r"(?:\s*/\s*\d*(?:\.\d+)?\s*(?:ml|mg|g|l))?\b",
    re.I,
)
_FORMS = re.compile(
    r"\b(tablets?|tabs?|capsules?|caps?|syrup|suspension|cream|ointment|"
    r"solution|drops?|gel|patch|chewable|chewables|er|xr|sr|film[- ]coated|"
    r"extended[- ]release|delayed[- ]release|immediate[- ]release|"
    r"modified[- ]release)\b",
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
    "er": "er",
    "xr": "xr",
    "sr": "sr",
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

    def has_modifier(self) -> bool:
        return bool(
            self.strengths
            or self.forms
            or self.routes
            or self.salts
            or self.combination
        )

    def requests_product(self) -> bool:
        return bool(self.strengths or self.forms)


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
    """Harmless lookup cleanup: case, punctuation, whitespace. Keeps clinical tokens."""
    t = text.lower().strip()
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


def parse_identity(text: str) -> Identity:
    """Interpret medication attributes. Does not remove them from the lookup string."""
    t = text.lower()
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
    # A slash inside a strength (100 mg/5 mL) was already consumed above. A
    # remaining separator is an explicit combination marker. Multiple words
    # are intentionally not enough: brands and ingredient qualifiers are often
    # multiword names too.
    combination = explicit_combination
    return Identity(
        strengths,
        forms,
        routes,
        salts,
        combination=combination,
        ingredient_tokens=tuple(leftover),
    )


def _has_identity_modifier(text: str) -> bool:
    return parse_identity(text).has_modifier()


def attributes_compatible(query: Identity, candidate_name: str) -> bool:
    """True when candidate attributes confirm the requested attributes."""
    return _attribute_state(query, candidate_name) == "compatible"


def _attribute_state(query: Identity, candidate_name: str) -> str:
    """Classify candidate attributes as compatible, missing, or conflicting."""
    cand = parse_identity(candidate_name)
    for requested, available in (
        (query.strengths, cand.strengths),
        (query.forms, cand.forms),
        (query.routes, cand.routes),
        (query.salts, cand.salts),
    ):
        if requested and not available:
            return "missing"
        if requested and available and not set(requested).issubset(available):
            return "conflict"
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


# ---------------------------------------------------------------- API layer
def _get(path: str, params: dict) -> dict:
    last: Exception | None = None
    for attempt in range(RETRIES + 1):
        try:
            r = requests.get(f"{BASE_URL}{path}", params=params, timeout=TIMEOUT_SEC)
            r.raise_for_status()
            payload = r.json()
            if not isinstance(payload, dict):
                raise ValueError("response JSON must be an object")
            return payload
        except requests.HTTPError as e:
            last = e
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status is None:
                status = getattr(r, "status_code", None)
            retryable = status == 429 or (status is not None and 500 <= status <= 599)
            if not retryable:
                break
        except (requests.RequestException, ValueError) as e:
            last = e
        if attempt < RETRIES:
            time.sleep(BACKOFF_BASE_SEC * (2**attempt))
    raise RxNormUnavailable(f"{path}: {last or 'request failed'}")


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
        with self._props_lock:
            cached = self._props_cache.get(rxcui)
        if cached is not None:
            return cached
        value = _props(rxcui)
        with self._props_lock:
            cached = self._props_cache.get(rxcui)
            if cached is None:
                self._remember(self._props_cache, rxcui, value)
                return value
            return cached

    def _get_related(self, rxcui: str):
        with self._related_lock:
            cached = self._related_cache.get(rxcui)
        if cached is not None:
            return cached
        value = _related(rxcui)
        with self._related_lock:
            cached = self._related_cache.get(rxcui)
            if cached is None:
                self._remember(self._related_cache, rxcui, value)
                return value
            return cached

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

        exact = _exact(term)
        self._log("exact:", exact)
        for rx in exact:
            add(rx, None)

        sugg = _spelling(term)[:5]
        self._log("spelling suggestions:", sugg)
        for s in sugg:
            for rx in _exact(s):
                add(rx, s.lower())

        approx = _approx(term)
        diagnostics = getattr(approx, "diagnostics", [])
        self.diagnostics.extend(diagnostics)
        for diagnostic in diagnostics:
            self._log("approximate:", diagnostic)
        self._log("approximate:", approx[:5])
        for c in approx:
            add(c.get("rxcui"), None)
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
            if text and not identity.has_modifier():
                score = max(score, _lexical_score(term, normalize_query(text)))
            scored.append((rxcui, score, name, tty))
        scored.sort(key=lambda row: (-row[1], row[0], row[2]))
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
        for rxcui, score, name, _tty in compatible[1:]:
            if self._same_concept_family(top_rxcui, rxcui):
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
        """Allow only an explicit brand/ingredient relationship to group rivals."""
        if first == second:
            return True
        _, first_tty = self._get_props(first)
        _, second_tty = self._get_props(second)
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
        with self._cache_lock:
            cached = self._cache.get(key)
        if cached is not None:
            return cached
        try:
            cands = self.gather_candidates(term)
            result = self.decide(name, term, cands)
        except RxNormUnavailable as e:  # NOT cached, so caller can retry
            return Result(
                name, None, None, 0.0, "error", f"RxNorm API unavailable: {e}"
            )
        with self._cache_lock:
            cached = self._cache.get(key)
            if cached is None:
                self._remember(self._cache, key, result)
                return result
            return cached


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
