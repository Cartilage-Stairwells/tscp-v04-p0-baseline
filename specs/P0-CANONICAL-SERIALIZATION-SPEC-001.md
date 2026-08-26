# P0-CANONICAL-SERIALIZATION-SPEC-001 — Canonical Receipt Serialization

**Date:** 2026-08-26
**Source:** Aria (via Sean), Solas
**Status:** DESIGN — pre-implementation
**Parent:** P0-RESOLVER-SPEC-001, Workspace Protocol v0.4 Generation Specification
**Supersedes:** RFC 8785 JCS-only instruction for v0.4 protocol objects (see §13)

---

## Governing Invariant

### INV-SERIAL-001

> No receipt hash may be accepted as cryptographically valid unless the verifier can independently reconstruct the canonical byte representation of the receipt and recompute its SHA-256 digest.

This prevents the v0.3 failure from reappearing one layer lower. A `sha256:`-prefixed string in a receipt field is an assertion, not a verification. Only independent recomputation from canonical bytes establishes a hash.

---

## Trust Chain

The serializer is NOT a trusted helper. The trust chain remains:

```
Persistent bytes → Resolver → Observation → Canonical interpretation → Independent recomputation → Verification → Custody promotion
```

And separately:

```
Canonical receipt bytes → independently recomputed digest → receipt-chain verification
```

The serializer produces a deterministic byte representation. The verifier independently reconstructs that representation and recomputes the digest. If they differ, verification fails.

---

## 1. Serialization Domain

### Canonically serializable object types in v0.4

| Type | Canonical? | Notes |
|------|-----------|-------|
| Receipt | YES | The primary canonical object |
| ResolutionResult | YES | Resolver evidence output |
| ArtifactManifest | YES | Artifact metadata bundle |
| BindingRecord | YES | Artifact-to-hash binding |
| AuditReport | YES | Verification audit output |
| Ordinary JSON / API responses | NO | These use standard JSON, not canonical serialization |

Only objects in the canonical domain are hashed. API/transport JSON representations are explicitly NOT canonical and must not be hashed.

---

## 2. Field Ordering

### Receipt field order (frozen, schema-defined total order)

```
 1. protocol_version        string
 2. schema_version          string
 3. receipt_id              string
 4. sequence_number         integer
 5. receipt_type            enum: PREPARE | COMMIT | ABORT | CHECKPOINT
 6. transaction_id          string
 7. artifact_id             string
 8. artifact_location       string
 9. artifact_byte_size      integer
10. artifact_sha256         string (64 lowercase hex chars)
11. previous_receipt_hash   string (64 hex) | null
12. base_receipt_hash       string (64 hex) | null
13. custody_state           enum: UNVERIFIED | OBSERVED | VERIFIED | FAILED | FROZEN
14. transaction_state       enum: NONE | STAGED | COMMITTING | COMMITTED | ABORTED
15. observed_sha256         string (64 hex) | null
16. observed_byte_size      integer | null
17. timestamp              string (ISO-8601 UTC)
18. resolver_identity       string | null
19. evidence_id             string | null
```

**Critical rule:** Field order is schema-defined, NOT lexicographic. Two implementations that produce semantically identical receipts but with fields in different order MUST produce different hashes. Only the schema-defined order is canonical.

This is a deliberate departure from RFC 8785 JCS (which uses lexicographic ordering). See §13 for the supersession rationale.

---

## 3. Primitive Encoding

### UTF-8
- All output is UTF-8 encoded.
- No BOM (Byte Order Mark).
- Canonical UTF-8 (shortest form per RFC 3629).

### Integers
- Decimal representation: digits 0-9, no leading zeros (except the integer 0 itself).
- No sign prefix for non-negative integers.
- Negative integers: `-` followed by digits (same rules).
- Range: signed 64-bit (-9,223,372,036,854,775,808 to 9,223,372,036,854,775,807).
- No floating-point values in canonical protocol objects.

### Booleans
- Lowercase: `true` or `false`.
- No 0/1, no yes/no, no True/False.

### Null
- Lowercase: `null`.
- Null is a semantic value, not an absence. See §5.

