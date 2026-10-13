import rxnorm_normalize as rx


class FakeNormalizer(rx.RxNormNormalizer):
    def __init__(self, props, related=None):
        super().__init__()
        self.props = props
        self.related = related or {}

    def _get_props(self, rxcui):
        return self.props[rxcui]

    def _get_related(self, rxcui):
        return self.related.get(rxcui, [])


def test_generic_and_brand_are_distinct_verified_concepts():
    normalizer = FakeNormalizer(
        {
            "161": ("acetaminophen", "IN"),
            "202": ("Tylenol", "BN"),
        },
        {"202": [("161", "acetaminophen", "IN")]},
    )

    result = normalizer.decide(
        "Tylenol", "tylenol", [("202", "tylenol"), ("161", "acetaminophen")]
    )

    assert (result.status, result.rxcui, result.matched_name) == (
        "resolved",
        "202",
        "Tylenol",
    )


def test_product_does_not_fall_back_to_its_ingredient():
    normalizer = FakeNormalizer(
        {
            "161": ("acetaminophen", "IN"),
            "1001": ("acetaminophen 500 MG Oral Tablet", "SCD"),
        }
    )

    result = normalizer.decide(
        "acetaminophen 500 mg tablet",
        "acetaminophen 500 mg tablet",
        [("161", "acetaminophen"), ("1001", "acetaminophen 500 mg tablet")],
    )

    assert (result.status, result.rxcui, result.matched_name) == (
        "resolved",
        "1001",
        "acetaminophen 500 MG Oral Tablet",
    )


def test_product_strengths_are_not_conflated():
    normalizer = FakeNormalizer(
        {
            "500": ("metformin 500 MG Oral Tablet", "SCD"),
            "1000": ("metformin 1000 MG Oral Tablet", "SCD"),
        }
    )

    result = normalizer.decide(
        "metformin 500 mg tablet",
        "metformin 500 mg tablet",
        [("500", "metformin 500 mg tablet"), ("1000", "metformin 1000 mg tablet")],
    )

    assert (result.status, result.rxcui) == ("resolved", "500")


def test_combination_returns_multiple_ingredient_concept():
    normalizer = FakeNormalizer(
        {
            "723": ("amoxicillin", "IN"),
            "131270": ("amoxicillin / clavulanate", "MIN"),
        }
    )

    result = normalizer.decide(
        "amoxicillin clavulanate",
        "amoxicillin clavulanate",
        [("723", "amoxicillin"), ("131270", "amoxicillin clavulanate")],
    )

    assert (result.status, result.rxcui, result.matched_name) == (
        "resolved",
        "131270",
        "amoxicillin / clavulanate",
    )


def test_single_ingredient_does_not_resolve_to_combination_product():
    normalizer = FakeNormalizer(
        {"combo": ("metformin 500 MG / sitagliptin 50 MG Oral Tablet", "SCD")}
    )
    result = normalizer.decide(
        "metformin 500 mg tablet",
        "metformin 500 mg tablet",
        [("combo", "metformin 500 mg / sitagliptin 50 mg tablet")],
    )
    assert result.status == "unresolved"
    assert result.rxcui is None


def test_different_salts_are_not_treated_as_same_by_name_substrings():
    normalizer = FakeNormalizer(
        {
            "a": ("metoprolol sodium", "PIN"),
            "b": ("metoprolol tartrate", "PIN"),
        }
    )

    result = normalizer.decide(
        "metoprolol salt",
        "metoprolol salt",
        [("a", "metoprolol sodium"), ("b", "metoprolol tartrate")],
    )

    assert result.status == "unresolved"
    assert result.rxcui is None


def test_close_unrelated_candidates_are_ambiguous():
    normalizer = FakeNormalizer(
        {
            "a": ("metformin", "IN"),
            "b": ("metformin", "IN"),
        }
    )

    result = normalizer.decide(
        "metformin", "metformin", [("a", "metformina"), ("b", "metformin")]
    )

    assert result.status == "unresolved"
    assert result.rxcui is None


