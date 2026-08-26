# P0-RESOLVER-IMPLEMENTATION-001 — Persistent Artifact Resolver Implementation

**Date:** 2026-08-26
**Status:** IMPLEMENTED — all acceptance tests PASS
**Parent:** P0-RESOLVER-SPEC-001, P0-ARTIFACT-REFERENCE-SPEC-001, P0-CANONICAL-SERIALIZATION-SPEC-001
**Language:** Python 3
**Files:** `resolver.py`, `canonical_serialization.py`, `test_resolver.py`

---

## Test Results

```
TSCP v0.4 — P0-RESOLVER-IMPLEMENTATION-001 Acceptance Test Suite
ALL TESTS PASSED

Three fundamental propositions verified:
  1. ABSENCE: No bytes -> no verification -> no custody promotion
  2. CONTRADICTION: Wrong bytes -> FAILED (not UNVERIFIED)
  3. CONFIRMATION: Correct bytes -> eligible for verification

The resolver has NO custody promotion path by construction.
resolve() -> ResolutionResult. Not resolve() -> VERIFIED.
```

### Phase 1: Three Fundamental Propositions (18 assertions)

| Proposition | Test | Result |
|-------------|------|--------|
| ABSENCE | Declared artifact, no bytes resolvable | PASS — NOT_FOUND, UNVERIFIED, no promotion |
| CONTRADICTION | Bytes found, identity mismatch (L1 binding) | PASS — RESOLVED + MISMATCH, FAILED, no promotion |
| CONFIRMATION | Bytes found, identity match | PASS — RESOLVED + MATCH, ELIGIBLE_FOR_VERIFIED, promotion permitted |

### Phase 2: V04-CUSTODY-001 (8 tests)

| Case | Description | Result |
|------|-------------|--------|
| 001-A | Hash mismatch (L1 binding failure) | PASS — REJECT |
| 001-B | Missing artifact | PASS — REJECT |
| 001-C | Never persisted (v0.3 pattern) | PASS — REJECT |
| 001-D | Correct artifact, exact match | PASS — PASS |
| 001-E | Modified after registration | PASS — REJECT |
| 001-F | Byte size mismatch | PASS — REJECT |
| 001-G | Unauthorized location | PASS — REJECT (at construction) |
| 001-H | Conversation-only artifact (v0.3 regression) | PASS — REJECT (at construction) |

### Phase 3: REF-001 through REF-012 (12 tests)

| Test | Attack | Result |
|------|--------|--------|
| REF-001 | Nonexistent path | PASS — NOT_FOUND |
| REF-002 | Path resolves to wrong bytes | PASS — RESOLVED + IDENTITY_MISMATCH |
| REF-003 | Path replaced after registration | PASS — old identity preserved |
| REF-004 | Directory where file expected | PASS — REJECT (UNREADABLE) |
| REF-005 | Symlink escapes authorized root | PASS — REJECT (ACCESS_DENIED) |
| REF-006 | Relative path traversal | PASS — REJECT (at construction) |
| REF-007 | Ambiguous URI | PASS — REJECT |
| REF-008 | Conversation-only artifact | PASS — REJECT (at construction) |
| REF-009 | Ephemeral memory reference | PASS — REJECT (at construction) |
| REF-010 | Same bytes at two authorized locations | PASS — same identity, distinct provenance |
| REF-011 | Same path, different bytes | PASS — different identities |
| REF-012 | Declared size differs from observed | PASS — REJECT promotion |

### Phase 4: Golden Vectors (9 assertions + 3 chain checks)

| Vector | Computed SHA-256 | Spec Expected | Match |
|--------|-----------------|---------------|-------|
| GV1 (Genesis PREPARE) | e559c314... | e559c314... | ✓ |
| GV2 (COMMIT) | 84542189... | 84542189... | ✓ |
| GV3 (ABORT) | b45863b8... | b45863b8... | ✓ |

Chain verification:
- GV2.previous_receipt_hash == SHA256(GV1): ✓
- GV3.previous_receipt_hash == SHA256(GV2): ✓
- GV1 genesis: previous_receipt_hash is None: ✓

### Phase 5: Cross-Implementation Verification (10 assertions)

- All three golden vectors independently recomputed: ✓
- All hashes are 64 lowercase hex chars: ✓
- No whitespace in canonical bytes: ✓
- Modified receipt produces different hash: ✓

---

## Architecture

### Separation of concerns

