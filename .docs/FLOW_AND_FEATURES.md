# Alur dan Fitur Penyesuaian Pajak PPN (FLOW_AND_FEATURES.md)

Dokumen ini menjelaskan langkah-langkah penggunaan sistem penyesuaian PPN beserta aturan-aturan bisnis di dalamnya agar pemakaian lebih mudah dipahami, aman, dan lancar untuk kebutuhan pelaporan keuangan Anda.

## Alur Penggunaan Aplikasi

### 1. Menentukan Database Asal
1. Pengguna menentukan file database asal yang berisi seluruh data transaksi penjualan asli yang belum diubah.
   - **a. Memilih File:** Klik tombol browse untuk mencari file database asal di komputer Anda (biasanya berakhiran `.db` atau `.sqlite`).
   - **b. Input MySQL:** Jika menggunakan server MySQL, masukkan alamat host, port, username, password, dan nama database asal secara lengkap pada kolom yang tersedia.

### 2. Menentukan Database Target Pajak
2. Pengguna menentukan database tujuan yang akan digunakan khusus untuk pelaporan pajak (database target).
   - **a. Menentukan File Target:** Pilih lokasi penyimpanan file database target yang baru atau yang sudah ada melalui tombol browse.
   - **b. Konfirmasi Kloning:** Jika database target yang Anda pilih ternyata belum ada di komputer Anda, sistem akan mendeteksinya secara otomatis dan menawarkan untuk membuatkannya langsung dengan menyalin struktur dan data awal dari database asal.

### 3. Melakukan Tes Koneksi
3. Pengguna menekan tombol **Tes Koneksi** untuk memastikan kedua database dapat terhubung dengan lancar dan aman.
   - **a. Penyimpanan Otomatis (Auto-Save):** Jika tes koneksi berhasil, sistem akan langsung menyimpan pengaturan koneksi Anda ke dalam file `connection_settings.json` agar Anda tidak perlu mengetik ulang saat membuka aplikasi di kemudian hari.
   - **b. Membaca Data Cabang:** Sistem akan membaca daftar kode cabang (akun) dari tabel `accinv`. Jika tabel tersebut kosong, sistem memiliki kecerdasan buatan untuk beralih (*fallback*) mencari akun yang aktif langsung dari tabel `BARANG`.
   - **c. Pengaman Kegagalan:** Jika koneksi ke salah satu database gagal, sistem memunculkan pesan peringatan merah dan mengunci tombol proses demi menghindari kesalahan data.

### 4. Menentukan Parameter dan Target Pajak (Double Engine PPN & BTKP)
4. Pengguna memilih cabang yang akan disesuaikan, menentukan rentang tanggal transaksi, serta memasukkan angka target pajak secara terpisah untuk PPN dan BTKP di UI.
   - **a. Pilihan Cabang (Akun):** Klik menu dropdown akun dan pilih cabang toko yang ingin disesuaikan. Kini tersedia pilihan **"ALL - A1 & A3 (Gabungan)"**.
   - **b. Batasan Tanggal:** Tentukan tanggal mulai dan tanggal akhir penyesuaian agar transaksi di luar rentang waktu tersebut tidak ikut terganggu.
   - **c. Pengisian Target Pajak Terpisah (Double Engine):** Masukkan nominal target secara independen pada kolom `target_ppn_input` (untuk barang kena pajak) dan `target_btkp_input` (untuk barang bebas pajak).
   - **d. Tampilan Output Detail:** Sistem menampilkan total penjualan kotor asli, retur, dan penjualan bersih (netto) secara terpisah di UI untuk memantau status secara langsung:
     - Penjualan Asli: `current_ppn_omset_input` dan `current_btkp_omset_input`
     - Retur: `current_ppn_retur_input` dan `current_btkp_retur_input`
     - Omset Bersih: `current_net_ppn_input` dan `current_net_btkp_input`
   - **e. Kalkulasi Single-Scan Efisien:** Di balik layar (`workers.py`), sistem melakukan satu query database menggunakan fungsi `SUM(CASE WHEN...)` untuk menghitung omset PPN (filter `b.PAJAK IN (1, 3)`) dan BTKP (filter `b.PAJAK = 2`) sekaligus. Hal ini menghemat penggunaan memori RAM Python secara signifikan karena tidak perlu menarik ribuan baris data transaksi ke memori untuk dihitung secara manual.