def test_bare_name_with_competing_clinically_distinct_candidates_is_unresolved():
    normalizer = FakeNormalizer(
        {
            "tartrate": ("metoprolol tartrate", "PIN"),
            "succinate": ("metoprolol succinate", "PIN"),
        }
    )
    result = normalizer.decide(
        "metoprolol",
        "metoprolol",
        [
            ("tartrate", "metoprolol tartrate"),
            ("succinate", "metoprolol succinate"),
        ],
    )
    assert (result.status, result.rxcui) == ("unresolved", None)


def test_existing_generic_resolution_keeps_verified_concept():
    normalizer = FakeNormalizer({"6809": ("metformin", "IN")})
    result = normalizer.decide("metformn", "metformn", [("6809", "metformin")])

    assert (result.status, result.rxcui, result.matched_name) == (
        "resolved",
        "6809",
        "metformin",
    )


def test_ingredient_qualifiers_do_not_look_like_combination_products():
    normalizer = FakeNormalizer({"253182": ("insulin, regular, human", "IN")})
    result = normalizer.decide("inslin", "inslin", [("253182", "insulin")])

    assert (result.status, result.rxcui) == ("resolved", "253182")


def test_multiword_brand_name_is_not_inferred_as_combination():
    assert not rx.parse_identity("Tylenol Extra Strength").combination


def test_ingredient_qualifier_is_not_inferred_as_combination():
    assert not rx.parse_identity("insulin regular human").combination


def test_space_separated_combination_requires_verified_min_and_ingredients():
    normalizer = FakeNormalizer(
        {
            "723": ("amoxicillin", "IN"),
            "896": ("clavulanate", "IN"),
            "131270": ("amoxicillin / clavulanate", "MIN"),
        },
        {
            "131270": [
                ("723", "amoxicillin", "IN"),
                ("896", "clavulanate", "IN"),
            ]
        },
    )
    result = normalizer.decide(
        "amoxicillin clavulanate",
        "amoxicillin clavulanate",
        [("723", "amoxicillin"), ("131270", "amoxicillin clavulanate")],
    )
    assert (result.status, result.rxcui) == ("resolved", "131270")


def test_normalize_query_preserves_clinical_strengths():
    for raw in ("500 mg", "0.5 mg", "100 mg/5 mL", "5 mg/mL"):
        kept = rx.normalize_query(raw)
        assert kept
        assert "mg" in kept
        assert rx.clean(raw) == kept
    assert "0.5" in rx.normalize_query("0.5 mg")
    assert rx.normalize_query("0.5 mg") != "0 5 mg"
    assert "/" in rx.normalize_query("100 mg/5 mL")
    assert "/" in rx.normalize_query("5 mg/mL")


def test_clean_does_not_strip_form_or_salt():
    assert "tablet" in rx.clean("acetaminophen 500 mg tablet")
    assert "500" in rx.clean("acetaminophen 500 mg tablet")
    assert "tartrate" in rx.clean("metoprolol tartrate")
    assert "succinate" in rx.clean("metoprolol succinate")


def test_parse_identity_strength_forms_salts_and_combinations():
    half = rx.parse_identity("acetaminophen 0.5 mg tablet")
    assert half.strengths == ("0.5 mg",)
    assert "tablet" in half.forms
    conc = rx.parse_identity("amoxicillin 100 mg/5 mL suspension")
    assert "100 mg/5 ml" in conc.strengths
    assert "suspension" in conc.forms
    per_ml = rx.parse_identity("morphine 5 mg/mL injection")
    assert "5 mg/ml" in per_ml.strengths
    assert "injection" in per_ml.routes
    salt = rx.parse_identity("metoprolol tartrate 50 mg")
    assert "tartrate" in salt.salts
    assert "succinate" in rx.parse_identity("metoprolol succinate").salts
    combo = rx.parse_identity("amoxicillin / clavulanate")
    assert combo.combination
    assert rx.parse_identity("amoxicillin/clavulanate").combination
    assert rx.parse_identity("amoxicillin clavulanate").combination is False
    assert rx.parse_identity("amoxicillin 100 mg/5 mL suspension").combination is False
    assert "extended-release" in rx.parse_identity("metformin extended release").forms


