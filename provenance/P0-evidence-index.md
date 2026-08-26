# P0 Evidence Index — Funding-Relevant Claims to Artifacts

**Commit:** `cfc56a405e59b6f4dd8295886ee48a1a160087c2`
**Tag:** `v0.4-p0-resolver-baseline`
**Repository:** `Cartilage-Stairwells/tscp-v04-p0-baseline` (PRIVATE)
**Date:** 2026-08-26

This document maps every funding-relevant claim to the exact artifact, test, and commit that supports it. It exists to prevent claims from outrunning evidence.

---

## Claim 1: "Canonical serialization is specified and independently verified"

**Evidence:**

| Component | File | SHA-256 |
|-----------|------|---------|
| Specification | `specs/P0-CANONICAL-SERIALIZATION-SPEC-001.md` | `7dffb2b4...` |
| Production implementation | `implementation/canonical_serialization.py` | `96e09e8b...` |
| Independent implementation | `independent/independent_verifier_v1.py` | `27e0bff8...` |
| Independent verification harness | `independent/independent_verification_harness.py` | `e17e977a...` |
| Verification artifact | `evidence/iv_p0_001_verification_artifact.json` | `feed5c5e...` |

**Test command:** `PYTHONPATH=implementation:independent python3 independent/independent_verification_harness.py`

**Result:** PASS. Independent implementation reproduces golden vectors GV1 (`e559c314...`), GV2 (`84542189...`), GV3 (`b45863b8...`). 12/12 negative controls pass. Independent implementation imports zero production code.

**RFC correction:** `provenance/RFC-R1-revision.md` documents the correction from incorrect RFC reference to JSON Data Interchange Format + JCS (RFC 8785). Pre-correction hashes recorded. Golden vectors revalidated post-correction — byte-identical.

**Claim status:** ESTABLISHED

---

## Claim 2: "Artifact reference model is specified and frozen"

**Evidence:**

| Component | File | SHA-256 |
|-----------|------|---------|
| Specification | `specs/P0-ARTIFACT-REFERENCE-SPEC-001.md` | `58cfab31...` |

**Key invariants:**
- INV-REF-001: Reference determinacy (same reference → same authorized source)
- INV-REF-002: Location ≠ identity (path change does not alias identity)
- INV-REF-003: Location is not proof of identity (authorized source allowlist enforced)

**Adversarial tests:** 12 adversarial test cases (REF-001 through REF-012) codified in the spec, including path traversal rejection, conversation-only reference rejection, and byte-size discrepancy detection.

**Claim status:** ESTABLISHED (specification frozen); verification via resolver behavioral matrix (Claim 3)

---

## Claim 3: "Resolver behavior is independently verified via differential testing"

**Evidence:**

| Component | File | SHA-256 |
|-----------|------|---------|
| Resolver specification | `specs/P0-RESOLVER-SPEC-001.md` | `a7d153de...` |
| Implementation specification | `specs/P0-RESOLVER-IMPLEMENTATION-001.md` | `8ae81b06...` |
| Production implementation | `implementation/resolver.py` | `9b951c5b...` |
| Independent implementation | `independent/independent_resolver_v1.py` | `a9046a18...` |
| Differential test harness | `tests/iv_p0_002_differential_test.py` | `d436106d...` |
| Verification artifact | `evidence/iv_p0_002_verification_artifact.json` | `ba28efc8...` |

**Test command:** `PYTHONPATH=implementation:independent python3 tests/iv_p0_002_differential_test.py`

**Result:** PASS. 15/15 differential behavioral matrix cases. Both implementations (production + independent, zero shared code) converge on same outputs. The SPEC was the oracle, not production outputs.

**Test cases:**
1. Existing correct file → RESOLVED + MATCH + ELIGIBLE_FOR_VERIFIED
2. Missing file → NOT_FOUND + UNVERIFIED
3. Wrong bytes (hash mismatch) → RESOLVED + MISMATCH + FAILED
4. Wrong byte size (correct hash, wrong declared size) → RESOLVED + MISMATCH + FAILED
5. Directory instead of file → UNREADABLE + UNVERIFIED
6. Symlink escape (outside authorized root) → ACCESS_DENIED + UNVERIFIED
7. Path traversal (../ in locator) → REJECTED_AT_CONSTRUCTION
8. Conversation-only reference (prohibited source) → REJECTED_AT_CONSTRUCTION
9. Same bytes, two locations → RESOLVED + MATCH (identity ≠ location)
10. Empty file (0 bytes, correct hash) → RESOLVED + MATCH
11. Same path, declared hash from different bytes → RESOLVED + MISMATCH + FAILED
12. Safe symlink within authorized root → RESOLVED + MATCH
13. Declared hash all zeros (placeholder) → RESOLVED + MISMATCH + FAILED
14. Declared hash all f's (placeholder) → RESOLVED + MISMATCH + FAILED
15. Declared byte size 0 but file has content → RESOLVED + MISMATCH + FAILED

**Independence constraints enforced:** Independent resolver (`independent_resolver_v1.py`) imports nothing from `resolver.py` or `canonical_serialization.py`. Legitimate independent design decisions documented (bare path locator vs `filesystem:` prefix, different class structure).

**Claim status:** ESTABLISHED

---

## Claim 4: "Recursive custody works — verification evidence is itself subjected to the resolver boundary"

**Evidence:**

