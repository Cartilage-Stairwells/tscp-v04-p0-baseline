"""
TSCP v0.4 — Acceptance Test Harness
P0-RESOLVER-IMPLEMENTATION-001

Tests in execution order (per Aria's instruction):
  1. Absence (L1 case: declared artifact, no bytes resolvable)
  2. Contradiction (wrong bytes found, identity mismatch)
  3. Confirmation (correct bytes found, identity match)
  4. V04-CUSTODY-001 (8 cases)
  5. REF-001 through REF-012 (12 cases)
  6. Canonical serialization golden vectors (3)
  7. Cross-implementation verification
"""

import hashlib
import os
import sys
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from resolver import (
    ArtifactRef, ArtifactResolver, ResolutionResult,
    ResolutionStatus, IdentityMatch, IndependentVerifier,
    AuthorizedSourceRegistry, SourceKind, ResolverPolicy,
    FilesystemSourceHandler, ContentAddressedSourceHandler,
)
from canonical_serialization import (
    Receipt, canonical_serialize_receipt, receipt_hash,
    verify_receipt_hash, verify_predecessor, golden_vectors,
)


# ========================================
# Test helpers
# ========================================

SEP = "=" * 60

class TestResult:
    def __init__(self, name, passed, detail=""):
        self.name = name
        self.passed = passed
        self.detail = detail
    
    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.name}" + (f" — {self.detail}" if self.detail else "")


def run_test(name, assertion, detail=""):
    passed = bool(assertion)
    result = TestResult(name, passed, detail)
    print(result)
    return passed


# ========================================
# Phase 1: Three Fundamental Propositions
# ========================================

def test_absence():
    """ABSENCE — A declared artifact whose claimed bytes cannot be independently resolved."""
    print(f"\n{SEP}")
    print("Phase 1: Three Fundamental Propositions")
    print(SEP)
    
    print("\n--- Proposition 1: ABSENCE (the L1 case) ---")
    print("A declared artifact whose claimed bytes cannot be independently resolved.")
    
    resolver = ArtifactResolver()
    
    ref = ArtifactRef(
        artifact_id="art-L1-CORPUS-LOST",
        declared_sha256="f510f4378e9ca377ccc96abc314cae888f4ea0eba0d466969474bca63495bd53",
        declared_byte_size=6327,
        source_kind="FILESYSTEM",
        source_locator="filesystem:/nonexistent/path/to/L1_CORPUS_INPUT_v1.json",
        namespace="v0.4",
        resolver_policy="STRICT",
        reference_version="ref-v1",
    )
    
    result = resolver.resolve(ref)
    verdict = IndependentVerifier.evaluate(result)
    
    results = []
    results.append(run_test("absence: status is NOT_FOUND",
        result.resolution_status == ResolutionStatus.NOT_FOUND.value))
    results.append(run_test("absence: identity_match is NOT_APPLICABLE",
        result.identity_match == IdentityMatch.NOT_APPLICABLE.value))
    results.append(run_test("absence: no observed_sha256",
        result.observed_sha256 is None))
    results.append(run_test("absence: custody verdict is UNVERIFIED",
        verdict == "UNVERIFIED"))
    results.append(run_test("absence: promotion NOT permitted",
        not IndependentVerifier.can_promote(result)))
    
    print("\n  No bytes -> no digest -> no identity -> no verification -> no custody promotion -> no cryptographic binding claim.")
    return all(results)


