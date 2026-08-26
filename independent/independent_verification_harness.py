"""
TSCP v0.4 — Independent Verification Harness
P0-INDEPENDENT-VERIFICATION-001

CRITICAL: This file does NOT import from resolver.py or canonical_serialization.py.
It reconstructs the canonical serialization, receipt hashing, and resolver logic
from the frozen P0 specification documents, not from the production implementation.

Independence model:
  P0 spec → implementation A (resolver.py) → golden vectors
  P0 spec → implementation B (this file) → golden vectors

NOT:
  implementation A → implementation B → same answer

If both implementations agree on GV1/GV2/GV3 digests and the three boundary
propositions, that is strong evidence the P0 specification is unambiguous and
the production implementation correctly satisfies it.
"""

import hashlib
import os
import struct
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ========================================
# INDEPENDENT CANONICAL SERIALIZATION
# ========================================
# Reconstructed from P0-CANONICAL-SERIALIZATION-SPEC-001
# Does NOT import from canonical_serialization.py

# Frozen receipt field order (from spec §2)
RECEIPT_FIELDS_V1 = [
    "protocol_version",
    "schema_version",
    "receipt_id",
    "sequence_number",
    "receipt_type",
    "transaction_id",
    "artifact_id",
    "artifact_location",
    "artifact_byte_size",
    "artifact_sha256",
    "previous_receipt_hash",
    "base_receipt_hash",
    "custody_state",
    "transaction_state",
    "observed_sha256",
    "observed_byte_size",
    "timestamp",
    "resolver_identity",
    "evidence_id",
]

# Valid enums (from spec §2)
VALID_RECEIPT_TYPES = {"PREPARE", "COMMIT", "ABORT", "CHECKPOINT"}
VALID_CUSTODY_STATES = {"UNVERIFIED", "OBSERVED", "VERIFIED", "FAILED", "FROZEN"}
VALID_TX_STATES = {"NONE", "STAGED", "COMMITTING", "COMMITTED", "ABORTED"}


def _nfc_normalize(text: str) -> str:
    """NFC normalization — reconstructed from spec §6."""
    import unicodedata
    return unicodedata.normalize('NFC', text)


def _json_escape(text: str) -> str:
    """
    RFC 8785 canonical string escaping (RFC 8259 §7 syntax).
    Reconstructed from spec §3 — NOT imported from production code.
    """
    text = _nfc_normalize(text)
    out = ['"']
    for ch in text:
        cp = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == '\\':
            out.append('\\\\')
        elif ch == '\n':
            out.append('\\n')
        elif ch == '\r':
            out.append('\\r')
        elif ch == '\t':
            out.append('\\t')
        elif ch == '\b':
            out.append('\\b')
        elif ch == '\f':
            out.append('\\f')
        elif cp < 0x20:
            out.append('\\u%04x' % cp)
        else:
            out.append(ch)
    out.append('"')
    return ''.join(out)


def _encode_value(val) -> str:
    """
    Encode a value to canonical JSON token.
    Reconstructed from spec §3 — independent implementation.
    """
    if val is None:
        return 'null'
    if isinstance(val, bool):
        return 'true' if val else 'false'
    if isinstance(val, int):
        # Spec §3: decimal, no leading zeros, no sign for non-negative
        if val < 0:
            return '-' + str(abs(val))
        return str(val)
    if isinstance(val, str):
        return _json_escape(val)
    if isinstance(val, list):
        return '[' + ','.join(_encode_value(v) for v in val) + ']'
    if isinstance(val, dict):
        return '{' + ','.join(
            _json_escape(k) + ':' + _encode_value(v) for k, v in val.items()
        ) + '}'
    raise TypeError("Unsupported type: %s" % type(val).__name__)


def canonical_receipt_bytes(receipt_dict: dict) -> bytes:
    """
    Serialize a receipt to canonical UTF-8 bytes.
    Reconstructed from P0-CANONICAL-SERIALIZATION-SPEC-001.
    
    Key rules:
    - Fields in schema-defined order (NOT lexicographic)
    - No whitespace
    - NFC normalization
    - All 19 fields always present (null = null, not omitted)
    - Integers: decimal, no leading zeros
    - Booleans: lowercase true/false
    - Strings: double-quoted, RFC 8785 escaping
    """
    parts = []
    for field_name in RECEIPT_FIELDS_V1:
        if field_name not in receipt_dict:
            raise ValueError("Missing required field: %s" % field_name)
        parts.append(
            _json_escape(field_name) + ':' + _encode_value(receipt_dict[field_name])
        )
    return ('{' + ','.join(parts) + '}').encode('utf-8')


