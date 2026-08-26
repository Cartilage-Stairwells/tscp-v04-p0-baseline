# RFC-R1 Correction Record

**Date:** 2026-08-26
**Authority:** Aria (via Sean)
**Status:** APPLIED

## Finding

The canonical serialization specification (P0-CANONICAL-SERIALIZATION-SPEC-001) originally cited an incorrect RFC for JSON escaping rules. The correct references are:

- **JSON Data Interchange Format** (for base JSON syntax)
- **JSON Canonicalization Scheme (JCS)** — RFC 8785 (for canonical escaping)

The error was found in three files:
1. `P0-CANONICAL-SERIALIZATION-SPEC-001.md` (spec)
2. `P0-RESOLVER-SPEC-001.md` (resolver spec, §6)
3. `canonical_serialization.py` (implementation comments)

## Correction Applied

All three files were corrected to reference the JSON Data Interchange Format and JCS (RFC 8785).

## Pre-correction hashes (for provenance)

| File | Pre-correction SHA-256 |
|------|----------------------|
| `P0-CANONICAL-SERIALIZATION-SPEC-001.md` | `34e60f9ab45be452416295bcfd6daac1596b9f2778bbfe51cdffcb90bb1115c0` |
| `P0-RESOLVER-SPEC-001.md` | `94d4eae9ba62f2c22973b71287079e582875fbd44743bb4b71ea005fe7c3fa9c` |
| `canonical_serialization.py` | `df50b89c62b26888e14279579abea88d92ed9e57b500da885a6865255c5e9962` |

## Post-correction hashes

| File | Post-correction SHA-256 |
|------|----------------------|
| `P0-CANONICAL-SERIALIZATION-SPEC-001.md` | `7dffb2b41af28fcb3921d6f04f2b0aa82c033e9dad066eb88ca5dd3e6888ff03` |
| `P0-RESOLVER-SPEC-001.md` | `a7d153ded976b30e5b28be8629846dabdb3addfd9158676961a28c1836026fe4` |
| `canonical_serialization.py` | `96e09e8bb115d3f091d9c819eac4209de182a52f9de817202b5fd3e8db86cf79` |

## Impact

The RFC reference error was present in spec comments and documentation. It did not affect the implementation's actual serialization behavior, which correctly implements JCS-compatible canonical serialization. The golden vectors (GV1-GV3) were revalidated after correction and remain byte-identical.

The pre-correction source files are preserved as historical artifacts (SHA-256 recorded above) but are not included in the frozen source tree to avoid confusion with supported implementations.