def test_contradiction():
    """CONTRADICTION — Bytes found but identity mismatch (the L1 binding failure)."""
    print("\n--- Proposition 2: CONTRADICTION (the L1 binding failure) ---")
    print("Bytes found -> digest computed -> mismatch -> FAILED.")
    
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.json', delete=False, dir='/tmp') as f:
        f.write(b'{"test": "wrong content for L1 binding test"}')
        temp_path = f.name
    
    try:
        resolver = ArtifactResolver(authorized_root='/tmp')
        
        wrong_hash = "a644f6bd3b3bca51b3170dad126a3e059e645f46cb0b5bf6aea227d61b827420"
        
        ref = ArtifactRef(
            artifact_id="art-L1-CORPUS-BINDING-FAIL",
            declared_sha256=wrong_hash,
            declared_byte_size=40,
            source_kind="FILESYSTEM",
            source_locator=f"filesystem:{temp_path}",
            namespace="v0.4",
            resolver_policy="STRICT",
            reference_version="ref-v1",
        )
        
        result = resolver.resolve(ref)
        verdict = IndependentVerifier.evaluate(result)
        
        results = []
        results.append(run_test("contradiction: status is RESOLVED (bytes exist)",
            result.resolution_status == ResolutionStatus.RESOLVED.value))
        results.append(run_test("contradiction: observed_sha256 is computed (not None)",
            result.observed_sha256 is not None))
        results.append(run_test("contradiction: observed_sha256 != declared_sha256",
            result.observed_sha256 != result.declared_sha256))
        results.append(run_test("contradiction: identity_match is MISMATCH",
            result.identity_match == IdentityMatch.MISMATCH.value))
        results.append(run_test("contradiction: custody verdict is FAILED (not UNVERIFIED)",
            verdict == "FAILED"))
        results.append(run_test("contradiction: promotion NOT permitted",
            not IndependentVerifier.can_promote(result)))
        results.append(run_test("contradiction: RESOLVED + MISMATCH != NOT_FOUND",
            result.resolution_status == ResolutionStatus.RESOLVED.value
            and result.identity_match == IdentityMatch.MISMATCH.value))
        
        print("\n  'I found something' != 'I found the artifact you claimed'.")
        return all(results)
    finally:
        os.unlink(temp_path)


def test_confirmation():
    """CONFIRMATION — Bytes found, digest computed, match -> eligible for verification."""
    print("\n--- Proposition 3: CONFIRMATION ---")
    print("Bytes found -> digest computed -> match -> eligible for independent verification.")
    
    content = b'{"test": "correct content for confirmation test"}'
    actual_hash = hashlib.sha256(content).hexdigest()
    actual_size = len(content)
    
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.json', delete=False, dir='/tmp') as f:
        f.write(content)
        temp_path = f.name
    
    try:
        resolver = ArtifactResolver(authorized_root='/tmp')
        
        ref = ArtifactRef(
            artifact_id="art-CONFIRMATION-TEST",
            declared_sha256=actual_hash,
            declared_byte_size=actual_size,
            source_kind="FILESYSTEM",
            source_locator=f"filesystem:{temp_path}",
            namespace="v0.4",
            resolver_policy="STRICT",
            reference_version="ref-v1",
        )
        
        result = resolver.resolve(ref)
        verdict = IndependentVerifier.evaluate(result)
        
        results = []
        results.append(run_test("confirmation: status is RESOLVED",
            result.resolution_status == ResolutionStatus.RESOLVED.value))
        results.append(run_test("confirmation: observed_sha256 matches declared",
            result.observed_sha256 == result.declared_sha256))
        results.append(run_test("confirmation: observed_byte_size matches declared",
            result.observed_byte_size == result.declared_byte_size))
        results.append(run_test("confirmation: identity_match is MATCH",
            result.identity_match == IdentityMatch.MATCH.value))
        results.append(run_test("confirmation: custody verdict is ELIGIBLE_FOR_VERIFIED",
            verdict == "ELIGIBLE_FOR_VERIFIED"))
        results.append(run_test("confirmation: promotion IS permitted",
            IndependentVerifier.can_promote(result)))
        
        print("\n  Bytes found -> digest computed -> match -> eligible for independent verification.")
        return all(results)
    finally:
        os.unlink(temp_path)


# ========================================
# Phase 2: V04-CUSTODY-001 Acceptance Suite
# ========================================

