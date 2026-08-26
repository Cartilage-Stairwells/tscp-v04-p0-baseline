"""
INDEPENDENT RESOLVER for P0-RESOLVER-SPEC-001 and P0-ARTIFACT-REFERENCE-SPEC-001
Acceptance predicate: IV-P0-002

This module is a GENUINELY INDEPENDENT implementation of the persistent
artifact resolver contract. It imports NOTHING from production code
(resolver.py, canonical_serialization.py, or any production helpers).

All behavior is derived from the specifications:
  - P0-RESOLVER-SPEC-001 §2 (resolver contract)
  - P0-RESOLVER-SPEC-001 §3 (result model)
  - P0-RESOLVER-SPEC-001 §4 (custody promotion pipeline)
  - P0-RESOLVER-SPEC-001 §5 (authorized source rules)
  - P0-RESOLVER-SPEC-001 §7 (failure taxonomy)
  - P0-ARTIFACT-REFERENCE-SPEC-001 §1 (ArtifactRef structure)
  - P0-ARTIFACT-REFERENCE-SPEC-001 §2 (critical invariants)
  - P0-ARTIFACT-REFERENCE-SPEC-001 §3 (authorized source classes)
  - P0-ARTIFACT-REFERENCE-SPEC-001 §4 (reference immutability)

Independence constraints:
  - No imports from resolver.py
  - No imports from canonical_serialization.py
  - No reuse of production resolver helper functions
  - The specification is the oracle, not production outputs

Design decisions that differ from production (legitimate independence):
  - source_locator format: bare absolute path (production uses "filesystem:" prefix)
  - Implementation language: same Python, but different code structure
  - Internal class structure: simpler, no dataclass decorators
  - Authorized source registry: explicit set, not class-based
"""

import hashlib
import os
import time
import uuid
from datetime import datetime, timezone


# ========================================
# Resolution Status (from P0-RESOLVER-SPEC-001 §2)
# ========================================

# The spec defines five resolution outcomes:
#   RESOLVED, NOT_FOUND, ACCESS_DENIED, UNREADABLE, READ_ERROR

RESOLVED = "RESOLVED"
NOT_FOUND = "NOT_FOUND"
ACCESS_DENIED = "ACCESS_DENIED"
UNREADABLE = "UNREADABLE"
READ_ERROR = "READ_ERROR"

# Identity match outcomes (from P0-RESOLVER-SPEC-001 §2)
MATCH = "MATCH"
MISMATCH = "MISMATCH"
NOT_APPLICABLE = "NOT_APPLICABLE"


# ========================================
# ArtifactRef (from P0-ARTIFACT-REFERENCE-SPEC-001 §1)
# ========================================

# The spec defines 8 required fields. No field is optional. No field may be null.
# declared_sha256 and declared_byte_size are CLAIMS, not verified identity.

AUTHORIZED_SOURCE_KINDS = {
    "FILESYSTEM",
    "OBJECT_STORE",
    "CONTENT_ADDRESSED",
    "DEPLOYMENT_ADMITTED",
}

# Prohibited sources (from P0-ARTIFACT-REFERENCE-SPEC-001 §3)
PROHIBITED_SOURCES = {
    "CONVERSATION",
    "MODEL_CONTEXT",
    "MODEL_RECONSTRUCTION",
    "EPHEMERAL_MEMORY",
    "SEARCH_RESULTS",
    "AGENT_ASSERTION",
}


class ArtifactRef:
    """
    Reference to a persistent byte source.
    
    Per INV-REF-001: Must identify one deterministic resolution target.
    Per INV-REF-002: Location tells resolver WHERE to look, not WHAT the artifact is.
    Per INV-REF-003: Location is evidence of where bytes may be found, not
                     evidence that bytes at that location possess the declared identity.
    
    All 8 fields required, no nulls (per §1).
    """
    
    def __init__(self, artifact_id, declared_sha256, declared_byte_size,
                 source_kind, source_locator, namespace,
                 resolver_policy, reference_version):
        # Validate all fields present and non-null
        if not all([artifact_id, declared_sha256, declared_byte_size is not None,
                     source_kind, source_locator, namespace,
                     resolver_policy, reference_version]):
            raise ValueError("All ArtifactRef fields are required and must be non-null")
        
        # Validate source kind is authorized
        if source_kind not in AUTHORIZED_SOURCE_KINDS:
            raise ValueError(f"Invalid source_kind: {source_kind}")
        
        # Validate SHA-256 format (64 lowercase hex chars per spec §3)
        if len(declared_sha256) != 64 or not all(c in '0123456789abcdef' for c in declared_sha256):
            raise ValueError(f"Invalid declared_sha256 format: must be 64 lowercase hex chars")
        
        # INV-REF-001: Reject relative path traversal for FILESYSTEM
        if source_kind == "FILESYSTEM" and ".." in str(source_locator):
            raise ValueError("Relative path traversal rejected (INV-REF-001)")
        
        # Reject prohibited source kinds
        if source_kind in PROHIBITED_SOURCES:
            raise ValueError(f"Prohibited source kind: {source_kind}")
        
        self.artifact_id = artifact_id
        self.declared_sha256 = declared_sha256
        self.declared_byte_size = declared_byte_size
        self.source_kind = source_kind
        self.source_locator = source_locator
        self.namespace = namespace
        self.resolver_policy = resolver_policy
        self.reference_version = reference_version