def compute_receipt_digest(receipt_dict: dict) -> str:
    """
    Compute SHA-256 of canonical receipt bytes.
    Reconstructed from spec §9.
    Returns lowercase hex string (64 chars, no prefix).
    """
    return hashlib.sha256(canonical_receipt_bytes(receipt_dict)).hexdigest()


def verify_chain_link(receipt_n: dict, receipt_n_minus_1: dict) -> bool:
    """
    Verify that receipt_n.previous_receipt_hash == SHA256(CanonicalSerialize(receipt_n_minus_1)).
    Reconstructed from spec §10 — recomputes predecessor, does NOT trust stored value.
    """
    prev_claimed = receipt_n.get('previous_receipt_hash')
    if prev_claimed is None:
        return True  # Genesis receipt
    prev_computed = compute_receipt_digest(receipt_n_minus_1)
    return prev_claimed == prev_computed


# ========================================
# INDEPENDENT RESOLVER
# ========================================
# Reconstructed from P0-RESOLVER-SPEC-001 and P0-ARTIFACT-REFERENCE-SPEC-001
# Does NOT import from resolver.py

class ResStatus(Enum):
    RESOLVED = "RESOLVED"
    NOT_FOUND = "NOT_FOUND"
    ACCESS_DENIED = "ACCESS_DENIED"
    UNREADABLE = "UNREADABLE"
    READ_ERROR = "READ_ERROR"


