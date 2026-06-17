# E2E GUI Test Infrastructure Documentation

This document describes the test suite architecture, design, and execution guidelines for verifying the PyQt5 GUI frontend (`proses_adjustment_pajak_gui.py`) of the PPN Tax Adjustment application.

---

## 1. Test Architecture & Methodology

GUI testing in server, headless, or automated CI/CD environments is often prone to windowing errors if no active display server is present. To prevent window rendering errors, the test suite `test_gui.py` utilizes the following mechanisms:

### Headless Execution
We set the platform environment variable:
```python
os.environ["QT_QPA_PLATFORM"] = "offscreen"
```
This forces PyQt5 to render all widgets in memory, bypasses the display server, and avoids the common `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"` or corresponding Windows graphics errors.

### Event Loop Management (Non-blocking)
To verify multithreading (ensuring the UI thread remains responsive while the worker thread handles intensive SQLite transactions in the background), the test suite uses `QEventLoop`:
- The process button is clicked asynchronously using `QTest.mouseClick`.
- A local event loop is spun up (`loop = QEventLoop()`) and bound to the background QThread's `finished` and `error_signal` signals.
- This allows events (like logging messages and progress callbacks) to continue being processed on the main thread, while waiting for the background thread to finish cleanly.

### Mocking Dialog Interfaces
Qt message dialogs like `QMessageBox` block the execution thread until a user clicks "Ok" or "Yes". To run fully automated E2E tests, the test suite monkeypatches:
- `QMessageBox.information`
- `QMessageBox.critical`
- `QMessageBox.warning`
- `QMessageBox.question`
These dialogs are redirected to test-controlled callbacks that append status to a log and return immediate default options (like `Ok` or `Yes`).

---

## 2. Test Cases Overview

The `test_gui.py` suite contains four main E2E test cases:

### 1. Form Component Initialization (`test_1_form_components_exist`)
Verifies that all GUI components are instantiated correctly, bound, and visible in the layout with expected names:
- Database path input (`db_path_input`)
- Browse button (`btn_browse`)
- Account selection QComboBox (`combo_acc`)
- Start Date and End Date inputs (`tgl_awal` and `tgl_akhir`)
- Target PPN line edit (`target_ppn_input`)
- Real-time debug log widget (`log_widget`)
- Run button (`btn_proses`)
- Export button (`btn_export`)

### 2. Dynamic Account Loading (`test_2_load_accounts_on_db_change`)
Simulates user interaction by entering a path into the database input. It verifies that when the database is loaded, the app connects to the database, reads account codes from the `accinv` table, and updates the `QComboBox` values dynamically.

### 3. State Lock, Responsiveness, & Logs (`test_3_state_management_multithreading_and_logging`)
Performs a full E2E run:
- Sets parameters for a typical reduction process.
- Triggers execution via `btn_proses`.
- Verifies that all form inputs are locked (disabled) immediately when background processing starts.
- Processes background worker execution while maintaining main thread responsiveness (multithreading).
- Verifies that upon completion, all inputs are re-enabled.
- Verifies that real-time logs are successfully printed to the `QListWidget`.
- Verifies that a completion summary message is displayed.

### 4. Detail Export (`test_4_csv_export_operation`)
Simulates the export flow:
- Mocks the `QFileDialog.getSaveFileName` interface.
- Executes the adjustment process to gather action logs.
- Triggers the export button.
- Verifies that a valid CSV file containing columns `["Index", "Tindakan / Action Log"]` and detail records is successfully generated.

---

## 3. How to Run the GUI Tests

### Prerequisites
Make sure PyQt5 and dependencies are installed in your Python environment:
```powershell
pip install -r python_test/requirements.txt
```

### Execution Command
Run the test suite using standard `unittest`:
```powershell
python -m unittest python_test/adjusment_ppn/test_gui.py
```

### Expected Output
Upon running, you should see:
```text
....
----------------------------------------------------------------------
Ran 4 tests in 1.458s

OK
```
This confirms that the GUI initializes correctly, locks states appropriately during multithreading, receives real-time progress callbacks, and generates the required CSV files.
