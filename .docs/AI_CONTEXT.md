# Technical Guide: Sales Transactions PPN Adjustment System (AI_CONTEXT.md)

This technical document serves as a comprehensive guide for future AI agents, software engineers, and system architects. It describes the design patterns, component organization, database schemas, SQL translation engine, core business logic scenarios, and testing framework of the PPN (Value Added Tax) Adjustment system.

---

## 1. MVC and Clean Architecture Pattern

The codebase is structured according to Clean Architecture principles combined with the Model-View-Controller (MVC) architectural pattern. This separates concerns, decouples core business logic from graphical presentation, and isolates SQL differences between MySQL and SQLite.

```
                  ┌──────────────────────────────┐
                  │          run_gui.py          │ (Entry Point)
                  └──────────────┬───────────────┘
                                 │ Instantiates & Binds
                                 ▼
                  ┌──────────────────────────────┐
                  │   ProsesAdjustmentPajakApp   │ (View / PyQt Widgets)
                  └───────┬───────▲──────────────┘
                          │       │
        Emits Custom      │       │ Updates View State
        PyQt5 Signals     │       │ & UI Elements
        (e.g., proses_    │       │
         clicked)         │       │
                          ▼       │
                  ┌───────────────┴──────────────┐
                  │  AdjustmentPajakController   │ (Controller / Mediator)
                  └──────────────┬───────────────┘
                                 │
                                 │ Spawns & Connects Signals
                                 ▼
                  ┌──────────────────────────────┐
                  │    WorkerThread (QThread)    │ (Asynchronous Workers)
                  └──────────────┬───────────────┘
                                 │
                                 │ Invokes Backend API
                                 ▼
                  ┌──────────────────────────────┐
                  │     adjustment_ppn_core      │ (Core Business Logic)
                  └──────────────────────────────┘
```

### 1.1 Separation of Concerns
- **View (`adjustment_ppn_gui/main_window.py`)**: Built on PyQt5. Defines UI layouts, buttons, progress bar, text inputs, date pickers, and logger. It automatically loads connection settings from `connection_settings.json` upon initialization. User interactions emit PyQt5 signals (e.g., `proses_clicked = pyqtSignal()`).
- **Controller (`adjustment_ppn_gui/controller.py`)**: Connects the View to the core backend. It handles UI validation, orchestrates popups, manages background workers, writes `connection_settings.json` upon successful tests, and implements fallback logic (e.g., reading from `barang` if `accinv` is empty for account dropdowns).
- **Workers (`adjustment_ppn_gui/workers.py`)**: Long-running or blocking calls—such as connection testing, database cloning, and adjustment calculations—are executed in asynchronous threads (`QThread`) to keep the main GUI thread responsive. Inter-thread communication is achieved via PyQt signals (e.g., `progress_signal`, `finished_signal`, `error_signal`).
- **Core Business Logic (`adjustment_ppn_core/`)**: Includes the calculation engines, SQL query translation layers, ledger rollback facilities, and database schema migrations. This core is independent of PyQt5 and can be executed via command-line scripts.

---

## 2. Component Layout

The structure of the `python_test` directory is organized as follows:

