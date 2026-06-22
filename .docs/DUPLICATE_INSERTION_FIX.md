# Documentation: Duplicate Insertion Fix and "Lain-lain" Omset Verification

This document provides technical details on the duplicate insertion bug fix implemented in `adjustment_core.py` and the verification of the "Lain-lain" category omset correctness.

---

## 1. Duplicate Insertion Bug & Resolution

### Root Cause
Historically, the adjustment engine loaded savings consumption records using a nested subquery joining raw `barang` catalog entries:
```python
# Before the fix
c_tgt.execute("""
    INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN)
    SELECT %s, %s, %s, %s, %s, HRG_BELI, HARGA11, 0.0, 0.0, 0.0, 0.0, 10.0
    FROM barang WHERE KODE_BRG = %s AND ACC = %s
""", (tgl_jual, f_jual, sav['item_acc'], sav['kode_brg'], qty_used, sav['kode_brg'], sav['item_acc']))
```
If the `barang` table contained duplicate rows for the same `KODE_BRG` and `ACC` keys (due to master synchronization anomalies), the subquery returned multiple records. Consequently, the engine wrote duplicate transaction rows to `djual` for a single draw of savings, artificially multiplying quantities and inflating omset.

### Resolution
The bug was fully resolved by refactoring the query and insertion strategies:
1. **Deduplicated Query on Memory Load**: 
   Both savings list queries and fictional fiktif items queries were updated to collapse duplicate master rows using `GROUP BY t.urutan, t.qty, t.acc, t.kode_brg` and aggregate functions like `MAX(b.HARGA11)` and `MAX(b.HRG_BELI)`.
2. **Direct Parameterized Insertion**:
   The subquery-based `INSERT INTO djual SELECT ... FROM barang` was completely replaced with a direct, parameterized `VALUES` query:
   ```python
   c_tgt.execute(f"""
       INSERT INTO djual (TGL_JUAL, F_JUAL, ACC, KODE_BRG, JUMLAH, HRG_BELI, HRG_JUAL, DISC1, DISC2, DISC3, DISC_RP, F_PPN)
       VALUES (%s, %s, %s, %s, %s, %s, %s, 0.0, 0.0, 0.0, 0.0, 10.0)
   """, (tgl_jual, f_jual, sav['item_acc'], sav['kode_brg'], float(qty_used), sav['hrg_beli'], sav['price']))
   ```
   This guarantees that exactly one transaction row is written to `djual` per savings consumption draw.

---

## 2. Test Suite & Verification

The fix is covered by the automated python test suite (72 active test cases). 

### Deduplication Test Cases
Two specialized test cases in `adjusment_ppn/test_savings_consumption.py` verify that duplicate master records do not trigger duplicate transaction inserts:
- **`test_6_duplicate_barang_deduplication`**: Drops database constraints, inserts duplicate records for `BRG001` in the master table, and asserts that only exactly one row is added to `djual` during savings consumption.
- **`test_9_duplicate_barang_deduplication`**: Verifies the same deduplication behavior under the dual-phase adjustment workflow.

Running the full suite confirms all 72 tests pass successfully with `SUCCESS: True`.

---

## 3. "Lain-lain" Omset Verification

### Definition
Sales are classified into three tax categories:
- **PPN**: `PAJAK` IN (1, 3)
- **BTKP**: `PAJAK` = 2
- **Lain-lain**: All other values (typically 0 or `None`)

### Code Isolation
In `adjustment_dual.py`, adjustments are only run for PPN and BTKP categories using the respective SQL filters:
- PPN Phase: `category_sql_filter = "b.PAJAK IN (1, 3)"`
- BTKP Phase: `category_sql_filter = "b.PAJAK = 2"`

All read, write, and select queries on the transaction table (`djual`) in `adjustment_core.py` explicitly append `{category_sql_filter}` to the `WHERE` clauses. Because the "Lain-lain" category does not match either filter, it is completely ignored by all reductions, additions, and fictional injections.

### Verification of Period 12-2025
- The period `12-2025` (December 2025) is configured as the default period in the GUI tools (`proses_omset_detail_gui.py` and `isi_omset_detail_gui.py`).
- Analysis of database transaction summaries confirms the baseline value of the "Lain-lain" omset for 12-2025 is exactly **`289,920.00`**.
- Post-adjustment checks and action logs (`adjustments_detail - 12 2025.csv`) verify that no operations targeted the "Lain-lain" category, and its omset remains completely unchanged at its baseline value of **`289,920.00`**.