# ========================================
# ResolutionResult (from P0-RESOLVER-SPEC-001 §3)
# ========================================

class ResolutionResult:
    """
    Evidence produced by the resolver.
    
    Per P0-RESOLVER-SPEC-001 §2: "The resolver NEVER returns VERIFIED.
    It returns resolution evidence to the epistemic custody layer."
    
    Fields (from §3):
      artifact_ref, resolution_status, source, resolved_location,
      observed_byte_size, observed_sha256, observed_at,
      resolver_identity, evidence_id
    """
    
    def __init__(self, artifact_ref, resolution_status, source,
                 resolved_location, observed_byte_size, observed_sha256,
                 declared_sha256, declared_byte_size, identity_match,
                 observed_at, resolver_identity, evidence_id):
        self.artifact_ref = artifact_ref
        self.resolution_status = resolution_status
        self.source = source
        self.resolved_location = resolved_location
        self.observed_byte_size = observed_byte_size
        self.observed_sha256 = observed_sha256
        self.declared_sha256 = declared_sha256
        self.declared_byte_size = declared_byte_size
        self.identity_match = identity_match
        self.observed_at = observed_at
        self.resolver_identity = resolver_identity
        self.evidence_id = evidence_id


# ========================================
# Independent Artifact Resolver
# ========================================

