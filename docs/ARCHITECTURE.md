# Architecture — Agent Decision Confidence (meta-layer)

Status: **reference implementation with three real vendor adapters**. The
meta-layer ships as `src/decision_confidence.py`, per-vendor adapters as
`src/adapters/`, and both are exposed over MCP by `src/mcp_server.py` (stdio,
two tools). The token-domain library in `src/normalize.py` remains the shipped,
frozen public API (`score_token` / `TokenInputs`).

Deliberately **not** built, and why:

| Not built | Reason |
| --- | --- |
| HTTP fetching inside the library | Breaks the no-network invariant that makes the library sandbox-safe and trivially testable. Fetching lives in `examples/live_multi_source.py`, the one networked file in the repo. |
| Auth / API-key handling | The library holds no credentials and reaches nothing. Adding auth would invent a concern that belongs to the host. |
| Multi-tenant isolation | There is no server-side state to isolate. A stdio MCP process is already per-host. |
| Calibrated thresholds | No labelled data in hand. `tools/calibrate.py` is the instrument; the numbers are still uncalibrated and labelled as such. |

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

### 3.1 Adapter protocol and registry

An adapter is a pure function:

```python
def parse(subject: str, raw: Dict[str, Any]) -> List[SourceObservation]: ...
```

Registered by vendor id in `src/adapters/__init__.py`:

```python
DEFAULT_REGISTRY.register("goplus", goplus.parse, "…")
observations = observe_vendor("goplus", "goplus", subject, raw)
```

Adapters own:

- Scale interpretation (is vendor 100 "safe" or "risky"?)
- Field extraction and light validation
- Status: `ok` | `missing` | `malformed` | `unavailable`
- The `construct` each observation measures (§3.4)

They must **not** perform network I/O. The caller (agent runtime, MCP host, or
example script) fetches and passes `raw`.

**One payload, several observations.** `parse` returns a *list*, not a single
observation, because real vendors are not single-scalar. GoPlus carries both
contract-authority findings and holder concentration; compliance vendors
typically separate ownership risk from counterparty risk. Collapsing that
before the meta-layer sees it destroys the information the meta-layer exists to
reason over.

**Unknown vendors still work.** `observe_vendor` falls back to
`observe_from_raw` shape sniffing and records the fallback in the note. Shape
sniffing remains a reasonable default for a generic tool surface and a poor
default for production — two vendors can ship the same key with opposite
polarity.

### 3.2 Shipped adapters

All three are public and need no API key. Response shapes verified live on
2026-07-26; captures are frozen in `tests/fixtures/`.

| Vendor | Endpoint | Constructs emitted |
| --- | --- | --- |
| GoPlus Token Security | `api.gopluslabs.io/api/v1/token_security/{chain_id}` | `authority_control`, `holder_concentration` |
| honeypot.is v2 | `api.honeypot.is/v2/IsHoneypot` | `tradability` |
| DexScreener | `api.dexscreener.com/latest/dex/tokens/{address}` | `liquidity_depth` |

Three field-level traps these adapters exist to absorb, each found by reading
real responses rather than docs:

1. **GoPlus flags are strings, and absence ≠ false.** `"0"`/`"1"`, and a field
   that is simply not present means "not applicable / not detected". Scoring
   absence as safe is the easiest way to under-report with this vendor, so
   absent flags are counted and surfaced in the note.
2. **A honeypot simulation that did not run is not a pass.**
   `simulationSuccess: false` yields `unavailable`, never a low score.
3. **DexScreener's token endpoint is keyed by address, not by (chain,
   address).** Querying the Ethereum USDT address returns PulseChain pools —
   the same address on a fork chain. Taking `pairs[0]`, or even
   `max(liquidity)`, silently scores the wrong chain. The adapter refuses:
   either the caller names the chain, or the observation comes back
   `unavailable` naming the chains it saw.

### 3.3 Heterogeneous raw shapes (generic fallback)

| Source class | Example raw keys | Notes |
| --- | --- | --- |
| On-chain risk score | `{"score": 82, "scale": "safety_0_100"}` | May need polarity flip |
| Fraud / scam prediction | `{"fraud_probability": 0.91}` or `{"label": "scam"}` | Prob → 0–100 risk |
| KYT / compliance tier | `{"tier": "HIGH"}` | Ordinal map to 0–100 |

### 3.4 Constructs — what a source is actually measuring

`decision_confidence.CONSTRUCTS`: `authority_control`, `tradability`,
`liquidity_depth`, `holder_concentration`, `compliance_exposure`,
`fraud_prediction`.

