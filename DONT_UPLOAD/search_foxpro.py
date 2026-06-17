import codecs

with codecs.open('scratch_mirror.txt', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if 'INDEX' in l.upper() or 'IND' in l.upper() or 'JUAL' in l.upper():
        print(f"Line {i}: {l.strip()}")
