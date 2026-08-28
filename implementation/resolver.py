"""
TSCP v0.4 — Persistent Artifact Resolver
Implementation of P0-RESOLVER-IMPLEMENTATION-001

The resolver establishes byte identity by independently resolving,
observing, and computing SHA-256 over artifact bytes. It NEVER promotes
custody. It returns ResolutionResult — evidence for the epistemic layer.

Implements:
  - P0-RESOLVER-SPEC-001 (resolver contract, pipeline, promotion gate)
  - P0-ARTIFACT-REFERENCE-SPEC-001 (reference model, authorized sources)
  - P0-CANONICAL-SERIALIZATION-SPEC-001 (receipt hashing)

Architecture:
  PERSISTENT SOURCE → ARTIFACT REF → RESOLVER → OBSERVATION EVIDENCE
    → INDEPENDENT VERIFIER → CUSTODY VERDICT → TRANSACTION/RECEIPT LAYER

The resolver sits at "OBSERVATION EVIDENCE" and does not cross into
custody verdicts. This separation is structural, not conventional.
"""

import hashlib
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ========================================
# Enums
# ========================================

class ResolutionStatus(Enum):
    """Possible resolution outcomes."""
    RESOLVED = "RESOLVED"
    NOT_FOUND = "NOT_FOUND"
    ACCESS_DENIED = "ACCESS_DENIED"
    UNREADABLE = "UNREADABLE"
    READ_ERROR = "READ_ERROR"


class SourceKind(Enum):
    """Authorized source classes."""
    FILESYSTEM = "FILESYSTEM"
    OBJECT_STORE = "OBJECT_STORE"
    CONTENT_ADDRESSED = "CONTENT_ADDRESSED"
    DEPLOYMENT_ADMITTED = "DEPLOYMENT_ADMITTED"


class ResolverPolicy(Enum):
    """Resolution behavior policy."""
    STRICT = "STRICT"
    MULTI_SOURCE = "MULTI_SOURCE"
    CONTENT_ADDRESSED = "CONTENT_ADDRESSED"


class IdentityMatch(Enum):
    """Result of comparing declared vs observed identity."""
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    NOT_APPLICABLE = "NOT_APPLICABLE"  # Resolution failed, no observation


# ========================================
# ArtifactRef (from P0-ARTIFACT-REFERENCE-SPEC-001)
# ========================================

@dataclass
class ArtifactRef:
    """
    Reference to a persistent byte source.
    
    INV-REF-001: Must identify one deterministic resolution target.
    INV-REF-002: Location tells resolver WHERE to look, not WHAT the artifact is.
    INV-REF-003: Location is evidence of where bytes may be found, not evidence
                 that bytes at that location possess the declared identity.
    """
    artifact_id: str
    declared_sha256: str          # claim, not verified identity
    declared_byte_size: int        # claim, not verified size
    source_kind: str               # SourceKind enum value
    source_locator: str           # addressable location within source_kind
    namespace: str                # provenance namespace
    resolver_policy: str          # ResolverPolicy enum value
    reference_version: str        # schema version of this reference

    def __post_init__(self):
        # INV-REF-001: Validate determinacy
        if self.resolver_policy == "STRICT":
            # STRICT policy: one source, no fallback
            pass
        # Validate source kind
        valid_kinds = {sk.value for sk in SourceKind}
        if self.source_kind not in valid_kinds:
            raise ValueError(f"Invalid source_kind: {self.source_kind}")
        # Validate resolver policy
        valid_policies = {rp.value for rp in ResolverPolicy}
        if self.resolver_policy not in valid_policies:
            raise ValueError(f"Invalid resolver_policy: {self.resolver_policy}")
        # Validate SHA-256 format
        if len(self.declared_sha256) != 64 or not all(c in '0123456789abcdef' for c in self.declared_sha256):
            raise ValueError(f"Invalid declared_sha256 format")
        # INV-REF-001: Reject relative paths
        if self.source_kind == "FILESYSTEM" and ".." in self.source_locator:
            raise ValueError(f"Relative path traversal rejected (INV-REF-001)")


# ========================================
# ResolutionResult (the resolver's ONLY output)
# ========================================

