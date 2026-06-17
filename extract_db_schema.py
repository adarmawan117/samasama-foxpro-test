import os
import re

base_dir = r"c:\Users\adarmawan117\Downloads\UndfxffAllW\RESULTS\python_test"
src_file = os.path.join(base_dir, "proses_adjustment_pajak.py")

with open(src_file, "r", encoding="utf-8") as f:
    content = f.read()

# Define the boundaries of blocks to extract using regex
# We can also just search for the start of the function and the start of the next function.

def extract_funcs(names, content):
    extracted = []
    # Match the start of the function/class and everything until the next function/class/block without indentation
    for name in names:
        pattern = re.compile(r"^(def|class)\s+" + re.escape(name) + r"\b.*?(?=\n^(def|class|\# ==========================================)\s+|\Z)", re.MULTILINE | re.DOTALL)
        match = pattern.search(content)
        if match:
            extracted.append(match.group(0).strip())
        else:
            print(f"Could not find {name}")
    return "\n\n\n".join(extracted)

# Categories
sqlite_funcs = ['sqlite_date_format', 'is_pk_constraint_for_col', 'strip_comments_and_whitespace', 'parse_create_table_to_sqlite', 'make_sqlite_compatible', 'translate_query']
conn_funcs = ['SQLiteCursorWrapper', 'SQLiteConnectionWrapper', 'MySQLConnectionWrapper', 'get_db_connection', 'test_dual_connection']
migration_funcs = ['create_tabungan_dan_hutang_table', 'create_log_mutasi_tabungan_table']
cloning_funcs = ['check_target_db_exists', 'clone_full_database', 'initialize_sandbox_db', 'inisialisasi_sandbox_db']

sqlite_content = extract_funcs(sqlite_funcs, content)
conn_content = extract_funcs(conn_funcs, content)
migration_content = extract_funcs(migration_funcs, content)
cloning_content = extract_funcs(cloning_funcs, content)

# Write to files
os.makedirs(os.path.join(base_dir, "adjustment_ppn_core", "database"), exist_ok=True)
os.makedirs(os.path.join(base_dir, "adjustment_ppn_core", "schema"), exist_ok=True)

with open(os.path.join(base_dir, "adjustment_ppn_core", "__init__.py"), "w", encoding="utf-8") as f:
    pass
with open(os.path.join(base_dir, "adjustment_ppn_core", "database", "__init__.py"), "w", encoding="utf-8") as f:
    pass
with open(os.path.join(base_dir, "adjustment_ppn_core", "schema", "__init__.py"), "w", encoding="utf-8") as f:
    pass

with open(os.path.join(base_dir, "adjustment_ppn_core", "database", "sqlite_translator.py"), "w", encoding="utf-8") as f:
    f.write('import re\nimport datetime\n\n')
    f.write(sqlite_content)

with open(os.path.join(base_dir, "adjustment_ppn_core", "database", "connection.py"), "w", encoding="utf-8") as f:
    f.write('import os\nimport sys\nimport sqlite3\nfrom .sqlite_translator import sqlite_date_format, translate_query\n\n')
    f.write(conn_content)

with open(os.path.join(base_dir, "adjustment_ppn_core", "schema", "migrations.py"), "w", encoding="utf-8") as f:
    f.write('import traceback\nimport logging\n\n')
    f.write(migration_content)

with open(os.path.join(base_dir, "adjustment_ppn_core", "schema", "cloning.py"), "w", encoding="utf-8") as f:
    f.write('import os\nimport sys\nimport traceback\nimport re\nfrom adjustment_ppn_core.database.connection import get_db_connection\nfrom adjustment_ppn_core.database.sqlite_translator import make_sqlite_compatible\nfrom adjustment_ppn_core.schema.migrations import create_tabungan_dan_hutang_table, create_log_mutasi_tabungan_table\n\n')
    f.write(cloning_content)

# Now remove the extracted functions from the main file
# We will use re.sub for each block

new_content = content
for name in sqlite_funcs + conn_funcs + migration_funcs + cloning_funcs:
    pattern = re.compile(r"^(def|class)\s+" + re.escape(name) + r"\b.*?(?=\n^(def|class|\# ==========================================)\s+|\Z)", re.MULTILINE | re.DOTALL)
    new_content = pattern.sub("", new_content)

# Add imports right after the initial imports
imports_to_add = """
from adjustment_ppn_core.database.sqlite_translator import *
from adjustment_ppn_core.database.connection import *
from adjustment_ppn_core.schema.migrations import *
from adjustment_ppn_core.schema.cloning import *
"""

# Insert right after `import datetime`
new_content = new_content.replace('import datetime\n', 'import datetime\n' + imports_to_add + '\n')

with open(src_file, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Extraction complete.")