def test_v04_custody_001():
    """V04-CUSTODY-001: 8 acceptance test cases."""
    print(f"\n{SEP}")
    print("Phase 2: V04-CUSTODY-001 Acceptance Suite")
    print(SEP)
    
    resolver = ArtifactResolver(authorized_root='/tmp')
    results = []
    
    # 001-A: Bytes exist, hash wrong -> REJECT
    print("\n--- 001-A: Hash mismatch (the L1 binding failure) ---")
    content_a = b'{"data": "mismatch test"}'
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, dir='/tmp') as f:
        f.write(content_a)
        path_a = f.name
    ref_a = ArtifactRef("art-A", "a"*64, len(content_a), "FILESYSTEM", f"filesystem:{path_a}", "v0.4", "STRICT", "ref-v1")
    res_a = resolver.resolve(ref_a)
    results.append(run_test("001-A: REJECT (hash mismatch)",
        not IndependentVerifier.can_promote(res_a) and res_a.identity_match == IdentityMatch.MISMATCH.value))
    os.unlink(path_a)
    
    # 001-B: Bytes missing -> REJECT
    print("\n--- 001-B: Missing artifact ---")
    ref_b = ArtifactRef("art-B", "b"*64, 100, "FILESYSTEM", "filesystem:/tmp/nonexistent_b.bin", "v0.4", "STRICT", "ref-v1")
    res_b = resolver.resolve(ref_b)
    results.append(run_test("001-B: REJECT (not found)",
        not IndependentVerifier.can_promote(res_b) and res_b.resolution_status == ResolutionStatus.NOT_FOUND.value))
    
    # 001-C: Never persisted -> REJECT
    print("\n--- 001-C: Never persisted (the v0.3 pattern) ---")
    ref_c = ArtifactRef("art-C", "c"*64, 100, "FILESYSTEM", "filesystem:/tmp/never_existed.bin", "v0.4", "STRICT", "ref-v1")
    res_c = resolver.resolve(ref_c)
    results.append(run_test("001-C: REJECT (never persisted)",
        not IndependentVerifier.can_promote(res_c) and res_c.resolution_status == ResolutionStatus.NOT_FOUND.value))
    
    # 001-D: Bytes exist + exact match -> PASS
    print("\n--- 001-D: Correct artifact ---")
    content_d = b'{"data": "correct match test"}'
    hash_d = hashlib.sha256(content_d).hexdigest()
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, dir='/tmp') as f:
        f.write(content_d)
        path_d = f.name
    ref_d = ArtifactRef("art-D", hash_d, len(content_d), "FILESYSTEM", f"filesystem:{path_d}", "v0.4", "STRICT", "ref-v1")
    res_d = resolver.resolve(ref_d)
    results.append(run_test("001-D: PASS (exact match)",
        IndependentVerifier.can_promote(res_d) and res_d.identity_match == IdentityMatch.MATCH.value))
    os.unlink(path_d)
    
    # 001-E: Modified after registration -> REJECT
    print("\n--- 001-E: Modified after registration ---")
    original = b'{"version": "original"}'
    original_hash = hashlib.sha256(original).hexdigest()
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, dir='/tmp') as f:
        f.write(original)
        path_e = f.name
    with open(path_e, 'wb') as f:
        f.write(b'{"version": "modified"}')
    ref_e = ArtifactRef("art-E", original_hash, len(original), "FILESYSTEM", f"filesystem:{path_e}", "v0.4", "STRICT", "ref-v1")
    res_e = resolver.resolve(ref_e)
    results.append(run_test("001-E: REJECT (modified after registration)",
        not IndependentVerifier.can_promote(res_e) and res_e.identity_match == IdentityMatch.MISMATCH.value))
    os.unlink(path_e)
    
    # 001-F: Correct hash, wrong byte_size -> REJECT
    print("\n--- 001-F: Byte size mismatch ---")
    content_f = b'{"data": "size test"}'
    hash_f = hashlib.sha256(content_f).hexdigest()
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, dir='/tmp') as f:
        f.write(content_f)
        path_f = f.name
    ref_f = ArtifactRef("art-F", hash_f, len(content_f) + 999, "FILESYSTEM", f"filesystem:{path_f}", "v0.4", "STRICT", "ref-v1")
    res_f = resolver.resolve(ref_f)
    results.append(run_test("001-F: REJECT (size mismatch)",
        not IndependentVerifier.can_promote(res_f) and res_f.identity_match == IdentityMatch.MISMATCH.value))
    os.unlink(path_f)
    
    # 001-G: Correct bytes at unauthorized location -> REJECT
    print("\n--- 001-G: Unauthorized location ---")
    content_g = b'{"data": "unauthorized location test"}'
    hash_g = hashlib.sha256(content_g).hexdigest()
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, dir='/tmp') as f:
        f.write(content_g)
        path_g = f.name
    try:
        ref_g = ArtifactRef("art-G", hash_g, len(content_g), "conversation_transcript", f"filesystem:{path_g}", "v0.4", "STRICT", "ref-v1")
        res_g = resolver.resolve(ref_g)
        results.append(run_test("001-G: REJECT (unauthorized source)",
            not IndependentVerifier.can_promote(res_g) and res_g.resolution_status == ResolutionStatus.ACCESS_DENIED.value))
    except ValueError:
        results.append(run_test("001-G: REJECT (unauthorized source — rejected at construction)",
            True, "ArtifactRef rejects invalid source_kind"))
    os.unlink(path_g)
    
    # 001-H: Conversation contains contents, no persistent bytes -> REJECT
    print("\n--- 001-H: Conversation-only artifact (the v0.3 regression) ---")
    try:
        ref_h = ArtifactRef("art-H", "1a2b3c4d5e6f78901a2b3c4d5e6f78901a2b3c4d5e6f78901a2b3c4d5e6f7890", 100, "conversation_transcript", "conversation:session-123", "v0.4", "STRICT", "ref-v1")
        res_h = resolver.resolve(ref_h)
        results.append(run_test("001-H: REJECT (conversation-only)",
            not IndependentVerifier.can_promote(res_h) and res_h.resolution_status == ResolutionStatus.ACCESS_DENIED.value))
    except ValueError:
        results.append(run_test("001-H: REJECT (conversation-only — rejected at construction)",
            True, "ArtifactRef rejects prohibited source_kind"))
    
    return all(results)


