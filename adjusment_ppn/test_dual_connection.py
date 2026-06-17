# test_dual_connection.py
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from proses_adjustment_pajak import parse_args, test_dual_connection, get_db_connection

class TestDualConnection(unittest.TestCase):
    def test_argparser_dual_db(self):
        """Test that the backend argparser parses dual database arguments correctly."""
        args_list = [
            "--source-host", "192.168.1.10",
            "--source-port", "3307",
            "--source-user", "src_user",
            "--source-pass", "src_pass",
            "--source-db", "src_db_name",
            "--target-host", "192.168.1.20",
            "--target-port", "3308",
            "--target-user", "tgt_user",
            "--target-pass", "tgt_pass",
            "--target-db", "tgt_db_name",
            "--acc", "001",
            "--start-date", "2026-06-01",
            "--end-date", "2026-06-30",
            "--target-ppn", "-15000.0"
        ]
        args = parse_args(args_list)
        self.assertEqual(args.source_host, "192.168.1.10")
        self.assertEqual(args.source_port, 3307)
        self.assertEqual(args.source_user, "src_user")
        self.assertEqual(args.source_pass, "src_pass")
        self.assertEqual(args.source_db, "src_db_name")
        self.assertEqual(args.target_host, "192.168.1.20")
        self.assertEqual(args.target_port, 3308)
        self.assertEqual(args.target_user, "tgt_user")
        self.assertEqual(args.target_pass, "tgt_pass")
        self.assertEqual(args.target_db, "tgt_db_name")
        self.assertEqual(args.acc, "001")
        self.assertEqual(args.start_date, "2026-06-01")
        self.assertEqual(args.end_date, "2026-06-30")
        self.assertEqual(args.target_ppn, -15000.0)

    @patch("pymysql.connect")
    def test_mock_pymysql_connections(self, mock_connect):
        """Mock pymysql.connect to verify correct parameters are passed for Source and Target DBs."""
        # Set up mock connections
        mock_src_conn = MagicMock()
        mock_tgt_conn = MagicMock()
        
        # side_effect returns src first, then tgt
        mock_connect.side_effect = [mock_src_conn, mock_tgt_conn]

        source_config = {
            'host': 'src-host',
            'port': '3306',
            'user': 'src-user',
            'password': 'src-password',
            'database': 'src-db'
        }
        target_config = {
            'host': 'tgt-host',
            'port': '3307',
            'user': 'tgt-user',
            'password': 'tgt-password',
            'database': 'tgt-db'
        }

        # Run test connection (not sandbox mode)
        test_dual_connection(source_config, target_config, sandbox=False)

        # Assert connect was called twice
        self.assertEqual(mock_connect.call_count, 2)

        # Verify source connection arguments
        first_call_args = mock_connect.call_args_list[0][1]
        self.assertEqual(first_call_args['host'], 'src-host')
        self.assertEqual(first_call_args['port'], 3306)
        self.assertEqual(first_call_args['user'], 'src-user')
        self.assertEqual(first_call_args['password'], 'src-password')
        self.assertEqual(first_call_args['database'], 'src-db')

        # Verify target connection arguments
        second_call_args = mock_connect.call_args_list[1][1]
        self.assertEqual(second_call_args['host'], 'tgt-host')
        self.assertEqual(second_call_args['port'], 3307)
        self.assertEqual(second_call_args['user'], 'tgt-user')
        self.assertEqual(second_call_args['password'], 'tgt-password')
        self.assertEqual(second_call_args['database'], 'tgt-db')

    @patch("pymysql.connect")
    def test_connection_failure_source(self, mock_connect):
        """Verify that a failure in Source DB connection raises the correct exception."""
        # Mock Source failure
        mock_connect.side_effect = Exception("Connection timed out")

        source_config = {'host': 'src-host', 'database': 'src-db'}
        target_config = {'host': 'tgt-host', 'database': 'tgt-db'}

        with self.assertRaises(Exception) as context:
            test_dual_connection(source_config, target_config, sandbox=False)
            
        self.assertIn("Source DB gagal: Connection timed out", str(context.exception))

    @patch("pymysql.connect")
    def test_connection_failure_target(self, mock_connect):
        """Verify that a failure in Target DB connection raises the correct exception."""
        # Mock Source success, Target failure
        mock_src_conn = MagicMock()
        mock_connect.side_effect = [mock_src_conn, Exception("Access denied")]

        source_config = {'host': 'src-host', 'database': 'src-db'}
        target_config = {'host': 'tgt-host', 'database': 'tgt-db'}

        with self.assertRaises(Exception) as context:
            test_dual_connection(source_config, target_config, sandbox=False)
            
        self.assertIn("Target DB gagal: Access denied", str(context.exception))

    def test_invalid_port_type(self):
        """Verify that an invalid non-numeric port type raises a ValueError wrapped in Exception."""
        source_config = {'host': 'src-host', 'port': 'invalid_port', 'database': 'src-db'}
        target_config = {'host': 'tgt-host', 'port': '3306', 'database': 'tgt-db'}
        
        with self.assertRaises(Exception) as context:
            test_dual_connection(source_config, target_config, sandbox=False)
        self.assertIn("invalid literal for int()", str(context.exception))

    @patch("sqlite3.connect")
    def test_empty_database_param_sandbox(self, mock_sqlite_connect):
        """Verify that when sandbox is True, empty/None database parameters default to sandbox.db."""
        mock_conn = MagicMock()
        mock_sqlite_connect.return_value = mock_conn
        
        source_config = {'database': ''}
        target_config = {'database': None}
        
        # Run dual test connection in sandbox mode
        test_dual_connection(source_config, target_config, sandbox=True)
        
        # Verify that sqlite3.connect was called twice with 'sandbox.db'
        self.assertEqual(mock_sqlite_connect.call_count, 2)
        mock_sqlite_connect.assert_any_call('sandbox.db')

    @patch("sqlite3.connect")
    def test_sqlite_locked_exception(self, mock_sqlite_connect):
        """Verify that SQLite locks (OperationalError) are handled correctly and reported."""
        import sqlite3
        # Simulate locked database on source connection
        mock_sqlite_connect.side_effect = sqlite3.OperationalError("database is locked")
        
        source_config = {'database': 'test_locked.db'}
        target_config = {'database': 'target.db'}
        
        with self.assertRaises(Exception) as context:
            test_dual_connection(source_config, target_config, sandbox=True)
            
        self.assertIn("Source DB gagal: database is locked", str(context.exception))

if __name__ == "__main__":
    unittest.main()