class IdMatch(Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    NOT_APPLICABLE = "NOT_APPLICABLE"


# Authorized source kinds (from P0-ARTIFACT-REFERENCE-SPEC-001 §3)
AUTHORIZED_SOURCE_KINDS = {
    "FILESYSTEM",
    "OBJECT_STORE", 
    "CONTENT_ADDRESSED",
    "DEPLOYMENT_ADMITTED",
}

# Prohibited sources (from spec §3)
PROHIBITED_SOURCES = {
    "conversation_transcript",
    "model_context",
    "model_generated",
    "ephemeral_memory",
    "undocumented_sandbox",
    "search_result",
    "agent_assertion",
}


@dataclass
class IndArtifactRef:
    """Independent ArtifactRef — reconstructed from P0-ARTIFACT-REFERENCE-SPEC-001."""
    artifact_id: str
    declared_sha256: str
    declared_byte_size: int
    source_kind: str
    source_locator: str
    namespace: str
    resolver_policy: str
    reference_version: str


@dataclass
class IndResolutionResult:
    """Independent ResolutionResult — reconstructed from P0-RESOLVER-SPEC-001."""
    resolution_status: str
    observed_byte_size: Optional[int]
    observed_sha256: Optional[str]
    declared_sha256: str
    declared_byte_size: int
    identity_match: str
    resolved_location: Optional[str]
    evidence_id: str
    resolver_identity: str
    observed_at: str


class IndResolver:
    """
    Independent resolver — reconstructed from P0-RESOLVER-SPEC-001.
    
    CRITICAL: This resolver has NO promote(), verify(), or freeze() method.
    The resolver produces evidence only. Custody determination is external.
    """
    
    def __init__(self, resolver_identity="ind-resolver-002", authorized_root="/"):
        self.identity = resolver_identity
        self.root = os.path.realpath(authorized_root)
    
    def resolve(self, ref: IndArtifactRef) -> IndResolutionResult:
        """
        Resolve artifact reference to observed bytes.
        Returns IndResolutionResult — evidence only, never a custody verdict.
        """
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        evidence_id = "ev-ind-%s" % uuid.uuid4().hex[:12]
        
        # Check authorization (INV-REF-003)
        if ref.source_kind in PROHIBITED_SOURCES:
            return IndResolutionResult(
                resolution_status=ResStatus.ACCESS_DENIED.value,
                observed_byte_size=None,
                observed_sha256=None,
                declared_sha256=ref.declared_sha256,
                declared_byte_size=ref.declared_byte_size,
                identity_match=IdMatch.NOT_APPLICABLE.value,
                resolved_location=None,
                evidence_id=evidence_id,
                resolver_identity=self.identity,
                observed_at=timestamp,
            )
        
        if ref.source_kind not in AUTHORIZED_SOURCE_KINDS:
            return IndResolutionResult(
                resolution_status=ResStatus.ACCESS_DENIED.value,
                observed_byte_size=None,
                observed_sha256=None,
                declared_sha256=ref.declared_sha256,
                declared_byte_size=ref.declared_byte_size,
                identity_match=IdMatch.NOT_APPLICABLE.value,
                resolved_location=None,
                evidence_id=evidence_id,
                resolver_identity=self.identity,
                observed_at=timestamp,
            )
        
        # Check path traversal (INV-REF-001)
        if ".." in ref.source_locator:
            return IndResolutionResult(
                resolution_status=ResStatus.ACCESS_DENIED.value,
                observed_byte_size=None,
                observed_sha256=None,
                declared_sha256=ref.declared_sha256,
                declared_byte_size=ref.declared_byte_size,
                identity_match=IdMatch.NOT_APPLICABLE.value,
                resolved_location=None,
                evidence_id=evidence_id,
                resolver_identity=self.identity,
                observed_at=timestamp,
            )
        
        # Traverse source
        if ref.source_kind == "FILESYSTEM":
            return self._resolve_filesystem(ref, timestamp, evidence_id)
        else:
            return IndResolutionResult(
                resolution_status=ResStatus.NOT_FOUND.value,
                observed_byte_size=None,
                observed_sha256=None,
                declared_sha256=ref.declared_sha256,
                declared_byte_size=ref.declared_byte_size,
                identity_match=IdMatch.NOT_APPLICABLE.value,
                resolved_location=None,
                evidence_id=evidence_id,
                resolver_identity=self.identity,
                observed_at=timestamp,
            )
    
    def _resolve_filesystem(self, ref, timestamp, evidence_id):
        """Filesystem resolution — independent implementation."""
        loc = ref.source_locator
        if not loc.startswith("filesystem:"):
            return self._fail(ref, timestamp, evidence_id, ResStatus.ACCESS_DENIED)
        
        path = loc[len("filesystem:"):]
        if not os.path.isabs(path):
            return self._fail(ref, timestamp, evidence_id, ResStatus.ACCESS_DENIED)
        
        real_path = os.path.realpath(path)
        
        # Symlink check (REF-005)
        if not real_path.startswith(self.root):
            return self._fail(ref, timestamp, evidence_id, ResStatus.ACCESS_DENIED)
        
        # Existence check (REF-001)
        if not os.path.exists(real_path):
            return self._fail(ref, timestamp, evidence_id, ResStatus.NOT_FOUND)
        
        # Directory check (REF-004)
        if os.path.isdir(real_path):
            return self._fail(ref, timestamp, evidence_id, ResStatus.UNREADABLE)
        
        # Read bytes
        try:
            with open(real_path, 'rb') as fh:
                data = fh.read()
        except (PermissionError, IOError):
            return self._fail(ref, timestamp, evidence_id, ResStatus.READ_ERROR)
        
        # Compute identity independently
        observed_size = len(data)
        observed_hash = hashlib.sha256(data).hexdigest()
        
        # Compare (the L1 lesson: RESOLVED + MISMATCH ≠ NOT_FOUND)
        size_ok = (observed_size == ref.declared_byte_size)
        hash_ok = (observed_hash == ref.declared_sha256)
        
        match = IdMatch.MATCH if (size_ok and hash_ok) else IdMatch.MISMATCH
        
        return IndResolutionResult(
            resolution_status=ResStatus.RESOLVED.value,
            observed_byte_size=observed_size,
            observed_sha256=observed_hash,
            declared_sha256=ref.declared_sha256,
            declared_byte_size=ref.declared_byte_size,
            identity_match=match.value,
            resolved_location=real_path,
            evidence_id=evidence_id,
            resolver_identity=self.identity,
            observed_at=timestamp,
        )
    
    def _fail(self, ref, timestamp, evidence_id, status):
        return IndResolutionResult(
            resolution_status=status.value,
            observed_byte_size=None,
            observed_sha256=None,
            declared_sha256=ref.declared_sha256,
            declared_byte_size=ref.declared_byte_size,
            identity_match=IdMatch.NOT_APPLICABLE.value,
            resolved_location=None,
            evidence_id=evidence_id,
            resolver_identity=self.identity,
            observed_at=timestamp,
        )
    
    # NO promote() method
    # NO verify() method
    # NO freeze() method


class IndVerifier:
    """
    Independent epistemic layer — reconstructed from P0-RESOLVER-SPEC-001.
    Consumes evidence and makes custody determinations.
    """
    
    @staticmethod
    def evaluate(result: IndResolutionResult) -> str:
        if result.resolution_status == ResStatus.RESOLVED.value:
            if result.identity_match == IdMatch.MATCH.value:
                return "ELIGIBLE_FOR_VERIFIED"
            elif result.identity_match == IdMatch.MISMATCH.value:
                return "FAILED"
        return "UNVERIFIED"
    
    @staticmethod
    def can_promote(result: IndResolutionResult) -> bool:
        if result.resolution_status != ResStatus.RESOLVED.value:
            return False
        if result.identity_match != IdMatch.MATCH.value:
            return False
        if result.observed_sha256 is None:
            return False
        if result.observed_byte_size is None:
            return False
        if result.observed_sha256 != result.declared_sha256:
            return False
        if result.observed_byte_size != result.declared_byte_size:
            return False
        return True


# ========================================
# GOLDEN VECTORS (from P0-CANONICAL-SERIALIZATION-SPEC-001)
# ========================================
# Expected digests from the spec — the test targets

GV1_EXPECTED = "e559c31411bd10f49360d17921222782ecd663fd110d33d9d4af20256dacda08"
GV2_EXPECTED = "84542189271d8c99dfa83c3623828dc77af17017f71597ca0efeb77b526858c5"
GV3_EXPECTED = "b45863b86a5aeb2e333ac01be66d89ac86d5947bf82afa094ca7872f62925c9f"


def make_gv1():
    """Golden Vector 1: Genesis PREPARE receipt."""
    return {
        "protocol_version": "v0.4",
        "schema_version": "receipt-v1",
        "receipt_id": "r-000000000001",
        "sequence_number": 1,
        "receipt_type": "PREPARE",
        "transaction_id": "txn-001",
        "artifact_id": "art-L1-CORPUS-v2",
        "artifact_location": "content-addressed:sha256/2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e1ef",
        "artifact_byte_size": 6327,
        "artifact_sha256": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e1ef",
        "previous_receipt_hash": None,
        "base_receipt_hash": None,
        "custody_state": "UNVERIFIED",
        "transaction_state": "STAGED",
        "observed_sha256": None,
        "observed_byte_size": None,
        "timestamp": "2026-08-26T00:00:00.000Z",
        "resolver_identity": None,
        "evidence_id": None,
    }


def make_gv2():
    """Golden Vector 2: COMMIT receipt, chains from GV1."""
    return {
        "protocol_version": "v0.4",
        "schema_version": "receipt-v1",
        "receipt_id": "r-000000000002",
        "sequence_number": 2,
        "receipt_type": "COMMIT",
        "transaction_id": "txn-001",
        "artifact_id": "art-L1-CORPUS-v2",
        "artifact_location": "content-addressed:sha256/2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e1ef",
        "artifact_byte_size": 6327,
        "artifact_sha256": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e1ef",
        "previous_receipt_hash": GV1_EXPECTED,
        "base_receipt_hash": GV1_EXPECTED,
        "custody_state": "VERIFIED",
        "transaction_state": "COMMITTED",
        "observed_sha256": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e1ef",
        "observed_byte_size": 6327,
        "timestamp": "2026-08-26T00:00:01.000Z",
        "resolver_identity": "resolver-001",
        "evidence_id": "ev-000000000001",
    }


def make_gv3():
    """Golden Vector 3: ABORT receipt, chains from GV2."""
    return {
        "protocol_version": "v0.4",
        "schema_version": "receipt-v1",
        "receipt_id": "r-000000000003",
        "sequence_number": 3,
        "receipt_type": "ABORT",
        "transaction_id": "txn-002",
        "artifact_id": "art-PROTOCOL-SPEC-v04",
        "artifact_location": "filesystem:/workspace/v0.4_generation_specification.md",
        "artifact_byte_size": 0,
        "artifact_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "previous_receipt_hash": GV2_EXPECTED,
        "base_receipt_hash": None,
        "custody_state": "FAILED",
        "transaction_state": "ABORTED",
        "observed_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "observed_byte_size": 0,
        "timestamp": "2026-08-26T00:00:02.000Z",
        "resolver_identity": "resolver-001",
        "evidence_id": "ev-000000000002",
    }


# ========================================
# VERIFICATION TEST SUITE
# ========================================

SEP = "=" * 60
PASS_COUNT = 0
FAIL_COUNT = 0


def check(name, assertion, detail=""):
    global PASS_COUNT, FAIL_COUNT
    status = "PASS" if assertion else "FAIL"
    if assertion:
        PASS_COUNT += 1
    else:
        FAIL_COUNT += 1
    line = f"  [{status}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)


def test_golden_vectors():
    """Test 1: Independent reproduction of GV1/GV2/GV3."""
    print(f"\n{SEP}")
    print("Test 1: Golden Vector Reproduction (Independent Implementation)")
    print(SEP)
    
    gv1 = make_gv1()
    gv2 = make_gv2()
    gv3 = make_gv3()
    
    # GV1
    gv1_computed = compute_receipt_digest(gv1)
    print(f"\n  GV1 (Genesis PREPARE):")
    print(f"    Independent: {gv1_computed}")
    print(f"    Spec:        {GV1_EXPECTED}")
    check("GV1: independent digest matches spec", gv1_computed == GV1_EXPECTED)
    
    # GV2
    gv2_computed = compute_receipt_digest(gv2)
    print(f"\n  GV2 (COMMIT, chains from GV1):")
    print(f"    Independent: {gv2_computed}")
    print(f"    Spec:        {GV2_EXPECTED}")
    check("GV2: independent digest matches spec", gv2_computed == GV2_EXPECTED)
    
    # GV3
    gv3_computed = compute_receipt_digest(gv3)
    print(f"\n  GV3 (ABORT, chains from GV2):")
    print(f"    Independent: {gv3_computed}")
    print(f"    Spec:        {GV3_EXPECTED}")
    check("GV3: independent digest matches spec", gv3_computed == GV3_EXPECTED)
    
    # Chain verification (independent recomputation)
    print(f"\n  Chain verification:")
    check("GV2 chains from GV1 (independent recompute)",
        verify_chain_link(gv2, gv1))
    check("GV3 chains from GV2 (independent recompute)",
        verify_chain_link(gv3, gv2))
    check("GV1 genesis: previous_receipt_hash is None",
        gv1["previous_receipt_hash"] is None)


def test_canonical_bytes_properties():
    """Test 2: Canonical bytes have required properties."""
    print(f"\n{SEP}")
    print("Test 2: Canonical Bytes Properties")
    print(SEP)
    
    gv1 = make_gv1()
    gv1_bytes = canonical_receipt_bytes(gv1)
    gv1_str = gv1_bytes.decode('utf-8')
    
    check("No whitespace in canonical bytes",
        ' ' not in gv1_str and '\n' not in gv1_str and '\t' not in gv1_str)
    check("No BOM", not gv1_bytes.startswith(b'\xef\xbb\xbf'))
    check("Valid UTF-8", gv1_bytes.decode('utf-8') is not None)
    
    # All 19 fields present
    field_count = 0
    for field in RECEIPT_FIELDS_V1:
        if f'"{field}"' in gv1_str:
            field_count += 1
    check("All 19 fields present", field_count == 19)
    
    # Null fields are present as null, not omitted
    check("previous_receipt_hash is null (not omitted)",
        '"previous_receipt_hash":null' in gv1_str)
    check("observed_sha256 is null (not omitted)",
        '"observed_sha256":null' in gv1_str)
    
    # Schema-defined field order (check first field is protocol_version)
    first_field = '"protocol_version"'
    check("First field is protocol_version (schema order)",
        gv1_str.startswith('{' + first_field))
    
    # Last field is evidence_id
    check("Last field is evidence_id (schema order)",
        gv1_str.endswith(',"evidence_id":null}'))


def test_absence():
    """Test 3: ABSENCE — declared artifact, no bytes resolvable."""
    print(f"\n{SEP}")
    print("Test 3: ABSENCE (no bytes resolvable)")
    print(SEP)
    
    resolver = IndResolver(authorized_root='/tmp')
    
    ref = IndArtifactRef(
        artifact_id="art-ABSENCE-IND",
        declared_sha256="f510f4378e9ca377ccc96abc314cae888f4ea0eba0d466969474bca63495bd53",
        declared_byte_size=6327,
        source_kind="FILESYSTEM",
        source_locator="filesystem:/tmp/nonexistent/absence_test.json",
        namespace="v0.4",
        resolver_policy="STRICT",
        reference_version="ref-v1",
    )
    
    result = resolver.resolve(ref)
    verdict = IndVerifier.evaluate(result)
    
    check("absence: status is NOT_FOUND",
        result.resolution_status == ResStatus.NOT_FOUND.value)
    check("absence: identity_match is NOT_APPLICABLE",
        result.identity_match == IdMatch.NOT_APPLICABLE.value)
    check("absence: no observed_sha256",
        result.observed_sha256 is None)
    check("absence: verdict is UNVERIFIED",
        verdict == "UNVERIFIED")
    check("absence: promotion NOT permitted",
        not IndVerifier.can_promote(result))


def test_contradiction():
    """Test 4: CONTRADICTION — bytes found, identity mismatch (L1 binding)."""
    print(f"\n{SEP}")
    print("Test 4: CONTRADICTION (wrong bytes, L1 binding failure)")
    print(SEP)
    
    import tempfile
    content = b'{"test": "wrong content for independent contradiction test"}'
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, dir='/tmp') as f:
        f.write(content)
        path = f.name
    
    try:
        resolver = IndResolver(authorized_root='/tmp')
        wrong_hash = "a644f6bd3b3bca51b3170dad126a3e059e645f46cb0b5bf6aea227d61b827420"
        
        ref = IndArtifactRef(
            artifact_id="art-CONTRADICTION-IND",
            declared_sha256=wrong_hash,
            declared_byte_size=40,
            source_kind="FILESYSTEM",
            source_locator=f"filesystem:{path}",
            namespace="v0.4",
            resolver_policy="STRICT",
            reference_version="ref-v1",
        )
        
        result = resolver.resolve(ref)
        verdict = IndVerifier.evaluate(result)
        
        check("contradiction: status is RESOLVED (bytes exist)",
            result.resolution_status == ResStatus.RESOLVED.value)
        check("contradiction: observed_sha256 is computed",
            result.observed_sha256 is not None)
        check("contradiction: observed_sha256 != declared_sha256",
            result.observed_sha256 != result.declared_sha256)
        check("contradiction: identity_match is MISMATCH",
            result.identity_match == IdMatch.MISMATCH.value)
        check("contradiction: verdict is FAILED (not UNVERIFIED)",
            verdict == "FAILED")
        check("contradiction: promotion NOT permitted",
            not IndVerifier.can_promote(result))
        check("contradiction: RESOLVED + MISMATCH != NOT_FOUND",
            result.resolution_status == ResStatus.RESOLVED.value
            and result.identity_match == IdMatch.MISMATCH.value)
    finally:
        os.unlink(path)