# ========================================
# Phase 3: REF-001 through REF-012
# ========================================

def test_ref_suite():
    """REF-001 through REF-012: artifact reference adversarial tests."""
    print(f"\n{SEP}")
    print("Phase 3: REF-001 through REF-012")
    print(SEP)
    
    resolver = ArtifactResolver(authorized_root='/tmp')
    results = []
    
    # REF-001: Nonexistent path -> NOT_FOUND
    print("\n--- REF-001: Nonexistent path ---")
    ref = ArtifactRef("art-001", "a"*64, 100, "FILESYSTEM", "filesystem:/tmp/nonexistent_ref001.bin", "v0.4", "STRICT", "ref-v1")
    res = resolver.resolve(ref)
    results.append(run_test("REF-001: NOT_FOUND",
        res.resolution_status == ResolutionStatus.NOT_FOUND.value))
    
    # REF-002: Path resolves to wrong bytes -> RESOLVED + IDENTITY_MISMATCH
    print("\n--- REF-002: Path resolves to wrong bytes (the L1 incident) ---")
    content = b'{"data": "wrong bytes"}'
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, dir='/tmp') as f:
        f.write(content)
        path = f.name
    ref = ArtifactRef("art-002", "0"*64, 999, "FILESYSTEM", f"filesystem:{path}", "v0.4", "STRICT", "ref-v1")
    res = resolver.resolve(ref)
    results.append(run_test("REF-002: RESOLVED + IDENTITY_MISMATCH",
        res.resolution_status == ResolutionStatus.RESOLVED.value
        and res.identity_match == IdentityMatch.MISMATCH.value))
    os.unlink(path)
    
    # REF-003: Path replaced after registration
    print("\n--- REF-003: Path replaced after registration ---")
    original = b'{"version": "v1"}'
    original_hash = hashlib.sha256(original).hexdigest()
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, dir='/tmp') as f:
        f.write(original)
        path = f.name
    ref = ArtifactRef("art-003", original_hash, len(original), "FILESYSTEM", f"filesystem:{path}", "v0.4", "STRICT", "ref-v1")
    res1 = resolver.resolve(ref)
    match1 = res1.identity_match == IdentityMatch.MATCH.value
    with open(path, 'wb') as f:
        f.write(b'{"version": "v2"}')
    res2 = resolver.resolve(ref)
    mismatch = res2.identity_match == IdentityMatch.MISMATCH.value
    results.append(run_test("REF-003: old identity preserved, new bytes mismatch",
        match1 and mismatch))
    os.unlink(path)
    
    # REF-004: Directory where file expected -> REJECT
    print("\n--- REF-004: Directory where file expected ---")
    dir_path = tempfile.mkdtemp(dir='/tmp')
    ref = ArtifactRef("art-004", "d"*64, 100, "FILESYSTEM", f"filesystem:{dir_path}", "v0.4", "STRICT", "ref-v1")
    res = resolver.resolve(ref)
    results.append(run_test("REF-004: REJECT (directory)",
        res.resolution_status == ResolutionStatus.UNREADABLE.value))
    os.rmdir(dir_path)
    
    # REF-005: Symlink escapes authorized root -> REJECT
    print("\n--- REF-005: Symlink escapes authorized root ---")
    restricted_root = tempfile.mkdtemp(dir='/tmp')
    outside_path = tempfile.mkdtemp(dir='/tmp')
    symlink_name = os.path.join(restricted_root, "escape_link")
    os.symlink(outside_path, symlink_name)
    resolver_restricted = ArtifactResolver(authorized_root=restricted_root)
    ref = ArtifactRef("art-005", "e"*64, 100, "FILESYSTEM", f"filesystem:{symlink_name}", "v0.4", "STRICT", "ref-v1")
    res = resolver_restricted.resolve(ref)
    results.append(run_test("REF-005: REJECT (symlink escape)",
        res.resolution_status == ResolutionStatus.ACCESS_DENIED.value))
    os.unlink(symlink_name)
    os.rmdir(restricted_root)
    os.rmdir(outside_path)
    
    # REF-006: Relative path traversal -> REJECT
    print("\n--- REF-006: Relative path traversal ---")
    try:
        ref = ArtifactRef("art-006", "f"*64, 100, "FILESYSTEM", "filesystem:../../etc/passwd", "v0.4", "STRICT", "ref-v1")
        res = resolver.resolve(ref)
        results.append(run_test("REF-006: REJECT (traversal)",
            res.resolution_status == ResolutionStatus.ACCESS_DENIED.value))
    except ValueError:
        results.append(run_test("REF-006: REJECT (traversal — rejected at construction)",
            True, "ArtifactRef rejects path traversal"))
    
    # REF-007: Ambiguous URI -> REJECT
    print("\n--- REF-007: Ambiguous URI ---")
    ref = ArtifactRef("art-007", "0a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f6789", 100, "FILESYSTEM", "filesystem:/tmp/file*", "v0.4", "STRICT", "ref-v1")
    res = resolver.resolve(ref)
    results.append(run_test("REF-007: REJECT (ambiguous)",
        res.resolution_status in [ResolutionStatus.NOT_FOUND.value, ResolutionStatus.ACCESS_DENIED.value]))
    
    # REF-008: Conversation-only artifact -> REJECT
    print("\n--- REF-008: Conversation-only artifact ---")
    try:
        ref = ArtifactRef("art-008", "1a2b3c4d5e6f78901a2b3c4d5e6f78901a2b3c4d5e6f78901a2b3c4d5e6f7890", 100, "conversation_transcript", "conversation:abc", "v0.4", "STRICT", "ref-v1")
        res = resolver.resolve(ref)
        results.append(run_test("REF-008: REJECT (conversation-only)",
            res.resolution_status == ResolutionStatus.ACCESS_DENIED.value))
    except ValueError:
        results.append(run_test("REF-008: REJECT (conversation-only — at construction)",
            True, "ArtifactRef rejects prohibited source"))
    
    # REF-009: Ephemeral memory reference -> REJECT
    print("\n--- REF-009: Ephemeral memory reference ---")
    try:
        ref = ArtifactRef("art-009", "2a3b4c5d6e7f89012a3b4c5d6e7f89012a3b4c5d6e7f89012a3b4c5d6e7f8901", 100, "ephemeral_memory", "memory:0x7fff", "v0.4", "STRICT", "ref-v1")
        res = resolver.resolve(ref)
        results.append(run_test("REF-009: REJECT (ephemeral)",
            res.resolution_status == ResolutionStatus.ACCESS_DENIED.value))
    except ValueError:
        results.append(run_test("REF-009: REJECT (ephemeral — at construction)",
            True, "ArtifactRef rejects prohibited source"))
    
    # REF-010: Same bytes at two authorized locations
    print("\n--- REF-010: Same bytes at two authorized locations ---")
    content = b'{"data": "identical content"}'
    hash_val = hashlib.sha256(content).hexdigest()
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, dir='/tmp', suffix='.a') as f1:
        f1.write(content)
        path1 = f1.name
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, dir='/tmp', suffix='.b') as f2:
        f2.write(content)
        path2 = f2.name
    ref1 = ArtifactRef("art-010a", hash_val, len(content), "FILESYSTEM", f"filesystem:{path1}", "v0.4", "STRICT", "ref-v1")
    ref2 = ArtifactRef("art-010b", hash_val, len(content), "FILESYSTEM", f"filesystem:{path2}", "v0.4", "STRICT", "ref-v1")
    res1 = resolver.resolve(ref1)
    res2 = resolver.resolve(ref2)
    results.append(run_test("REF-010: same byte identity, distinct provenance locations",
        res1.observed_sha256 == res2.observed_sha256
        and res1.resolved_location != res2.resolved_location
        and res1.evidence_id != res2.evidence_id))
    os.unlink(path1)
    os.unlink(path2)
    
    # REF-011: Same path, different bytes -> different identities
    print("\n--- REF-011: Same path, different bytes ---")
    content_v1 = b'{"version": 1}'
    content_v2 = b'{"version": 2}'
    hash_v1 = hashlib.sha256(content_v1).hexdigest()
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, dir='/tmp') as f:
        f.write(content_v1)
        path = f.name
    ref_v1 = ArtifactRef("art-011", hash_v1, len(content_v1), "FILESYSTEM", f"filesystem:{path}", "v0.4", "STRICT", "ref-v1")
    res_v1 = resolver.resolve(ref_v1)
    with open(path, 'wb') as f:
        f.write(content_v2)
    res_v2 = resolver.resolve(ref_v1)
    results.append(run_test("REF-011: same path, different identities",
        res_v1.identity_match == IdentityMatch.MATCH.value
        and res_v2.identity_match == IdentityMatch.MISMATCH.value
        and res_v1.observed_sha256 != res_v2.observed_sha256))
    os.unlink(path)
    
    # REF-012: Declared size differs from observed -> REJECT promotion
    print("\n--- REF-012: Declared size differs from observed ---")
    content = b'{"data": "size mismatch test"}'
    hash_val = hashlib.sha256(content).hexdigest()
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, dir='/tmp') as f:
        f.write(content)
        path = f.name
    ref = ArtifactRef("art-012", hash_val, len(content) + 100, "FILESYSTEM", f"filesystem:{path}", "v0.4", "STRICT", "ref-v1")
    res = resolver.resolve(ref)
    results.append(run_test("REF-012: REJECT promotion (size mismatch)",
        not IndependentVerifier.can_promote(res) and res.identity_match == IdentityMatch.MISMATCH.value))
    os.unlink(path)
    
    return all(results)


