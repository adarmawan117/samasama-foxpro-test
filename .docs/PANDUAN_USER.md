# Operational Guide: Sales Transactions PPN Adjustment System (PANDUAN_USER.md)

This operational manual is designed for developers, operators, and database administrators. It describes how to configure the environment, run the GUI application, execute automated tests, and troubleshoot common deployment issues.

---

## 1. Environment Setup

The application is built using Python 3.12 (compatible with Python 3.8+) and PyQt5. Follow these steps to prepare your local workspace:

### 1.1 Create and Activate a Virtual Environment
It is recommended to run the application in a local virtual environment (`venv`) to avoid dependency conflicts:
```powershell
# Navigate to the project root directory
cd c:\Users\adarmawan117\Downloads\UndfxffAllW\RESULTS

# Create the virtual environment
python -m venv python_test/venv

# Activate the virtual environment
.\python_test\venv\Scripts\Activate.ps1
```

### 1.2 Install Required Dependencies
With the virtual environment activated, install the required packages using the project's `requirements.txt`:
```powershell
pip install -r python_test/requirements.txt
```

The system relies on the following packages:
- `PyMySQL==1.2.0` (For MySQL database driver connectivity)
- `PyQt5==5.15.11` (For user interface layout and event binding)
- `PyQt5-Qt5==5.15.2` (Core Qt5 libraries)
- `PyQt5_sip==12.18.0` (C/C++ binding wrapper)

---

## 2. Database Connection Configuration

The system requires two database connections:
1. **Source DB (Database Asal)**: The read-only repository containing original transactions.
2. **Target DB (Database Target Pajak)**: The destination database where adjustments will be applied.

### 2.1 Connection Modes
The application dynamically detects the database type based on the input string:
- **SQLite Sandbox Mode**: Triggers if the database path ends with `.db` or `.sqlite`. Useful for local testing and development. No hostname, port, or user credentials are required; users can select files using the **Browse** buttons.
- **Production MySQL Mode**: Triggers if the database input is a standard database name without a file extension. The application uses the hostname, port, username, and password fields to connect.

### 2.2 MySQL Configuration Parameters
Default MySQL configuration parameters are defined in `python_test/db_config.py`. Update these parameters to match your local server environment:
```python
class DBConfig:
    HOST = 'localhost'
    USER = 'root'
    PASSWORD = 'your_mysql_password'
    NAME = 'INVENTORY'
```

---

## 3. Launching and Running the GUI

### 3.1 Start the Application
Run the GUI entry point script from the root directory:
```powershell
python python_test/run_gui.py
```

### 3.2 Workflow in the GUI
1. **Configure Connections**:
   - For SQLite: Click **Browse** for both Source and Target databases and select the respective database files.
   - For MySQL: Enter the Host, Port, User, and Password details, then enter the database names in the Source and Target fields.
2. **Test Database Connections**:
   - Click the **Test Connection** button.
   - The application will attempt to connect to both databases.
   - **Auto-Save Settings**: Upon a successful connection test, the application automatically saves your connection settings (host, port, user, password, database) into `connection_settings.json`. These settings will be automatically loaded the next time you open the application.
   - If the Target Database is missing, the application will display a warning: **"Database Target belum ada. Apakah Anda ingin melanjutkan dengan mengkloning saat proses berjalan?"**
   - Click **Yes** to authorize the system to clone the database structure and initial transactions from the Source DB when the adjustment is started. **Note:** Clicking Yes will also automatically trigger the Auto-Save Settings feature.
3. **Select Account & Target Parameters**:
   - After a successful connection test, the account dropdown menu will populate with accounts retrieved from the source `accinv` table. If the `accinv` table is empty or missing, the system will fallback to fetching distinct active accounts directly from the `barang` table (ensuring `A1` and `A3` are always available). You can select a specific branch or the "ALL - A1 & A3 (Gabungan)" option.
   - If "ALL" is chosen, the single Target PPN you enter will be proportionally deducted/added across the combined total omset of both A1 and A3.
   - This "ALL" mode activates the **Silang Subsidi (Cross-Pollination)** feature: any leftover deductions (savings) from A1 can be automatically used to cover additions in A3, and vice versa.
   - Define the start and end dates for the adjustment range using the date widgets.
   - Enter the target PPN (tax value) to achieve in the target database.
4. **Jalankan Proses (Execute Adjustment)**:
   - Click the **Proses** button. The application locks input controls and displays an indeterminate progress bar.
   - **Idempotency Check**: If transactions already exist in the target database within the specified date range, the application displays a confirmation prompt: **"Konfirmasi Rerun. Apakah Anda ingin melakukan rollback dan menulis ulang data transaksi pada rentang tanggal tersebut?"**
   - Click **Yes** to execute a full rollback of the ledger tables (`tabungan_dan_hutang` and `log_mutasi_tabungan`), purge existing target transactions, re-synchronize clean raw data from the Source DB, and run the adjustment.
