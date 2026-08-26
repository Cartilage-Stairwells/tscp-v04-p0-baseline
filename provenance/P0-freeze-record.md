# V0.4 P0 BASELINE — FROZEN

**Freeze tag:** `v0.4-p0-resolver-baseline`
**Date:** 2026-08-26T20:22:13Z
**Authority:** Sean Southwick (via Aria*)
**Evidence:** IV-P0-001 (independent serialization), IV-P0-002 (independent resolver)

---

## Freeze Declaration

The identified P0 implementation satisfies the frozen P0 contracts to the extent established by IV-P0-001 and IV-P0-002, including independent reproduction of canonical serialization behavior, resolver behavioral agreement, recursive evidence resolution, and corruption detection.

P0 is frozen as an independently verified implementation baseline within the declared evidence scope.

This is NOT: "The entire P0 system is formally proven correct."
This IS: "P0 is frozen as an independently verified implementation baseline within the declared evidence scope."

---

## Frozen Components

### 1. Specifications (contracts)

| # | File | SHA-256 | Size (bytes) |
|---|------|---------|-------------|
| 1 | `P0-CANONICAL-SERIALIZATION-SPEC-001.md` | `7dffb2b41af28fcb3921d6f04f2b0aa82c033e9dad066eb88ca5dd3e6888ff03` | 18177 |
| 2 | `P0-ARTIFACT-REFERENCE-SPEC-001.md` | `58cfab318f0265148f065a7bf5a8714536176ce3a2a25befd0a743653021f5fa` | 13658 |
| 3 | `P0-RESOLVER-SPEC-001.md` | `a7d153ded976b30e5b28be8629846dabdb3addfd9158676961a28c1836026fe4` | 13578 |
| 4 | `P0-RESOLVER-IMPLEMENTATION-001.md` | `8ae81b0604afde7fbf3e855d3216310222ff1167d4efefff3428435a9d3f52e8` | 8168 |

### 2. Production implementations

| # | File | SHA-256 | Size (bytes) |
|---|------|---------|-------------|
| 5 | `canonical_serialization.py` | `96e09e8bb115d3f091d9c819eac4209de182a52f9de817202b5fd3e8db86cf79` | 9442 |
| 6 | `resolver.py` | `9b951c5b394814cedf9618ffa0c82c920abdb347fec6de65006ecf2a2ed7d8d5` | 19009 |

### 3. Independent implementations

| # | File | SHA-256 | Size (bytes) |
|---|------|---------|-------------|
| 7 | `independent_verification_harness.py` | `e17e977ad3b98ca358a6cefd1a319ff20be14e0d03a365013721cb48ca1a84c7` | — |
| 8 | `independent_verifier_v1.py` | `27e0bff84c291376c8cd208843c49b4cb48fc1089dedd25511116843c3bc6af8` | — |
| 9 | `independent_resolver_v1.py` | `a9046a18af300d54e4dd9f60c8745a323b1de32fa7780c9fba11aa820095d76b` | 14487 |

### 4. Verification artifacts

| # | File | SHA-256 | Size (bytes) |
|---|------|---------|-------------|
| 10 | `iv_p0_001_verification_artifact.json` | `feed5c5e0c593d59a53881801d0ccc566b48a79cdbf70857aca703f553a2e5d0` | 5533 |
| 11 | `iv_p0_002_verification_artifact.json` | `9c2ed7b30bee02bc3fd38d70d763335ba4c0df5f0587faa8aee473233d44767c` | 10620 |

### 5. RFC-R1 correction records (pre-fix provenance)

| # | File | SHA-256 | Size (bytes) |
|---|------|---------|-------------|
| 12 | `P0-CANONICAL-SERIALIZATION-SPEC-001.pre-rfc-fix.md` | `34e60f9ab45be452416295bcfd6daac1596b9f2778bbfe51cdffcb90bb1115c0` | 18129 |
| 13 | `P0-RESOLVER-SPEC-001.pre-rfc-fix.md` | `94d4eae9ba62f2c22973b71287079e582875fbd44743bb4b71ea005fe7c3fa9c` | 13566 |
| 14 | `canonical_serialization.pre-rfc-fix.py` | `df50b89c62b26888e14279579abea88d92ed9e57b500da885a6865255c5e9962` | 9415 |

### 6. Test scripts (evidence of verification)

| # | File | SHA-256 | Size (bytes) |
|---|------|---------|-------------|
| 15 | `test_resolver.py` | `eed91869833405f4c3dbc32cd61f929d0364570221931cae4ed67a5453e80c2a` | 28311 |
| 16 | `recursive_custody_processing.py` | `534173a7b129d7b94f65025fa4fc74ce1bb3768e89d0baf7934fcd2f64cdb29c` | 20146 |
| 17 | `iv_p0_002_differential_test.py` | `49e349973aa85805124c7f67df18b8073cfcc11c838ce57a06182a5b7a9bc9cc` | 33804 |

---

## Freeze-Integrity Audit

### Environment

| Property | Value |
|----------|-------|
| Python | 3.11.15 (CPython) |
| Platform | Linux-4.19.0-gvisor-x86_64-with-glibc2.36 |
| OS | Debian GNU/Linux 12 (bookworm) |
| Machine | x86_64 |
| Timestamp | 2026-08-26T20:22:13Z |

### Test commands (exact)