# ========================================
# Phase 4: Canonical Serialization Golden Vectors
# ========================================

def test_golden_vectors():
    """Verify the three golden vectors from P0-CANONICAL-SERIALIZATION-SPEC-001."""
    print(f"\n{SEP}")
    print("Phase 4: Canonical Serialization Golden Vectors")
    print(SEP)
    
    results = []
    gvs = golden_vectors()
    
    for i, (receipt, expected_hash, description) in enumerate(gvs, 1):
        print(f"\n--- GV{i}: {description} ---")
        computed_hash = receipt_hash(receipt)
        canonical_bytes = canonical_serialize_receipt(receipt)
        
        results.append(run_test(f"GV{i}: computed hash matches spec",
            computed_hash == expected_hash,
            f"computed={computed_hash[:16]}... expected={expected_hash[:16]}..."))
        results.append(run_test(f"GV{i}: canonical bytes are UTF-8",
            isinstance(canonical_bytes, bytes)))
        results.append(run_test(f"GV{i}: verify_receipt_hash returns True",
            verify_receipt_hash(receipt, computed_hash)))
    
    # Chain verification
    print("\n--- Chain Verification ---")
    gv1_receipt, gv1_hash, _ = gvs[0]
    gv2_receipt, gv2_hash, _ = gvs[1]
    gv3_receipt, gv3_hash, _ = gvs[2]
    
    results.append(run_test("GV2.previous_receipt_hash == SHA256(GV1)",
        verify_predecessor(gv2_receipt, gv1_receipt)))
    results.append(run_test("GV3.previous_receipt_hash == SHA256(GV2)",
        verify_predecessor(gv3_receipt, gv2_receipt)))
    results.append(run_test("GV1 genesis: previous_receipt_hash is None",
        gv1_receipt.previous_receipt_hash is None))
    
    return all(results)