### 5. Menjalankan Penyesuaian (Arsitektur Dual-Loop & Commit Terisolasi)
5. Pengguna menekan tombol **Proses** untuk memulai perhitungan dan perubahan transaksi di database target secara otomatis di latar belakang melalui mekanisme Dual-Loop.
   - **a. Alur Eksekusi Terpisah (Dual-Loop):** Proses penyesuaian dijalankan dalam dua fase terisolasi secara sekuensial (fase PPN terlebih dahulu, diikuti fase BTKP) melalui modul `adjustment_dual.py`. Hal ini mencegah konflik penulisan data dan menjaga kebersihan logika program.
   - **b. Commit Transaksi Mandiri:** Di setiap akhir fase (setelah siklus penyesuaian PPN selesai dan sebelum siklus BTKP dimulai), sistem memanggil `target_conn.commit()`. Komitmen memori terpisah ini melepaskan penguncian (row/page locks) pada database, mencegah masalah database terkunci (*lock contention*), mengurangi risiko kebocoran memori (*memory leak*), dan menghindari error fatal *access violation* pada sistem operasi.
   - **c. Deteksi Transaksi Ulang (Rerun):** Jika sistem mendeteksi bahwa penyesuaian pernah dijalankan sebelumnya pada rentang tanggal yang sama, sistem akan menampilkan pertanyaan konfirmasi. Pengguna dapat memilih untuk membatalkan proses atau menyetujui penulisan ulang data (rerun).
   - **d. Pemulihan Otomatis (Rollback):** Jika pengguna menyetujui rerun, sistem akan melakukan pemulihan otomatis terlebih dahulu untuk mengembalikan jumlah barang di celengan ke posisi semula dan membersihkan transaksi sebelumnya agar tidak terjadi penumpukan data ganda.
   - **e. Ekspor Laporan Akhir:** Setelah penyesuaian selesai, pengguna dapat menekan tombol **Export** untuk menyimpan seluruh detail tindakan pemotongan atau penambahan barang ke dalam file Excel/CSV sebagai arsip laporan.

---

## Penjelasan Aturan Bisnis Penyesuaian

Sistem ini bekerja layaknya sebuah tim pencatat keuangan yang menggunakan metode tabungan dan utang barang (celengan) agar transaksi yang dilaporkan tetap logis dan tidak mencurigakan. Berikut adalah penjelasannya dalam bahasa sehari-hari:

### 6. Potong Omset dan Celengan Barang
6. Ketika target pajak yang Anda masukkan mengharuskan pengurangan omset penjualan, sistem akan memotong jumlah barang yang terjual di database target.
   - **a. Cara Pemotongan:** Sistem akan memilah barang-barang yang sesuai kategori pajak (PPN vs BTKP), lalu mengurangi jumlahnya secara adil (proporsional) mulai dari transaksi yang paling bawah (terakhir) pada nota penjualan.
   - **b. Aturan Anti-Hapus Kuantitas Minimal 1 (Global Reduction Loop):** Sistem menjamin tidak ada baris transaksi (`djual`) yang dihapus secara fisik (tidak menggunakan kueri `DELETE`). Pengurangan kuantitas dibatasi hingga batas aman minimal 1 unit (`max_qty_to_reduce = item['jumlah'] - 1`). Jika suatu baris barang sudah bernilai 1, sistem akan mengabaikannya agar nota tersebut tidak kosong atau nomor struk melompat (terputus).
   - **c. Celengan Barang:** Jumlah barang yang dipotong dari transaksi penjualan ini tidak dibuang begitu saja, melainkan disimpan ke dalam sistem "Celengan Barang" (tabungan) sebagai stok cadangan yang sewaktu-waktu bisa digunakan kembali jika kita perlu menaikkan omset.

