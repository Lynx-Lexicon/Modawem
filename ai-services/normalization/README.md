# RxNorm normalizer evaluation

## Python Service Boundary

The delivered component is a small internal Python HTTP service. It exposes a
stable API boundary for a Spring Boot client; this repository does not include
a Spring Boot client or claim to test one. Build and run the service with
Docker:

```powershell
docker build -t rxnorm-normalizer .
docker run --rm -p 127.0.0.1:8080:8080 rxnorm-normalizer
```

Without Docker, install the package and start the same service:

```powershell
python -m pip install .
rxnorm-server
```

### Trust boundary

This HTTP service is an internal, unauthenticated trust boundary. It accepts
arbitrary medication names and makes outbound HTTPS requests to the public
RxNorm API; it does not provide authentication, authorization, TLS, rate
limiting, or tenant isolation. The direct-run default binds to `127.0.0.1`.
The container image must bind to `0.0.0.0` so a container port can be reached,
but that does not make public exposure safe: publish it only on a private
network or place it behind an authenticated gateway that enforces access
control, TLS, and operational limits. Do not publish an unauthenticated
container port directly to the public internet.

Set `RXNORM_SERVICE_HOST` and `RXNORM_SERVICE_PORT` explicitly when deploying
behind that controlled boundary. Treat `/v1/normalize` as private; health
checks should use `/healthz` and should not be used as an access-control
mechanism.

The service exposes `GET /healthz` and `POST /v1/normalize`. Send a JSON body
with a single `name` field:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8080/v1/normalize `
  -ContentType 'application/json' `
  -Body '{"name":"amoxcilin"}'
```

Clients should treat HTTP 200 with `status=resolved` as a confirmed exact
RxCUI, HTTP 200 with `status=unresolved` as a reviewable non-match, and HTTP
503 with `status=error` as a retryable dependency failure. Do not use
`closest` as a confirmed medication identity.

Operational assumptions: configure the service URL in the consuming
application, use a client timeout, retry HTTP 503 with backoff, and retain the
`rxcui` as a string. The service calls the public RxNorm API and therefore
requires outbound HTTPS access. The threaded HTTP server permits independent
requests to overlap; the normalizer protects its bounded caches while leaving
network-backed work outside cache locks.

## Commands

Run the automated test suite:

```powershell
pytest -q
```

Run the acceptance fixture evaluation against RxNorm:

```powershell
  python rxnorm_normalize.py --eval tests/rxnorm_fixture.csv
```

Run the adversarial rejection evaluation separately:

```powershell
  python rxnorm_normalize.py --eval tests/rxnorm_adversarial.csv
```

The fixture evaluator requires `case_category`, `input`, and
`expected_rxcui` columns. Positive fixtures must contain at least 100
`correct` rows and 100 `misspelled` rows. Each resolved row must return the
exact expected RxCUI; a close name or a different RxCUI is not a pass.
Adversarial rows additionally use `expected_status` and
`expected_acceptance`; accepted controls include an independently verified
RxCUI, while rejection cases leave `expected_rxcui` blank.

## JSON contract

Resolved input:

```json
{
  "input": "metformin",
  "rxcui": "6809",
  "matched_name": "metformin",
  "score": 1.0,
  "status": "resolved",
  "reason": null,
  "closest": [
    { "rxcui": "6809", "name": "metformin", "score": 1.0, "tty": "IN" }
  ]
}
```

Unresolved or unavailable input never presents a closest candidate as a
confirmed RxCUI:

```json
{
  "input": "notarealmedicine",
  "rxcui": null,
  "matched_name": null,
  "score": 0.0,
  "status": "unresolved",
  "reason": "RxNorm returned no candidates for this name",
  "closest": []
}
```

## Acceptance evidence

The evaluator reports correct-name accuracy and misspelled-name accuracy
separately, with targets of 95% and 85%. It also reports false-positive
resolutions, unresolved cases, and API errors separately. Adversarial rows
with `expected_acceptance=false` must remain unresolved; valid adversarial
controls are checked against their exact expected RxCUI.

The latest local results are recorded here only after running the commands in
this document. Live fixture results depend on RxNorm availability and are not
substituted with mocked results.

The evidence below is intentionally split into local unit tests and external
API-backed checks so the different assurance levels remain clear.

### Unit test evidence

```text
pytest -q
49 passed, 1 deselected in 7.11s
```

### Live API-backed checks

```text
python rxnorm_normalize.py --eval tests/rxnorm_adversarial.csv
summary: correct_name_accuracy=0/0; misspelled_name_accuracy=0/0; false_positive_resolutions=0; unresolved_cases=4; api_errors=0; positive_matches=0

python rxnorm_normalize.py --eval tests/rxnorm_fixture.csv
correct: accuracy=105/105 = 100.0% (target 95%) PASS; unresolved=0; api_errors=0
misspelled: accuracy=101/104 = 97.1% (target 85%) PASS; unresolved=3; api_errors=0
summary: correct_name_accuracy=105/105; misspelled_name_accuracy=101/104; false_positive_resolutions=0; unresolved_cases=3; api_errors=0; positive_matches=206
```

The live API-backed run completed on 2026-10-11 with zero API errors. Correct
and misspelled names meet their targets. The three remaining misspelled
failures are `clindamyc` -> 2582, `metoprol` -> 6918, and `loratadn` -> 28889;
each is a conservative lexical-floor rejection at the reviewed 0.9091
threshold. Earlier failures were classified as retrieval/ranking issues or
clinical-attribute parsing issues and corrected without changing expected
RxCUIs.

Failure classification for the original 16 misses: 9 candidate retrieval or
ranking failures, 1 wrong approximate-product ranking (`aspirn`), 2 clinically
ambiguous rankings (`metoprol` and `carvediloll`), 1 candidate attribute parse
failure (`inslin`), and 3 conservative threshold rejections. There were no
incorrect fixtures and no API/integration failures. The final residual list
above contains the three conservative cases after the other 13 were corrected.

The adversarial `metforman` case is intentionally unresolved: RxNorm can
retrieve `metformin`, but this one-edit nonstandard spelling scores only
0.8889 and is below the reviewed lexical floor. That conservative rejection
prevents an unverified near-name from becoming a confirmed RxCUI; the valid
`metformn` spelling remains a separate positive control.

The fixture audit also corrected a duplicated `ezetimibe` row that had been
labelled `misspelled` despite being an exact, correctly spelled match. Both
fixtures now load through schema, status, acceptance, and duplicate-label
validation before evaluation.

## Limitations

Lexical similarity ranks candidates but is not a probability of clinical
correctness. The normalizer requires compatible strength, dosage form, route,
salt, and combination attributes where supplied. Live API outages are
reported as errors and count against the positive accuracy denominator.
