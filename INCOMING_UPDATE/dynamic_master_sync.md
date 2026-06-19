# AGENT HANDOFF DOCUMENT: Dynamic Master Data Sync
**STATUS:** PENDING (Ditunda karena ada prioritas lain yang lebih *urgent*)

Halo Agen AI! Jika Anda membaca dokumen ini, Anda ditugaskan untuk mengembangkan fitur *Dynamic Master Data Synchronization* pada aplikasi PPN Tax Adjustment. Dokumen ini merangkum seluruh konteks arsitektur agar Anda bisa langsung memahami masalah tanpa perlu melihat riwayat percakapan sebelumnya.

## 1. Konteks Arsitektur (Server Ori vs Server Gemuk)
Aplikasi ini melakukan penyesuaian (manipulasi) nilai Pajak Pertambahan Nilai (PPN) dari database perusahaan.
- **Server Ori (Source DB):** Database *live* asli milik perusahaan. Ini adalah sumber kebenaran data (*source of truth*).
- **Server Gemuk (Target DB):** Database kloningan yang khusus digunakan untuk uji coba atau pelaporan yang telah dimanipulasi (khususnya tabel omset/penjualan).

## 2. Definisi Masalah
Jika seorang auditor memeriksa "Server Gemuk", mereka berharap profil perusahaan, rincian pelanggan, info *supplier*, dan gudang adalah **sama persis (*mirror 100%*)** dengan "Server Ori".
Saat ini, sebelum proses penyesuaian pajak berjalan (diatur di `adjustment_ppn_gui/workers.py`), sistem memanggil fungsi `sync_master_data()` (terletak di `adjustment_ppn_core/etl/sync_manager.py`). 
**Bug/Kekurangan:** Fungsi ini di-*hardcode* hanya untuk melakukan *TRUNCATE* dan *INSERT* pada 3 tabel saja (`barang`, `accinv`, dan `golongan`). Jika ada *supplier* baru di Server Ori, Server Gemuk tidak akan mengetahuinya karena tabel `supplier` tidak ikut disinkronisasi.

## 3. Misi Anda
Ubah logika di dalam `sync_master_data()` agar tidak lagi statis/hardcode. Fungsi ini harus menggunakan `SHOW TABLES` (atau ekuivalen) di *Source DB* untuk menarik daftar SEMUA tabel, kemudian menyalinnya (*TRUNCATE & Batch INSERT*) ke *Target DB*.

## 4. PERINGATAN KRITIS & Blocker
**ANDA TIDAK BOLEH MENYINKRONISASIKAN (MENIMPA) TABEL TRANSAKSI.**
Server Gemuk memiliki data transaksi (historis maupun yang sedang diedit) yang *haram* untuk di-*reset* ke aslinya. Jika Anda menimpa tabel transaksi, Anda akan menghapus hasil manipulasi PPN yang sudah susah payah dihitung!

**Langkah pertama yang HARUS Anda lakukan sebelum menyentuh kode:**
Tanyakan kepada User bagaimana cara memisahkan "Tabel Transaksi" dengan "Tabel Master":
- **Opsi A (Prefix):** Apakah tabel transaksi di database ini memiliki awalan spesifik? (Misal: awalan `d` untuk *detail* dan `h` untuk *header* seperti `djual`, `hjual`, `dbeli`).
- **Opsi B (Blacklist):** Minta User mendaftar semua tabel transaksi yang eksis secara eksplisit untuk Anda abaikan (*exclude*).

*Catatan: Tabel berikut sudah pasti masuk Blacklist dan jangan pernah disentuh oleh `sync_master_data`:*
- Tabel transaksi utama: `djual`, `drjual`, `dbeli`, `drbeli`
- Tabel penampungan internal aplikasi: `tabungan_dan_hutang`, `log_mutasi_tabungan`, `SETOR_PAJAK_DETAIL`

## 5. Lokasi File Penting
- **Root Direktori:** `c:\Users\adarmawan117\Downloads\UndfxffAllW\RESULTS\python_test`
- **Logic Sinkronisasi:** `adjustment_ppn_core/etl/sync_manager.py` (Fokus pada fungsi `sync_master_data`)
- **Pemanggilan Logic:** `adjustment_ppn_gui/workers.py` (Di dalam `WorkerThread.run()`)

---
**Instruksi Eksekusi:** Silakan buat `implementation_plan.md` berdasarkan dokumen ini, pastikan Anda mendapatkan izin dan jawaban *blacklist* dari User, baru kemudian modifikasi `sync_manager.py`. Good luck!