### 7. Tambah Omset Menggunakan Celengan
7. Ketika target pajak mengharuskan penambahan omset penjualan, sistem akan mencoba menambahkan jumlah barang terjual pada nota tanpa membuat data baru dari nol.
   - **a. Prioritas Utama:** Sebelum menyisipkan barang sembarangan, sistem akan melihat apakah kita memiliki stok cadangan di "Celengan Barang" (hasil pemotongan dari aturan nomor 6).
   - **b. Pencocokan Nilai (Prioritas A):** Sistem akan mencari barang di celengan yang total nilainya (harga dikali jumlah barang) pas dengan nominal tambahan yang dibutuhkan nota tersebut.
   - **c. Pencocokan Sebagian (Prioritas B):** Jika tidak ada yang pas, sistem mencari barang di celengan yang harga satuannya kelipatan dari nilai tambahan yang dibutuhkan nota, lalu mengambil sebagian stok dari celengan tersebut.
   - **d. Pencocokan Terdekat (Prioritas C):** Jika masih tidak ada, sistem akan mengambil barang dari celengan yang nilainya paling mendekati target tambahan tanpa melebihinya.

### 8. Pinjam Barang (Hutang)
8. Jika celengan barang kosong atau tidak mencukupi untuk memenuhi kebutuhan tambah omset, sistem akan menggunakan metode pinjam barang.
   - **a. Suntikan Fiktif dengan Strict Scoping (Sistem Cabut Undian):** Sistem memilih barang fiktif dengan kategori pajak yang sama persis dengan nota penjualan target (`category_sql_filter`). Barang fiktif berkategori PPN hanya disuntikkan ke struk PPN asli, dan barang BTKP hanya ke struk BTKP asli. Pemilihan produk fiktif menggunakan **Global Exhaustion Pool** di mana seluruh produk sesuai filter diacak, dan barang yang telah dipakai akan dibuang permanen dari putaran agar tidak muncul berulang di faktur yang sama atau berdekatan (menghindari deteksi auditor). Jika daftar habis terpakai, sistem otomatis mereset dan mengacak ulangnya.
   - **b. Kuantitas Teracak (Random QTY):** Untuk menambah kealamian, sistem tidak akan menggunakan 1 jenis barang untuk langsung menambal target sekaligus (misal langsung beli 10 unit). Sistem akan **mengacak kuantitas** (misal 2 atau 3 unit), lalu mencari barang jenis lain lagi untuk menambal sisa kekurangannya, menciptakan variasi pembelanjaan layaknya pembeli asli.
   - **c. Catatan Hutang:** Karena barang tersebut tidak diambil dari celengan stok riil, sistem akan mencatat tindakan ini sebagai "Hutang Barang" (minus) di buku kasir target. Ini berarti toko kita berutang stok barang tersebut pada laporan pajak.

### 9. Bayar Hutang (Self-Healing)
9. Sistem memiliki kecerdasan untuk melunasi hutang barang secara otomatis tanpa campur tangan pengguna saat ada kesempatan pemotongan omset berikutnya.
   - **a. Pelunasan Otomatis:** Apabila di masa mendatang (atau pada nota lain di rentang tanggal yang sama) terjadi pemotongan omset untuk barang yang sedang kita utangi, jumlah barang yang dipotong tersebut akan langsung dialokasikan untuk melunasi hutang terlebih dahulu.
   - **b. Bebas Hutang:** Setelah hutang lunas, sisa barang hasil pemotongan baru akan dimasukkan kembali sebagai celengan barang (plus) yang siap digunakan untuk penambahan omset berikutnya.