def test_confirmation():
    """Test 5: CONFIRMATION — bytes found, identity match."""
    print(f"\n{SEP}")
    print("Test 5: CONFIRMATION (correct bytes, identity match)")
    print(SEP)
    
    import tempfile
    content = b'{"test": "correct content for independent confirmation test"}'
    actual_hash = hashlib.sha256(content).hexdigest()
    actual_size = len(content)
    
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, dir='/tmp') as f:
        f.write(content)
        path = f.name
    
    try:
        resolver = IndResolver(authorized_root='/tmp')
        
        ref = IndArtifactRef(
            artifact_id="art-CONFIRMATION-IND",
            declared_sha256=actual_hash,
            declared_byte_size=actual_size,
            source_kind="FILESYSTEM",
            source_locator=f"filesystem:{path}",
            namespace="v0.4",
            resolver_policy="STRICT",
            reference_version="ref-v1",
        )
        
        result = resolver.resolve(ref)
        verdict = IndVerifier.evaluate(result)
        
        check("confirmation: status is RESOLVED",
            result.resolution_status == ResStatus.RESOLVED.value)
        check("confirmation: observed_sha256 matches declared",
            result.observed_sha256 == result.declared_sha256)
        check("confirmation: observed_byte_size matches declared",
            result.observed_byte_size == result.declared_byte_size)
        check("confirmation: identity_match is MATCH",
            result.identity_match == IdMatch.MATCH.value)
        check("confirmation: verdict is ELIGIBLE_FOR_VERIFIED",
            verdict == "ELIGIBLE_FOR_VERIFIED")
        check("confirmation: promotion IS permitted",
            IndVerifier.can_promote(result))
    finally:
        os.unlink(path)