```
PERSISTENT SOURCE
      │
      ▼
 ARTIFACT REF (ArtifactRef)
      │
      ▼
   RESOLVER (ArtifactResolver.resolve)
      │
      ▼
 OBSERVATION EVIDENCE (ResolutionResult)
      │
      ▼
 INDEPENDENT VERIFIER (IndependentVerifier)
      │
      ▼
 CUSTODY VERDICT (UNVERIFIED | FAILED | ELIGIBLE_FOR_VERIFIED)
      │
      ▼
 TRANSACTION / RECEIPT LAYER
```

The resolver sits at "OBSERVATION EVIDENCE" and does not cross into custody verdicts. This separation is structural, not conventional.

### The resolver has NO custody promotion path

```python
class ArtifactResolver:
    def resolve(self, artifact_ref: ArtifactRef) -> ResolutionResult:
        ...
    
    # NO promote() method
    # NO verify() method
    # NO freeze() method
    # The resolver produces evidence. Period.
```

### RESOLVED + IDENTITY_MISMATCH ≠ NOT_FOUND

The three fundamental propositions map to three distinct custody outcomes:

| Proposition | Resolution | Identity | Custody Verdict |
|-------------|-----------|----------|-----------------|
| Absence | NOT_FOUND | NOT_APPLICABLE | UNVERIFIED |
| Contradiction | RESOLVED | MISMATCH | FAILED |
| Confirmation | RESOLVED | MATCH | ELIGIBLE_FOR_VERIFIED |

"I found something" and "I found the artifact you claimed" are not equivalent propositions. v0.3 treated them as equivalent. v0.4 does not.

---

## Implementation Files

### resolver.py
- `ArtifactRef` — 8-field reference to persistent bytes (INV-REF-001, INV-REF-002, INV-REF-003)
- `ResolutionResult` — evidence object with observed bytes, size, SHA-256, identity match
- `ArtifactResolver` — resolves refs to evidence; NEVER promotes custody
- `FilesystemSourceHandler` — FILESYSTEM source with symlink protection, path traversal rejection
- `ContentAddressedSourceHandler` — CONTENT_ADDRESSED source (hash-keyed store)
- `AuthorizedSourceRegistry` — INV-REF-003 enforcement; prohibited sources list
- `IndependentVerifier` — epistemic layer; evaluates evidence, makes custody determinations

### canonical_serialization.py
- `Receipt` — 19-field canonical receipt with enum validation
- `canonical_serialize_receipt()` — deterministic UTF-8 bytes per spec
- `receipt_hash()` — SHA-256 of canonical bytes
- `verify_receipt_hash()` — independent recomputation (INV-SERIAL-001)
- `verify_predecessor()` — receipt-chain verification by recomputation
- `golden_vectors()` — three golden vectors with expected SHA-256 digests

### test_resolver.py
- Phase 1: Three fundamental propositions (absence, contradiction, confirmation)
- Phase 2: V04-CUSTODY-001 (8 acceptance tests)
- Phase 3: REF-001 through REF-012 (12 adversarial tests)
- Phase 4: Golden vector reproduction and chain verification
- Phase 5: Cross-implementation verification

---

## What This Implementation Prevents

| v0.3 Failure | v0.4 Prevention | Test |
|---------------|-----------------|------|
| Conversation claim as artifact existence | Prohibited source kinds rejected at construction | 001-H, REF-008 |
| Path treated as identity | Location resolved, identity independently computed | INV-REF-002, REF-002 |
| Mutable path as stable identity | Reference immutability; old identity preserved | REF-003, REF-011 |
| "Found something" = "found claimed artifact" | RESOLVED + MISMATCH ≠ NOT_FOUND | Proposition 2, REF-002 |
| Binding hash mismatch treated as stale | MISMATCH → FAILED, not repaired | 001-A, REF-002 |
| Placeholder hashes accepted | Independent recomputation required | INV-SERIAL-001, Golden vectors |
| Unauthorized location accepted | AuthorizedSourceRegistry enforces boundary | 001-G, REF-005 |
| Relative path traversal | Rejected at construction | REF-006 |
| Symlink escape | Realpath check against authorized root | REF-005 |

---

## Next Steps

Per Aria's instruction: resist moving to 2PC until the resolver implementation and its acceptance evidence are independently verified and frozen.

1. Independent verification of this implementation (second implementation reproducing golden vectors)
2. Freeze the resolver + acceptance evidence as v0.4 P0 baseline
3. Only then proceed to P1 (cryptographic receipts) or P2 (transaction integrity)

---

*P0-RESOLVER-IMPLEMENTATION-001. 2026-08-26. The resolver produces evidence. The verifier produces verdicts. The chain is established by independent computation. No bytes means no identity means no custody means no binding claim. This is the foundation v0.3 was missing.*
