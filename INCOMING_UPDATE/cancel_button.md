# Rencana Pembaruan Mendatang (INCOMING_UPDATE): Fitur Pembatalan (Cancel/Stop)

## Deskripsi Tujuan
Menambahkan fitur "Batal" (Cancel) untuk menghentikan proses *adjustment* PPN (penyesuaian omset) di pertengahan jalan secara aman tanpa merusak database. Ketika dibatalkan, sistem akan berhenti memproses sisa faktur, menghentikan seluruh *thread* di latar belakang secara aman, dan memicu *database rollback* secara otomatis.

---

## Rencana Implementasi

### 1. Modifikasi Antarmuka (GUI) - `adjustment_ppn_gui/main_window.py`
- Tambahkan tombol `self.btn_batal = QPushButton("Batal")` di sebelah tombol "Proses".
- Buat *custom signal* baru: `batal_clicked = pyqtSignal()`.
- Hubungkan (bind) klik pada `btn_batal` ke `self.batal_clicked.emit`.

### 2. Modifikasi Controller - `adjustment_ppn_gui/controller.py`
- Tangkap sinyal klik batal: `self.view.batal_clicked.connect(self.on_batal_clicked)`.
- Saat `on_batal_clicked` dipanggil, periksa apakah `WorkerThread` sedang berjalan, lalu panggil metode `self.view.worker.cancel()`.
- Sesuaikan pengaktifan/penonaktifan `btn_batal` (diaktifkan hanya ketika proses sedang berjalan).

### 3. Modifikasi Worker Latar Belakang - `adjustment_ppn_gui/workers.py`
- Di dalam kelas `WorkerThread`, tambahkan variabel bendera (*flag*) `self._is_cancelled = False`.
- Buat metode `cancel(self)` yang akan mengubah `self._is_cancelled = True`.
- Buat fungsi penangkap status pembatalan, misal `lambda: self._is_cancelled`, lalu lempar ke dalam fungsi inti sebagai parameter `cancel_event`.
- Tangkap pengecualian khusus pembatalan (`ProcessCancelledException`) di dalam blok `try...except` dan pancarkan sinyal error ke GUI: `"Proses dibatalkan oleh pengguna."`

### 4. Modifikasi Inti Perhitungan - `adjustment.py` & `concurrency.py`
- Buat kelas pengecualian kustom `ProcessCancelledException` di dalam `concurrency.py`.
- Sesuaikan metode `stop_and_wait(self, commit=True)` di kelas antrian database (`DbWriterQueue`). Jika `commit=False`, panggil `target_conn.rollback()` alih-alih `commit()`.
- Di dalam iterasi `for` pemrosesan tiap faktur di `adjustment.py` (`proses_pengurangan_omset`, `proses_penambahan_omset`, dan `distribusikan_global_gap`), tambahkan pemeriksaan status: `if cancel_event and cancel_event(): break`.
- Setelah *loop* antrian komputasi selesai atau terputus, periksa sekali lagi apakah pembatalan terjadi. Jika iya, matikan paksa antrian penulisan dengan `db_queue.stop_and_wait(commit=False)` lalu angkat (raise) kesalahan `ProcessCancelledException`.

---

## Keamanan Data
Karena *rollback* diaktifkan seketika setelah interupsi, maka pembatalan di persentase berapapun (misal di faktur ke-688) akan menjamin **database target kembali utuh dan bersih** seperti sebelum proses dimulai. Database asli (sumber) juga tetap aman karena ia hanya bersifat "Baca-Saja" (*Read-Only*).
