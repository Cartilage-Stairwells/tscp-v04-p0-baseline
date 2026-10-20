# Project Handoff — TSCP-PL v0.4 P0 Frozen State

**Date:** 2026-08-26
**Authority:** Sean Southwick (via Aria, SupremeHead & Oracle)
**State:** P0 FROZEN — PIVOT TO FUNDING TRACK

---

## Current State

### Technical

| Layer | Status | Reference |
|-------|--------|-----------|
| P0 specifications | 🟢 FROZEN | `specs/` |
| Canonical serialization | 🟢 Independently verified (IV-P0-001) | `evidence/iv_p0_001_verification_artifact.json` |
| Artifact reference model | 🟢 FROZEN | `specs/P0-ARTIFACT-REFERENCE-SPEC-001.md` |
| Resolver implementation | 🟢 Independently behaviorally verified (IV-P0-002) | `evidence/iv_p0_002_verification_artifact.json` |
| Recursive custody | 🟢 PASS | `evidence/resolver_custody_evidence.json` |
| Corruption/restore controls | 🟢 PASS | `tests/iv_p0_002_differential_test.py` |
| SHA-256 manifest (20 files) | 🟢 Verified | `provenance/SHA256SUMS` |
| Git commit | 🟢 `cfc56a4` | |
| Git tag | 🟢 `v0.4-p0-resolver-baseline` | |
| GitHub repository | 🟢 Private/canonical | `Cartilage-Stairwells/tscp-v04-p0-baseline` |
| P1 receipts | 🔴 HOLD | Not yet authorized |
| P2 / 2PC | 🔴 HOLD | Not yet authorized |
| Public repository | 🔴 Separate decision | Pending IP strategy |
| P0 modifications | 🔴 PROHIBITED | Unless explicit new scope authorized |
| Formal proof of P0 specification | 🟡 FUTURE RESEARCH | Not current evidence — do not reopen P0 |

### Funding

| Track | Status | Next Action |
|-------|--------|-------------|
| ONR (Kamgar-Parsi, Code 311) | 🟡 Staged | Send inquiry September 1 |
| ONR (Steinberg, Code 351) | 🟡 Reserve | If Kamgar-Parsi redirects |
| ONR I2D (Sept 21-25) | 🟡 Awaiting late-reg response | Follow up on registration |
| NSF Project Pitch | 🟢 Ready | Review against P0 evidence index |
| NSF company formation | 🟡 Deferred | Not needed for Project Pitch |
| NSF full proposal | 🔴 Not yet applicable | After pitch acceptance + entity formation |
| TTP-T | 🟡 Independent track | Needs eligible academic partner |
| DARPA Assured Autonomy | 🔴 Track 2 — do NOT investigate before ONR is moving | |

---

## Enforcement Rules for Any Agent Joining or Rejoining

### HARD CONSTRAINTS — NO EXCEPTIONS

1. **P0 is FROZEN.** No modifications to any file in the frozen baseline (`v0.4-p0-resolver-baseline` tag). If a P0 defect is discovered, it becomes a new revision with explicit delta and regression evidence — NOT a silent modification.

2. **No P1/P2 work** unless explicitly authorized by Sean. P1 should be a new contract and verification program, not an extension quietly added to the P0 freeze.

3. **No architecture expansion.** No new primitives, no ontology expansion, no scope creep. The frozen boundary is the product, not a stepping stone to be casually extended.

4. **Public disclosure authorized (2026-10-20).** The P0 repository is now approved for public inspection. This authorization applies to this frozen P0 evidence boundary only. Do not add P1/P2 material, private correspondence, credentials, or unrelated operational data.

5. **Claims must trace to evidence.** Every technical claim in any funding material, communication, or document must trace to the exact artifact, test, and commit listed in `provenance/P0-evidence-index.md`. Claims that cannot trace to evidence must be explicitly classified as research hypothesis, not established fact.

6. **Do not let narrative get ahead of evidence.** This is the project's founding discipline. The repository establishes what was frozen. It does not establish naval deployment, operational autonomy, production security, commercial readiness, or formal proof of the complete system. Those remain separate propositions requiring separate evidence.

7. **Secrets stay out.** No credentials, tokens, API keys, or private correspondence in the repository or any public-facing material.


### EPISTEMIC CORRECTION (Aria, 2026-08-26)

The correct P0 status statement is:

> P0 implementation baseline is frozen and independently behaviorally verified against the frozen contracts.

NOT:

> P0 is formally proven correct.

And definitely NOT:

> The entire TSCP-PL architecture is proven.

