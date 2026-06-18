import unittest
import sys
import os

# Set offscreen platform for Qt headless test execution
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Add parent directory to path so it can import proses_adjustment_pajak_gui
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

if __name__ == '__main__':
    # Discover all tests in the current directory matching 'test_*.py'
    suite = unittest.defaultTestLoader.discover(start_dir=os.path.dirname(os.path.abspath(__file__)), pattern='test_*.py')
    with open('live_test_log.txt', 'w', encoding='utf-8', buffering=1) as f:
        runner = unittest.TextTestRunner(stream=f, verbosity=2)
        result = runner.run(suite)
    
    with open('test_run_results.txt', 'w', encoding='utf-8') as f:
        f.write(f"\nSUCCESS: {result.wasSuccessful()}\n")
        
    sys.exit(0 if result.wasSuccessful() else 1)
