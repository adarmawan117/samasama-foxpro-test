# Alur Testing: Modifikasi Logic Proses Omset (PPN Breakdown)

Dokumen ini berisi panduan *step-by-step* untuk memverifikasi bahwa kalkulasi pemecahan omset (berdasarkan `PAJAK` barang menjadi *PPN*, *BTKP*, dan *Lain-lain*) berjalan dengan akurat menggunakan database asli dari server (MySQL 5.0 -> MySQL 5.7).

## 1. Persiapan Environment
1. Pastikan servis **MySQL 5.7** di FlyEnv sudah berjalan (status *Running*).
2. Buka terminal (Command Prompt/PowerShell), navigasi ke direktori proyek:
   ```cmd
   cd c:\Users\adarmawan117\Downloads\UndfxffAllW\RESULTS\python_test
   ```
3. Aktifkan *Virtual Environment* Python:
   ```cmd
   .\venv\Scripts\activate
   ```

## 2. Proses Rekapitulasi Data (Backend Logic)
Langkah ini menggantikan proses perhitungan *gelondongan* lama yang ada di FoxPro (`MIRROR_OMSETX.SCX`).

1. Jalankan aplikasi pemrosesan omset:
   ```cmd
   python proses_omset_detail_gui.py
   ```
   *(Atau Anda bisa langsung klik ganda `run_proses_omset.cmd` dari File Explorer)*
2. Di jendela aplikasi **Proses Data Omset**:
   - Biarkan opsi **Account** pada `SEMUA ACC`.
   - Pilih **Tanggal Awal** dan **Tanggal Akhir** ke periode yang datanya terisi padat di database (misal: `1 Mei 2026` hingga `31 Mei 2026`).
3. Tekan tombol **Proses**.
4. Tunggu *progress bar* hingga selesai (karena melibatkan lebih dari 5,3 juta record `djual`, proses mungkin memakan waktu beberapa saat).
5. Akan muncul notifikasi *Sukses* ketika kalkulasi selesai.

## 3. Verifikasi Data (Frontend UI)
Setelah data terhitung dan masuk ke tabel `SETOR_PAJAK_DETAIL`, kita perlu melihat hasilnya.

1. Tutup aplikasi `proses_omset_detail_gui.py`.
2. Dari terminal yang sama, jalankan aplikasi penampil UI:
   ```cmd
   python isi_omset_detail_gui.py
   ```
   *(Atau jalankan via `run_test_detail.cmd`)*
3. Pada tabel grid antarmuka yang muncul:
   - Pastikan terdapat pemisahan baris untuk **Bulan/Tahun** yang sama (misalnya `05-2026`).
   - Anda seharusnya melihat maksimal 3 baris kategori:
     - `PPN (PPN + Gung gung)`
     - `BTKP`
     - `Lain-lain`
   - Pastikan nominal pada kolom **Penjualan (Jual)**, **Retur Penjualan (R Jual)**, **Pembelian (Beli)**, dan **Retur Pembelian (R Beli)** terisi sesuai hasil kalkulasi bersyarat.

## 4. Validasi Akhir (Opsional tapi Direkomendasikan)
Untuk memastikan tidak ada record `djual` yang bocor atau tidak ikut terhitung:
1. Hitung manual (jumlahkan) total Jual dari ketiga baris (`PPN`, `BTKP`, `Lain-lain`) pada bulan `05-2026`.
2. Bandingkan angka total tersebut dengan total omset *gelondongan* (semua kategori) yang biasa Anda lihat melalui program Visual FoxPro lama (`isi_omset.scx`).
3. Jika totalnya **sama persis**, maka algoritma baru ini valid dan siap diimplementasikan penuh.