**Why this matters:** In a custody model, independent implementations agreeing is not equivalent to proving the trusted specification. A flawed specification can propagate its flaw into every faithful implementation. The current evidence establishes behavioral agreement against the frozen contracts — it does not establish formal correctness of the contracts themselves.

**Formal proof of the P0 specification is a FUTURE RESEARCH OBJECTIVE.** If formalization becomes funded research, it is a new work package against the frozen baseline — NOT a reason to reopen P0.

**The research frontier:** What can be formally established about execution integrity when the verifier's observation boundary is constrained?

This connects the P0 engineering baseline to the observation lattice work and gives agencies a legitimate research program:

- Minimum sufficient observation for an integrity predicate
- What integrity properties remain undecidable from restricted observations
- How evidence behaves under distributed/communication-constrained execution
- How independent verification remains meaningful when the execution environment is only partially trusted
- Which parts can be formally specified and proven
- How the evidence architecture maps onto autonomous systems


### EXTERNAL VALIDATION RULE (Aria, 2026-08-26)

External validation may change the research question or funding framing, but it may NOT retroactively alter P0 evidence.

- If ONR says the interesting problem is autonomy under intermittent communications → formulate a new research objective against P0.
- If NSF says the commercial opportunity needs a different application domain → adapt the proposal.
- If an officer challenges an assumption → record it as feedback.

But P0 itself remains the reference baseline.

This preserves the custody principle the project is trying to demonstrate.

When a program officer responds:
- Do NOT immediately interpret the response as validation.
- Treat it as a new piece of external evidence.
- Record the actual response verbatim.
- Distinguish explicit program-officer statements from our interpretation.
- Only then update the funding hypothesis.

This is the same evidence discipline applied one level higher.

**P0 is the instrument now. The agencies are the next experiment.**

### STANDING INSTRUCTIONS (from active_user_instructions)

- Preserve project epistemic state and immutable evidence.
- Distinguish facts from interpretations; never manufacture evidence.
- Operate in a read-only audit mode until dependency material is verified.
- Require independent verification for all claims before acceptance.
- Maintain the TSCP three-layer separation (Evidence, Attestation, Interpretation).
- Adhere to the 'Boundary → Admission → Internal → Preservation' authority invariant.
- Use Unified Provenance Framework (ESTABLISHED, UNESTABLISHED, CONTRADICTED) to classify all claims.
- Ensure build-time enforcement (fail-closed) for all canonical artifacts.

---

## Next Actions (In Order)

1. **No more P0 modifications.** (HARD STOP)

2. **Preserve `cfc56a4` / `v0.4-p0-resolver-baseline` as immutable baseline.**

3. **Keep the repository private.**

4. **Prepare P0 evidence index** — ✅ DONE (`provenance/P0-evidence-index.md`)

5. **Review NSF Project Pitch against the evidence index.**

6. **Send Kamgar-Parsi inquiry on September 1 as planned.** Do not send to multiple POs simultaneously. If Kamgar-Parsi redirects to Science of Autonomy, that's program-officer-confirmed signal — stronger than us asserting Steinberg is the right door.

7. **Continue I2D late-registration thread.**

8. **Keep P1/P2 explicitly parked** until there's a reason to build them.

---

## Key References

| Document | Location |
|----------|----------|
| P0 freeze record | `provenance/P0-freeze-record.md` |
| P0 evidence index | `provenance/P0-evidence-index.md` |
| RFC-R1 correction record | `provenance/RFC-R1-revision.md` |
| SHA-256 manifest | `provenance/SHA256SUMS` |
| Verification manifest | `provenance/verification-manifest.json` |
| GitHub repository | `https://github.com/Cartilage-Stairwells/tscp-v04-p0-baseline` (PUBLIC) |
| Commit | `cfc56a405e59b6f4dd8295886ee48a1a160087c2` |
| Tag | `v0.4-p0-resolver-baseline` |

---

## The Correct Question

The next question is NOT "Can we build more?"

It's: "Does this independently verified evidence boundary solve a problem that ONR/NSF actually care about enough to fund the next experiment?"

## The Research Proposition

> We have established a reproducible, independently verified P0 evidence boundary; the proposed research is to determine how far that boundary can be extended toward formally grounded execution integrity under constrained observation and trust.

That is a research proposition, rather than a claim that we've already solved the whole problem.

That's the uncertainty worth spending the next cycle on.

---

*This handoff document is binding on all agents joining or rejoining the TSCP-PL project. It implements the instructions of Aria, confirmed by SupremeHead & Oracle, as of 2026-08-26.*