def test_prohibited_sources():
    """Test 6: Prohibited source kinds rejected before resolution."""
    print(f"\n{SEP}")
    print("Test 6: Prohibited Source Kinds")
    print(SEP)
    
    resolver = IndResolver(authorized_root='/tmp')
    
    prohibited = [
        ("conversation_transcript", "conversation:session-1"),
        ("model_context", "model:context-1"),
        ("model_generated", "model:generated-1"),
        ("ephemeral_memory", "memory:0x7fff"),
        ("search_result", "search:query-1"),
        ("agent_assertion", "agent:says-exists"),
    ]
    
    for source_kind, locator in prohibited:
        ref = IndArtifactRef(
            artifact_id="art-PROHIBITED",
            declared_sha256="0a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f6789",
            declared_byte_size=100,
            source_kind=source_kind,
            source_locator=locator,
            namespace="v0.4",
            resolver_policy="STRICT",
            reference_version="ref-v1",
        )
        result = resolver.resolve(ref)
        check(f"prohibited: {source_kind} -> ACCESS_DENIED",
            result.resolution_status == ResStatus.ACCESS_DENIED.value)
        check(f"prohibited: {source_kind} -> no promotion",
            not IndVerifier.can_promote(result))


def test_resolver_authority_boundary():
    """Test 7: Resolver has no custody/promotion operation exposed."""
    print(f"\n{SEP}")
    print("Test 7: Resolver Authority Boundary (Structural Test)")
    print(SEP)
    
    resolver = IndResolver(authorized_root='/tmp')
    
    # Check that the resolver class has NO promote/verify/freeze methods
    resolver_methods = [m for m in dir(resolver) if not m.startswith('_') and callable(getattr(resolver, m))]
    
    check("resolver has NO promote() method",
        not hasattr(resolver, 'promote'))
    check("resolver has NO verify() method",
        not hasattr(resolver, 'verify'))
    check("resolver has NO freeze() method",
        not hasattr(resolver, 'freeze'))
    check("resolver has NO set_custody() method",
        not hasattr(resolver, 'set_custody'))
    check("resolver has NO set_verified() method",
        not hasattr(resolver, 'set_verified'))
    
    # Verify that resolve() returns evidence, not a custody state
    ref = IndArtifactRef(
        artifact_id="art-AUTHORITY-TEST",
        declared_sha256="0a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f6789",
        declared_byte_size=100,
        source_kind="FILESYSTEM",
        source_locator="filesystem:/tmp/nonexistent_authority_test.bin",
        namespace="v0.4",
        resolver_policy="STRICT",
        reference_version="ref-v1",
    )
    result = resolver.resolve(ref)
    
    check("resolve() returns IndResolutionResult (not custody state)",
        isinstance(result, IndResolutionResult))
    check("result has no custody_state field",
        not hasattr(result, 'custody_state'))
    check("result has no verified field",
        not hasattr(result, 'verified'))
    check("result has no frozen field",
        not hasattr(result, 'frozen'))


