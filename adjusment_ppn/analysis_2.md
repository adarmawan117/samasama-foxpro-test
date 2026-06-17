# Comprehensive Analysis Report: Dual-Database Refactoring (Milestone 1)

This report details the exploration of the database connections, CLI parsing, GUI structure, and test suites for the Dual-Database Refactoring project.

---

## 1. Backend Analysis (`proses_adjustment_pajak.py`)

### 1.1 Existing Database Connection Setup
The current database connection setup is managed in `get_db_connection` (lines 351–422) as follows:
- **Sandbox/SQLite Mode**: If `sandbox=True` (or if `--sandbox` is present in `sys.argv`), the script connects using `sqlite3.connect(database)`. It registers a custom mock implementation of MySQL's `DATE_FORMAT` function (`sqlite_date_format`) and wraps the connection in `SQLiteConnectionWrapper`.
- **MySQL Mode**: If `sandbox=False`, it attempts to load credentials from `db_config.py` (specifically `DBConfig.HOST`, `DBConfig.USER`, `DBConfig.PASSWORD`, `DBConfig.NAME`). If that fails, it falls back to: Host=`localhost`, User=`root`, Password=`root`, DB=`INVENTORY`.
- **Driver Selection**: It tries importing `pymysql` first; if not present, it falls back to `mysql.connector`. The connection is wrapped in `MySQLConnectionWrapper`.

### 1.2 CLI Arguments Parsing
Currently (lines 1310–1320), CLI arguments are parsed using `argparse`:
- `--db` (required): Path to SQLite database file or name of MySQL database.
- `--acc` (required): Account code.
- `--start-date` (required): Start date (YYYY-MM-DD).
- `--end-date` (required): End date (YYYY-MM-DD).
- `--target-ppn` (required, float): Target adjustment value.

### 1.3 Query Execution Mapping (Source vs. Target)
In the refactored dual-database model, queries must be partitioned between the **Source DB** (read-only original sales transactions) and the **Target DB** (read-write tax database where adjustments are applied). 

