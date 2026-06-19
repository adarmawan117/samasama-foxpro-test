# Rencana Pengembangan Fase 2: Implementasi Multi-threading pada Proses Penyesuaian

## Latar Belakang
Saat ini, proses *Adjustment* (Penyesuaian PPN) berjalan menggunakan *single-thread* pada `WorkerThread` di backend. Ketika melakukan proses iterasi ke ratusan atau ribuan struk (terutama saat *Fictional Injection* atau *Draw Savings*), proses memakan waktu yang cukup lama.

## Kebutuhan (Requirements)
1. **Multithreading/Multiprocessing:** Proses penyesuaian (terutama `proses_penambahan_omset`, `proses_pengurangan_omset`, dan `distribusikan_global_gap`) harus dibuat berjalan paralel (multithread) agar lebih cepat.
2. **Dynamic Resource Allocation:** Sistem tidak boleh di-*hardcode* jumlah *thread*-nya (misalnya langsung `max_workers=10`). Sistem harus mendeteksi secara dinamis jumlah *core* CPU atau kemampuan komputasi perangkat yang digunakan (misal `os.cpu_count()`), lalu menggunakan persentase daya komputasi yang aman (misalnya 70%-80% dari total *core*) agar PC pengguna tidak hang/berat.
3. **Thread Safety pada Database:** Karena menggunakan SQLite / MySQL secara konkuren, harus diimplementasikan *Connection Pooling* atau antrean tulis (*write queue*) yang *thread-safe* agar tidak terjadi *database lock* (OperationalError) atau *race condition* saat mencatat *log* mutasi tabungan atau memperbarui tabel `djual`.

## Target File yang Akan Dimodifikasi
1. `adjustment_ppn_core/calculator/adjustment.py` (untuk memecah *workload* loop faktur agar bisa diparalelkan via `concurrent.futures.ThreadPoolExecutor` atau `ProcessPoolExecutor`).
2. `adjustment_ppn_gui/workers.py` (untuk mengatur siklus hidup *thread pool* dan menyalurkan sinyal progres ke GUI).
3. `adjustment_ppn_core/database/connection.py` (jika diperlukan penyesuaian agar *connection* bersifat *thread-safe* atau *thread-local*).

## Eksekusi
- **Status:** Menunggu (Fase 2).
- Eksekusi fitur ini akan dilakukan HANYA SETELAH fase pemerataan *chunking global gap* selesai dan stabil.