| Component | File | SHA-256 |
|-----------|------|---------|
| Recursive custody test | `tests/recursive_custody_processing.py` | `0646b898...` |
| Input artifact (IV-P0-001 evidence) | `evidence/iv_p0_001_verification_artifact.json` | `feed5c5e...` |
| Custody evidence output | `evidence/resolver_custody_evidence.json` | `d37ee06e...` |

**Test command:** `PYTHONPATH=implementation:independent python3 tests/recursive_custody_processing.py`

**Result:** PASS. 10/10 acceptance conditions pass. The IV-P0-001 verification artifact was processed through the full pipeline: ArtifactRef → resolver → observation → SHA-256 recomputation → identity comparison → custody evaluation. Both resolvers independently observe the correct SHA-256 (`feed5c5e...`) and return ELIGIBLE_FOR_VERIFIED + can_promote=True.

**Architectural property established:** Resolution is not identity. RESOLVED + MISMATCH ≠ NOT_FOUND. The resolver produces evidence; the custody layer produces verdicts. No promotion path exists inside the resolver.

**Claim status:** ESTABLISHED

---

## Claim 5: "Corruption of evidence is detectable by both implementations"

**Evidence:**

| Component | File | SHA-256 |
|-----------|------|---------|
| Corruption test (in differential test) | `tests/iv_p0_002_differential_test.py` | `d436106d...` |
| Verification artifact | `evidence/iv_p0_002_verification_artifact.json` | `ba28efc8...` |

**Test:** One byte of `evidence/iv_p0_001_verification_artifact.json` was changed ('P' → 'Q' at byte index 5483). Both implementations run against the corrupted file.

**Result:** PASS. Both resolvers independently returned: RESOLVED + IDENTITY_MISMATCH + FAILED + no promotion. Restore test confirmed: original bytes re-resolved correctly by both implementations.

**Claim status:** ESTABLISHED

---

## Claim 6: "The frozen source tree is cryptographically manifested and reproducible"

**Evidence:**

| Component | File | SHA-256 |
|-----------|------|---------|
| SHA-256 manifest | `provenance/SHA256SUMS` | (20 files, all verified OK) |
| Freeze record | `provenance/P0-freeze-record.md` | `62fc3020...` |
| Verification manifest | `provenance/verification-manifest.json` | `40c7f7ff...` |
| RFC-R1 correction record | `provenance/RFC-R1-revision.md` | `550a7ff6...` |

**Verification:** `sha256sum -c provenance/SHA256SUMS` → all 20 files OK

**Reproducibility:**
```
git clone https://github.com/Cartilage-Stairwells/tscp-v04-p0-baseline.git
cd tscp-v04-p0-baseline
git checkout v0.4-p0-resolver-baseline
sha256sum -c provenance/SHA256SUMS
PYTHONPATH=implementation:independent python3 tests/test_resolver.py
PYTHONPATH=implementation:independent python3 independent/independent_verification_harness.py
PYTHONPATH=implementation:independent python3 tests/recursive_custody_processing.py
PYTHONPATH=implementation:independent python3 tests/iv_p0_002_differential_test.py
```

**Claim status:** ESTABLISHED

---

## Claims that are NOT established

The following are explicitly NOT established by the P0 evidence:

| Claim | Status | What would establish it |
|-------|--------|------------------------|
| Naval deployment capability | NOT ESTABLISHED | Operational testing in naval environment |
| Production security | NOT ESTABLISHED | Security audit, penetration testing |
| Resistance to all adversaries | NOT ESTABLISHED | Adversarial analysis beyond the 15 test cases |
| Commercial readiness | NOT ESTABLISHED | Product development, user testing |
| Formal proof of complete system | NOT ESTABLISHED | Formal verification (Lean/Coq) of all components |
| P1 (cryptographic receipts) | NOT ESTABLISHED | New contract, implementation, independent verification |
| P2 (transaction integrity / 2PC) | NOT ESTABLISHED | New contract, implementation, independent verification |
| ONR/NSF funding fit confirmed | NOT ESTABLISHED | Program officer response |
| Operational autonomous-system validation | NOT ESTABLISHED | Testing in operational conditions |

---

## Funding narrative mapping

### For ONR (Kamgar-Parsi / Science of Autonomy):

**What we can say:**
> TSCP-PL has established an independently verified P0 evidence boundary for artifact identity, resolution, and custody promotion. The research question is whether this evidence architecture can be extended to assured execution integrity in autonomous systems under constrained trust, communication, and observability.

**What backs this:**
- Claims 1-6 above (all ESTABLISHED)
- Commit `cfc56a4`, tag `v0.4-p0-resolver-baseline`
- Private GitHub repository (reproducible)

**What we cannot say:**
> "Our cryptographically verified production framework has demonstrated operational autonomy in naval environments."

This is NOT established. No operational testing has been conducted.

### For NSF (Project Pitch / SBIR):

**What we can say:**
> P0 baseline: independently verified and frozen. Research: extension from the controlled P0 environment into operational autonomous-system conditions. Unresolved scientific questions: observation sufficiency, distributed evidence coherence, constrained-resource operation, and adversarial execution environments.

**What backs this:**
- Claims 1-6 (credible starting point)
- Explicit list of unresolved questions (nontrivial technical uncertainty)
- DoD/autonomy relevance (commercial/DoD need)

**What we cannot say:**
> "Production-ready framework with demonstrated commercial viability."

This is NOT established.

---

*This evidence index is the authoritative mapping of claims to artifacts for the v0.4-p0-resolver-baseline. Any future claim must trace to the artifact listed here, or be explicitly classified as research hypothesis rather than established evidence.*
