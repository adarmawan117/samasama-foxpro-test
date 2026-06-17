import os
import glob

test_dir = r"c:\Users\adarmawan117\Downloads\UndfxffAllW\RESULTS\python_test\adjusment_ppn"
parent_dir_code = """
# Add parent directory to path to import modules
import sys
import os
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
"""

for py_file in glob.glob(os.path.join(test_dir, "*.py")):
    with open(py_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if "import sys" in content and "sys.path.insert(0, os.path.dirname(os.path.dirname" not in content:
        # replace the sys.path.insert or sys.path.append for __file__ with parent_dir_code
        if "sys.path.append(os.path.dirname(os.path.abspath(__file__)))" in content:
            content = content.replace("sys.path.append(os.path.dirname(os.path.abspath(__file__)))", parent_dir_code + "\nsys.path.append(os.path.dirname(os.path.abspath(__file__)))")
        elif "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))" in content:
            content = content.replace("sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))", parent_dir_code + "\nsys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))")
        else:
            # just insert after import sys
            content = content.replace("import sys\n", "import sys\n" + parent_dir_code + "\n")
            
        with open(py_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {os.path.basename(py_file)}")
