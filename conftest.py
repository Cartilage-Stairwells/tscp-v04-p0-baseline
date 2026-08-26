"""
Path setup for P0 tests. Run all tests from the repository root.

    python3 tests/test_resolver.py
    python3 independent/independent_verification_harness.py
    python3 tests/recursive_custody_processing.py
    python3 tests/iv_p0_002_differential_test.py
"""
import os
import sys

# Determine repo root (parent of this file's directory)
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# Add implementation/ and independent/ to Python path
sys.path.insert(0, os.path.join(REPO_ROOT, "implementation"))
sys.path.insert(0, os.path.join(REPO_ROOT, "independent"))

# Make path constants available
EVIDENCE_DIR = os.path.join(REPO_ROOT, "evidence")
SPECS_DIR = os.path.join(REPO_ROOT, "specs")
IMPLEMENTATION_DIR = os.path.join(REPO_ROOT, "implementation")
INDEPENDENT_DIR = os.path.join(REPO_ROOT, "independent")
TESTS_DIR = os.path.join(REPO_ROOT, "tests")