| Function | Query / Operation | Target Table | Type | Assigned DB | Rationale |
|---|---|---|---|---|---|
| `create_tabungan_dan_hutang_table` | `CREATE TABLE IF NOT EXISTS tabungan_dan_hutang` | `tabungan_dan_hutang` | WRITE | **Target DB** | Table holds adjustment states; must exist in Target. |
| `upsert_tabungan_dan_hutang` | `SELECT qty ... FROM tabungan_dan_hutang WHERE ...` | `tabungan_dan_hutang` | READ | **Target DB** | Checks current adjustment state. |
| `upsert_tabungan_dan_hutang` | `INSERT INTO tabungan_dan_hutang ...` / `UPDATE ...` | `tabungan_dan_hutang` | WRITE | **Target DB** | Writes adjustment state. |
| `settle_debt_with_savings` | `SELECT urutan ... FROM tabungan_dan_hutang WHERE ...` | `tabungan_dan_hutang` | READ | **Target DB** | Checks current savings state. |
| `settle_debt_with_savings` | `DELETE ...` / `UPDATE ...` | `tabungan_dan_hutang` | WRITE | **Target DB** | Adjusts savings state. |
| `proses_pengurangan_omset` | `SELECT COUNT(*) FROM drjual d JOIN barang b ...` | `drjual`, `barang` | READ | **Source DB** | Checks original sales returns. |
| `proses_pengurangan_omset` | `SELECT SUM(d.JUMLAH * d.HRG_JUAL) FROM djual ...` | `djual`, `barang` | READ | **Source DB** | Calculates original gross sales. |
| `proses_pengurangan_omset` | `SELECT d.TGL_JUAL, d.F_JUAL, d.KODE_BRG ... FROM djual ...` | `djual`, `barang` | READ | **Source DB** | Fetches original transactions to adjust. |
| `proses_pengurangan_omset` | `SELECT F_JUAL, COUNT(*) FROM djual ... GROUP BY F_JUAL` | `djual` | READ | **Source DB** | Analyzes original receipt item counts. |
| `proses_pengurangan_omset` | `DELETE FROM djual WHERE urutan = %s` | `djual` | WRITE | **Target DB** | Applies adjustments to Target. |
| `proses_pengurangan_omset` | `UPDATE djual SET jumlah = %s WHERE urutan = %s` | `djual` | WRITE | **Target DB** | Applies adjustments to Target. |
| `proses_penambahan_omset` | `SELECT TGL_JUAL, F_JUAL, KODE_BRG ... FROM djual ...` | `djual` | READ | **Source DB** | Gets original transactions for month. |
| `proses_penambahan_omset` | `SELECT urutan FROM djual WHERE ... KODE_BRG = %s` | `djual` | READ | **Target DB** | Checks if item already exists in Target's receipt. |
| `proses_penambahan_omset` | `UPDATE djual SET jumlah = jumlah + %s WHERE ...` | `djual` | WRITE | **Target DB** | Updates transaction quantity in Target. |
| `proses_penambahan_omset` | `INSERT INTO djual ... VALUES (...)` | `djual` | WRITE | **Target DB** | Injects new transaction in Target. |
| `proses_penambahan_omset` | `SELECT b.KODE_BRG, b.HRG_JUAL ... FROM barang b ...` | `barang` | READ | **Source DB** | Fetches master catalog details. |
| `proses_penambahan_omset` | `SELECT DISTINCT KODE_BRG FROM djual WHERE F_JUAL = %s` | `djual` | READ | **Target DB** | Gets unique codes in Target's active receipt. |
| `distribusikan_global_gap` | `SELECT d.TGL_JUAL ... FROM djual d JOIN barang b ...` | `djual`, `barang` | READ | **Source DB** | Fetches original transactions for distribution. |
| `distribusikan_global_gap` | `SELECT F_JUAL, COUNT(*) FROM djual GROUP BY F_JUAL` | `djual` | READ | **Source DB** | Checks original receipt counts. |
| `distribusikan_global_gap` | `SELECT DISTINCT TGL_JUAL, F_JUAL FROM djual WHERE ...` | `djual` | READ | **Source DB** | Selects candidate receipts from original data. |
| `distribusikan_global_gap` | `DELETE FROM djual ...` / `UPDATE djual ...` | `djual` | WRITE | **Target DB** | Distributes remaining gap on Target DB. |
| Main (Balancing Target PPN=0) | `SELECT TGL_JUAL, F_JUAL, COUNT(*) FROM djual GROUP BY ...` | `djual` | READ | **Source DB** | Analyzes original receipts. |
| Main (Balancing Target PPN=0) | `SELECT d.TGL_JUAL ... FROM djual d JOIN barang b ...` | `djual`, `barang` | READ | **Source DB** | Fetches candidate items to shift. |
| Main (Balancing Target PPN=0) | `DELETE FROM djual ...` / `UPDATE djual ...` / `INSERT INTO djual ...` | `djual` | WRITE | **Target DB** | Performs balancing operations on Target. |

---

## 2. Frontend Analysis (`proses_adjustment_pajak_gui.py`)

### 2.1 Existing GUI Structure
The GUI is structured as a `QMainWindow` utilizing a `QFormLayout` for parameter inputs:
- **Database Entry**: A single line input (`self.db_path_input`) with a "Browse..." button (`self.btn_browse`) connected to a file dialog.
- **Account Entry**: A combo box (`self.combo_acc`) populated dynamically on text change of `self.db_path_input` via `self.load_accounts`.
- **Date Range Entries**: `self.tgl_awal` and `self.tgl_akhir` QDateEdit elements.
- **Target Entry**: A validated line input (`self.target_ppn_input`) for target PPN adjustment.
- **Execution & Output**: `self.btn_proses` starts the calculation; progress logs are printed into `self.log_widget` (QListWidget) in real-time, and `self.btn_export` exports logs to a CSV.
- **Threading Model**: A `WorkerThread` (subclassing `QThread`) is spun up when clicking "Proses" to avoid freezing the GUI.

### 2.2 Proposed Dual-Database Layout & Design
The single "Database Path" row should be replaced by two distinct connection sections grouped inside `QGroupBox` elements:

#### Group 1: Source Database (Read-Only)
- `source_host_input` (QLineEdit, default: `localhost`)
- `source_port_input` (QLineEdit, default: `3306`)
- `source_user_input` (QLineEdit, default: `root`)
- `source_pass_input` (QLineEdit, default: `root`, echoMode: Password)
- `source_db_input` (QLineEdit, default: `INVENTORY_SOURCE` or `sandbox.db`)
- `btn_browse_source` (QPushButton, text "Browse...") - enabled for SQLite files.