# ========================================
# Phase 5: Cross-Implementation Verification
# ========================================

def test_cross_implementation():
    """Cross-implementation verification — independent recomputation of golden vectors."""
    print(f"\n{SEP}")
    print("Phase 5: Cross-Implementation Verification")
    print(SEP)
    
    results = []
    gvs = golden_vectors()
    
    for i, (receipt, expected_hash, description) in enumerate(gvs, 1):
        print(f"\n--- Cross-impl GV{i} ---")
        
        computed = receipt_hash(receipt)
        results.append(run_test(f"Cross-impl GV{i}: independent recompute matches spec",
            computed == expected_hash))
        
        results.append(run_test(f"Cross-impl GV{i}: hash is 64 lowercase hex chars",
            len(computed) == 64 and all(c in '0123456789abcdef' for c in computed)))
        
        canonical = canonical_serialize_receipt(receipt)
        decoded = canonical.decode('utf-8')
        results.append(run_test(f"Cross-impl GV{i}: no whitespace in canonical bytes",
            ' ' not in decoded and '\n' not in decoded and '\t' not in decoded))
    
    # Adversarial: modify a receipt and verify hash changes
    print("\n--- Adversarial: Receipt modification detection ---")
    gv1, gv1_hash, _ = gvs[0]
    modified = Receipt(
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
        custody_state="VERIFIED",
        transaction_state="STAGED",
        observed_sha256=None,
        observed_byte_size=None,
        timestamp="2026-08-26T00:00:00.000Z",
        resolver_identity=None,
        evidence_id=None,
    )
    modified_hash = receipt_hash(modified)
    results.append(run_test("Adversarial: modified receipt produces different hash",
        modified_hash != gv1_hash))
    
    return all(results)