Two vendors can disagree numerically while both being right, because they are
answering different questions. A structural-authority scanner and a honeypot
simulator will always diverge on a centralised-but-perfectly-tradable token,
and treating that as "one of them is wrong" is a category error. Declaring the
construct lets the engine separate **definitional** disagreement from
**factual** disagreement (§5.2).

The field is optional. An observation with `construct=None` behaves exactly as
it did before constructs existed — tagging is strictly opt-in.

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
| `construct_mismatch` | Wide spread across sources measuring different things | authority scanner vs honeypot simulator |

Rules operate only on `status == "ok"` observations. Fewer than two ok sources
→ no pairwise contradiction (confidence still low due to thin evidence).

**Construct-aware severity.** When a `polarity` or `range` clash involves two
sources with *different* declared constructs, severity is downgraded (high →
medium) and the detail says why: the disagreement may be definitional rather
than factual. When constructs match, or either is undeclared, severity is
unchanged.

`construct_mismatch` is a statement about the **composite**, not about any
source: if the weighted mean is averaging several distinct constructs and they
spread widely, the mean is not a like-for-like average and the report says so
instead of quietly presenting a single number.

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

Implemented in `src/mcp_server.py` — stdio transport, two tools. Optional
dependency: `pip install -e ".[mcp]"`. The core library stays dependency-free.

### Tool: `list_supported_vendors`

No arguments. Returns `{vendor_id: description}` for every registered adapter,
so an agent can decide whether to tag a source with `vendor` before calling
`decision_confidence`.

### Tool: `decision_confidence`

**Input (sketch):**

```jsonc
{
  "subject": "0x… or SYMBOL",
  "sources": [
    {
      "source_id": "goplus",
      "vendor": "goplus",                       // optional; uses the real adapter
      "raw": { "code": 1, "result": { "0x…": { "is_mintable": "1" } } }
    },
    {
      "source_id": "beta_kyt",
      "raw": { "tier": "HIGH" }                 // no vendor → shape sniffing
    },
    {
      "source_id": "gamma_fraud",
      "raw": { "fraud_probability": 0.12 }
    }
  ],
  "weights": { "goplus": 1.0, "beta_kyt": 1.0, "gamma_fraud": 1.0 }  // optional
}
```

Note that a `vendor`-tagged source may expand into **several** observations
(GoPlus produces two), so `weights` keyed by `source_id` weights the vendor's
primary observation; derived observations carry their own suffixed id such as
`goplus:concentration`.

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
- Heuristic thresholds are uncalibrated. `tools/calibrate.py` can measure them
  against labelled data; no such calibration has been run here
- Three real adapters ship, each covering EVM tokens only. Nothing here handles
  Solana, addresses-as-subjects, or compliance vendors — those shapes are
  described in §3.3 but only exercised through the generic fallback
- GoPlus contributes two of the observations in the default three-vendor setup,
  so it carries double weight unless the caller says otherwise (open question 1)
- MCP auth, multi-tenant isolation, and streaming are out of scope by design,
  not pending — see the table at the top of this document

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
| Phase 2 | `src/decision_confidence.py` module, `src/mcp_server.py` (stdio), `tests/` regression suite | done |
| **Phase 3 (this)** | `src/adapters/` registry + three real vendor adapters, construct tagging, `examples/live_multi_source.py`, real-payload fixtures, `tools/calibrate.py` | done |
| Phase 3 — dropped | HTTP in-library, auth, multi-tenancy | out of scope by design; see the table at the top |
| Phase 3 — open | Actually running a calibration against labelled data | not started; needs a dataset and per-subject payload capture |

Token instance demos remain: `examples/pepe_caller_supplied.py`.

**Phase 2 non-regression:** the module was extracted from the example without
behaviour change — `python examples/decision_confidence_demo.py` produced
byte-identical output before and after (verified by checksum), and
`src/normalize.py` is untouched.

**Phase 3 non-regression:** all eleven Phase 2 tests are unchanged and still
pass alongside the twenty-five new ones; `src/normalize.py` is still untouched.
Diffing `examples/decision_confidence_demo.py` output against `HEAD~1` shows
**no numeric change at all** — not one composite, verdict, confidence,
severity, or contradiction moved. The only differences are two new nullable
fields serialising as `null` (`construct`, `constructs`) and one reworded note
string, which had claimed "mock only — no network" and was no longer accurate
once real adapters shipped. Construct tagging is additive and opt-in: an
observation built the Phase 2 way scores and contradicts exactly as it did.
