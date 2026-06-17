# E2E Test Suite Ready

## Test Runner
- Command: `python adjusment_ppn/run_tests_via_python.py`
- Expected: all tests pass with exit code 0

## Coverage Summary
| Tier | Count | Description |
|------|------:|-------------|
| 1. Feature Coverage | 21 | Happy path coverage for Reduction, Addition, Global Gap, and Self-Healing |
| 2. Boundary & Corner | 21 | Boundary limits, zero values, extreme values, single items, constraints |
| 3. Cross-Feature | 5 | Combination sequence scenarios (e.g. Reduction -> Savings -> Addition) |
| 4. Real-World Application | 5 | Real-world month/year adjustment scenarios |
| **Total** | **52** | All 52 test cases from test_cases.py pass |

## Feature Checklist
| Feature | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---------|:------:|:------:|:------:|:------:|
| Reduction | 8 | 8 | ✓ | ✓ |
| Addition | 8 | 8 | ✓ | ✓ |
| Global Gap | 3 | 3 | ✓ | ✓ |
| Self-Healing | 2 | 2 | ✓ | ✓ |