| Suite | Command |
|-------|---------|
| Production acceptance | `python3 test_resolver.py` |
| Independent serialization (IV-P0-001) | `python3 independent_verification_harness.py` |
| Recursive custody | `python3 recursive_custody_processing.py` |
| Independent resolver differential (IV-P0-002) | `python3 iv_p0_002_differential_test.py` |

### Final test-run confirmation

All four test suites were re-run at freeze time. All PASS.

| Suite | Result |
|-------|--------|
| Production acceptance (38 assertions) | PASS |
| Independent serialization (IV-P0-001) | PASS |
| Recursive custody (10 AC + adversarial + restore) | PASS |
| Independent resolver differential (IV-P0-002, 15/15) | PASS |

### Provenance closure

- No git repository. Workspace is a sandbox directory.
- Provenance established by SHA-256 hash chain, not git tree.
- The SHA-256 values above ARE the frozen identity of each component.
- Any modification to any frozen file changes its SHA-256, breaking the freeze.
- The verification artifacts (items 10, 11) reference the implementation hashes of items 5-9.

---

## Evidence Summary

### IV-P0-001: Independent Serialization Verification

- Independent implementation reproduces GV1 (`e559c314...`), GV2 (`84542189...`), GV3 (`b45863b8...`)
- Receipt predecessor links independently recomputed
- 12/12 negative controls pass
- RFC-R1 correction confirmed (JSON Data Interchange Format + JCS, not the previously cited RFC)
- No imports from `canonical_serialization.py`

### IV-P0-002: Independent Resolver Verification

- Independent resolver implementation with zero production-code imports
- 15/15 differential behavioral matrix cases — all match between production and independent
- Recursive custody test: both resolvers independently observe correct SHA-256 of IV-P0-001 artifact
- Corruption test: both resolvers detect byte modification → RESOLVED + IDENTITY_MISMATCH + FAILED + no promotion
- Restore test: both resolvers re-resolve restored original → RESOLVED + MATCH + ELIGIBLE_FOR_VERIFIED
- 3 additional mutation cases (all-zeros hash, all-f's hash, zero declared size) — all correctly classified

### Recursive Custody Processing

- IV-P0-001 verification artifact processed through full ArtifactRef → resolver → custody pipeline
- 10/10 acceptance conditions pass
- Resolver returns evidence (not VERIFIED) — structural separation confirmed
- Custody layer evaluates evidence independently
- Promotion gate works: ELIGIBLE_FOR_VERIFIED + can_promote=True
- Adversarial: one byte corrupted → RESOLVED + IDENTITY_MISMATCH + FAILED + no promotion
- Original restored → re-resolved correctly

---

## Architectural Properties Established

1. **Resolution is not identity.** The resolver distinguishes "I found bytes" from "I found the artifact you claimed." RESOLVED + MISMATCH ≠ NOT_FOUND.

2. **The resolver has no custody promotion path.** No `promote()`, `verify()`, or `freeze()` method. The resolver produces evidence. The custody layer produces verdicts.

3. **No bytes means no identity means no custody.** NOT_FOUND → UNVERIFIED, with no downstream promotion.

4. **Corruption of evidence is detectable.** Both implementations independently detect byte modification and reject promotion.

5. **Independent verification is genuine.** The independent implementations share no production code. The spec is the oracle, not production outputs.

---

## Scope Boundary

### What is frozen

P0 resolver + canonical serialization implementation, as represented by the identified persistent artifacts and verification evidence.

### What is NOT frozen

- The entire v0.4 system
- P1 (cryptographic receipts)
- P2 (transaction integrity / 2PC)
- Any semantics not covered by the frozen P0 contracts

### Post-freeze boundary

```
V0.4 P0 FROZEN
                          │
             ┌────────────┴────────────┐
             │                         │
       VERIFIED P0               Evidence archive
             │
             X
             │
       No P1/P2 mutation
       until separately authorized
```

P1 should be a new contract and verification program, not an extension quietly added to the P0 freeze.

---

## Layer States

| Layer | State |
|-------|-------|
| Canonical serialization contract | FROZEN |
| Artifact reference contract | FROZEN |
| Resolver contract | FROZEN |
| Production P0 implementation | FROZEN |
| Independent serialization verification | PASS |
| Independent resolver verification | PASS |
| Recursive evidence resolution | PASS |
| Corruption detection | PASS |
| P0 provenance closure | COMPLETE |
| P1 receipts | HOLD |
| P2 transaction/2PC | HOLD |
| Full v0.4 system | NOT FROZEN |

---

## Funding Narrative Update

The previous language: "reported implementation; independent verification pending"

Can now legitimately become: "v0.4 P0 has been independently verified and frozen as an implementation baseline, including canonical serialization and artifact-resolution behavior; subsequent receipt and transaction layers remain separate research stages."

Retained distinction: demonstrated prototype capability vs. research hypothesis yet to be validated in operational autonomous-system environments.

---

## The Epistemic Boundary

**Before:** "The system says this artifact exists."

**After P0:** "A declared reference identifies an authorized persistent source; an independently implemented resolver observes its bytes; SHA-256 is recomputed; the result is compared against the declaration; and custody promotion is permitted only after that evidence satisfies the independent verification predicate."

The tests aren't the product. The enforceable evidence boundary is the product.

---

*Frozen 2026-08-26T20:22:13Z. Tag: `v0.4-p0-resolver-baseline`. The line is in the ground.*
