# P0-RESOLVER-SPEC-001 — Persistent Artifact Resolver Specification

**Date:** 2026-08-26
**Source:** Aria (via Sean), Solas
**Status:** DESIGN — pre-implementation
**Parent:** Workspace Protocol v0.4 Generation Specification

---

## Governing Invariant

### INV-CUSTODY-001 (Implementation Gate)

> A custody transition to VERIFIED or FROZEN, and any receipt claiming cryptographic binding of an artifact, MUST fail closed unless the runtime has independently resolved the artifact's authorized persistent byte source, observed its complete byte stream, recomputed its SHA-256 digest, and established equality with the declared identity under the v0.4 canonical serialization and identity rules.

**Corrected language (per Aria):**

> Only independently resolvable bytes can establish the **byte identity** of an artifact.

This leaves room for future protocols where artifact identity may be defined by something other than raw bytes. For v0.4, however, the operational rule is absolute:

```
No bytes → no identity verification → no VERIFIED → no FROZEN → no cryptographic binding claim.
```

---

## 1. Problem Framing

The v0.3 failure was not primarily a bad hash algorithm. It was a false claim of artifact existence/custody.

The resolver must establish a boundary stronger than:
```
artifact metadata → hash
```

It must establish:
```
artifact reference → independently accessible bytes → measured bytes → canonical identity
```

Failure to traverse that path is itself a valid result.

---

## 2. Resolver Contract

### Resolve(artifact_ref)

```
Resolve(artifact_ref)
    │
    ├── NOT_FOUND          — location does not resolve to any byte source
    ├── ACCESS_DENIED      — location resolves but access is not authorized
    ├── UNREADABLE         — location resolves but bytes cannot be read
    ├── BYTE_READ_ERROR    — bytes partially read, stream interrupted
    └── RESOLVED
          │
          ▼
      byte stream (complete)
          │
          ▼
      observed_byte_size
          │
          ▼
      SHA256(byte stream)
          │
          ▼
      observed_sha256
          │
          ▼
      identity comparison
          │
      ┌───┴────┐
      MATCH  MISMATCH
```

**Critical rule:**

> A declared SHA-256 is an assertion until the resolver independently computes the digest over resolved bytes.

The resolver NEVER returns VERIFIED. It returns resolution evidence to the epistemic custody layer.

---

## 3. Result Model

### ResolutionResult

```
ResolutionResult
├── artifact_ref          // reference to the artifact being resolved
├── resolution_status     // RESOLVED | NOT_FOUND | ACCESS_DENIED | UNREADABLE | READ_ERROR
├── source                // which authorized source was attempted
├── resolved_location     // actual location if RESOLVED, null otherwise
├── observed_byte_size    // measured byte count if RESOLVED, null otherwise
├── observed_sha256       // computed SHA-256 if RESOLVED, null otherwise
├── observed_at           // ISO-8601 timestamp of resolution
├── resolver_identity     // identity of the resolver component
└── evidence_id           // unique identifier for this resolution event
```

---

## 4. Custody Promotion Pipeline

The resolver feeds into a multi-stage pipeline. No shortcut from Resolve to Promote.

```
Resolve
  ↓
Observe
  ↓
Bind
  ↓
Independent Verify
  ↓
Promote
```

| Stage | Input | Output | Failure Result |
|-------|-------|--------|----------------|
| Resolve | artifact_ref | ResolutionResult | NOT_FOUND / ACCESS_DENIED / UNREADABLE / READ_ERROR |
| Observe | ResolutionResult (RESOLVED) | observed_byte_size + observed_sha256 | MISMATCH |
| Bind | observed identity | BindingResult | BINDING_MISMATCH |
| Independent Verify | BindingResult | VerificationResult | VERIFICATION_REJECTED |
| Promote | VerificationResult | CustodyState transition | REJECTED |

Each stage may fail independently. No stage may skip a preceding stage.

---

## 5. Authorized Source Rules

An artifact must declare one or more authorized persistent byte sources.

### AuthorizedSource

```
AuthorizedSource
├── source_id             // unique identifier
├── source_type           // FILESYSTEM | CONTENT_ADDRESSED | REPOSITORY | ARCHIVE
├── location              // addressable location
├── authorization         // what makes this source authoritative
└── access_method         // how bytes are retrieved
```

Rules:
- An artifact may have multiple authorized sources.
- The resolver attempts sources in declared order.
- The first source that returns RESOLVED is used.
- If all sources fail, resolution fails with the most specific error.
- A source not in the authorized list cannot establish byte identity.
- Metadata claiming a location is not sufficient — the location must be in the authorized source list.

