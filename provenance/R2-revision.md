# R2 Revision Record: runnable verification commands

**Repository:** `Cartilage-Stairwells/tscp-v04-p0-baseline`
**Base freeze:** tag `v0.4-p0-resolver-baseline` at `cfc56a405e59b6f4dd8295886ee48a1a160087c2`
**Revision purpose:** repair the verification runbook and stale status text without changing the P0 specifications or production resolver behavior.

## Changes

- The README now supplies the `PYTHONPATH` required by the standalone test scripts.
- The IV-P0-002 harness resolves implementation paths relative to the repository instead of the caller's working directory.
- The recursive-custody status output now reflects the already-recorded IV-P0-002 independent resolver verification.
- No P1/P2 work, specification change, or production implementation change is introduced.

## Acceptance

From the repository root, all commands in `README.md` must exit successfully:

```sh
PYTHONPATH=implementation python3 tests/test_resolver.py
PYTHONPATH=implementation:independent python3 independent/independent_verification_harness.py
PYTHONPATH=implementation python3 tests/recursive_custody_processing.py
PYTHONPATH=implementation:independent python3 tests/iv_p0_002_differential_test.py
sha256sum -c provenance/SHA256SUMS
```

The frozen baseline tag remains immutable. This is an explicit maintenance
revision with its own commit and manifest update, not a silent modification of
that tag.
