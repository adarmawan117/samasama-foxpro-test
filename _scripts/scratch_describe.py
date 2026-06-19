import pymysql
conn = pymysql.connect(host='localhost', user='root', password='root', database='INVENTORY')
cursor = conn.cursor()
cursor.execute("DESCRIBE barang")
columns = cursor.fetchall()
print([c[0] for c in columns])
conn.close()