### 10. Distribusi Sisa Pembulatan (Global Gap)
10. Akibat pembulatan pecahan desimal dan batas minimal nota, terkadang masih tersisa sedikit selisih angka (gap) setelah penyesuaian utama selesai. Sistem akan membagi rata sisa selisih ini ke seperempat (25%) dari total nota penjualan Anda.
    - **a. Pembagian Selisih Kurang:** Sistem akan mendistribusikan selisih sisa secara merata dengan mengambil sebagian barang dari 25% faktur agar tidak ada faktur tunggal yang mendadak susut nilainya.
    - **b. Pembagian Selisih Tambah:** Sistem akan mendistribusikan penambahan omset dari celengan atau menyuntikkan barang tambahan secara merata ke dalam 25% faktur yang ada, guna menghindari membengkaknya satu faktur penjualan menjadi nilai yang tidak logis.

### 11. Dukungan Pemrosesan Multi-Thread Cepat
11. Menghitung ribuan transaksi dalam hitungan detik membutuhkan kekuatan komputasi yang besar. Sistem ini kini dilengkapi dukungan _multithreading_ canggih untuk proses pemotongan (pengurangan) maupun penambahan omset:
    - **a. Perhitungan Otomatis Kekuatan PC:** Sistem mendeteksi jumlah core CPU (otak prosesor) komputer Anda secara otomatis, dan menggunakan hingga 70% kecepatannya (ThreadPoolExecutor) agar penyesuaian PPN berjalan jauh lebih cepat secara paralel.
    - **b. Caching RAM & Preloading:** Sebelum memulai pemrosesan paralel, sistem melakukan pre-load data master barang dan data celengan (savings) langsung ke memori (RAM) komputer. Ini menghilangkan kueri database yang berulang-ulang di dalam thread sehingga performa komputasi melesat tanpa hambatan I/O.
    - **c. Mekanisme Kunci Aman (Locking):** Demi menghindari bentrokan data (data races) saat beberapa thread mencoba mengakses celengan barang yang sama pada waktu bersamaan, sistem menerapkan mekanisme penguncian (Locking) yang sinkron dan thread-safe.
    - **d. Antrian Penulisan Aman:** Semua eksekusi perubahan data (INSERT, UPDATE, DELETE) dikirim ke DbWriterQueue yang memproses penulisan ke database secara berurutan pada satu thread khusus. Ini mencegah database mengalami penguncian (deadlock).

### 12. Auto-Sync Master Data dan Otomasi Tabel
12. Sebagai pengaman sebelum proses dimulai, aplikasi memproteksi integritas data dengan persiapan otomatis:
    - **a. Sinkronisasi Harga Barang:** Sistem secara otomatis akan menyalin ulang data dari tabel `barang`, `accinv`, dan `golongan` terbaru dari database asli untuk memastikan penyesuaian PPN menggunakan harga barang (HPP/Harga Jual) yang paling mutakhir.
    - **b. Penanganan Tabel Fleksibel:** Jika ada tabel transaksi tambahan seperti `drjual` atau `drbeli` (retur) yang belum dibuat di database, aplikasi akan membiarkannya alih-alih menampilkan error (crash), sehingga alur penyesuaian dapat terus berjalan lancar.

### 13. Fitur Gabungan Akun (Silang Subsidi)
13. Jika Anda memilih opsi "ALL - A1 & A3 (Gabungan)", sistem akan memproses kedua cabang secara bersamaan dengan keuntungan "Silang Subsidi":
    - **a. Berbagi Celengan:** Kelebihan atau sisa barang hasil pemotongan (celengan) dari cabang A1 dapat secara otomatis dipakai untuk menambal kekurangan target di nota cabang A3, begitu pula sebaliknya.
    - **b. Target Gabungan:** Anda hanya perlu memasukkan satu angka target pajak, dan sistem akan membaginya secara adil ke kedua cabang sesuai besar omset masing-masing.
    - **c. Penanda Log:** Pada hasil export laporan akhir (CSV), setiap baris tindakan akan diberi penanda `[A1]` atau `[A3]` agar Anda mudah melacak dari cabang mana transaksi tersebut berasal.