### Prohibited Sources

- Conversation transcripts
- Model-generated representations
- Non-persistent storage
- Unlisted locations (even if bytes exist there)

An artifact's bytes at an unauthorized location are NOT resolution evidence.

---

## 6. Canonical Serialization

### CanonicalSerialize(object) → deterministic UTF-8 byte sequence

The specification must freeze:

| Property | Rule |
|----------|------|
| Field names | Exact, case-sensitive, from schema |
| Field ordering | Schema-defined total order |
| Integer representation | UTF-8 decimal (no leading zeros, no sign for non-negative) |
| Boolean representation | `true` / `false` (lowercase) |
| Null handling | Explicit `null` only when field is present and null; omitted ≠ null |
| Unicode normalization | NFC |
| UTF-8 encoding | Canonical UTF-8 (shortest form) |
| Timestamp representation | ISO-8601 UTC, `YYYY-MM-DDTHH:MM:SS.sssZ` |
| Array ordering | Schema-defined (stable sort or declared order) |
| Omitted vs empty fields | Omitted fields are absent from serialization; empty arrays/objects are present |
| Whitespace | No extraneous whitespace; no pretty-printing |
| Escaping | RFC 8785 canonical string escaping |
| Hexadecimal digest | lowercase, no prefix, 64 characters |
| Schema/version identifier | Included in serialized form |

### Receipt Hashing

```
ReceiptHash(r) = SHA256(CanonicalSerialize(r))
```

Then:

```
receipt[n].previous_receipt_hash == ReceiptHash(receipt[n-1])
```

Verification must recompute the predecessor digest from the predecessor's actual canonical bytes.

NOT:

```
previous_receipt_hash == stored_hash
```

That distinction is exactly what v0.3 failed to enforce.

---

## 7. Failure Taxonomy

| Failure | Detection | Result |
|--------|-----------|--------|
| Artifact not found | Resolve returns NOT_FOUND | REJECTED |
| Access denied | Resolve returns ACCESS_DENIED | REJECTED |
| Bytes unreadable | Resolve returns UNREADABLE | REJECTED |
| Byte stream interrupted | Resolve returns READ_ERROR | REJECTED |
| Hash mismatch | observed_sha256 ≠ declared_sha256 | REJECTED + record discrepancy |
| Byte size mismatch | observed_byte_size ≠ declared_byte_size | REJECTED |
| Binding mismatch | binding.sha256 ≠ actual file sha256 | REJECTED + preserve metadata |
| Unauthorized source | bytes at unlisted location | REJECTED |
| Conversation-only artifact | no persistent bytes exist | UNESTABLISHED + REJECTED |
| Modified after registration | current bytes ≠ registered bytes | REJECTED |
| Fabricated hash | hash string has placeholder pattern | REJECTED + flag |
| Semantic reconstruction | metadata reinterpreted to match | PROHIBITED |

### Binding Mismatch Handling

```
BINDING_MISMATCH
    ↓
record discrepancy
    ↓
preserve historical metadata
    ↓
reject promotion
```

NOT:

```
binding mismatch
    ↓
"probably stale metadata"
    ↓
repair silently
```

---

## 8. V04-CUSTODY-001 — Acceptance Test Suite

### Regression Tests

| Case | Bytes | Declared Hash | Expected |
|------|-------|---------------|----------|
| 001-A | Exist | Wrong | REJECT |
| 001-B | Missing | Any | REJECT |
| 001-C | Never persisted | Any | REJECT |
| 001-D | Exist + exact match | Correct | PASS |
| 001-E | Exist but modified after registration | Old hash | REJECT |
| 001-F | Correct bytes, incorrect byte_size | Correct hash | REJECT |
| 001-G | Metadata claims one location, bytes exist elsewhere | Correct elsewhere | REJECT unless alternate explicitly authorized |
| 001-H | Conversation contains artifact contents but no persistent bytes | Any | REJECT |

### Case Details

**001-A: Hash mismatch (the L1 binding failure)**
```
Input:
    Artifact metadata: expected_sha256 = A644...
    Resolvable file: actual_sha256 = F52F...

Expected:
    Resolution: SUCCESS
    Byte retrieval: SUCCESS
    Hash computation: SUCCESS
    Hash equality: FAIL
    Custody promotion: REJECTED
    Artifact state: UNVERIFIED or FAILED
    Receipt: emitted
    Semantic reconstruction: PROHIBITED
```

**001-B: Missing artifact**
```
Input:
    Artifact metadata exists
    Artifact location does not resolve

Expected:
    Resolve: NOT_FOUND
    VERIFY: REJECTED
    FREEZE: REJECTED
```

