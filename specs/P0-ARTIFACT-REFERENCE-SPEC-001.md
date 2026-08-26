# P0-ARTIFACT-REFERENCE-SPEC-001 — Artifact Reference and Address Model

**Date:** 2026-08-26
**Source:** Aria (via Sean), Solas
**Status:** DESIGN — pre-implementation
**Parent:** P0-RESOLVER-SPEC-001, Workspace Protocol v0.4 Generation Specification
**Depends on:** P0-CANONICAL-SERIALIZATION-SPEC-001 (for receipt/identity serialization)

---

## Central Question

> Given an artifact reference, what exact persistent byte source is the resolver authorized to traverse?

This spec answers that question by distinguishing three things that v0.3 conflated:

1. **Identity** — what the artifact IS (its byte identity)
2. **Location** — where bytes may be FOUND (a path/URI)
3. **Resolution authority** — whether the resolver is PERMITTED to traverse that location

---

## 1. ArtifactRef Structure

```
ArtifactRef
├── artifact_id           string — unique identifier within namespace
├── declared_sha256        string (64 hex chars) — claimed byte identity
├── declared_byte_size     integer — claimed byte count
├── source_kind            enum — class of storage (see §3)
├── source_locator         string — addressable location within source_kind
├── namespace              string — provenance namespace (e.g., "v0.4")
├── resolver_policy        enum — resolution behavior (see §6)
└── reference_version      string — schema version of this reference (e.g., "ref-v1")
```

All fields are required. No field is optional. No field may be null.

The `declared_sha256` and `declared_byte_size` are **claims**. They are not verified identity. The resolver independently computes observed values and compares.

---

## 2. Critical Invariants

### INV-REF-001 — Reference Determinacy

> An artifact reference must identify one deterministic authorized resolution target. Ambiguous locations, fuzzy searches, semantic lookup, and "latest version" references cannot establish byte identity.

Consequences:
- A reference points to exactly one location within one source kind.
- "Latest version" references are prohibited. Every reference is pinned to specific bytes.
- A reference that could resolve to different bytes at different times is non-deterministic and cannot establish byte identity.
- A reference that could resolve to different bytes depending on resolver state is non-deterministic and cannot establish byte identity.

### INV-REF-002 — Location ≠ Identity

> A path or URI tells the resolver where to look. It does not establish what the artifact is.

The resolution chain is:
```
location → bytes → SHA-256 → identity verification
```

Never:
```
location → identity
```

A file at `/workspace/artifact.bin` with hash `X` is not "artifact `X`" by virtue of being at that path. It is artifact `X` only because its independently computed SHA-256 equals `X`.

### INV-REF-003 — Authorized Source Boundary

> An artifact location is evidence about where bytes may be found; it is never evidence that the bytes at that location possess the declared artifact identity.

The resolver may only traverse locations within explicitly authorized source classes. Finding bytes at an unauthorized location does not establish byte identity, even if those bytes happen to match the declared hash.

---

## 3. Authorized Source Classes

### Allowed (with explicit registration)

| Source Kind | `source_kind` value | Description |
|-------------|---------------------|-------------|
| Persistent workspace filesystem | `FILESYSTEM` | Files in a persistent, addressable workspace directory |
| Registered object store | `OBJECT_STORE` | Explicitly registered blob/object store with content addressing |
| Registered content-addressed store | `CONTENT_ADDRESSED` | Store where location IS the hash (e.g., `sha256/...`) |
| Deployment-admitted source | `DEPLOYMENT_ADMITTED` | Other sources explicitly admitted by v0.4 deployment policy |

Each authorized source must be explicitly registered in the deployment configuration. Registration is not automatic.

### Prohibited

| Source | Why |
|--------|-----|
| Conversation transcripts | Not persistent; not byte-addressable |
| Model context / model memory | Ephemeral; not independently verifiable |
| Model-generated reconstruction | Not original bytes; reconstruction ≠ artifact |
| Ephemeral process memory | Not persistent across sessions |
| Undocumented sandbox locations | Not in authorized source list |
| Search results | Ambiguous; not deterministic |
| "The agent says it exists" | Assertion is not resolution |

A resolver encountering bytes at a prohibited source MUST reject resolution, regardless of whether the bytes match the declared hash.

---

## 4. Reference Immutability

### Once used for a custody claim, a reference is frozen.

If:
```
Artifact A
  ref → path X
  observed hash → H1
  custody state → VERIFIED or FROZEN
```