### 14. Aturan Prioritas A1 untuk Celengan Barang (A1 Priority Rule)
14. Demi menjaga konsistensi pelaporan pajak barang retail dan grosir, sistem menerapkan aturan prioritas untuk akun retail A1 atas akun grosir A3:
    - **a. Prioritas Akun A1:** Sebelum menyimpan data celengan baru (`tambah`), catatan hutang (`kurang`), atau melakukan suntikan fiktif dari celengan barang, sistem akan memeriksa tabel master barang. Jika kode barang (`KODE_BRG`) tersebut terdaftar di bawah akun `A1`, maka mutasi celengan barang tersebut wajib dicatat menggunakan akun `ACC = 'A1'`, meskipun nota transaksi yang sedang diproses berasal dari akun grosir `A3`.
    - **b. Fallback Akun Asal:** Jika barang tersebut tidak terdaftar di bawah akun `A1` pada master barang, sistem akan menggunakan akun asal dari nota transaksi tersebut (misalnya tetap dicatat sebagai `A3`).
    - **c. Pembersihan Bersih (Rollback):** Saat proses pemulihan (rollback) dijalankan untuk akun target tertentu (seperti `A3`), sistem akan mendeteksi barang-barang yang dialihkan ke akun `A1` tersebut secara otomatis. Sistem akan membersihkan riwayat mutasi celengan dan catatan hutang baik yang tercatat di `A3` maupun yang dialihkan ke `A1` untuk barang-barang terkait, sehingga data kembali bersih sempurna tanpa ada catatan celengan yang tertinggal.

### 15. Logika Perhitungan Target Penjualan dan Penanganan Duplikasi
15. Sistem mematuhi standar perhitungan terbaru yang langsung berpatokan pada Omset Kotor, serta mengamankan konsistensi data dari anomali duplikasi:
    - **a. Perhitungan Omset Saat Ini:** Sistem menghitung total omset saat ini secara terpisah untuk PPN dan BTKP dengan menjumlahkan harga bersih setelah diskon bertingkat dan diskon rupiah melalui satu kueri efisien.
    - **b. Selisih (GAP) Omset:** Angka target yang diinput di aplikasi kini langsung dibandingkan terhadap omset bersih per kategori pajak untuk mencari selisih (gap) penyesuaian.
    - **c. Harga Suntikan Fiktif:** Jika sistem harus menyuntikkan barang baru (fiktif) ke dalam struk penjualan, sistem akan mengambil patokan harga dari field **`HARGA11`** (satuan terkecil/pcs) di tabel master barang.
    - **d. Proteksi Duplikasi Master Barang (Bugfix 'Lain Lain'):** Untuk mencegah efek ledakan data (*Cartesian Explosion*) akibat duplikasi row / composite key pada tabel `barang` (di mana kombinasi `KODE_BRG` dan `ACC` bisa memiliki lebih dari satu baris karena riwayat perubahan harga), sistem menggunakan perintah kueri teragregasi dengan clause `GROUP BY KODE_BRG, ACC` dan `MAX(...)` saat memuat data master barang maupun data tabungan/hutang. Ini menghentikan bug membengkaknya omset barang generik seperti "Lain Lain".
    - **e. Nilai Diskon Fiktif Nol (Diskon 0):** Barang fiktif yang disuntikkan akan secara eksplisit diatur untuk tidak memiliki diskon sama sekali (persentase DISC1, DISC2, DISC3, dan nilai rupiah DISC_RP diatur langsung ke angka `0` via `VALUES 0` di select list). Hal ini menghindari anomali naiknya omset fiktif akibat kalkulasi diskon tidak terduga pada item cadangan.
