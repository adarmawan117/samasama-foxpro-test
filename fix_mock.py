import os
import re

files = [
    'adjusment_ppn/test_cases.py',
    'adjusment_ppn/test_savings_consumption.py'
]

for fpath in files:
    if os.path.exists(fpath):
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # We only want to replace "HRG_JUAL" with "HARGA11" inside dictionaries that represent barang.
        # Barang dicts look like: {"ACC": "...", "KODE_BRG": "...", "NAMA_BRG": "...", "PAJAK": 1, "HRG_JUAL": 12000.0, "HRG_BELI": 9000.0}
        # We can just replace '"HRG_JUAL"' with '"HARGA11"' if "NAMA_BRG" is in the same line or dict.
        # Actually, let's just do a simple string replace for specific lines
        
        lines = content.split('\n')
        new_lines = []
        for line in lines:
            if '"NAMA_BRG"' in line and '"HRG_JUAL"' in line:
                line = line.replace('"HRG_JUAL"', '"HARGA11"')
            new_lines.append(line)
            
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
        print(f"Updated {fpath}")