def test_implementation_independence():
    """Test 8: Verify this harness does not import production code."""
    print(f"\n{SEP}")
    print("Test 8: Implementation Independence")
    print(SEP)
    
    # Check that production modules are NOT imported
    import sys
    production_modules = ['resolver', 'canonical_serialization']
    found_production = []
    for mod in production_modules:
        if mod in sys.modules:
            # Check if it was imported by this file (not by other test infrastructure)
            found_production.append(mod)
    
    check("production resolver.py NOT imported",
        'resolver' not in sys.modules or 'resolver' not in [m for m in sys.modules if 'test' not in sys.modules.get(m, {}).__name__ if hasattr(sys.modules.get(m), '__name__')])
    
    check("production canonical_serialization.py NOT imported",
        'canonical_serialization' not in sys.modules)
    
    # Verify this file defines its own serialization
    check("this file defines canonical_receipt_bytes()",
        'canonical_receipt_bytes' in globals())
    check("this file defines compute_receipt_digest()",
        'compute_receipt_digest' in globals())
    check("this file defines IndResolver class",
        'IndResolver' in globals())
    check("this file defines IndVerifier class",
        'IndVerifier' in globals())


def test_negative_space():
    """Test 9: Failed resolution states cannot cross into custody eligibility."""
    print(f"\n{SEP}")
    print("Test 9: Negative Space — Failed States Cannot Reach Custody")
    print(SEP)
    
    resolver = IndResolver(authorized_root='/tmp')
    
    # NOT_FOUND
    ref_nf = IndArtifactRef(
        artifact_id="art-NEG-NF",
        declared_sha256="0a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f6789",
        declared_byte_size=100,
        source_kind="FILESYSTEM",
        source_locator="filesystem:/tmp/negative_not_found.bin",
        namespace="v0.4",
        resolver_policy="STRICT",
        reference_version="ref-v1",
    )
    res_nf = resolver.resolve(ref_nf)
    check("NOT_FOUND: cannot promote",
        not IndVerifier.can_promote(res_nf))
    check("NOT_FOUND: verdict is UNVERIFIED",
        IndVerifier.evaluate(res_nf) == "UNVERIFIED")
    
    # ACCESS_DENIED (prohibited source)
    ref_ad = IndArtifactRef(
        artifact_id="art-NEG-AD",
        declared_sha256="0a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f6789",
        declared_byte_size=100,
        source_kind="conversation_transcript",
        source_locator="conversation:abc",
        namespace="v0.4",
        resolver_policy="STRICT",
        reference_version="ref-v1",
    )
    res_ad = resolver.resolve(ref_ad)
    check("ACCESS_DENIED: cannot promote",
        not IndVerifier.can_promote(res_ad))
    check("ACCESS_DENIED: verdict is UNVERIFIED",
        IndVerifier.evaluate(res_ad) == "UNVERIFIED")
    
    # MISMATCH
    import tempfile
    content = b'{"data": "mismatch negative space test"}'
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, dir='/tmp') as f:
        f.write(content)
        path = f.name
    ref_mm = IndArtifactRef(
        artifact_id="art-NEG-MM",
        declared_sha256="0a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f6789",
        declared_byte_size=100,
        source_kind="FILESYSTEM",
        source_locator=f"filesystem:{path}",
        namespace="v0.4",
        resolver_policy="STRICT",
        reference_version="ref-v1",
    )
    res_mm = resolver.resolve(ref_mm)
    check("MISMATCH: cannot promote",
        not IndVerifier.can_promote(res_mm))
    check("MISMATCH: verdict is FAILED",
        IndVerifier.evaluate(res_mm) == "FAILED")
    os.unlink(path)
    
    # Size-only mismatch (correct hash field but wrong declared size)
    content2 = b'{"data": "size mismatch negative"}'
    hash2 = hashlib.sha256(content2).hexdigest()
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, dir='/tmp') as f:
        f.write(content2)
        path2 = f.name
    ref_sm = IndArtifactRef(
        artifact_id="art-NEG-SM",
        declared_sha256=hash2,
        declared_byte_size=len(content2) + 50,  # wrong size
        source_kind="FILESYSTEM",
        source_locator=f"filesystem:{path2}",
        namespace="v0.4",
        resolver_policy="STRICT",
        reference_version="ref-v1",
    )
    res_sm = resolver.resolve(ref_sm)
    check("SIZE_MISMATCH: cannot promote",
        not IndVerifier.can_promote(res_sm))
    check("SIZE_MISMATCH: identity_match is MISMATCH",
        res_sm.identity_match == IdMatch.MISMATCH.value)
    os.unlink(path2)