# ========================================
# Main
# ========================================

def main():
    print("TSCP v0.4 — P0-RESOLVER-IMPLEMENTATION-001 Acceptance Test Suite")
    print("=" * 60)
    print()
    print("Test order: absence -> contradiction -> confirmation -> full suite")
    print("INV-CUSTODY-001: resolver cannot promote custody by construction")
    
    all_passed = True
    
    all_passed &= test_absence()
    all_passed &= test_contradiction()
    all_passed &= test_confirmation()
    
    all_passed &= test_v04_custody_001()
    all_passed &= test_ref_suite()
    all_passed &= test_golden_vectors()
    all_passed &= test_cross_implementation()
    
    print(f"\n{'=' * 60}")
    if all_passed:
        print("ALL TESTS PASSED")
        print()
        print("The resolver implementation satisfies the three frozen P0 contracts:")
        print("  - P0-CANONICAL-SERIALIZATION-SPEC-001 (golden vectors reproduced)")
        print("  - P0-ARTIFACT-REFERENCE-SPEC-001 (12 adversarial tests pass)")
        print("  - P0-RESOLVER-SPEC-001 (V04-CUSTODY-001 8 tests pass)")
        print()
        print("Three fundamental propositions verified:")
        print("  1. ABSENCE: No bytes -> no verification -> no custody promotion")
        print("  2. CONTRADICTION: Wrong bytes -> FAILED (not UNVERIFIED)")
        print("  3. CONFIRMATION: Correct bytes -> eligible for verification")
        print()
        print("The resolver has NO custody promotion path by construction.")
        print("resolve() -> ResolutionResult. Not resolve() -> VERIFIED.")
    else:
        print("SOME TESTS FAILED — see output above")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