### Strings
- Double-quoted: `"..."`.
- RFC 8785 §3.2.2.2 canonical string escaping (RFC 8259 §7 syntax): `"`, `\`, control characters (`\n`, `\r`, `\t`, `\b`, `\f`, `\uXXXX` for U+0000 through U+001F).
- No escaping of forward slash (`/`) — it is not required by RFC 8259 §7 and introduces ambiguity.
- NFC normalization applied before encoding (see §6).

### Timestamps
- ISO-8601 UTC.
- Exact format: `YYYY-MM-DDTHH:MM:SS.sssZ`
- Milliseconds required (3 digits).
- `Z` suffix required (no `+00:00` or `+0000`).
- No alternate equivalent forms.
- Example: `2026-08-26T00:00:00.000Z`

### SHA-256 digests
- Lowercase hexadecimal.
- No prefix (no `sha256:` or `0x`).
- Exactly 64 characters.
- Example: `e559c31411bd10f49360d17921222782ecd663fd110d33d9d4af20256dacda08`

---

## 4. Collections

### Arrays
- Array order is **semantic** by default. The order of elements carries meaning.
- Arrays MUST NOT be sorted during canonical serialization.
- For explicitly unordered collections (future types), the spec will define a deterministic ordering (e.g., lexicographic by a key field). This ordering must be specified per-collection, never left implicit.

### Objects
- Fields in schema-defined order (§2).
- Recursive: nested objects follow their own schema order.
- No empty objects in canonical receipts (all receipt fields are defined).

---

## 5. Omission Semantics

These four states must NOT collapse into one another:

| State | Serialization | Meaning |
|-------|--------------|---------|
| Absent (field not in schema) | Field not serialized | Field does not exist in this object type |
| Null (field present, value is null) | `"field":null` | Field exists but has no value (semantic null) |
| Empty array | `"field":[]` | Field exists, collection is empty |
| Empty object | `"field":{}` | Field exists, object has no fields (not used in v0.4 receipts) |

**Critical rule:** In canonical receipts, all 19 fields are ALWAYS present. Fields that have no value are serialized as `null`, NOT omitted. Omitting a null field produces a non-canonical representation and a different hash.

This is the key distinction from v0.3: `null` and absent are different bytes, different hashes, different semantics.

---

## 6. Unicode

### NFC normalization
- All string values are normalized to Unicode Normalization Form C (NFC) before serialization.
- Normalization is applied to the semantic value, not to the serialized JSON.
- Normalization happens before escaping.
- The canonical form of a string is: NFC(value) → escape → UTF-8 encode.

### What is normalized
- Field values (string-type fields)
- Enum values
- String elements in arrays (if any)
- NOT field names (field names are ASCII and already canonical)

### What is NOT normalized
- SHA-256 hex strings (already lowercase ASCII)
- Timestamps (already ASCII)
- Field names (ASCII schema identifiers)

---

## 7. Numbers

### No floating-point
- Floating-point values are PROHIBITED in canonical protocol objects.
- There is no compelling reason for floats in receipt metadata.
- If a future protocol version requires floats, a separate canonicalization specification must define exact IEEE 754 representation rules.

### Integer bounds
- Signed 64-bit range: -9,223,372,036,854,775,808 to 9,223,372,036,854,775,807.
- All v0.4 integer fields (sequence_number, artifact_byte_size, observed_byte_size) are non-negative.
- Byte sizes: 0 to 2^63 - 1.
- Sequence numbers: 1 to 2^63 - 1.

---

## 8. Timestamp Canonicalization

- UTC only. No timezone offsets.
- One exact representation: `YYYY-MM-DDTHH:MM:SS.sssZ`
- Milliseconds: always 3 digits (zero-padded).
- Seconds: always 2 digits.
- Date: `YYYY-MM-DD` (4-digit year, 2-digit month, 2-digit day).
- Time separator: `T` (uppercase).
- UTC suffix: `Z` (uppercase).
- No fractional seconds beyond milliseconds.
- No leap seconds (follow POSIX time: 23:59:60 does not appear).

---

## 9. Digest Construction

```
canonical_bytes(receipt)
        ↓
    SHA-256
        ↓
  receipt_hash
```

- Input: canonical UTF-8 byte sequence per this specification.
- Algorithm: SHA-256 (FIPS 180-4).
- Output: 64 lowercase hexadecimal characters, no prefix.

```
ReceiptHash(r) = SHA256(CanonicalSerialize(r))
```

---

## 10. Receipt Predecessor Verification

The chain is verified by recomputation, not by comparison to stored values.

```
resolve predecessor receipt (by receipt_id or sequence_number)
       ↓
obtain canonical predecessor bytes
       ↓
recompute SHA-256 (independently)
       ↓
compare against claimed previous_receipt_hash
       ↓
accept / reject
```

### Verification rule

```
receipt[n].previous_receipt_hash
    ==
