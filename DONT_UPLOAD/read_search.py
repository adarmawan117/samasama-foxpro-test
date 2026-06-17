import codecs

try:
    with codecs.open('search_result.txt', 'r', encoding='utf-16le') as f:
        data = f.read()
    with codecs.open('search_result_utf8.txt', 'w', encoding='utf-8') as f_out:
        f_out.write(data)
except Exception as e:
    print(e)