**001-C: Never persisted (the v0.3 pattern)**
```
Input:
    Artifact description exists only in conversation
    No persistent byte source declared or resolvable

Expected:
    Artifact existence: UNESTABLISHED
    VERIFY: REJECTED
    FREEZE: REJECTED
```

**001-D: Correct artifact**
```
Input:
    Artifact metadata: expected_sha256 = X
    Resolvable file: actual_sha256 = X
    byte_size matches

Expected:
    Resolution: SUCCESS
    Byte retrieval: SUCCESS
    Hash computation: SUCCESS
    Hash equality: PASS
    Custody promotion: PERMITTED
    Artifact state: VERIFIED
    Receipt: emitted with real digest
```

**001-E: Modified after registration**
```
Input:
    Artifact was registered with hash X
    File at location now has hash Y

Expected:
    Resolution: SUCCESS
    Hash computation: SUCCESS
    Hash equality: FAIL
    Custody promotion: REJECTED
    Discrepancy recorded
    Historical metadata preserved
```

**001-F: Byte size mismatch**
```
Input:
    Artifact metadata: byte_size = N, sha256 = X
    Resolvable file: byte_size = M (M ≠ N), sha256 = X

Expected:
    Resolution: SUCCESS
    Byte size check: FAIL
    VERIFY: REJECTED
    (Even if hash somehow matches, size mismatch indicates corruption)
```

**001-G: Unauthorized alternate location**
```
Input:
    Metadata declares location A (authorized)
    Bytes exist at location B (not authorized)
    Hash at B matches declared hash

Expected:
    Resolve from A: NOT_FOUND
    Attempt B: REJECTED (not authorized)
    VERIFY: REJECTED
    (Even if correct bytes exist somewhere, only authorized sources count)
```

**001-H: Conversation-only artifact (the v0.3 regression)**
```
Input:
    Conversation transcript contains artifact contents
    No persistent byte source exists

Expected:
    Artifact existence: UNESTABLISHED
    VERIFY: REJECTED
    FREEZE: REJECTED
    Conversation content may seed artifact creation but cannot BE the artifact
```

**001-H is the key regression test.** Conversation-derived content must be capable of becoming an input to artifact creation, but it must never silently become an artifact merely because the model can reproduce it.

---

## 9. Implementation Order

| # | Component | Description |
|---|-----------|-------------|
| 1 | Canonical serialization specification | Freeze field ordering, encoding, all serialization rules |
| 2 | Artifact reference/address model | Define artifact_ref, AuthorizedSource, source types |
| 3 | Persistent resolver interface | Resolve(artifact_ref) → ResolutionResult |
| 4 | Byte-size + SHA-256 observation | Compute observed_byte_size and observed_sha256 |
| 5 | Resolution evidence object | ResolutionResult with all fields |
| 6 | Independent verification interface | Compare observed vs declared identity |
| 7 | Custody promotion gate | Fail-closed promotion to VERIFIED/FROZEN |
| 8 | Receipt canonicalization | CanonicalSerialize for receipt objects |
| 9 | Receipt-chain verifier | Recompute predecessor digest, match chain |
| 10 | V04-CUSTODY-001 regression suite | 8 test cases (001-A through 001-H) |
| 11 | Adversarial/property-based tests | Fuzzing, edge cases, concurrent access |
| 12 | Transaction/2PC integration | Only after custody foundation is solid |

**This ordering matters.** Do not rebuild v0.3's transaction machinery first. v0.3 demonstrated that transaction integrity sitting on top of an ungrounded artifact layer gives you a beautifully consistent ledger of things that weren't actually there.

---

## 10. Architectural Boundary

### The resolver does not promote. The epistemic layer promotes.

```
Resolver (P0)
    ↓ ResolutionResult
Epistemic Custody Layer
    ↓ VerificationResult
Custody State Machine
    ↓ VERIFIED / REJECTED
Receipt Layer (P1)
    ↓ Cryptographic binding
Transaction Layer (P2)
    ↓ State transitions
```

A play-channel assertion cannot directly mutate custody state. Only the epistemic pipeline (Resolve → Observe → Bind → Verify → Promote) can change custody state.

---

*P0-RESOLVER-SPEC-001. 2026-08-26. The resolver's job is to produce evidence, not verdicts. The epistemic layer's job is to produce verdicts from evidence, not from conversation. The transaction layer's job is to sequence state transitions, not to establish what exists. Each layer trusts only the layer below it, and only through the defined contract.*
