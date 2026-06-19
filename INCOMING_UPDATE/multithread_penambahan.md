# Rencana Pembaruan Mendatang (INCOMING_UPDATE): Multithreading Penambahan Omset

## Deskripsi Tujuan
Memperbaiki fitur *Multithreading* yang ternyata belum diterapkan pada fungsi `proses_penambahan_omset` (Penambahan/Suntikan Fiktif). Saat ini, sistem hanya menggunakan *multithreading* penuh pada proses pemotongan (pengurangan). Kita akan merefaktor kode penambahan agar berjalan paralel dan lari kencang menggunakan seluruh 14 *thread* yang tersedia.

---

## Rencana Implementasi

### 1. Modifikasi Inti Komputasi - `adjustment_ppn_core/calculator/adjustment.py`
- Refaktor fungsi `proses_penambahan_omset` untuk diapit oleh `ThreadPoolExecutor(max_workers=max_workers)`.
- Buat sub-fungsi `worker_task` yang memproses pencarian stok di celengan (`tabungan_dan_hutang`) dan pencarian barang untuk suntikan fiktif secara paralel untuk setiap faktur.
- Ganti semua eksekusi kueri langsung (`target_cursor.execute` dan `source_cursor.execute`) di dalam *loop* iterasi menjadi sistem dorong antrian `db_queue.push(...)` menggunakan `DbWriterQueue`. Hal ini krusial untuk mencegah terjadinya *database deadlock*.

### 2. Mekanisme Penguncian (*Locking*) dan RAM *Caching*
- Terapkan mekanisme penguncian (*Lock*) pada `savings_cache` dan `total_actual_addition_lock`. Ini wajib dilakukan untuk mencegah tabrakan data (Data Race) ketika belasan *thread* secara bersamaan mencoba mengambil stok dari satu celengan barang yang sama.
- Lakukan *Pre-load* data barang (tabel Master `BARANG`) yang memiliki status `PAJAK = 1` ke dalam memori (RAM) di awal fungsi.
- **Tujuan Pre-load:** Agar ke-14 *thread* yang sedang mencari "Barang Pengganti" (Suntikan Fiktif) tidak perlu bolak-balik melontarkan kueri `SELECT` ke database MySQL. Dengan memindahkannya ke RAM, CPU bisa bekerja penuh 100% tanpa waktu tunggu I/O (*Input/Output*), sehingga performa melesat eksponensial.

---

## Rencana Pengujian (Verification Plan)
- **Unit Test:** Menjalankan unit test via `adjusment_ppn/run_tests_via_python.py` untuk memastikan bahwa logika silang subsidi (A1 Priority) dan penarikan stok celengan tidak kacau atau menjadi dobel akibat balapan antar-*thread* (Race Conditions).
- **Stress Test Manual:** Melakukan injeksi besar pada puluhan ribu data faktur untuk menguji apakah pemakaian RAM meningkat wajar (karena *caching* tabel barang) dan CPU Load menyentuh batas target ~70%.
