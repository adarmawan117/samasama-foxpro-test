import pymysql
conn = pymysql.connect(host='localhost', user='root', password='root', db='INVENTORY')
cursor = conn.cursor()
cursor.execute("SELECT COUNT(DISTINCT F_JUAL) FROM djual WHERE TGL_JUAL >= '2026-03-01' AND TGL_JUAL <= '2026-03-31'")
count = cursor.fetchone()[0]
print(count)
conn.close()