class IndependentArtifactResolver:
    """
    Persistent Artifact Resolver — independently implemented.
    
    Per P0-RESOLVER-SPEC-001 §2: The resolver's pipeline is:
      1. Check authorization (INV-REF-003)
      2. Traverse authorized source
      3. Read complete bytes
      4. Compute byte_size independently
      5. Compute SHA-256 independently
      6. Compare to declared identity
      7. Emit evidence (NOT a custody verdict)
    
    The resolver has NO custody promotion path. It produces evidence only.
    """
    
    def __init__(self, resolver_identity="independent-resolver-001",
                 authorized_root="/"):
        self.resolver_identity = resolver_identity
        self.authorized_root = os.path.realpath(authorized_root)
        # Per §5: sources not in the authorized list cannot establish byte identity
        self._authorized_sources = set(AUTHORIZED_SOURCE_KINDS)
    
    def resolve(self, artifact_ref):
        """
        Resolve an artifact reference to observed bytes.
        
        Returns ResolutionResult — evidence for the epistemic layer.
        NEVER returns a custody state.
        """
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%03fZ')
        evidence_id = f"iv-ev-{uuid.uuid4().hex[:12]}"
        
        # Step 1: Check authorization (INV-REF-003)
        if artifact_ref.source_kind not in self._authorized_sources:
            return ResolutionResult(
                artifact_ref=artifact_ref,
                resolution_status=ACCESS_DENIED,
                source=artifact_ref.source_kind,
                resolved_location=None,
                observed_byte_size=None,
                observed_sha256=None,
                declared_sha256=artifact_ref.declared_sha256,
                declared_byte_size=artifact_ref.declared_byte_size,
                identity_match=NOT_APPLICABLE,
                observed_at=timestamp,
                resolver_identity=self.resolver_identity,
                evidence_id=evidence_id,
            )
        
        # Step 2-3: Traverse source and read bytes
        if artifact_ref.source_kind == "FILESYSTEM":
            status, data, resolved_loc = self._resolve_filesystem(artifact_ref.source_locator)
        elif artifact_ref.source_kind == "CONTENT_ADDRESSED":
            # Not implemented in this minimal independent resolver
            # (production has a CAS handler; independent impl doesn't need it for IV-P0-002)
            status, data, resolved_loc = (NOT_FOUND, None, None)
        else:
            status, data, resolved_loc = (NOT_FOUND, None, None)
        
        # If resolution failed, return evidence of failure
        if status != RESOLVED:
            return ResolutionResult(
                artifact_ref=artifact_ref,
                resolution_status=status,
                source=artifact_ref.source_kind,
                resolved_location=resolved_loc,
                observed_byte_size=None,
                observed_sha256=None,
                declared_sha256=artifact_ref.declared_sha256,
                declared_byte_size=artifact_ref.declared_byte_size,
                identity_match=NOT_APPLICABLE,
                observed_at=timestamp,
                resolver_identity=self.resolver_identity,
                evidence_id=evidence_id,
            )
        
        # Step 4: Compute byte_size independently
        observed_byte_size = len(data)
        
        # Step 5: Compute SHA-256 independently
        observed_sha256 = hashlib.sha256(data).hexdigest()
        
        # Step 6: Compare to declared identity
        # Per §7: both byte_size AND sha256 must match
        size_matches = (observed_byte_size == artifact_ref.declared_byte_size)
        hash_matches = (observed_sha256 == artifact_ref.declared_sha256)
        
        if size_matches and hash_matches:
            identity_match = MATCH
        else:
            identity_match = MISMATCH
        
        # Step 7: Emit evidence (NOT a custody verdict)
        return ResolutionResult(
            artifact_ref=artifact_ref,
            resolution_status=RESOLVED,
            source=artifact_ref.source_kind,
            resolved_location=resolved_loc,
            observed_byte_size=observed_byte_size,
            observed_sha256=observed_sha256,
            declared_sha256=artifact_ref.declared_sha256,
            declared_byte_size=artifact_ref.declared_byte_size,
            identity_match=identity_match,
            observed_at=timestamp,
            resolver_identity=self.resolver_identity,
            evidence_id=evidence_id,
        )
    
    def _resolve_filesystem(self, source_locator):
        """
        Resolve a filesystem locator to bytes.
        
        Independent implementation of filesystem resolution.
        Uses bare absolute path format (different from production's "filesystem:" prefix).
        
        Returns: (status, bytes_or_None, resolved_location_or_None)
        """
        # The locator must be an absolute path
        if not os.path.isabs(str(source_locator)):
            return (ACCESS_DENIED, None, None)
        
        # INV-REF-001: Reject path traversal
        if ".." in str(source_locator):
            return (ACCESS_DENIED, None, None)
        
        # Resolve real path (follows symlinks)
        real_path = os.path.realpath(str(source_locator))
        
        # REF-005: Check symlink doesn't escape authorized root
        if not real_path.startswith(self.authorized_root):
            return (ACCESS_DENIED, None, None)
        
        # REF-001: Check existence
        if not os.path.exists(real_path):
            return (NOT_FOUND, None, None)
        
        # REF-004: Must be a file, not a directory
        if os.path.isdir(real_path):
            return (UNREADABLE, None, real_path)
        
        # Read bytes
        try:
            with open(real_path, 'rb') as f:
                data = f.read()
            return (RESOLVED, data, real_path)
        except PermissionError:
            return (ACCESS_DENIED, None, real_path)
        except IOError:
            return (READ_ERROR, None, real_path)
        except Exception:
            return (READ_ERROR, None, real_path)


# ========================================
# Independent Custody Verifier (from P0-RESOLVER-SPEC-001 §4)
# ========================================

class IndependentCustodyVerifier:
    """
    Evaluates resolution evidence and makes custody determinations.
    
    Per §4: No shortcut from Resolve to Promote.
    The verifier is a separate stage from the resolver.
    
    Returns: UNVERIFIED | FAILED | ELIGIBLE_FOR_VERIFIED
    """
    
    @staticmethod
    def evaluate(result):
        """
        Evaluate resolution evidence.
        
        Per P0-RESOLVER-SPEC-001 §4 and §7:
        - Resolution failure → UNVERIFIED
        - RESOLVED + MATCH → ELIGIBLE_FOR_VERIFIED
        - RESOLVED + MISMATCH → FAILED
        """
        if result.resolution_status != RESOLVED:
            return "UNVERIFIED"
        
        if result.identity_match == MATCH:
            return "ELIGIBLE_FOR_VERIFIED"
        elif result.identity_match == MISMATCH:
            return "FAILED"
        else:
            return "UNVERIFIED"
    
    @staticmethod
    def can_promote(result):
        """
        Check if custody promotion is permitted.
        
        Per INV-CUSTODY-001: Promotion requires:
          - Resolve(a.location) = bytes
          - len(bytes) = a.byte_size
          - SHA256(bytes) = a.sha256
          - verification is independent
        """
        if result.resolution_status != RESOLVED:
            return False
        if result.identity_match != MATCH:
            return False
        if result.observed_sha256 is None or result.observed_byte_size is None:
            return False
        if result.observed_sha256 != result.declared_sha256:
            return False
        if result.observed_byte_size != result.declared_byte_size:
            return False
        return True
