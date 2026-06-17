# E2E Test Suite Executable Summary Report

Date executed: 2026-06-17 21:41:29
Mock script path: `python_test/proses_adjustment_pajak.py`

## Performance Dashboard

| Metrics | Value |
|---|---|
| **Total Test Cases** | 52 |
| **Passed Cases** | 52 |
| **Failed Cases** | 0 |
| **Pass Rate** | 100.00% |

## Tier Summary

- **Tier 1 (Feature Coverage)**: Passed 21 / 21
- **Tier 2 (Boundary/Edge)**: Passed 21 / 21
- **Tier 3 (Combination)**: Passed 5 / 5
- **Tier 4 (Real-world Scenarios)**: Passed 5 / 5

## Detailed Test Log

| ID | Tier | Category | Description | Status | Message |
|---|---|---|---|---|---|
| TC-T1-01 | Tier 1 | Feature Coverage - Reduction | Basic reduction: exact match of target. Reduces Sabun by 2 qty, removing its row. | ✅ PASS | Passed |
| TC-T1-02 | Tier 1 | Feature Coverage - Reduction | Basic reduction: qty > 1 decreased. Sabun reduced from 3 to 1. | ✅ PASS | Passed |
| TC-T1-03 | Tier 1 | Feature Coverage - Reduction | Scanning order bottom-to-top. Items closer to the bottom are cut first. | ✅ PASS | Passed |
| TC-T1-04 | Tier 1 | Feature Coverage - Reduction | Anti-Struk Kosong: cannot delete the only item in a receipt. | ✅ PASS | Passed |
| TC-T1-05 | Tier 1 | Feature Coverage - Reduction | Deleting item row when quantity is reduced to 0. | ✅ PASS | Passed |
| TC-T1-06 | Tier 1 | Feature Coverage - Reduction | Decreasing quantity without row deletion because qty remains > 0. | ✅ PASS | Passed |
| TC-T1-07 | Tier 1 | Feature Coverage - Reduction | Multiple items reduced in a single invoice to meet reduction target. | ✅ PASS | Passed |
| TC-T1-08 | Tier 1 | Feature Coverage - Reduction | Accumulating remainder to global_gap when exact reduction is impossible. | ✅ PASS | Passed |
| TC-T1-09 | Tier 1 | Feature Coverage - Addition | Addition: Exact value matches and pulls Baju from savings. | ✅ PASS | Passed |
| TC-T1-10 | Tier 1 | Feature Coverage - Addition | Addition from savings: pulls partial quantity of savings (2 out of 5 Baju). | ✅ PASS | Passed |
| TC-T1-11 | Tier 1 | Feature Coverage - Addition | Addition: pulls closest possible below target. Target is 15000, draws 1 Baju (10000). | ✅ PASS | Passed |
| TC-T1-12 | Tier 1 | Feature Coverage - Addition | Fictional injection: savings empty. Increases Baju qty in receipt by 2. | ✅ PASS | Passed |
| TC-T1-13 | Tier 1 | Feature Coverage - Addition | Fictional injection: savings empty. Invents new item Sabun x3 from master barang. | ✅ PASS | Passed |
| TC-T1-14 | Tier 1 | Feature Coverage - Addition | Addition: Drains available savings Baju x1 and inserts fictional Sabun x9. | ✅ PASS | Passed |
| TC-T1-15 | Tier 1 | Feature Coverage - Addition | Addition uses latest master price instead of historical transaction values. | ✅ PASS | Passed |
| TC-T1-16 | Tier 1 | Feature Coverage - Addition | Savings record is fully deleted from tabungan_dan_hutang when remaining qty is 0. | ✅ PASS | Passed |
| TC-T1-17 | Tier 1 | Feature Coverage - Global Gap | Global gap positive distribution: remaining reduction gap distributed to other invoice. | ✅ PASS | Passed |
| TC-T1-18 | Tier 1 | Feature Coverage - Global Gap | Global gap negative distribution (addition matching & remainder). | ✅ PASS | Passed |
| TC-T1-19 | Tier 1 | Feature Coverage - Global Gap | Tolerable minor gap is ignored without executing further reductions. | ✅ PASS | Passed |
| TC-T1-20 | Tier 1 | Feature Coverage - Self-Healing | Self-healing on reduction: reduces existing debt record instead of adding savings. | ✅ PASS | Passed |
| TC-T1-21 | Tier 1 | Feature Coverage - Self-Healing | Self-healing on reduction: completely clears/deletes existing debt record. | ✅ PASS | Passed |
| TC-T2-01 | Tier 2 | Boundary/Edge - Zero & Empty Values | Target adjustment is 0%, no database changes should occur. | ✅ PASS | Passed |
| TC-T2-02 | Tier 2 | Boundary/Edge - Zero & Empty Values | Zero sales in targeted month, script executes without crashing. | ✅ PASS | Passed |
| TC-T2-03 | Tier 2 | Boundary/Edge - Zero & Empty Values | Transaction row has quantity=0. Ignored/skipped for adjustment. | ✅ PASS | Passed |
| TC-T2-04 | Tier 2 | Boundary/Edge - Zero & Empty Values | Empty tabungan during addition. Triggers fictional injection. | ✅ PASS | Passed |
| TC-T2-05 | Tier 2 | Boundary/Edge - Zero & Empty Values | Product in tabungan is missing in Master BARANG. System skips it without crashing. | ✅ PASS | Passed |
| TC-T2-06 | Tier 2 | Boundary/Edge - Single Item Receipts | Single item with qty=1 under reduction. Skipped to prevent empty invoice. | ✅ PASS | Passed |
| TC-T2-07 | Tier 2 | Boundary/Edge - Single Item Receipts | Single item with qty>1 under reduction. Allowed to reduce up to qty=1. | ✅ PASS | Passed |
| TC-T2-08 | Tier 2 | Boundary/Edge - Maximum/Extreme Values | 99% reduction target: must retain at least one item row with qty 1. | ✅ PASS | Passed |
| TC-T2-09 | Tier 2 | Boundary/Edge - Maximum/Extreme Values | 500% addition target: handles injecting massive quantity of fictional items. | ✅ PASS | Passed |
| TC-T2-10 | Tier 2 | Boundary/Edge - Maximum/Extreme Values | Max integer qty: reduces successfully without integer overflow or crash. | ✅ PASS | Passed |
| TC-T2-11 | Tier 2 | Boundary/Edge - Maximum/Extreme Values | Very high item price (1 billion) in Master is skipped for addition because it exceeds target. | ✅ PASS | Passed |
| TC-T2-12 | Tier 2 | Boundary/Edge - Maximum/Extreme Values | Very low item price (Rp 1) matching target. Draws large quantity (1000) of cheap item. | ✅ PASS | Passed |
| TC-T2-13 | Tier 2 | Boundary/Edge - Receipt Details & Constraints | Multiple items with qty=1 under reduction. Lowest item(s) cut, topmost PPN item kept. | ✅ PASS | Passed |
| TC-T2-14 | Tier 2 | Boundary/Edge - Receipt Details & Constraints | Negative qty in tabungan: script auto-corrects to absolute value during execution. | ✅ PASS | Passed |
| TC-T2-15 | Tier 2 | Boundary/Edge - Receipt Details & Constraints | Purchasing tables (DBELI and DRBELI) must never be modified by the script. | ✅ PASS | Passed |
| TC-T2-16 | Tier 2 | Boundary/Edge - Receipt Details & Constraints | Sales returns (DRJUAL) presence affects target calculation (target = net sales). | ✅ PASS | Passed |
| TC-T2-17 | Tier 2 | Boundary/Edge - Receipt Details & Constraints | Non-PPN items (Lain-lain, PAJAK=0) are ignored and not cut during reduction. | ✅ PASS | Passed |
| TC-T2-18 | Tier 2 | Boundary/Edge - Receipt Details & Constraints | BTKP items (PAJAK=2) are ignored and never selected for reduction. | ✅ PASS | Passed |
| TC-T2-19 | Tier 2 | Boundary/Edge - Receipt Details & Constraints | Addition skips non-PPN items in tabungan and injects fictional PPN item. | ✅ PASS | Passed |
| TC-T2-20 | Tier 2 | Boundary/Edge - Receipt Details & Constraints | Invoice with only non-PPN/BTKP items under reduction: skipped, gap accumulated. | ✅ PASS | Passed |
| TC-T2-21 | Tier 2 | Boundary/Edge - Receipt Details & Constraints | Invoice with only non-PPN items under addition. Baju (PPN) is successfully added. | ✅ PASS | Passed |
| TC-T3-01 | Tier 3 | Combination - Sequences | Reduction in first invoice generates savings, which is then drawn to add to second invoice. | ✅ PASS | Passed |
| TC-T3-02 | Tier 3 | Combination - Sequences | Reduction targets 15000. INV01 has 2 Baju, gets reduced by 1. excess 5000 goes to global_gap. | ✅ PASS | Passed |
| TC-T3-03 | Tier 3 | Combination - Sequences | Addition target 10000: draws 3 Sabun (3000) from savings, then injects fictional Sabun x7 (7000). | ✅ PASS | Passed |
| TC-T3-04 | Tier 3 | Combination - Sequences | Invoice has Buku (BTKP) and Baju (PPN). Baju is cut, receipt left with only Buku (valid). | ✅ PASS | Passed |
| TC-T3-05 | Tier 3 | Combination - Sequences | Addition target creates negative global gap distributed, triggering self-healing of debt. | ✅ PASS | Passed |
| TC-T4-01 | Tier 4 | Real-world - Month Scenarios | Surplus Month (High Sales, Low Tax Target): high-volume reductions with multiple invoices. | ✅ PASS | Passed |
| TC-T4-02 | Tier 4 | Real-world - Month Scenarios | Deficit Month: uses active savings to add PPN items to multiple transactions. | ✅ PASS | Passed |
| TC-T4-03 | Tier 4 | Real-world - Month Scenarios | Deficit Month with empty savings: triggers fictional injections (debts) across multiple invoices. | ✅ PASS | Passed |
| TC-T4-04 | Tier 4 | Real-world - Month Scenarios | Fluctuating month: reductions heal previous debts from multiple products. | ✅ PASS | Passed |
| TC-T4-05 | Tier 4 | Real-world - Month Scenarios | End-of-Year: mixed PPN/Non-PPN reconciliation ensures only PPN items are adjusted. | ✅ PASS | Passed |
