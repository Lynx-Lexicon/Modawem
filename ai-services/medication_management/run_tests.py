"""Automated test runner and verification suite for Modawem

Can be run with a single command:
    python run_tests.py
"""

import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent


def main() -> int:
    print("=" * 80)
    print("Modawem AI Engineering Tasks — Task 2: Medication Adherence (PDC & MPR)")
    print("Running Automated Test Suite & Acceptance Criteria Verification")
    print("=" * 80)

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(ROOT_DIR / "tests"), pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 80)
    print(f"Test Summary: Ran {result.testsRun} tests.")
    if result.wasSuccessful():
        print("STATUS: ALL TESTS PASSED SUCCESSFULLY! (100% SUCCESS)")
        print("=" * 80)
        return 0
    else:
        print(
            f"STATUS: FAILED ({len(result.failures)} failures, {len(result.errors)} errors)"
        )
        print("=" * 80)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
