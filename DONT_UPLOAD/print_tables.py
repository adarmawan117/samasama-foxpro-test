import re

with open(r'c:\Users\adarmawan117\Downloads\UndfxffAllW\RESULTS\databases\INVENTORY.sql', 'r') as f:
    content = f.read()

target_tables = ['djual', 'drjual', 'dbeli', 'drbeli', 'barang']

# Find CREATE TABLE statements
matches = re.finditer(r'CREATE TABLE IF NOT EXISTS `([^`]+)` \((.*?)\) ENGINE', content, re.DOTALL | re.IGNORECASE)
found = False
for m in matches:
    table_name = m.group(1).lower()
    if table_name in target_tables or any(t in table_name for t in target_tables):
        print(f"Table: {m.group(1)}")
        print(m.group(2).strip())
        print("-" * 50)
        found = True

if not found:
    # Let's search with a broader regex
    matches = re.finditer(r'CREATE TABLE `([^`]+)` \((.*?)\)', content, re.DOTALL | re.IGNORECASE)
    for m in matches:
        table_name = m.group(1).lower()
        if table_name in target_tables or any(t in table_name for t in target_tables):
            print(f"Table: {m.group(1)}")
            print(m.group(2).strip())
            print("-" * 50)
