# TSCP v0.4 P0 Baseline

**Status:** FROZEN
**Tag:** `v0.4-p0-resolver-baseline`
**Date:** 2026-08-26

This repository contains the frozen v0.4 P0 implementation baseline for the TSCP (Trusted Supply Chain Protocol) project. It has been independently verified by second implementations with zero production-code imports.

## What's in this repository

```
specs/           — Frozen P0 contracts (canonical serialization, artifact reference, resolver)
implementation/  — Production implementations (canonical_serialization.py, resolver.py)
independent/     — Independent verification implementations (zero production imports)
tests/           — Acceptance test suites and differential test harness
evidence/        — Persistent verification artifacts (IV-P0-001, IV-P0-002)
provenance/      — Freeze record, RFC-R1 correction, SHA-256 manifest
```

## Verification status

| Verification | Result |
|-------------|--------|
| IV-P0-001 (independent serialization) | PASS |
| IV-P0-002 (independent resolver, 15/15 differential) | PASS |
| Recursive custody | PASS |
| Corruption detection | PASS |
| Restoration | PASS |

## What is NOT in scope

- P1 (cryptographic receipts)
- P2 (transaction integrity / 2PC)
- Full v0.4 system
- Operational autonomous-system validation
- Formal proof of the entire implementation

## Running the tests

```bash
PYTHONPATH=implementation python3 tests/test_resolver.py
PYTHONPATH=implementation:independent python3 independent/independent_verification_harness.py
PYTHONPATH=implementation python3 tests/recursive_custody_processing.py
PYTHONPATH=implementation:independent python3 tests/iv_p0_002_differential_test.py
```

All tests must pass from the repository root.


## Public release boundary

This repository is public for inspection and reproduction of the frozen P0 evidence boundary. Public visibility does not grant a license to reuse the code or artifacts. P1/P2 work, private correspondence, credentials, and operational material remain outside this repository.
