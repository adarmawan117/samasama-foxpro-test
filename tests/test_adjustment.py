import sys
import os
import pymysql

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from adjustment_ppn_core.database.connection import get_db_connection
from adjustment_ppn_core.calculator.adjustment_dual import proses_adjustment_dual
from adjustment_ppn_core.etl.sync_manager import sync_raw_transactions_in_range, sync_master_data

def run_tests():
    print("Running Integration Test for Adjustment Logic...")
    source_config = {
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'password': 'root',
        'database': 'inventory'
    }
    
    target_config = {
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'password': 'root',
        'database': 'target_db'
    }
    
    source_conn = get_db_connection(sandbox=False, **source_config)
    target_conn = get_db_connection(sandbox=False, **target_config)
    
    # Test Data setup
    acc = 'A1'
    start_date = '2026-03-01'
    end_date = '2026-03-01'
    target_ppn = 50000000  # 50 million
    target_btkp = 5000000  # 5 million
    
    print("1. Syncing Master Data...")
    sync_master_data(source_conn, target_conn, is_sandbox=False)
    print("2. Syncing Transactions...")
    sync_raw_transactions_in_range(source_conn, target_conn, acc, start_date, end_date)
    
    def log_cb(msg):
        print(f"LOG: {msg}")
        
    print("3. Running proses_adjustment_dual...")
    try:
        proses_adjustment_dual(source_conn, target_conn, acc, start_date, end_date, target_ppn, target_btkp, is_sandbox=False, log_callback=log_cb)
        print("TEST PASSED: No SQL errors encountered.")
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    run_tests()