```
python_test/
│
├── .docs/                             # System documentation directory
│   ├── AI_CONTEXT.md                  # This technical design guide
│   ├── PANDUAN_USER.md                # System operational user guide
│   └── FLOW_AND_FEATURES.md           # Friendly end-user manual (Indonesian)
│
├── adjustment_ppn_core/               # Core backend packages (Framework agnostic)
│   ├── calculator/
│   │   ├── __init__.py
│   │   ├── adjustment.py              # Single-run legacy proportional adjustment logic
│   │   ├── adjustment_core.py         # Sub-fases for addition, reduction, and global gap (grouped, anti-delete, strict scoping)
│   │   ├── adjustment_dual.py         # Orchestrator running sequential PPN and BTKP dual loops with independent commits
│   │   └── concurrency.py             # Helper classes for thread pools and lock controls
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py              # SQLite/MySQL driver connections & UDF registration
│   │   └── sqlite_translator.py       # SQL dialect parsing and state-machine translator
│   ├── etl/
│   │   ├── __init__.py
│   │   ├── ledger_rollback.py         # Restoring tabungan levels and deleting mutasi logs
│   │   └── sync_manager.py            # Purging target database & synchronizing raw transactions
│   └── schema/
│       ├── __init__.py
│       ├── cloning.py                 # SQLite native backup & MySQL schema streaming copy
│       └── migrations.py              # DDL schema definition for tabungan & log_mutasi tables
│
├── adjustment_ppn_gui/                # Presentation tier (PyQt5 frontend)
│   ├── __init__.py
│   ├── controller.py                  # Mediator connecting View and Workers
│   ├── main_window.py                 # Layout definitions, widgets, and getters/setters
│   └── workers.py                     # QThread wrappers for DB operations and adjustment runs
│
├── adjusment_ppn/                     # Automated test suites
│   ├── run_tests_via_python.py        # Automated test loader and headless environment runner
│   ├── test_cases.py                  # Predefined E2E test cases (Tiers 1-4)
│   ├── test_infra.py                  # Test harness spawning subprocesses on temporary DB files
│   ├── test_gui.py                    # Unit and integration tests for View and Controller
│   ├── test_schema_cloning.py         # Tests for DDL translations and existence validation
│   ├── test_idempotent_etl.py         # Verification of repeated runs and warnings
│   ├── test_ledger_rollback.py        # Validates floating-point rounding during ledger reversal
│   ├── test_savings_consumption.py    # Soft-delete constraints under foreign keys
│   ├── test_stress_challenger.py      # SQLite WAL checkpoint and window-close guards
│   ├── test_challenger.py             # Config file parser fallbacks
│   └── test_dual_connection.py        # Connection exception paths
│
├── run_gui.py                         # GUI entry point
├── run_proses_adjustment.py           # CLI entry point
└── db_config.py                       # Global database host/user configuration parameters
```

---

## 3. Database Schema Specifications

The adjustment process uses two specialized ledger tables in the target database to track accumulated quantities of tax-free/tax-reduced items (savings) and fictional injections (debts).

### 3.1 Table: `tabungan_dan_hutang`
Tracks product-specific balances that have been reduced (resulting in a "tambah" or savings balance) or added fictionally (resulting in a "kurang" or debt balance).

| Column Name | Data Type (MySQL) | Data Type (SQLite) | Nullable | Default | Description |
|---|---|---|---|---|---|
| `urutan` | `INT AUTO_INCREMENT` | `INTEGER PRIMARY KEY AUTOINCREMENT` | No | | Primary key, automatically incremented. |
| `acc` | `VARCHAR(3)` | `VARCHAR(3)` | No | `''` | Branch/account identification code. |
| `kode_brg` | `VARCHAR(10)` | `VARCHAR(10)` | No | | Unique product identifier code. |
| `qty` | `DOUBLE(15,3)` | `DOUBLE(15,3)` | No | `0.0` | Accumulated quantity balance. |
| `tipe` | `VARCHAR(10)` | `VARCHAR(10)` | No | | Either `'tambah'` (savings balance) or `'kurang'` (debt balance). |
| `tanggal_dibuat`| `DATE` | `DATE` | Yes | `NULL` | Timestamp of when the ledger entry was generated. |

**Constraints:**
- `CHECK (tipe IN ('tambah', 'kurang'))`: Enforces valid transaction types.
- `CONSTRAINT uq_acc_brg_tipe UNIQUE (acc, kode_brg, tipe)`: Ensures only one ledger entry exists per branch, product, and transaction type.

### 3.2 Table: `log_mutasi_tabungan`
Maintains a detailed audit trail of how and when savings entries (`tambah`) were consumed during subsequent sales transaction additions.