5. **Export Log details**:
   - When the process completes, the UI displays the final remaining gap (rounding remainder).
   - The **Export** button becomes active. Click it to save the action logs to a CSV file (e.g., `adjustments_detail.csv`). If you processed the "ALL" batch, the log entries will include a prefix like `[A1]` or `[A3]` to indicate the origin branch.

---

## 4. Running the Automated Tests

The testing framework includes 63 test cases covering GUI layouts, SQL translations, rollback logic, and stress scenarios.

### 4.1 Execute the Test Runner
Run the test runner from the root directory:
```powershell
python python_test/adjusment_ppn/run_tests_via_python.py
```

### 4.2 How the Test Runner Operates
- **Headless Mode**: The test runner sets `os.environ["QT_QPA_PLATFORM"] = "offscreen"`. This prevents PyQt5 from attempting to initialize physical graphics buffers, allowing tests to run in terminal-only environments.
- **Dynamic Database Sandboxing**: The testing framework creates temporary SQLite databases for each test, runs DDL schema migrations, seeds test data, invokes the CLI backend (`python_test/run_proses_adjustment.py`), and verifies output tables.
- **Logs**: Detailed test results are saved to `python_test/test_run_results.txt`.

---

## 5. Troubleshooting

### 5.1 Python UDF Registration Issue in SQLite
- **Symptom**: SQL statements containing `DATE_FORMAT` fail with the error: `no such function: DATE_FORMAT`.
- **Cause**: SQLite does not support MySQL's native date formatting functions.
- **Solution**: The application must register `sqlite_date_format` on the SQLite connection before running queries. In your code, verify that:
  ```python
  conn = sqlite3.connect(db_path)
  conn.create_function("DATE_FORMAT", 2, sqlite_date_format)
  ```

### 5.2 Database Locked Error (`sqlite3.OperationalError: database is locked`)
- **Symptom**: Write operations fail with a timeout or lock warning in SQLite.
- **Cause**: SQLite only allows one active write transaction at a time. Concurrently running processes or uncommitted transactions lock the database file.
- **Solution**:
  - Ensure all database cursor contexts are enclosed in `try...finally` blocks or context managers.
  - Verify that `connection.commit()` or `connection.rollback()` is executed at the end of every transaction.
  - Close connections when they are no longer needed, especially before spawning new background threads.

### 5.3 PyQt5 Headless/Offscreen Issues on Windows
- **Symptom**: Test runner fails immediately with a Qt platform plugin error.
- **Cause**: The system lacks display drivers or the offscreen platform is not configured correctly.
- **Solution**: Ensure `os.environ["QT_QPA_PLATFORM"] = "offscreen"` is set at the very beginning of the script, before importing any PyQt5 modules.

### 5.4 Access Violation (0xC0000005) on Test Suite Exit
- **Symptom**: The automated test suite executes all tests successfully, writes `SUCCESS: True` to `test_run_results.txt`, but exits with code `1` or crashes with `0xC0000005`.
- **Cause**: This is a known PyQt5 garbage-collection limitation on Windows. When the Python interpreter exits and unloads modules, C++ QObjects that were not deleted explicitly attempt to access deallocated memory.
- **Solution**:
  - This crash occurs during interpreter shutdown *after* all tests have run and logs have been saved. You can verify successful execution by checking the final lines of `python_test/test_run_results.txt` for the line: `SUCCESS: True`.

### 5.5 High CPU Utilization During Adjustment
- **Symptom**: The CPU usage spikes to ~70% when pressing the "Proses" button.
- **Cause**: The application is utilizing the new Multithreading Architecture (via `ThreadPoolExecutor`) to drastically reduce the adjustment time.
- **Solution**: This is expected behavior. The application intelligently caps CPU usage at 70% to ensure your operating system remains responsive for other tasks.

---

## 6. A1 Priority Business Rule for Savings

To manage shared inventory and tax liabilities between retail and wholesale channels, the tool enforces the **A1 Priority Business Rule** for the savings (`tabungan_dan_hutang`) system:

### 6.1 Priority Behavior
- Before recording a savings deposit (`tambah`), a debt entry (`kurang`), or performing a fictional injection from savings, the system checks the master `barang` table for the product code (`KODE_BRG`).
- If the product exists under account `A1`, the savings mutation is recorded under `ACC = 'A1'`, even if the current transaction being processed belongs to another account (e.g. grosir `A3`).
- If the product does not exist under `A1` in the master table, the system falls back to using the transaction's original account (e.g., `A3`).

### 6.2 Rollback Behavior
- When a rollback is performed for a target account (e.g., `A3`), the rollback engine queries the master `barang` table to identify which products of that account are redirected to `A1`.
- The engine then restores the consumed savings logs and deletes newly created savings/debt records for both the target account (`A3`) and the redirected account (`A1`) for those specific products. This ensures complete data integrity and prevents dangling overridden records.
