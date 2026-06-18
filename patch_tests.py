import os
import re

def patch_tests(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # We need to replace acc="A1" with acc=('A1',) or "A1" with ('A1',) in function calls
                # Looking at standard test files, it usually is acc='A1' or acc="A1"
                
                # Strategy:
                # 1. Replace acc="A1" with acc=('A1',)
                # 2. Replace acc='A1' with acc=('A1',)
                # 3. Replace 'A1' with ('A1',) when it's passed as an argument to test functions
                # Actually, let's look for acc="A1" and acc='A1'
                new_content = content.replace('acc="A1"', "acc=('A1',)")
                new_content = new_content.replace("acc='A1'", "acc=('A1',)")
                
                # Let's also check for specific positions if any, like test_adjustment.py which might have:
                # proses_pengurangan_omset(source_conn, target_conn, "A1", ...
                new_content = re.sub(r'(proses_pengurangan_omset\([^,]+,\s*[^,]+,\s*)(["\']A1["\'])', r'\1(\'A1\',)', new_content)
                new_content = re.sub(r'(proses_penambahan_omset\([^,]+,\s*[^,]+,\s*)(["\']A1["\'])', r'\1(\'A1\',)', new_content)
                new_content = re.sub(r'(distribusikan_global_gap\([^,]+,\s*[^,]+,\s*)(["\']A1["\'])', r'\1(\'A1\',)', new_content)
                new_content = re.sub(r'(check_transactions_exist_in_range\([^,]+,\s*)(["\']A1["\'])', r'\1(\'A1\',)', new_content)
                new_content = re.sub(r'(purge_transactions_in_range\([^,]+,\s*)(["\']A1["\'])', r'\1(\'A1\',)', new_content)
                new_content = re.sub(r'(sync_raw_transactions_in_range\([^,]+,\s*[^,]+,\s*)(["\']A1["\'])', r'\1(\'A1\',)', new_content)
                new_content = re.sub(r'(rollback_savings_in_range\([^,]+,\s*)(["\']A1["\'])', r'\1(\'A1\',)', new_content)
                new_content = re.sub(r'(WorkerThread\([^,]+,\s*[^,]+,\s*)(["\']A1["\'])', r'\1(\'A1\',)', new_content)

                if new_content != content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"Patched {filepath}")

if __name__ == '__main__':
    patch_tests('c:/Users/adarmawan117/Downloads/UndfxffAllW/RESULTS/python_test/adjusment_ppn')
