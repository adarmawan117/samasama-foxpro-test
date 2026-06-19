with open('adjusment_ppn/test_gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('itemData(1), ("001",)', 'itemData(1), "001"')
content = content.replace('setCurrentIndex(2)', 'setCurrentIndex(1)')

with open('adjusment_ppn/test_gui.py', 'w', encoding='utf-8') as f:
    f.write(content)