SHA256(CanonicalSerialize(receipt[n-1]))
```

NOT:

```
receipt[n].previous_receipt_hash == stored_hash_from_receipt[n-1]
```

That distinction is exactly what v0.3 failed to enforce. The verifier must independently reconstruct and recompute, not trust a stored value.

### Genesis receipt

The first receipt in a chain has `previous_receipt_hash: null`. This is a semantic null (field present, value null), NOT an omitted field. The verifier recognizes null as "no predecessor" and does not attempt predecessor verification.

---

## 11. Schema/Version Binding

Every canonical receipt includes:
- `protocol_version`: identifies the protocol generation (e.g., `"v0.4"`)
- `schema_version`: identifies the receipt schema version (e.g., `"receipt-v1"`)

### Identity boundary on schema change

A serializer change MUST produce a detectable identity boundary:

- If the schema changes (field added, removed, reordered, type changed), `schema_version` MUST be incremented.
- Receipts with different `schema_version` values have different canonical forms.
- A receipt with `schema_version: "receipt-v1"` cannot be verified against a `schema_version: "receipt-v2"` predecessor.
- The verifier rejects schema version mismatches as chain verification failures.

This prevents silent hash changes when the serializer evolves. A v1 receipt hash is immutable; a v2 receipt is a different object with a different hash.

---

## 12. Golden Vectors

Three complete canonical Receipt examples with computed SHA-256 digests. These are the interoperability test targets. Any implementation must reproduce these exact digests.

### Golden Vector 1: Genesis PREPARE receipt

```json
{"protocol_version":"v0.4","schema_version":"receipt-v1","receipt_id":"r-000000000001","sequence_number":1,"receipt_type":"PREPARE","transaction_id":"txn-001","artifact_id":"art-L1-CORPUS-v2","artifact_location":"content-addressed:sha256/2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e1ef","artifact_byte_size":6327,"artifact_sha256":"2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e1ef","previous_receipt_hash":null,"base_receipt_hash":null,"custody_state":"UNVERIFIED","transaction_state":"STAGED","observed_sha256":null,"observed_byte_size":null,"timestamp":"2026-08-26T00:00:00.000Z","resolver_identity":null,"evidence_id":null}
```

**Canonical byte size:** 659 bytes
**SHA-256:** `e559c31411bd10f49360d17921222782ecd663fd110d33d9d4af20256dacda08`

### Golden Vector 2: COMMIT receipt (chains from GV1)

```json
{"protocol_version":"v0.4","schema_version":"receipt-v1","receipt_id":"r-000000000002","sequence_number":2,"receipt_type":"COMMIT","transaction_id":"txn-001","artifact_id":"art-L1-CORPUS-v2","artifact_location":"content-addressed:sha256/2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e1ef","artifact_byte_size":6327,"artifact_sha256":"2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e1ef","previous_receipt_hash":"e559c31411bd10f49360d17921222782ecd663fd110d33d9d4af20256dacda08","base_receipt_hash":"e559c31411bd10f49360d17921222782ecd663fd110d33d9d4af20256dacda08","custody_state":"VERIFIED","transaction_state":"COMMITTED","observed_sha256":"2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e1ef","observed_byte_size":6327,"timestamp":"2026-08-26T00:00:01.000Z","resolver_identity":"resolver-001","evidence_id":"ev-000000000001"}
```

**Canonical byte size:** 868 bytes
**SHA-256:** `84542189271d8c99dfa83c3623828dc77af17017f71597ca0efeb77b526858c5`

**Chain verification:** `previous_receipt_hash` == SHA-256(GV1) ✓

### Golden Vector 3: ABORT receipt (chains from GV2)

```json
{"protocol_version":"v0.4","schema_version":"receipt-v1","receipt_id":"r-000000000003","sequence_number":3,"receipt_type":"ABORT","transaction_id":"txn-002","artifact_id":"art-PROTOCOL-SPEC-v04","artifact_location":"filesystem:/workspace/v0.4_generation_specification.md","artifact_byte_size":0,"artifact_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","previous_receipt_hash":"84542189271d8c99dfa83c3623828dc77af17017f71597ca0efeb77b526858c5","base_receipt_hash":null,"custody_state":"FAILED","transaction_state":"ABORTED","observed_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","observed_byte_size":0,"timestamp":"2026-08-26T00:00:02.000Z","resolver_identity":"resolver-001","evidence_id":"ev-000000000002"}
```

**Canonical byte size:** 765 bytes
**SHA-256:** `b45863b86a5aeb2e333ac01be66d89ac86d5947bf82afa094ca7872f62925c9f`

**Chain verification:** `previous_receipt_hash` == SHA-256(GV2) ✓

### Chain summary

| Receipt | Type | SHA-256 | Predecessor match |
|---------|------|---------|-------------------|
| GV1 | PREPARE | `e559c314...` | null (genesis) |
| GV2 | COMMIT | `84542189...` | ✓ matches GV1 |
| GV3 | ABORT | `b45863b8...` | ✓ matches GV2 |

### Interoperability requirement

At least two independent implementations must reproduce these exact digests byte-for-byte. The golden vectors are part of the specification, not deferred to implementation.

---

## 13. Adversarial Acceptance Tests

All adversarial tests use GV1 as the canonical reference. Each test produces a different SHA-256 from GV1's canonical hash, confirming the canonicalization is strict.

| Test | Input | Expected hash match | Computed hash |
|------|-------|-------------------|---------------|
| ADV-1 | Fields in lexicographic order | ≠ GV1 | `a4f9c042...` |
| ADV-2 | Whitespace added between tokens | ≠ GV1 | `816ff2d0...` |
| ADV-3 | Timestamp without milliseconds (`T00:00:00Z`) | ≠ GV1 | `8f75cfc6...` |
| ADV-4 | Uppercase hex digest | ≠ GV1 | `8a4ec0d5...` |
| ADV-5 | Integer as string (`"1"` instead of `1`) | ≠ GV1 | `886c7fa5...` |
| ADV-6 | Null fields omitted instead of serialized | ≠ GV1 | `b3970d2c...` |
| ADV-7 | Single byte alteration in receipt | ≠ GV1 | `064f3862...` |

### Additional acceptance tests (protocol-level, not byte-level)

| Test | Description | Expected |
|------|-------------|----------|
| ADV-8 | Claimed hash without recoverable receipt bytes | UNESTABLISHED |
| ADV-9 | Stored hash used without independent recomputation | Insufficient evidence |
| ADV-10 | NFD string where GV uses NFC | Canonicalization must produce NFC result |
| ADV-11 | Schema version mismatch between linked receipts | Chain verification REJECTED |

---

## 14. Supersession of RFC 8785 JCS

The earlier project instruction mandated RFC 8785 JCS for canonical serialization. This specification supersedes that instruction for v0.4 protocol objects.

### Why v0.4 diverges from JCS

| Property | JCS (RFC 8785) | v0.4 (this spec) | Reason |
|----------|----------------|-------------------|--------|
| Field ordering | Lexicographic (UTF-16) | Schema-defined | Protocol semantics require fixed field order independent of name |
| Unicode | No normalization | NFC | Provenance strings may contain user-input text requiring normalization |
| Numbers | IEEE 754 double | Integer only | No floating-point in protocol objects |
| No whitespace | ✓ | ✓ | Aligned |
| UTF-8 output | ✓ | ✓ | Aligned |
| RFC 8785 escaping | ✓ | ✓ | Aligned |

### What v0.4 retains from JCS

- No insignificant whitespace
- UTF-8 encoding
- RFC 8785 string escaping
- No BOM
- Deterministic output

JCS may still be referenced for encoding-level rules that do not conflict with this specification. Where they conflict, this specification is authoritative for v0.4.

---

## 15. Architecture: Where the Serializer Sits

```
Persistent bytes → Resolver → Observation → Canonical interpretation → Independent recomputation → Verification → Custody promotion

                         ↕ (separate chain)