Then path X later changes:
```
path X now contains bytes with hash H2
```

**The old artifact identity does NOT follow the path.**

Instead:
```
Artifact A remains: hash H1, custody state VERIFIED/FROZEN (historical)
Path X now resolves to: hash H2 (different artifact)
```

A new artifact (A' or version 2) must be registered for the new bytes. The old artifact's identity is preserved by its historical observation, not by re-reading the path.

This prevents mutable paths from becoming accidental identity aliases. A path is a resolution target at a point in time, not a permanent identity.

### Implementation consequence

The resolver does NOT mutate the ArtifactRef. Resolution produces a ResolutionResult — a separate evidence object. The reference remains as declared; the observation is recorded separately.

---

## 5. Resolution Produces Observation, Not Mutation

The clean sequence:
```
ArtifactRef
    ↓
Resolver
    ↓
ResolutionResult
    ↓
ObservedBytes
    ↓
SHA-256
    ↓
IdentityComparison
    ↓
Verification
```

### RESOLVED + IDENTITY_MISMATCH ≠ NOT_FOUND

This distinction is critical. It is the direct lesson from the L1 binding incident.

When the resolver finds bytes at an authorized location but those bytes do not match the declared identity:
```
RESOLVED
  observed_sha256 = H_WRONG
  declared_sha256 = H_EXPECTED
  identity_match = false
```

This is **NOT** `NOT_FOUND`. The bytes existed and were observed. The identity claim failed. Those are epistemically different failure modes:

| Outcome | Meaning | Custody Result |
|---------|---------|----------------|
| NOT_FOUND | No bytes at the location | UNVERIFIED — cannot establish |
| RESOLVED + MISMATCH | Bytes exist but identity differs | FAILED — identity contradicted |
| RESOLVED + MATCH | Bytes exist and identity matches | Eligible for VERIFIED |

"I found something" and "I found the artifact you claimed" are not equivalent propositions. v0.3 treated them as equivalent. v0.4 does not.

---

## 6. Resolver Policy

The `resolver_policy` field controls resolution behavior:

| Policy | Value | Behavior |
|--------|-------|----------|
| Strict | `STRICT` | Resolve exactly the declared source_locator. No fallback. No search. |
| Multi-source | `MULTI_SOURCE` | Resolve from a declared ordered list of sources. First RESOLVED wins. All sources must be authorized. |
| Content-addressed | `CONTENT_ADDRESSED` | Resolve from the hash itself (source_locator encodes the hash). Location IS the identity claim. |

### Default policy

The default resolver policy is `STRICT`. An artifact reference points to exactly one location. Multi-source resolution is opt-in and must declare all sources in advance.

### Content-addressed resolution

When `resolver_policy = CONTENT_ADDRESSED`:
- The `source_locator` contains the hash itself (e.g., `sha256/abc123...`).
- The resolver retrieves bytes from a content-addressed store keyed by that hash.
- The resolver STILL computes SHA-256 of the retrieved bytes and compares.
- Content-addressing is a storage optimization, not a verification shortcut. The resolver never trusts the address as identity — it always recomputes.

---

## 7. Namespace Isolation

Every ArtifactRef belongs to a namespace. Namespaces prevent cross-generation provenance contamination.

| Namespace | Purpose |
|-----------|---------|
| `v0.4` | v0.4 fresh provenance generation |
| `v0.3` | v0.3 historical record (CONTRADICTED — read-only) |
| `v0.2` | v0.2 historical record (frozen — read-only) |

An artifact in namespace `v0.4` cannot inherit provenance from namespace `v0.3` merely because it has the same content. Same bytes in different namespaces = different provenance.

This is the generation boundary made concrete at the reference level.

---

## 8. Source Locator Format

The `source_locator` is a string that addresses bytes within the declared `source_kind`.

| Source Kind | Locator Format | Example |
|-------------|---------------|---------|
| FILESYSTEM | `filesystem:<absolute_path>` | `filesystem:/workspace/artifacts/corpus.json` |
| OBJECT_STORE | `objectstore:<store_id>:<key>` | `objectstore:primary:artifacts/corpus_v2.json` |
| CONTENT_ADDRESSED | `contentaddr:<store_id>:sha256:<hash>` | `contentaddr:cas:sha256:2c26b46b...` |
| DEPLOYMENT_ADMITTED | `<custom_scheme>:<locator>` | Defined per deployment |

Rules:
- Locators must be absolute, not relative. No `../` traversal.
- Locators must identify a file, not a directory.
- Locators must not contain shell metacharacters.
- Locators must be ASCII.
- Locators are case-sensitive.

---

## 9. Adversarial Test Suite: REF-001 through REF-012

| Test | Attack | Expected Result |
|------|--------|-----------------|
| REF-001 | Nonexistent path | NOT_FOUND |
| REF-002 | Path resolves to wrong bytes | RESOLVED + IDENTITY_MISMATCH |
| REF-003 | Path replaced after registration | Old identity remains distinct; new bytes = new artifact |
| REF-004 | Directory supplied where file expected | REJECT (not a byte source) |
| REF-005 | Symlink escapes authorized root | REJECT (unauthorized location) |
| REF-006 | Relative-path traversal `../` | REJECT (path must be absolute) |
| REF-007 | Ambiguous URI | REJECT (determinacy violation) |
| REF-008 | Conversation-only artifact | REJECT (prohibited source) |
| REF-009 | Ephemeral memory reference | REJECT (prohibited source) |
| REF-010 | Same bytes at two authorized locations | Same byte identity, distinct provenance locations |
| REF-011 | Same path, different bytes (at different times) | Different identities |
| REF-012 | Declared size differs from observed size | REJECT promotion (size mismatch) |

### Key Test Details

**REF-002: Path resolves to wrong bytes (the L1 incident)**
```
Input:
    ArtifactRef:
        declared_sha256 = A644...
        source_locator = filesystem:/workspace/L1_CORPUS_v1.json
    File at location:
        actual_sha256 = F52F...

Expected:
    Resolution: RESOLVED
    observed_sha256 = F52F...
    declared_sha256 = A644...
    identity_match = false
    Custody: FAILED (not UNVERIFIED)
    "I found something" ≠ "I found the artifact you claimed"
```

**REF-003: Path replaced after registration**
```
Input:
    Artifact A registered with:
        ref → filesystem:/workspace/artifact.bin
        observed hash → H1
        custody → VERIFIED
    Path later contains bytes with hash H2

Expected:
    Artifact A remains: hash H1, custody VERIFIED (historical observation preserved)
    New observation at same path: hash H2 (different artifact, requires new registration)
    Old identity does NOT follow the path
```

**REF-010: Same bytes at two authorized locations**
```
Input:
    Location A: filesystem:/workspace/copy1.json → hash X
    Location B: filesystem:/workspace/copy2.json → hash X
    Both locations authorized

Expected:
    Byte identity: SAME (hash X at both)
    Provenance: DISTINCT (two separate resolution events, two separate locations)
    Same byte identity ≠ same provenance
```

---

## 10. Relationship to Other P0 Components

```
P0-CANONICAL-SERIALIZATION-SPEC-001
    ↓ (defines how artifacts are serialized and hashed)
P0-ARTIFACT-REFERENCE-SPEC-001 (this spec)
    ↓ (defines how artifacts are located and authorized)
P0-RESOLVER-SPEC-001
    ↓ (defines how resolution is executed and evidence is produced)
V04-CUSTODY-001
    ↓ (acceptance tests for the full custody pipeline)
```

The resolver implementation (P0-RESOLVER-IMPLEMENTATION-001) can now be written against a frozen reference contract rather than inventing addressing semantics while implementing.

---

## 11. What This Spec Prevents

| v0.3 Failure | v0.4 Prevention |
|---------------|-----------------|
| Conversation claim treated as artifact existence | INV-REF-003: conversation is a prohibited source |
| Path treated as identity | INV-REF-002: location ≠ identity |
| Mutable path treated as stable identity | §4: reference immutability after custody claim |
| "Found something" treated as "found the claimed artifact" | §5: RESOLVED + MISMATCH ≠ NOT_FOUND |
| Binding hash mismatch treated as stale metadata | REF-002: mismatch = FAILED, not repaired |
| "Latest version" treated as deterministic | INV-REF-001: references must be pinned |
| Cross-generation provenance inheritance | §7: namespace isolation |
| Unauthorized location accepted if bytes match | INV-REF-003: authorized source boundary |

---

*P0-ARTIFACT-REFERENCE-SPEC-001. 2026-08-26. A location tells the resolver where to look. Only independently computed bytes tell it what it found. The reference is a claim; the resolution is evidence; the comparison is verification. These are three different acts, and v0.4 treats them as three different acts.*