def test_half_mg_is_not_five_mg():
    normalizer = FakeNormalizer(
        {
            "half": ("acetaminophen 0.5 MG Oral Tablet", "SCD"),
            "five": ("acetaminophen 5 MG Oral Tablet", "SCD"),
        }
    )
    result = normalizer.decide(
        "acetaminophen 0.5 mg tablet",
        "acetaminophen 0.5 mg tablet",
        [
            ("half", "acetaminophen 0.5 mg tablet"),
            ("five", "acetaminophen 5 mg tablet"),
        ],
    )
    assert (result.status, result.rxcui) == ("resolved", "half")


def test_concentration_100_mg_per_5_ml_is_not_5_mg_per_ml():
    normalizer = FakeNormalizer(
        {
            "susp": ("amoxicillin 100 MG/5 ML Oral Suspension", "SCD"),
            "sol": ("amoxicillin 5 MG/ML Oral Solution", "SCD"),
        }
    )
    result = normalizer.decide(
        "amoxicillin 100 mg/5 mL suspension",
        rx.normalize_query("amoxicillin 100 mg/5 mL suspension"),
        [("susp", "amoxicillin 100 mg/5 mL"), ("sol", "amoxicillin 5 mg/mL")],
    )
    assert (result.status, result.rxcui) == ("resolved", "susp")


def test_five_mg_per_ml_resolves_when_attributes_match():
    normalizer = FakeNormalizer(
        {
            "sol": ("metformin 5 MG/ML Oral Solution", "SCD"),
            "tab": ("metformin 5 MG Oral Tablet", "SCD"),
        }
    )
    result = normalizer.decide(
        "metformin 5 mg/mL solution",
        rx.normalize_query("metformin 5 mg/mL solution"),
        [("sol", "metformin 5 mg/ml"), ("tab", "metformin 5 mg tablet")],
    )
    assert (result.status, result.rxcui) == ("resolved", "sol")


def test_dosage_forms_are_not_swapped():
    normalizer = FakeNormalizer(
        {
            "tab": ("acetaminophen 500 MG Oral Tablet", "SCD"),
            "syr": ("acetaminophen 500 MG/5 ML Oral Syrup", "SCD"),
        }
    )
    result = normalizer.decide(
        "acetaminophen 500 mg tablet",
        "acetaminophen 500 mg tablet",
        [("tab", "acetaminophen 500 mg tablet"), ("syr", "acetaminophen 500 mg syrup")],
    )
    assert (result.status, result.rxcui) == ("resolved", "tab")


def test_succinate_and_tartrate_are_distinct():
    normalizer = FakeNormalizer(
        {
            "succ": ("metoprolol succinate", "PIN"),
            "tart": ("metoprolol tartrate", "PIN"),
        }
    )
    result = normalizer.decide(
        "metoprolol succinate",
        "metoprolol succinate",
        [("succ", "metoprolol succinate"), ("tart", "metoprolol tartrate")],
    )
    assert (result.status, result.rxcui) == ("resolved", "succ")


def test_wrong_strength_only_candidate_is_not_accepted():
    normalizer = FakeNormalizer(
        {
            "1000": ("metformin 1000 MG Oral Tablet", "SCD"),
        }
    )
    result = normalizer.decide(
        "metformin 500 mg tablet",
        "metformin 500 mg tablet",
        [("1000", "metformin 1000 mg tablet")],
    )
    assert result.status == "unresolved"
    assert result.rxcui is None


def test_conflicting_high_score_candidate_does_not_block_compatible_candidate():
    normalizer = FakeNormalizer(
        {
            "capsule": ("metformin 500 MG Oral Capsule", "SCD"),
            "tablet": ("metformin 500 MG Oral Tablet", "SCD"),
        }
    )
    result = normalizer.decide(
        "metformin 500 mg tablet",
        "metformin 500 mg tablet",
        [
            ("capsule", "metformin 500 mg capsule"),
            ("tablet", "metformin 500 mg tablet"),
        ],
    )
    assert (result.status, result.rxcui) == ("resolved", "tablet")


def test_missing_candidate_attributes_are_not_confirmed_as_compatible():
    normalizer = FakeNormalizer({"generic": ("metformin", "SCD")})
    result = normalizer.decide(
        "metformin 500 mg tablet",
        "metformin 500 mg tablet",
        [("generic", "metformin")],
    )
    assert result.status == "unresolved"
    assert result.rxcui is None
    assert "enough medication attribute information" in result.reason


