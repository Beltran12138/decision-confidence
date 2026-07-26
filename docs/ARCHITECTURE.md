# Architecture — Agent Decision Confidence (meta-layer)

Status: **reference implementation**. The meta-layer ships as
`src/decision_confidence.py` and is exposed over MCP by `src/mcp_server.py`
(stdio, one tool). Still **not** in this release: live HTTP adapters for real
vendors, auth, multi-tenancy. The token-domain library in `src/normalize.py`
remains the shipped, frozen public API (`score_token` / `TokenInputs`).

---

## 1. Goal and non-goals

### Goal

Give an agent (or human caller) a **single decision-confidence report** when
multiple external risk APIs disagree in shape and often in substance:

- Map each source onto one **0–100 risk basis** (0 = safe / low risk, 100 = max risk)
- **Detect contradictions** across sources
- Emit **confidence** and an **audit trail** suitable for agent tool results

### Non-goals (this phase and generally)

| Non-goal | Why |
| --- | --- |
| Replace on-chain risk / fraud / KYT vendors | Meta-layer consumes them; does not compete |
| Fetch chain data or call vendor HTTP itself | Sandbox-friendly; caller supplies observations |
| Calibrated probability of "is this a scam" | Heuristic framework, not a trained model |
| Guaranteed safety or compliance sign-off | Explicitly out of scope |
| Mutate `normalize.py` public API | Already published; methodology is reused, not rewritten |

---

## 2. Pipeline

```
                    caller-supplied only (no network in-library)
  +------------------+  +------------------+  +------------------+
  | Risk API class A |  | Risk API class B |  | Risk API class C |
  | (score / safety) |  | (KYT tier)       |  | (fraud pred.)    |
  +--------+---------+  +--------+---------+  +--------+---------+
           |                     |                     |
           v                     v                     v
  +------------------+  +------------------+  +------------------+
  | Adapter A        |  | Adapter B        |  | Adapter C        |
  | → Observation    |  | → Observation    |  | → Observation    |
  +--------+---------+  +--------+---------+  +--------+---------+
           \                     |                     /
            \                    |                    /
             v                   v                   v
                    +------------------------+
                    | Normalize engine       |
                    | (method from           |
                    |  normalize.py style:   |
                    |  clamp, bands,         |
                    |  missing ≠ guess)      |
                    +-----------+------------+
                                |
                                v
                    +------------------------+
                    | Contradiction detect   |
                    +-----------+------------+
                                |
                                v
                    +------------------------+
                    | Confidence synthesis   |
                    +-----------+------------+
                                |
                                v
                    +------------------------+
                    | DecisionReport + Audit |
                    +------------------------+
```

**What reuses `normalize.py` methodology:** 0–100 risk orientation, clamp,
verdict bands, "present-only" weighting, never fabricate missing inputs,
confidence degraded by thin evidence or internal contradiction.

**What is new (meta-layer):** multi-vendor adapters, cross-source contradiction
kinds, decision audit records, future MCP tool surface. Token five-dimension
fields (`top10_pct`, `mint_authority`, …) are **not** required here.

---

## 3. Input layer

### 3.1 Adapter protocol (sketch)

Shipped shape: `decision_confidence.py` provides scale-specific normalizers
(`observe_safety_score` / `observe_risk_score` / `observe_kyt_tier` /
`observe_fraud_probability`) plus `observe_from_raw` for shape dispatch. An
adapter is then a thin binding of one vendor id to one normalizer — see the
three in `examples/decision_confidence_demo.py`. The protocol below is the
interface a registry-based Phase 3 would formalise:

```python
from typing import Any, Dict, Optional, Protocol

class RiskSourceAdapter(Protocol):
    """Maps one vendor's raw payload into a SourceObservation."""

    source_id: str  # stable id, e.g. "mock_alpha_risk"

    def parse(self, subject: str, raw: Dict[str, Any]) -> "SourceObservation":
        ...
```

Adapters own:

- Scale interpretation (is vendor 100 "safe" or "risky"?)
- Field extraction and light validation
- Status: `ok` | `missing` | `malformed` | `unavailable`

They must **not** perform network I/O. The caller (agent runtime, MCP host, or
demo) fetches and passes `raw`.

### 3.2 Heterogeneous raw shapes (illustrative)

| Source class | Example raw keys | Notes |
| --- | --- | --- |
| On-chain risk score | `{"score": 82, "scale": "safety_0_100"}` | May need polarity flip |
| Fraud / scam prediction | `{"fraud_probability": 0.91}` or `{"label": "scam"}` | Prob → 0–100 risk |
| KYT / compliance tier | `{"tier": "HIGH"}` | Ordinal map to 0–100 |

Real vendor field names vary; adapters isolate that churn from the engine.

### 3.3 Unified intermediate representation

```python
@dataclass
class SourceObservation:
    source_id: str
    subject: str                 # e.g. token address or symbol (caller-defined)
    raw: Dict[str, Any]          # as supplied, for audit
    normalized_0_100: Optional[int]  # None if missing/malformed
    status: str                  # ok | missing | malformed | unavailable
    note: str = ""               # e.g. "flipped safety→risk"
```

---

## 4. Normalize engine

### 4.1 Alignment with `normalize.py`

| Concern | Token instance (`score_token`) | Meta-layer |
| --- | --- | --- |
| Basis | 0–100 risk per dimension | 0–100 risk per **source** |
| Missing data | `score=None`, lowers confidence | `normalized_0_100=None`, lowers confidence |
| Composite | Weighted mean over present dims | Weighted mean over present sources (equal weight default; caller may override) |
| Bands | low / moderate / high / extreme | Same band table (reuse concept) |
| Fabrication | Never | Never |

**Frozen boundary:** do not change `score_token`, `TokenInputs`, or published
weight tables to "support" the meta-layer. Optional later: extract shared
helpers (`clamp`, `band`) if duplication becomes painful — only after API
review.

### 4.2 Direction convention

All engine-facing scores use:

```text
0   = safe / low risk
100 = maximum risk
```

Adapters that receive a vendor **safety** score must flip, e.g.
`risk = 100 - safety`, and record that in `note` / audit.

### 4.3 Per-source normalizers (heuristic sketch)

```text
safety_0_100     → risk = 100 - score
risk_0_100       → risk = score
fraud_probability → risk = round(p * 100)
KYT tier         → LOW=20, MEDIUM=55, HIGH=85  (example heuristics)
```

Thresholds are **rough**, same honesty bar as the token instance.

---

## 5. Contradiction detection

Contradiction is a **first-class** output for agents (not only a side effect
on confidence).

### 5.1 Sketch types

```python
@dataclass
class Contradiction:
    sources: List[str]           # source_ids involved
    kind: str                    # polarity | range | hard_flag
    detail: str
    severity: str = "medium"     # low | medium | high
```

### 5.2 Rule families (heuristics)

| Kind | Idea | Example |
| --- | --- | --- |
| `polarity` | One source low-risk, another high-risk | A ≤ 30 and B ≥ 70 |
| `range` | Spread among ok sources exceeds threshold | max − min ≥ 40 |
| `hard_flag` | Binary fraud/scam label vs low composite | fraud label while peers score "safe" |

Rules operate only on `status == "ok"` observations. Fewer than two ok sources
→ no pairwise contradiction (confidence still low due to thin evidence).

### 5.3 Relationship to token-instance contradiction

Token path already uses a simple heuristic: hard red flag + low composite →
force low confidence. Meta-layer **generalizes** that idea across vendors and
**surfaces** contradictions in the report body.

---

## 6. Confidence synthesis

Inputs:

- `n_ok` — count of sources with usable normalized scores
- `contradictions` — non-empty?
- optional: magnitude of range, missing/malformed count

Sketch:

```text
if any high-severity contradiction or n_ok < 2:
    confidence = "low"
elif n_ok >= 3 and no contradictions:
    confidence = "high"
else:
    confidence = "medium"
```

Tune later; document any production change. Confidence is **not** a
probability of correctness — it is an evidence-quality label for the agent.

---

## 7. Audit trail

Every report should be reconstructible without re-fetching:

```python
@dataclass
class AuditEntry:
    step: str          # adapt | normalize | contradict | composite | confidence
    source_id: Optional[str]
    detail: str
    # logical timestamp: caller or wall clock string; storage is out of scope
    at: Optional[str] = None

@dataclass
class DecisionReport:
    subject: str
    observations: List[SourceObservation]
    composite: Optional[int]
    verdict: str                 # low | moderate | high | extreme | unknown
    confidence: str              # high | medium | low
    contradictions: List[Contradiction]
    audit: List[AuditEntry]
    note: str = ""
```

Serialization: plain `dict` / JSON, same spirit as `Verdict.to_dict()`.

---

## 8. MCP surface (shipped)

Implemented in `src/mcp_server.py` — stdio transport, one tool. Optional
dependency: `pip install -e ".[mcp]"`. The core library stays dependency-free.

### Tool: `decision_confidence`

**Input (sketch):**

```jsonc
{
  "subject": "0x… or SYMBOL",
  "sources": [
    {
      "source_id": "alpha_risk",
      "raw": { "score": 82, "scale": "safety_0_100" }
    },
    {
      "source_id": "beta_kyt",
      "raw": { "tier": "HIGH" }
    },
    {
      "source_id": "gamma_fraud",
      "raw": { "fraud_probability": 0.12 }
    }
  ],
  "weights": { "alpha_risk": 1.0, "beta_kyt": 1.0, "gamma_fraud": 1.0 }  // optional
}
```

**Output:** `DecisionReport` as JSON (observations, composite, verdict,
confidence, contradictions, audit).

**Host responsibilities:** API keys, HTTP, rate limits, caching, PII policy.
**Library / MCP tool responsibilities:** pure transform of supplied `sources`.

---

## 9. Security and privacy

- **No secrets in repo or library state** — adapters never read `.env`
- **Caller-supplied only** — reduces accidental exfiltration from the library
- **Read-only** — no execution, no approvals, no chain writes
- **Audit may contain raw vendor payloads** — callers must strip secrets/PII
  before logging or sharing reports
- **Do not log API keys** in adapter notes or audit `detail`

---

## 10. Limitations and open questions

### Limitations (honest)

- Quality ≤ worst-case upstream availability and honesty
- Correlated vendors (shared data vendors / shared heuristics) understate risk
  of "agreement"
- Heuristic thresholds are uncalibrated
- Mock demo vendors are fictional; real adapters need per-vendor tests
- MCP auth, multi-tenant isolation, and streaming are unspecified here

### Open questions

1. Default weights per source class vs equal weight?
2. Should `hard_flag` short-circuit composite to extreme, or only confidence?
3. Subject identity: address vs symbol vs (chain_id, address)?
4. Versioning of rule sets for audit reproducibility?
5. Extract shared `clamp` / `band` from `normalize.py` without breaking the
   frozen public API?

---

## 11. Phase map

| Phase | Deliverable | Status |
| --- | --- | --- |
| Phase 1 | README reframe, this doc, `examples/decision_confidence_demo.py` | done |
| **Phase 2 (this)** | `src/decision_confidence.py` module, `src/mcp_server.py` (stdio, one tool), `tests/` regression suite | done |
| Phase 3 | Real vendor adapters over HTTP, auth, multi-tenant isolation, calibration against a labelled dataset | not started |

Token instance demos remain: `examples/pepe_caller_supplied.py`.

**Phase 2 non-regression:** the module was extracted from the example without
behaviour change — `python examples/decision_confidence_demo.py` produces
byte-identical output before and after (verified by checksum), and
`src/normalize.py` is untouched.