@dataclass
class ResolutionResult:
    """
    Evidence produced by the resolver. This is NOT a custody verdict.
    
    The epistemic layer consumes this evidence and makes the custody
    determination. The resolver cannot promote custody by construction.
    """
    artifact_ref: ArtifactRef
    resolution_status: str          # ResolutionStatus enum value
    source: str                      # which source was attempted
    resolved_location: Optional[str] # actual location if RESOLVED, None otherwise
    observed_byte_size: Optional[int]# measured byte count if RESOLVED, None otherwise
    observed_sha256: Optional[str]   # computed SHA-256 if RESOLVED, None otherwise
    declared_sha256: str             # echoed from ref for comparison
    declared_byte_size: int          # echoed from ref for comparison
    identity_match: str              # IdentityMatch enum value
    observed_at: str                 # ISO-8601 UTC timestamp
    resolver_identity: str           # identity of resolver component
    evidence_id: str                 # unique identifier for this resolution event


# ========================================
# Authorized Source Registry
# ========================================

class AuthorizedSourceRegistry:
    """
    INV-REF-003: Only explicitly authorized source classes may be traversed.
    
    Finding bytes at an unauthorized location does not establish byte identity,
    even if those bytes match the declared hash.
    """
    
    PROHIBITED_SOURCES = {
        "conversation_transcript",
        "model_context",
        "model_generated",
        "ephemeral_memory",
        "undocumented_sandbox",
        "search_result",
        "agent_assertion",
    }
    
    def __init__(self):
        self._registered = set()
        # Register default authorized sources
        self._registered.add(SourceKind.FILESYSTEM.value)
        self._registered.add(SourceKind.OBJECT_STORE.value)
        self._registered.add(SourceKind.CONTENT_ADDRESSED.value)
    
    def register(self, source_kind: str):
        """Explicitly register a source class as authorized."""
        self._registered.add(source_kind)
    
    def is_authorized(self, source_kind: str) -> bool:
        """Check if a source kind is authorized for resolution."""
        if source_kind in self.PROHIBITED_SOURCES:
            return False
        return source_kind in self._registered


# ========================================
# Source Handlers
# ========================================

class FilesystemSourceHandler:
    """Handles FILESYSTEM source kind."""
    
    def __init__(self, authorized_root: str = None):
        if authorized_root is None:
            raise ValueError(
                "authorized_root must be explicitly specified. "
                "Refusing to default to filesystem root '/' — "
                "this would disable symlink escape protection. "
                "(ARCHER Finding 1: default authorized_root='/' "
                "made startswith('/') always True.)"
            )
        self.authorized_root = os.path.realpath(authorized_root)
    
    def resolve(self, source_locator: str) -> tuple:
        """
        Resolve a filesystem locator to bytes.
        
        Returns: (status, bytes_or_none, resolved_location_or_none, error_or_none)
        """
        # Parse locator: filesystem:<absolute_path>
        if not source_locator.startswith("filesystem:"):
            return (ResolutionStatus.ACCESS_DENIED.value, None, None, "Invalid locator format")
        
        path_str = source_locator[len("filesystem:"):]
        
        # INV-REF-001: Must be absolute path
        if not os.path.isabs(path_str):
            return (ResolutionStatus.ACCESS_DENIED.value, None, None, "Path must be absolute")
        
        # REF-006: Reject relative-path traversal
        if ".." in path_str:
            return (ResolutionStatus.ACCESS_DENIED.value, None, None, "Path traversal rejected")
        
        # Resolve real path
        real_path = os.path.realpath(path_str)
        
        # REF-005: Check symlink doesn't escape authorized root
        if not real_path.startswith(self.authorized_root):
            return (ResolutionStatus.ACCESS_DENIED.value, None, None, "Symlink escapes authorized root")
        
        # REF-001: Check existence
        if not os.path.exists(real_path):
            return (ResolutionStatus.NOT_FOUND.value, None, real_path, "File does not exist")
        
        # REF-004: Must be a file, not a directory
        if os.path.isdir(real_path):
            return (ResolutionStatus.UNREADABLE.value, None, real_path, "Path is a directory, not a file")
        
        # Read bytes
        try:
            with open(real_path, 'rb') as f:
                data = f.read()
            return (ResolutionStatus.RESOLVED.value, data, real_path, None)
        except PermissionError:
            return (ResolutionStatus.ACCESS_DENIED.value, None, real_path, "Permission denied")
        except IOError as e:
            # REF-001 / READ_ERROR: partial read or other IO error
            return (ResolutionStatus.READ_ERROR.value, None, real_path, str(e))
        except Exception as e:
            return (ResolutionStatus.READ_ERROR.value, None, real_path, str(e))