def test_spelling_correction_does_not_drop_product_to_ingredient():
    normalizer = FakeNormalizer(
        {
            "161": ("acetaminophen", "IN"),
            "1001": ("acetaminophen 500 MG Oral Tablet", "SCD"),
        }
    )
    result = normalizer.decide(
        "paracetmol 500 mg tablet",
        "paracetmol 500 mg tablet",
        [("161", "acetaminophen"), ("1001", "acetaminophen 500 MG Oral Tablet")],
    )
    assert result.rxcui != "161"
    if result.status == "resolved":
        assert result.rxcui == "1001"


def test_spelling_and_approx_merge_even_when_exact_hits(monkeypatch):
    def fake_exact(term):
        return {"metformn": ["9"], "metformin": ["6809"]}.get(term, [])

    monkeypatch.setattr(rx, "_exact", fake_exact)
    monkeypatch.setattr(rx, "_spelling", lambda term: ["metformin"])
    monkeypatch.setattr(
        rx,
        "_approx",
        lambda term: [
            {"rxcui": "6809", "name": "metformin"},
            {"rxcui": "123", "name": "metform"},
        ],
    )
    cands = rx.RxNormNormalizer().gather_candidates("metformn")
    rxcuis = [rxcui for rxcui, _ in cands]
    assert rxcuis[0] == "9"
    assert "6809" in rxcuis
    assert "123" in rxcuis
    assert rxcuis.count("6809") == 1


def test_ranking_and_acceptance_are_separate():
    normalizer = FakeNormalizer(
        {
            "500": ("metformin 500 MG Oral Tablet", "SCD"),
            "1000": ("metformin 1000 MG Oral Tablet", "SCD"),
        }
    )
    term = "metformin 500 mg tablet"
    identity = rx.parse_identity(term)
    ranked = normalizer.rank_candidates(
        term,
        [("500", term), ("1000", "metformin 1000 mg tablet")],
        identity,
    )
    assert [row[0] for row in ranked] == ["500", "1000"]
    assert ranked[0][1] == rx._lexical_score(term, "metformin 500 MG Oral Tablet")
    assert isinstance(ranked[0][1], float)

    accepted = normalizer.accept("metformin 500 mg tablet", ranked, identity, True)
    assert (accepted.status, accepted.rxcui) == ("resolved", "500")

    rejected = normalizer.accept("metformin 500 mg tablet", ranked[1:], identity, True)
    assert rejected.status == "unresolved"
    assert rejected.rxcui is None
    assert ranked[1][0] == "1000"


def test_full_precision_score_below_threshold_is_not_rounded_up():
    normalizer = FakeNormalizer({"6809": ("metformin", "IN")})
    identity = rx.parse_identity("metformin")
    ranked = [("6809", 0.846154, "metformin", "IN")]
    result = normalizer.accept("metformin", ranked, identity, True)
    assert result.status == "unresolved"
    assert result.score == 0.846154
    assert round(result.score, 2) == 0.85


def test_calibrated_threshold_sits_between_true_and_false_friends():
    same = [
        ("metformn", "metformin"),
        ("acetaminophen 500 mg tablet", "acetaminophen 500 MG Oral Tablet"),
        (
            "amoxicillin 100 mg/5 ml suspension",
            "amoxicillin 100 MG/5 ML Oral Suspension",
        ),
        ("amoxicillin clavulanate", "amoxicillin / clavulanate"),
    ]
    distinct = [
        ("metformin 500 mg tablet", "metformin 1000 MG Oral Tablet"),
        ("acetaminophen 0.5 mg tablet", "acetaminophen 5 MG Oral Tablet"),
        ("amoxicillin 100 mg/5 ml", "amoxicillin 5 MG/ML Oral Solution"),
        ("metoprolol tartrate", "metoprolol succinate"),
    ]
    for query, name in same:
        score = rx._lexical_score(query, name)
        assert score >= rx.ACCEPT_THRESHOLD, (query, name, score)
        assert rx.attributes_compatible(rx.parse_identity(query), name)
    for query, name in distinct:
        assert not rx.attributes_compatible(rx.parse_identity(query), name), (
            query,
            name,
        )