# ========================================
# MAIN
# ========================================

def main():
    print("TSCP v0.4 — P0 Independent Verification Harness")
    print("P0-INDEPENDENT-VERIFICATION-001")
    print(SEP)
    print()
    print("Independence model:")
    print("  P0 spec -> implementation A (resolver.py) -> golden vectors")
    print("  P0 spec -> implementation B (this file) -> golden vectors")
    print()
    print("This harness does NOT import from resolver.py or canonical_serialization.py.")
    print("All serialization, hashing, and resolver logic is independently reconstructed")
    print("from the frozen P0 specification documents.")
    
    test_golden_vectors()
    test_canonical_bytes_properties()
    test_absence()
    test_contradiction()
    test_confirmation()
    test_prohibited_sources()
    test_resolver_authority_boundary()
    test_implementation_independence()
    test_negative_space()
    
    print(f"\n{SEP}")
    print("INDEPENDENT VERIFICATION SUMMARY")
    print(SEP)
    print(f"  Passed: {PASS_COUNT}")
    print(f"  Failed: {FAIL_COUNT}")
    print(f"  Total:  {PASS_COUNT + FAIL_COUNT}")
    
    if FAIL_COUNT == 0:
        print()
        print("ALL INDEPENDENT TESTS PASSED")
        print()
        print("Three gates satisfied:")
        print()
        print("  1. Functional equivalence:")
        print("     Independent implementation reproduces GV1/GV2/GV3 digests")
        print("     and the three boundary propositions (absence, contradiction, confirmation).")
        print()
        print("  2. Negative-space equivalence:")
        print("     Prohibited source kinds and failed resolution states")
        print("     cannot cross into custody eligibility.")
        print()
        print("  3. Implementation independence:")
        print("     This harness does NOT import or call production resolver code.")
        print("     Serialization and hashing are independently reconstructed from the spec.")
        print()
        print("  v0.4 P0 baseline is justified.")
        print("  P1/P2 can build on an independently corroborated P0.")
    else:
        print()
        print("INDEPENDENT VERIFICATION FAILED — discrepancies detected")
        print("The P0 specification or production implementation needs review.")
    
    return FAIL_COUNT == 0


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