class ContentAddressedSourceHandler:
    """Handles CONTENT_ADDRESSED source kind (hash-keyed store)."""
    
    def __init__(self):
        self._store = {}  # hash -> bytes mapping (simulated CAS)
    
    def put(self, sha256_hash: str, data: bytes):
        """Add bytes to the content-addressed store."""
        self._store[sha256_hash] = data
    
    def resolve(self, source_locator: str) -> tuple:
        """
        Resolve a content-addressed locator to bytes.
        Format: contentaddr:<store_id>:sha256:<hash>
        """
        if not source_locator.startswith("contentaddr:"):
            return (ResolutionStatus.ACCESS_DENIED.value, None, None, "Invalid locator format")
        
        parts = source_locator.split(":", 3)
        if len(parts) != 4 or parts[2] != "sha256":
            return (ResolutionStatus.ACCESS_DENIED.value, None, None, "Invalid content-addressed format")
        
        hash_key = parts[3]
        
        if hash_key not in self._store:
            return (ResolutionStatus.NOT_FOUND.value, None, None, "Hash not found in CAS")
        
        data = self._store[hash_key]
        return (ResolutionStatus.RESOLVED.value, data, source_locator, None)


# ========================================
# The Resolver
# ========================================

class ArtifactResolver:
    """
    Persistent Artifact Resolver.
    
    INV-CUSTODY-001: The resolver does NOT promote custody. It produces
    resolution evidence. The epistemic layer makes custody determinations.
    
    The resolver's interface makes this structurally obvious:
        resolve() → ResolutionResult
    
    NOT:
        resolve() → VERIFIED Artifact
    """
    
    def __init__(self, resolver_identity: str = "resolver-001",
                 authorized_root: str = None):
        self.resolver_identity = resolver_identity
        self.registry = AuthorizedSourceRegistry()
        self.fs_handler = FilesystemSourceHandler(authorized_root)
        self.cas_handler = ContentAddressedSourceHandler()
    
    def register_cas_entry(self, sha256_hash: str, data: bytes):
        """Register bytes in the content-addressed store (for testing)."""
        self.cas_handler.put(sha256_hash, data)
    
    def resolve(self, artifact_ref: ArtifactRef) -> ResolutionResult:
        """
        Resolve an artifact reference to observed bytes.
        
        Returns ResolutionResult — evidence for the epistemic layer.
        NEVER returns a custody state. NEVER mutates the artifact_ref.
        NEVER mutates custody state.
        
        The resolution pipeline:
            1. Check authorization (INV-REF-003)
            2. Traverse authorized source
            3. Read complete bytes
            4. Compute byte_size independently
            5. Compute SHA-256 independently
            6. Compare to declared identity
            7. Emit evidence
        """
        now = time.time()
        millis = int((now - int(now)) * 1000)
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.", time.gmtime(now)) + f"{millis:03d}Z"
        evidence_id = f"ev-{uuid.uuid4().hex[:12]}"
        
        # Step 1: Check authorization
        if not self.registry.is_authorized(artifact_ref.source_kind):
            return ResolutionResult(
                artifact_ref=artifact_ref,
                resolution_status=ResolutionStatus.ACCESS_DENIED.value,
                source=artifact_ref.source_kind,
                resolved_location=None,
                observed_byte_size=None,
                observed_sha256=None,
                declared_sha256=artifact_ref.declared_sha256,
                declared_byte_size=artifact_ref.declared_byte_size,
                identity_match=IdentityMatch.NOT_APPLICABLE.value,
                observed_at=timestamp,
                resolver_identity=self.resolver_identity,
                evidence_id=evidence_id,
            )
        
        # Step 2: Traverse authorized source
        status, data, resolved_loc, error = self._traverse_source(artifact_ref)
        
        # Steps 3-7: If resolution failed, return evidence of failure
        if status != ResolutionStatus.RESOLVED.value:
            return ResolutionResult(
                artifact_ref=artifact_ref,
                resolution_status=status,
                source=artifact_ref.source_kind,
                resolved_location=resolved_loc,
                observed_byte_size=None,
                observed_sha256=None,
                declared_sha256=artifact_ref.declared_sha256,
                declared_byte_size=artifact_ref.declared_byte_size,
                identity_match=IdentityMatch.NOT_APPLICABLE.value,
                observed_at=timestamp,
                resolver_identity=self.resolver_identity,
                evidence_id=evidence_id,
            )
        
        # Step 4: Compute byte_size independently
        observed_byte_size = len(data)
        
        # Step 5: Compute SHA-256 independently
        observed_sha256 = hashlib.sha256(data).hexdigest()
        
        # Step 6: Compare to declared identity
        # The comparison distinguishes RESOLVED + MISMATCH from RESOLVED + MATCH
        # This is the L1 lesson: "I found something" ≠ "I found the artifact you claimed"
        size_matches = (observed_byte_size == artifact_ref.declared_byte_size)
        hash_matches = (observed_sha256 == artifact_ref.declared_sha256)
        
        if size_matches and hash_matches:
            identity_match = IdentityMatch.MATCH.value
        else:
            identity_match = IdentityMatch.MISMATCH.value
        
        # Step 7: Emit evidence (NOT a custody verdict)
        return ResolutionResult(
            artifact_ref=artifact_ref,
            resolution_status=ResolutionStatus.RESOLVED.value,
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
    
    def _traverse_source(self, artifact_ref: ArtifactRef) -> tuple:
        """Dispatch to the appropriate source handler."""
        if artifact_ref.source_kind == SourceKind.FILESYSTEM.value:
            return self.fs_handler.resolve(artifact_ref.source_locator)
        elif artifact_ref.source_kind == SourceKind.CONTENT_ADDRESSED.value:
            return self.cas_handler.resolve(artifact_ref.source_locator)
        elif artifact_ref.source_kind == SourceKind.OBJECT_STORE.value:
            # Not implemented in this minimal resolver
            return (ResolutionStatus.NOT_FOUND.value, None, None, "Object store not configured")
        elif artifact_ref.source_kind == SourceKind.DEPLOYMENT_ADMITTED.value:
            return (ResolutionStatus.NOT_FOUND.value, None, None, "Deployment-admitted source not configured")
        else:
            return (ResolutionStatus.ACCESS_DENIED.value, None, None, f"Unknown source kind: {artifact_ref.source_kind}")
    
    # ========================================
    # Custody promotion is NOT here.
    # The resolver does not have a promote() method.
    # The resolver does not have a verify() method.
    # The resolver does not have a freeze() method.
    # The resolver produces evidence. Period.
    # ========================================


# ========================================
# Independent Verifier (epistemic layer)
# ========================================

class IndependentVerifier:
    """
    Consumes ResolutionResult evidence and makes custody determinations.
    
    This is the epistemic layer — separate from the resolver.
    Only this layer can promote custody state.
    """
    
    @staticmethod
    def evaluate(result: ResolutionResult) -> str:
        """
        Evaluate resolution evidence and return a custody verdict.
        
        Returns: UNVERIFIED | FAILED | ELIGIBLE_FOR_VERIFIED
        
        ELIGIBLE_FOR_VERIFIED means the evidence supports promotion,
        but promotion is a separate act (receipt emission + chain verification).
        """
        if result.resolution_status == ResolutionStatus.NOT_FOUND.value:
            return "UNVERIFIED"
        
        if result.resolution_status == ResolutionStatus.ACCESS_DENIED.value:
            return "UNVERIFIED"
        
        if result.resolution_status == ResolutionStatus.UNREADABLE.value:
            return "UNVERIFIED"
        
        if result.resolution_status == ResolutionStatus.READ_ERROR.value:
            return "UNVERIFIED"
        
        if result.resolution_status == ResolutionStatus.RESOLVED.value:
            if result.identity_match == IdentityMatch.MATCH.value:
                return "ELIGIBLE_FOR_VERIFIED"
            elif result.identity_match == IdentityMatch.MISMATCH.value:
                return "FAILED"
            else:
                return "UNVERIFIED"
        
        return "UNVERIFIED"
    
    @staticmethod
    def can_promote(result: ResolutionResult) -> bool:
        """
        Check if custody promotion is permitted.
        
        INV-CUSTODY-001: Promotion requires:
          - Resolve(a.location) = bytes
          - len(bytes) = a.byte_size
          - SHA256(bytes) = a.sha256
          - verification is independent
        """
        if result.resolution_status != ResolutionStatus.RESOLVED.value:
            return False
        
        if result.identity_match != IdentityMatch.MATCH.value:
            return False
        
        if result.observed_sha256 is None or result.observed_byte_size is None:
            return False
        
        # Independent recomputation check
        if result.observed_sha256 != result.declared_sha256:
            return False
        
        if result.observed_byte_size != result.declared_byte_size:
            return False
        
        return True