| Column Name | Data Type (MySQL) | Data Type (SQLite) | Nullable | Default | Description |
|---|---|---|---|---|---|
| `id_log` | `INT AUTO_INCREMENT` | `INTEGER PRIMARY KEY AUTOINCREMENT` | No | | Primary key, automatically incremented. |
| `id_tabungan` | `INT` | `INTEGER` | Yes | `NULL` | Foreign key referencing `tabungan_dan_hutang(urutan)`. |
| `qty_dipakai` | `DOUBLE` | `DOUBLE` | Yes | `NULL` | Quantity of savings consumed during this transaction. |
| `tanggal_dipakai`| `DATE` | `DATE` | Yes | `NULL` | Date when the savings were applied. |

**Constraints:**
- `FOREIGN KEY (id_tabungan) REFERENCES tabungan_dan_hutang(urutan)`: Prevents orphaned records and preserves referential integrity.

---

## 4. SQL Dialect Translator

SQLite lacks many features of MySQL. The `adjustment_ppn_core/database/sqlite_translator.py` module handles on-the-fly SQL compatibility translations when SQLite is used for local sandboxes or automated testing.

### 4.1 Mocking `DATE_FORMAT`
SQLite does not natively support MySQL’s `DATE_FORMAT` function. During SQLite connection setup, the custom Python function `sqlite_date_format` is registered:
```python
conn.create_function("DATE_FORMAT", 2, sqlite_date_format)
```
- It parses MySQL format specifiers (e.g., `%i` -> minute, `%s` -> second, `%M` -> month name, `%h` -> 12-hour hour) and maps them to their Python `strftime` equivalents.
- Parses multiple incoming string patterns (`%Y-%m-%d %H:%M:%S`, `%Y-%m-%d`, etc.) to return standard formatted outputs.

