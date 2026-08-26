"""
TSCP v0.4 — Canonical Receipt Serialization
Implementation of P0-CANONICAL-SERIALIZATION-SPEC-001

Serializes Receipt objects to deterministic UTF-8 byte sequences
and computes SHA-256 digests for receipt-chain verification.
"""

import hashlib
import unicodedata
from dataclasses import dataclass, field, asdict
from typing import Optional

# ========================================
# Receipt Schema (frozen field order)
# ========================================
RECEIPT_FIELDS = [
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

# Valid enum values
RECEIPT_TYPES = {"PREPARE", "COMMIT", "ABORT", "CHECKPOINT"}
CUSTODY_STATES = {"UNVERIFIED", "OBSERVED", "VERIFIED", "FAILED", "FROZEN"}
TRANSACTION_STATES = {"NONE", "STAGED", "COMMITTING", "COMMITTED", "ABORTED"}


@dataclass
class Receipt:
    """v0.4 canonical receipt object."""
    protocol_version: str
    schema_version: str
    receipt_id: str
    sequence_number: int
    receipt_type: str
    transaction_id: str
    artifact_id: str
    artifact_location: str
    artifact_byte_size: int
    artifact_sha256: str
    previous_receipt_hash: Optional[str]
    base_receipt_hash: Optional[str]
    custody_state: str
    transaction_state: str
    observed_sha256: Optional[str]
    observed_byte_size: Optional[int]
    timestamp: str
    resolver_identity: Optional[str]
    evidence_id: Optional[str]

    def __post_init__(self):
        # Validate enums
        if self.receipt_type not in RECEIPT_TYPES:
            raise ValueError(f"Invalid receipt_type: {self.receipt_type}")
        if self.custody_state not in CUSTODY_STATES:
            raise ValueError(f"Invalid custody_state: {self.custody_state}")
        if self.transaction_state not in TRANSACTION_STATES:
            raise ValueError(f"Invalid transaction_state: {self.transaction_state}")
        # Validate SHA-256 fields if not None
        for name, val in [("artifact_sha256", self.artifact_sha256),
                          ("previous_receipt_hash", self.previous_receipt_hash),
                          ("base_receipt_hash", self.base_receipt_hash),
                          ("observed_sha256", self.observed_sha256)]:
            if val is not None:
                if len(val) != 64 or not all(c in '0123456789abcdef' for c in val):
                    raise ValueError(f"Invalid SHA-256 format for {name}: {val}")


def _nfc(s: str) -> str:
    """Unicode NFC normalization."""
    return unicodedata.normalize('NFC', s)


def _escape_string(s: str) -> str:
    """RFC 8785 canonical string escaping (RFC 8259 §7 syntax) with NFC normalization."""
    s = _nfc(s)
    result = ['"']
    for ch in s:
        if ch == '"':
            result.append('\\"')
        elif ch == '\\':
            result.append('\\\\')
        elif ch == '\n':
            result.append('\\n')
        elif ch == '\r':
            result.append('\\r')
        elif ch == '\t':
            result.append('\\t')
        elif ch == '\b':
            result.append('\\b')
        elif ch == '\f':
            result.append('\\f')
        elif ord(ch) < 0x20:
            result.append(f'\\u{ord(ch):04x}')
        else:
            result.append(ch)
    result.append('"')
    return ''.join(result)


def _canonical_value(v) -> str:
    """Produce canonical JSON token for a value."""
    if v is None:
        return 'null'
    elif v is True:
        return 'true'
    elif v is False:
        return 'false'
    elif isinstance(v, int):
        if v < 0:
            return str(v)
        if v == 0:
            return '0'
        return str(v)
    elif isinstance(v, str):
        return _escape_string(v)
    elif isinstance(v, list):
        return '[' + ','.join(_canonical_value(e) for e in v) + ']'
    elif isinstance(v, dict):
        items = []
        for k, val in v.items():
            items.append(_escape_string(k) + ':' + _canonical_value(val))
        return '{' + ','.join(items) + '}'
    else:
        raise TypeError(f"Unsupported type for canonical serialization: {type(v)}")


def canonical_serialize_receipt(receipt: Receipt) -> bytes:
    """
    Serialize a Receipt to canonical UTF-8 bytes.
    
    Fields are in schema-defined order (NOT lexicographic).
    No whitespace. NFC normalization. All fields present (null = null, not omitted).
    """
    d = asdict(receipt)
    parts = []
    for field_name in RECEIPT_FIELDS:
        if field_name not in d:
            raise ValueError(f"Missing required field: {field_name}")
        parts.append(_escape_string(field_name) + ':' + _canonical_value(d[field_name]))
    return ('{' + ','.join(parts) + '}').encode('utf-8')


def receipt_hash(receipt: Receipt) -> str:
    """
    Compute SHA-256 of canonical receipt bytes.
    Returns lowercase hex string (64 chars, no prefix).
    """
    canonical_bytes = canonical_serialize_receipt(receipt)
    return hashlib.sha256(canonical_bytes).hexdigest()


def verify_receipt_hash(receipt: Receipt, claimed_hash: str) -> bool:
    """
    Reconstruct canonical bytes, compute SHA-256, compare to claimed hash.
    INV-SERIAL-001: No receipt hash accepted without independent recomputation.
    """
    computed = receipt_hash(receipt)
    return computed == claimed_hash


def verify_predecessor(receipt: Receipt, predecessor: Receipt) -> bool:
    """
    Verify that receipt.previous_receipt_hash == SHA256(CanonicalSerialize(predecessor)).
    Recomputes predecessor digest — does NOT trust stored value.
    """
    if receipt.previous_receipt_hash is None:
        return True  # Genesis receipt — no predecessor
    computed_predecessor_hash = receipt_hash(predecessor)
    return receipt.previous_receipt_hash == computed_predecessor_hash


# ========================================
# Golden Vectors (from P0-CANONICAL-SERIALIZATION-SPEC-001)
# ========================================

def golden_vectors():
    """Return the three golden vector receipts and their expected SHA-256 digests."""
    
    gv1 = Receipt(
        protocol_version="v0.4",
        schema_version="receipt-v1",
        receipt_id="r-000000000001",
        sequence_number=1,
        receipt_type="PREPARE",
        transaction_id="txn-001",
        artifact_id="art-L1-CORPUS-v2",
        artifact_location="content-addressed:sha256/2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e1ef",
        artifact_byte_size=6327,
        artifact_sha256="2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e1ef",
        previous_receipt_hash=None,
        base_receipt_hash=None,
        custody_state="UNVERIFIED",
        transaction_state="STAGED",
        observed_sha256=None,
        observed_byte_size=None,
        timestamp="2026-08-26T00:00:00.000Z",
        resolver_identity=None,
        evidence_id=None,
    )
    gv1_expected = "e559c31411bd10f49360d17921222782ecd663fd110d33d9d4af20256dacda08"
    
    gv2 = Receipt(
        protocol_version="v0.4",
        schema_version="receipt-v1",
        receipt_id="r-000000000002",
        sequence_number=2,
        receipt_type="COMMIT",
        transaction_id="txn-001",
        artifact_id="art-L1-CORPUS-v2",
        artifact_location="content-addressed:sha256/2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e1ef",
        artifact_byte_size=6327,
        artifact_sha256="2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e1ef",
        previous_receipt_hash=gv1_expected,
        base_receipt_hash=gv1_expected,
        custody_state="VERIFIED",
        transaction_state="COMMITTED",
        observed_sha256="2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e1ef",
        observed_byte_size=6327,
        timestamp="2026-08-26T00:00:01.000Z",
        resolver_identity="resolver-001",
        evidence_id="ev-000000000001",
    )
    gv2_expected = "84542189271d8c99dfa83c3623828dc77af17017f71597ca0efeb77b526858c5"
    
    gv3 = Receipt(
        protocol_version="v0.4",
        schema_version="receipt-v1",
        receipt_id="r-000000000003",
        sequence_number=3,
        receipt_type="ABORT",
        transaction_id="txn-002",
        artifact_id="art-PROTOCOL-SPEC-v04",
        artifact_location="filesystem:/workspace/v0.4_generation_specification.md",
        artifact_byte_size=0,
        artifact_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        previous_receipt_hash=gv2_expected,
        base_receipt_hash=None,
        custody_state="FAILED",
        transaction_state="ABORTED",
        observed_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        observed_byte_size=0,
        timestamp="2026-08-26T00:00:02.000Z",
        resolver_identity="resolver-001",
        evidence_id="ev-000000000002",
    )
    gv3_expected = "b45863b86a5aeb2e333ac01be66d89ac86d5947bf82afa094ca7872f62925c9f"
    
    return [
        (gv1, gv1_expected, "Genesis PREPARE (659 bytes)"),
        (gv2, gv2_expected, "COMMIT chains from GV1 (868 bytes)"),
        (gv3, gv3_expected, "ABORT chains from GV2 (765 bytes)"),
    ]
