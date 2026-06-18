# -*- coding: utf-8 -*-
"""
Wrapper script to initialize the SQLite sandbox database and perform basic sanity checks
on database connections, schemas, UDF registration, and query translation.
"""

import os
import sys
import sqlite3

# Ensure we can import proses_adjustment_pajak
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

from adjustment_ppn_core.schema.cloning import initialize_sandbox_db
from adjustment_ppn_core.database.connection import get_db_connection
from adjustment_ppn_core.schema.migrations import create_tabungan_dan_hutang_table

def run_sanity_checks():
    workspace_root = os.path.dirname(os.path.dirname(script_dir))
    db_path = os.path.join(workspace_root, 'sandbox.db')
    inventory_sql = os.path.join(workspace_root, 'databases', 'INVENTORY.sql')
    barang_sql = os.path.join(workspace_root, 'databases', 'barang.sql')
    
    # 1. Initialize the Sandbox Database
    # We only initialize if the database file doesn't exist, or if run with --force-init.
    # Since this is a test script, we can initialize it if it doesn't exist.
    force_init = '--force-init' in sys.argv
    if force_init or not os.path.exists(db_path):
        print("Sandbox database file not found or --force-init specified. Initializing...")
        initialize_sandbox_db(db_path, inventory_sql, barang_sql)
    else:
        print(f"Using existing sandbox database at: {os.path.abspath(db_path)}")
        
    # 2. Get connection
    print("\nConnecting to sandbox database using helper...")
    conn = get_db_connection(sandbox=True, database=db_path)
    
    try:
        cursor = conn.cursor()
        
        # Check 1: Query tabungan_dan_hutang schema & data
        print("Checking tabungan_dan_hutang table...")
        cursor.execute("SELECT * FROM tabungan_dan_hutang")
        rows = cursor.fetchall()
        print(f"  Query successful. Current rows: {len(rows)}")
        
        # Test unique constraint on tabungan_dan_hutang
        print("Testing UNIQUE constraint on tabungan_dan_hutang...")
        # Clean up first
        cursor.execute("DELETE FROM tabungan_dan_hutang WHERE acc = 'A00' AND kode_brg = 'B001'")
        # Insert first row
        cursor.execute(
            "INSERT INTO tabungan_dan_hutang (acc, kode_brg, qty, tipe) VALUES (%s, %s, %s, %s)",
            ('A00', 'B001', 10.5, 'tambah')
        )
        print("  Inserted test row 1 successfully.")
        
        # Try inserting duplicate (should fail unique constraint)
        try:
            cursor.execute(
                "INSERT INTO tabungan_dan_hutang (acc, kode_brg, qty, tipe) VALUES (%s, %s, %s, %s)",
                ('A00', 'B001', 5.0, 'tambah')
            )
            print("  WARNING: Duplicate insert succeeded! Unique constraint check failed.")
        except sqlite3.IntegrityError as e:
            print(f"  Success: Duplicate insert failed as expected with: {e}")
            
        # Check 2: Check query translation (%s -> ?)
        print("Testing query translation (%s -> ?)...")
        cursor.execute(
            "SELECT urutan, acc, kode_brg, qty, tipe FROM tabungan_dan_hutang WHERE acc = %s AND tipe = %s",
            ('A00', 'tambah')
        )
        test_row = cursor.fetchone()
        if test_row:
            print(f"  Query parameter translation worked! Row returned: {test_row}")
        else:
            print("  WARNING: No row returned, but query execution completed.")
            
        # Check 3: Check custom UDF DATE_FORMAT mock
        print("Testing DATE_FORMAT custom UDF...")
        cursor.execute("SELECT DATE_FORMAT('2026-06-15 20:49:00', '%Y-%m-%d %H:%i:%s')")
        formatted = cursor.fetchone()[0]
        print(f"  DATE_FORMAT output: {formatted}")
        assert formatted == '2026-06-15 20:49:00', f"DATE_FORMAT check failed. Got {formatted}"
        
        cursor.execute("SELECT DATE_FORMAT('2026-06-15 20:49:00', '%d-%m-%Y')")
        formatted2 = cursor.fetchone()[0]
        print(f"  DATE_FORMAT output: {formatted2}")
        assert formatted2 == '15-06-2026', f"DATE_FORMAT check failed. Got {formatted2}"
        print("  DATE_FORMAT UDF checks passed.")
        
        # Check 4: Check if INVENTORY tables exist (e.g. adjust, accinv)
        print("Verifying tables from INVENTORY.sql...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('adjust', 'accinv', 'barang')")
        tables = [r[0] for r in cursor.fetchall()]
        print(f"  Found tables: {tables}")
        for expected_table in ('adjust', 'accinv', 'barang'):
            if expected_table in tables:
                print(f"  - Table '{expected_table}' exists.")
                # Run a simple SELECT limit 1
                cursor.execute(f"SELECT COUNT(*) FROM {expected_table}")
                count = cursor.fetchone()[0]
                print(f"    Total rows in '{expected_table}': {count}")
            else:
                print(f"  - WARNING: Table '{expected_table}' NOT found.")
                
        print("\nAll sanity checks completed successfully!")
        
    except Exception as e:
        print(f"\nSanity checks failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    run_sanity_checks()