### 4.2 Query Placeholder State Machine (`translate_query`)
MySQL uses `%s` for parameterized query placeholders, while SQLite uses `?`. Simple string replacement fails if `%s` occurs inside string literals or modulo expressions.
- `translate_query(query_str)` uses a character-by-character state machine.
- It tracks single quotes (`'`), double quotes (`"`), and escape characters (`\`).
- A `%s` token is only translated to `?` if the machine is currently in an unquoted state, and the token is not part of a modulo query or string pattern.

### 4.3 Sanitizing SQL Commands (`make_sqlite_compatible`)
Sanitizes raw SQL dumps for compatibility with SQLite:
- Strips administrative MySQL statements (e.g., `LOCK TABLES`, `UNLOCK TABLES`, `SET FOREIGN_KEY_CHECKS=0`).
- Translates string escapes (`\'` -> `''` and `\"` -> `"`).
- Strips out single-line (`--`, `#`) and multi-line (`/* ... */`) comments.

### 4.4 DDL parsing (`parse_create_table_to_sqlite`)
Converts MySQL `CREATE TABLE` DDL statements to SQLite-compatible syntax:
- Drops incompatible inline column constraints (such as `CHARACTER SET ...` or `COLLATE ...`).
- Removes table-level secondary `KEY` and `INDEX` lines.
- Rewrites `AUTO_INCREMENT` primary key definitions to `INTEGER PRIMARY KEY AUTOINCREMENT`.
- Drops global primary key constraints if an auto-increment primary key is already defined, avoiding table-creation failures due to duplicate primary key definitions.

---

## 5. Core Business Logic Scenarios

The system performs transaction adjustments according to four primary logic scenarios to align the target tax database with specified target tax values. To handle regulatory requirements cleanly, the system utilizes a **Double Engine Kalkulator** and a **Dual-Loop Architecture** to separate PPN (Value Added Tax) and BTKP (Tax-Free) calculations.

### 5.1 Scenario 1: Double Engine Gap Calculation & GUI Inputs
The user inputs targets for both PPN and BTKP separately in the GUI:
- **GUI Target Inputs**:
  - `target_ppn_input`: Defines target turnover for PPN items.
  - `target_btkp_input`: Defines target turnover for BTKP items.
- **GUI Output Fields**:
  - `current_ppn_omset_input` / `current_btkp_omset_input`: Shows the original gross sales (PPN + Gunggung vs BTKP).
  - `current_ppn_retur_input` / `current_btkp_retur_input`: Shows the return totals for PPN vs BTKP.
  - `current_net_ppn_input` / `current_net_btkp_input`: Shows the actual current net turnover (gross minus returns and discounts) for PPN vs BTKP.

- **Optimized Single-Scan SQL Query**:
  In `adjustment_ppn_gui/workers.py`, the system calculates both PPN and BTKP net sales using a single SQL query using `SUM(CASE WHEN...)` to avoid Python memory overhead:
  ```sql
  SELECT 
      SUM(CASE WHEN b.PAJAK IN (1, 3) THEN (d.JUMLAH*d.HRG_JUAL*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH) ELSE 0 END),
      SUM(CASE WHEN b.PAJAK = 2 THEN (d.JUMLAH*d.HRG_JUAL*((100-d.DISC1)/100)*((100-d.DISC2)/100)*((100-d.DISC3)/100))-(d.DISC_RP*d.JUMLAH) ELSE 0 END)
  FROM djual d
  LEFT JOIN barang b ON d.KODE_BRG = b.KODE_BRG AND d.ACC = b.ACC
  WHERE d.ACC IN ({placeholders}) AND d.TGL_JUAL >= ... AND d.TGL_JUAL <= ...
  ```
  Here, PPN items are identified by `b.PAJAK IN (1, 3)` (PPN and Gunggung), and BTKP items are identified by `b.PAJAK = 2`. The query calculates the exact post-discount sales turnover in a single database pass, eliminating rounding errors and reducing memory usage.

### 5.2 Scenario 2: Dual-Loop Architecture & Independent Commits
The execution logic in `adjustment_dual.py` processes PPN and BTKP in separate, sequential phases rather than concurrently. This isolation eliminates database lock contention and prevents memory bloat or access violations:
1. **PPN Phase**:
   - Queries current PPN net omset using `b.PAJAK IN (1, 3)`.
   - Computes PPN gap: `target_ppn - current_ppn`.
   - Runs `proses_pengurangan_fase` (if gap < 0) or `proses_penambahan_fase` (if gap > 0) targeting only PPN items.
   - Commits changes to the target database immediately via `target_conn.commit()`.
2. **BTKP Phase**:
   - Queries current BTKP net omset using `b.PAJAK = 2`.
   - Computes BTKP gap: `target_btkp - current_btkp`.
   - Runs `proses_pengurangan_fase` (if gap < 0) or `proses_penambahan_fase` (if gap > 0) targeting only BTKP items.
   - Commits changes to the target database immediately via `target_conn.commit()`.

Committing at the end of each independent phase releases row and page locks on SQLite/MySQL early, ensuring no transaction deadlocks or access violations occur during the execution of the next phase.

### 5.3 Scenario 3: Tax Reduction & Strict Anti-Delete Rule (`proses_pengurangan_fase`)
Used when a target tax value (PPN or BTKP) needs to be reduced:
- **Proportional Reduction**: Calculates the reduction factor $P = \text{target\_omset\_change} / \text{total\_taxable\_omset}$.
- **Item Traversal**: Iterates through tax-category specific items (filtered by `category_sql_filter`) inside sales transactions (`djual`), sorted from bottom to top (`urutan DESC`).
- **Strict Anti-Delete Rule**: The system guarantees that no transaction row in `djual` is deleted, preserving the integrity of invoice sequences for tax audits (no empty receipts or gaps in invoice numbering).
  - The maximum allowable quantity to reduce is bounded by `max_qty_to_reduce = item['jumlah'] - 1`.
  - If `max_qty_to_reduce <= 0`, the system skips the item, enforcing a minimum quantity of 1 unit.
  - Reduction is executed using a SQL `UPDATE djual SET jumlah = ...` statement instead of a `DELETE` query.
- **Ledger Accrual**: The reduced quantity is saved in `tabungan_dan_hutang`:
  1. Checks if there is an active debt balance (`kurang`) for that product. If yes, it settles the debt first (Self-Healing).
  2. Saves the remaining quantity as a savings record (`tambah`).

### 5.4 Scenario 4: Priority Savings Draw (Tax Addition)
When the target tax requires transaction additions, the system first attempts to draw quantities from the savings ledger (`tabungan_dan_hutang` with type `'tambah'`). Candidates are filtered by the relevant tax category and sorted by price in descending order:
- **Priority A (Exact Value Match)**: A savings record where the product price multiplied by its available quantity matches the target receipt addition amount exactly ($\text{price} \times \text{qty} == \text{target}$).
- **Priority B (Exact Partial Match)**: A savings record where a subset quantity $k$ ($1 \le k \le \text{qty}$) matches the target receipt addition amount exactly ($\text{price} \times k == \text{target}$).
- **Priority C (Closest below Target)**: Finds a quantity $k$ from a savings record that yields the highest total value without exceeding the target receipt addition amount.

When savings are drawn:
- The savings record quantity is reduced in `tabungan_dan_hutang`.
- A record is added to `log_mutasi_tabungan`.
- The quantities are added to the transaction in `djual`.

### 5.5 Scenario 5: Fictional Injection & Strict Scoping (Fallback Tax Addition)
If the savings ledger cannot satisfy the target addition for a receipt, the system falls back to injecting fictional product quantities.
- **Strict Tax Category Scoping**: To comply with tax laws, fictional items must match the tax category of the receipt. The system uses a specific `category_sql_filter` when querying candidate receipts and when selecting fictional product candidates from the `barang` table:
  - Fictional PPN items (tax category `b.PAJAK IN (1, 3)`) are injected only into receipts that already contain PPN transactions.
  - Fictional BTKP items (tax category `b.PAJAK = 2`) are injected only into receipts that already contain BTKP transactions.
- **Product Selection Query**: Candidate products are queried with a category filter and aggregated to prevent Cartesian explosions (see Section 5.7). The smallest unit price `HARGA11` is used.
- **Global Exhaustion Pool**: Iterates through all available products in a globally shuffled pool. Used products are popped permanently from the pool. If empty, the pool resets.
- **QTY Randomization**: Finds the maximum possible quantity $max\_k$ for the selected product without exceeding the remaining target, then randomizes the injection quantity $k = random.randint(1, max\_k)$ to simulate natural shopping behavior.
- **Debt Accrual**: The injected quantity is recorded in `tabungan_dan_hutang` as a debt (`kurang`), which can be settled by future reductions (Self-Healing).

### 5.6 Scenario 6: Global Gap Distribution
If a residual global gap exists after primary reduction or addition, the system evenly distributes this leftover gap across 25% of the total available receipts (`total_receipts // 4`). This chunking mechanism ensures that no single receipt becomes abnormally bloated with extreme quantities, maintaining realistic transaction profiles.

### 5.7 Bugfix: Master Data Duplication & 'Lain Lain' Omset Inflation
In `adjustment_core.py`, database queries joining the transactions with the `barang` master data or `tabungan_dan_hutang` table could lead to a **Cartesian Explosion**. This occurs because products in the `barang` table use a composite key (`KODE_BRG`, `ACC`) and might contain duplicate entries due to price history. If joined directly without aggregation, the rows multiply, resulting in artificial omset inflation—especially for generic items like "Lain Lain".

To resolve this duplication bug, the system employs the following strategies:
1. **Aggregated Master Data Queries**:
   When querying the master `barang` data for fictional injections, the query groups by product and account, taking the maximum of the prices:
   ```sql
   SELECT KODE_BRG, ACC, MAX(HRG_BELI), MAX(HARGA11), 0, 0, 0, 0,
          MAX(HARGA11) as actual_price
   FROM barang b
   WHERE ACC IN ({placeholders}) AND {category_sql_filter} AND HARGA11 > 0
   GROUP BY KODE_BRG, ACC
   ```
2. **Aggregated Savings Queries**:
   Similarly, when querying `tabungan_dan_hutang` joined with `barang`, the query aggregates the records:
   ```sql
   SELECT t.urutan, t.qty, t.acc, t.kode_brg, 
          MAX(b.HARGA11) as base_price,
          MAX(b.HRG_BELI) as hrg_beli
   FROM tabungan_dan_hutang t
   JOIN barang b ON t.kode_brg = b.kode_brg AND t.acc = b.acc
   WHERE ...
   GROUP BY t.urutan, t.qty, t.acc, t.kode_brg
   ```
3. **Zero-Discount for Fictional Injections**:
   To prevent discounts from introducing unexpected price calculations or inflating other items, the query for fictional items statically binds discount percentages and values to `0` (mapping to DISC1, DISC2, DISC3, DISC_RP as `0, 0, 0, 0`). This ensures that fictional sales are injected with a clean net price matching `HARGA11`.


---

## 6. Concurrency and Optimization

To meet performance requirements without freezing the UI or overwhelming system resources, the system employs a targeted multithreading architecture.

### 6.1 Worker Threads and Dynamic CPU Allocation
Intensive calculation loops (like checking each receipt for savings draws and fictional injections) are parallelized using Python's `ThreadPoolExecutor`. The system calculates the maximum number of worker threads dynamically using `max_workers = max(1, int(os.cpu_count() * 0.7))`. This ensures the adjustment finishes quickly without starving the host machine of computational resources.

### 6.2 Thread-Safe Write Queue (`DbWriterQueue`)
MySQL and SQLite drivers must handle high-volume write operations carefully in a multithreaded context. The `DbWriterQueue` offloads all `UPDATE`, `INSERT`, and `DELETE` queries to a dedicated, single background daemon thread.
- Worker threads only perform `SELECT` queries (using shared connections or thread-local contexts) and calculate mathematics.
- Write operations are pushed onto a thread-safe `queue.Queue`.
- The `_writer_loop` pops queries and executes them sequentially. This eliminates `database is locked` SQLite errors and prevents MySQL deadlocks/race conditions.
- **CRITICAL**: The queue must be explicitly closed using `db_queue.stop_and_wait()` at the end of each processing phase. Failing to do so causes the daemon thread to leak into the next phase, which can corrupt the PyMySQL socket stream (resulting in `unpack_from` or `read of closed file` errors) if the main thread attempts to use the same connection concurrently.

### 6.3 UI Log Batching (`LogBatcher`)
Emitting thousands of PyQt5 signals per second from worker threads causes severe UI congestion and unresponsiveness. The `LogBatcher` intercepts log strings and groups them into batches (default size 20). Only when a batch is full (or when the process flushes at the end) does the worker emit the concatenated string via `progress_signal`, maintaining a smooth GUI experience.

### 6.4 Multithreading Addition Architecture (Caching and Locking)
The addition process (`proses_penambahan_omset`) has been refactored from a sequential database-bound loop into a highly optimized multithreaded architecture:
1. **RAM Caching & Pre-loading**: 
   - At the function start, the entire `barang` master data is queried from `source_conn` and cached in a RAM dictionary `barang_dict` and set `a1_products`.
   - Active savings records are queried from `target_conn` and cached in `savings_cache` in RAM.
   - Sales items (`djual`) are queried and grouped by `F_JUAL` (receipts) in RAM.
   - Worker threads process their assigned receipts using these in-memory structures, executing **zero SELECT queries inside the thread loop**.
2. **Synchronization & Locks**:
   - `savings_lock = threading.Lock()` guards all concurrent reads and updates on the shared `savings_cache` in RAM, preventing data races when threads draw savings or perform self-healing debt settlement.
   - `total_actual_addition_lock` synchronizes the accumulation of the total adjusted value.
3. **Local Transaction Representation**:
   - Each thread maintains a local, isolated representation of target database tables (such as `djual` and `tabungan_dan_hutang` records) during the loop. The final aggregated INSERT/UPDATE queries are generated and pushed to the `DbWriterQueue` only after receipt processing terminates.

### 6.5 Self-Healing & Global Gap Distribution
After proportional adjustments, minor rounding differences (global gaps) are resolved:
- **Negative Gap (Remaining Reduction)**: Iterates over selected receipts and reduces quantities of items, recording the reduction as savings (`tambah`).
- **Positive Gap (Remaining Addition)**: Chooses target receipts (distributed evenly). It first attempts to consume any remaining savings from `tabungan_dan_hutang`. If a gap still remains, it injects fictional quantities. Instead of deterministically selecting the highest-priced exact fit (which results in repetitive injections), the system calculates the math difference for all available products, gathers the best candidates that match perfectly, and performs a random draw (`random.choice(best_candidates)`) to determine which product to inject. This guarantees diverse and natural-looking tail-end invoices.

### 6.6 Multi-Account Cross-Pollination (Select All)
The system supports executing multiple accounts in a single tuple (e.g., `acc=('A1', 'A3')`). When processed in this "ALL" batch:
- **Proportional Targeting**: A single global PPN target is entered and proportionally distributed across all participating accounts based on their combined total omset.
- **Shared Ledger (Cross-Pollination)**: The core module allows cross-pollination of savings. Leftover item deductions (savings or `tambah`) from one account's receipt (e.g., A1) can be used to fulfill the PPN addition targets of another account's receipt (e.g., A3) automatically.

### 6.7 A1 Priority Rule for Savings
- **Priority Definition**: When recording or drawing savings (deposits, debts, or fictional injections), the system checks the master `barang` table for the product code (`KODE_BRG`).
- **Overriding Behavior**: If the product code exists under account `A1` in the master table, the savings mutation is recorded under `ACC = 'A1'`, regardless of whether the sales transaction originates from another account (e.g., grosir `A3`). If the product is not registered under `A1`, the system falls back to using the transaction's original account (e.g., `A3`).
- **Rollback Consistency**: When a rollback is performed for a target account (e.g., `A3`), the rollback engine queries the master `barang` table to identify any product codes redirected to `A1`. It then cleans up both the original target account records and the redirected `A1` savings records and mutation logs associated with those products.

---

## 7. Automated Testing Structure

The system includes a comprehensive suite of 67 automated tests.

### 7.1 Test Suites and Scope
- `test_multithreaded_addition.py`: Verifies multithreaded addition execution, RAM-based caching, locking mechanisms, fictional injections, and boundary/early exit conditions.
- `test_gui.py`: Verifies PyQt5 UI rendering, widget interaction, state controls (locking inputs during operations), and CSV log exports.
- `test_schema_cloning.py`: Validates MySQL-to-SQLite DDL syntax translations, auto-increment mappings, and target database existence checks.
- `test_idempotent_etl.py`: Verifies that rerun processes trigger warnings and that transactions within a date range are purged and re-synchronized correctly.
- `test_ledger_rollback.py`: Validates that performing rollbacks restores original ledger levels without floating-point rounding errors.
- `test_savings_consumption.py`: Verifies referential integrity and checks that soft-deleted entries (where `qty = 0`) prevent active foreign key violations.
- `test_stress_challenger.py`: Simulates writes during active SQLite Write-Ahead Logging (WAL) checkpoints.
- `test_challenger.py` & `test_dual_connection.py`: Validates configuration parser fallbacks and connection error pathways.

### 7.2 Test Runner Configuration (`run_tests_via_python.py`)
- **Headless Mode**: Sets the Qt QPA platform to offscreen to prevent opening physical windows:
  ```python
  os.environ["QT_QPA_PLATFORM"] = "offscreen"
  ```
- **Test Discovery**: Dynamically discovers all `test_*.py` files in the `adjusment_ppn` directory.
- **Execution**: Runs tests using `unittest.TextTestRunner` and captures the execution log in `test_run_results.txt`.