Canonical receipt bytes → independently recomputed digest → receipt-chain verification
```

The serializer is a component, not a trusted authority. It produces canonical bytes. The verifier independently reconstructs and recomputes. If they disagree, verification fails.

The serializer cannot:
- Promote custody state
- Skip the resolution pipeline
- Override the verifier
- Establish artifact identity
- Bind metadata to bytes

It can only:
- Produce a deterministic byte representation
- Enable hash computation
- Enable chain verification

---

## 16. Implementation Notes

### Serializer interface

```
CanonicalSerialize(receipt: Receipt) → bytes
ReceiptHash(receipt: Receipt) → string (64 hex chars)
VerifyChain(receipts: List[Receipt]) → ChainVerificationResult
```

### Verifier interface

```
VerifyReceiptHash(receipt: Receipt, claimed_hash: string) → bool
  // Reconstructs canonical bytes, computes SHA-256, compares

VerifyPredecessor(receipt: Receipt, predecessor: Receipt) → bool
  // Computes ReceiptHash(predecessor), compares to receipt.previous_receipt_hash
```

### Implementation order within P0

1. Define the canonical serializer (this spec)
2. Implement CanonicalSerialize for Receipt
3. Compute golden vector digests
4. Verify golden vectors against reference implementation (this document)
5. Second independent implementation reproduces golden vectors
6. Run adversarial test suite (ADV-1 through ADV-11)
7. Only then integrate with the resolver pipeline

---

*P0-CANONICAL-SERIALIZATION-SPEC-001. 2026-08-26. The serializer produces bytes. The verifier recomputes. The chain is established by independent computation, not by trust. INV-SERIAL-001 prevents the v0.3 placeholder hash failure from reappearing one layer lower.*