#### Group 2: Target Database (Read-Write)
- `target_host_input` (QLineEdit, default: `localhost`)
- `target_port_input` (QLineEdit, default: `3306`)
- `target_user_input` (QLineEdit, default: `root`)
- `target_pass_input` (QLineEdit, default: `root`, echoMode: Password)
- `target_db_input` (QLineEdit, default: `INVENTORY_TARGET` or `sandbox.db`)
- `btn_browse_target` (QPushButton, text "Browse...") - enabled for SQLite files.

*Note on Backward Compatibility*: To prevent breaking existing test cases in `test_gui.py`, we should define aliases in the main application class pointing to the new fields:
```python
self.db_path_input = self.source_db_input
self.btn_browse = self.btn_browse_source
```

#### Group 3: Connection Testing Logic
- Add a new "Test Connection" button (`btn_test_conn`) next to the "Proses" button.
- Implement a background connection worker (`TestConnectionWorkerThread`) to test connections asynchronously, preventing PyQt GUI freezes.
- **Testing steps**:
  1. Retrieve credentials from Source and Target forms.
  2. Call `test_dual_connection(source_params, target_params, sandbox=is_sandbox)`.
  3. If successful, show `QMessageBox.information` ("Koneksi Sukses!") and trigger `self.load_accounts()` to populate the account list from the Source database.
  4. If failed, display the detailed error message via `QMessageBox.critical` (distinguishing source/target failures e.g., "Source DB gagal: <detail>").
- Ensure all GUI inputs (text boxes and buttons) are disabled during the connection test and re-enabled afterward.

---

## 3. Test Suite Impact Analysis

### 3.1 Impact on `test_infra.py` (E2E Tests)
- **CLI Command Construction (Line 220)**: The runner invokes the subprocess by passing `["--db", db_path]`. Since `--db` will be removed in favor of separate `--source-db` and `--target-db` parameters, this command builder will throw errors.
- **Adjustment Required**: Change line 220 in `test_infra.py` to:
  ```python
  cmd = [
      sys.executable,
      script_path,
      "--source-db", db_path,
      "--target-db", db_path,
      "--acc", tc['params']['--acc'],
      "--start-date", tc['params']['--start-date'],
      "--end-date", tc['params']['--end-date'],
      "--target-ppn", tc['params']['--target-ppn'],
      "--sandbox"
  ]
  ```
  Since the test runner operates on a single sandbox SQLite file (`db_path`), pointing both `--source-db` and `--target-db` to `db_path` replicates the E2E behavior perfectly while complying with the new parser requirements.

### 3.2 Impact on `test_gui.py` (GUI Tests)
Virtually every test case in `test_gui.py` is impacted because they interact with the single database input field `self.window.db_path_input`.

- **`test_1_form_components_exist` (Lines 163-192)**:
  - Currently asserts existence of `db_path_input` and `btn_browse`.
  - **Impact**: Will fail if these elements are removed or renamed.
  - **Adjustment**: Assert the existence of both Source and Target input parameters (Host, Port, User, Password, DB Name, and Browse buttons) and the new "Test Connection" button.
- **`test_2_load_accounts_on_db_change` (Lines 193-203)**:
  - Updates `db_path_input` and checks if accounts are populated.
  - **Impact**: Will fail if `db_path_input` does not trigger account loading, or if the target connection is unconfigured and throws an error.
  - **Adjustment**: Test that updating the Source DB path triggers `load_accounts` (or that a successful test connection populates the combo box).
- **`test_3_state_management_multithreading_and_logging` (Lines 204-256)** and **`test_4_csv_export_operation` (Lines 257-302)**:
  - Both verify input locking state and process execution by filling `db_path_input`.
  - **Impact**: If only source is configured, WorkerThread might fail to instantiate the target connection.
  - **Adjustment**: Update tests to set both Source DB and Target DB inputs. Verify that all fields in both the Source and Target database groups are disabled during execution and re-enabled afterward.
- **`test_5_stale_accounts_cleared_on_invalid_db` (Lines 303-317)**:
  - Verifies account combo is cleared on invalid DB.
  - **Impact**: Needs to target the new Source DB path input.
- **`test_6_database_casing_support` (Lines 318-335)**:
  - Verifies uppercase extension support on `db_path_input`.
  - **Impact**: Needs to target the new Source DB path input.
- **`test_7_remote_mysql_bypass` (Lines 336-358)**:
  - Bypasses local file checks when the input is a MySQL database name.
  - **Impact**: Must be refactored to set both Source and Target DB names and mock connection calls for both configurations.
