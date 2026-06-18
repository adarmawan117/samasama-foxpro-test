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
   - **a. Membaca Data Cabang:** Setelah koneksi berhasil teruji, sistem akan secara otomatis membaca dan memuat seluruh daftar kode cabang (akun) yang aktif dari database asal ke dalam menu pilihan.
   - **b. Pengaman Kegagalan:** Jika koneksi ke salah satu database gagal (misalnya karena salah ketik password atau file tidak ditemukan), sistem akan memunculkan pesan peringatan merah dan mengunci tombol proses demi menghindari kesalahan data.

### 4. Menentukan Parameter dan Target Pajak PPN
4. Pengguna memilih cabang yang akan disesuaikan, menentukan rentang tanggal transaksi, serta memasukkan angka target pajak yang ingin dicapai.
   - **a. Pilihan Cabang (Akun):** Klik menu dropdown akun dan pilih cabang toko yang ingin disesuaikan. Kini tersedia pilihan **"ALL - A1 & A3 (Gabungan)"**.
   - **b. Batasan Tanggal:** Tentukan tanggal mulai dan tanggal akhir penyesuaian agar transaksi di luar rentang waktu tersebut tidak ikut terganggu.
   - **c. Pengisian Target Pajak:** Masukkan nominal target pajak PPN yang diinginkan. Jika Anda memilih "ALL", target ini akan dipotong secara proporsional ke total omset gabungan A1 dan A3.

### 5. Menjalankan Penyesuaian (Adjustment)
5. Pengguna menekan tombol **Proses** untuk memulai perhitungan dan perubahan transaksi di database target secara otomatis di latar belakang.
   - **a. Deteksi Transaksi Ulang (Rerun):** Jika sistem mendeteksi bahwa penyesuaian pernah dijalankan sebelumnya pada rentang tanggal yang sama, sistem akan menampilkan pertanyaan konfirmasi. Pengguna dapat memilih untuk membatalkan proses atau menyetujui penulisan ulang data (rerun).
   - **b. Pemulihan Otomatis (Rollback):** Jika pengguna menyetujui rerun, sistem akan melakukan pemulihan otomatis terlebih dahulu untuk mengembalikan jumlah barang di celengan ke posisi semula dan membersihkan transaksi sebelumnya agar tidak terjadi penumpukan data ganda.
   - **c. Ekspor Laporan Akhir:** Setelah penyesuaian selesai, pengguna dapat menekan tombol **Export** untuk menyimpan seluruh detail tindakan pemotongan atau penambahan barang ke dalam file Excel/CSV sebagai arsip laporan.

---

## Penjelasan Aturan Bisnis Penyesuaian

Sistem ini bekerja layaknya sebuah tim pencatat keuangan yang menggunakan metode tabungan dan utang barang (celengan) agar transaksi yang dilaporkan tetap logis dan tidak mencurigakan. Berikut adalah penjelasannya dalam bahasa sehari-hari:

### 6. Potong Omset dan Celengan Barang
6. Ketika target pajak yang Anda masukkan mengharuskan pengurangan omset penjualan, sistem akan memotong jumlah barang yang terjual di database target.
   - **a. Cara Pemotongan:** Sistem akan memilah barang-barang yang dikenakan pajak, lalu mengurangi jumlahnya secara adil (proporsional) mulai dari transaksi yang paling bawah (terakhir) pada nota penjualan.
   - **b. Aturan Anti-Nota Kosong:** Sistem menjaga agar tidak ada nota penjualan yang menjadi kosong atau terhapus total. Jika sebuah nota hanya berisi satu barang, sistem akan menyisakan minimal 1 unit barang agar nota tersebut tetap sah.
   - **c. Celengan Barang:** Jumlah barang yang dipotong dari transaksi penjualan ini tidak dibuang begitu saja, melainkan disimpan ke dalam sistem "Celengan Barang" (tabungan) sebagai stok cadangan yang sewaktu-waktu bisa digunakan kembali jika kita perlu menaikkan omset.

### 7. Tambah Omset Menggunakan Celengan
7. Ketika target pajak mengharuskan penambahan omset penjualan, sistem akan mencoba menambahkan jumlah barang terjual pada nota tanpa membuat data baru dari nol.
   - **a. Prioritas Utama:** Sebelum menyisipkan barang sembarangan, sistem akan melihat apakah kita memiliki stok cadangan di "Celengan Barang" (hasil pemotongan dari aturan nomor 6).
   - **b. Pencocokan Nilai (Prioritas A):** Sistem akan mencari barang di celengan yang total nilainya (harga dikali jumlah barang) pas dengan nominal tambahan yang dibutuhkan nota tersebut.
   - **c. Pencocokan Sebagian (Prioritas B):** Jika tidak ada yang pas, sistem mencari barang di celengan yang harga satuannya kelipatan dari nilai tambahan yang dibutuhkan nota, lalu mengambil sebagian stok dari celengan tersebut.
   - **d. Pencocokan Terdekat (Prioritas C):** Jika masih tidak ada, sistem akan mengambil barang dari celengan yang nilainya paling mendekati target tambahan tanpa melebihinya.

### 8. Pinjam Barang (Hutang)
8. Jika celengan barang kosong atau tidak mencukupi untuk memenuhi kebutuhan tambah omset, sistem akan menggunakan metode pinjam barang.
   - **a. Suntikan Fiktif:** Sistem akan memilih barang kena pajak yang harganya paling cocok untuk menutupi kekurangan target tambahan nota, lalu menambahkannya ke nota penjualan tersebut.
   - **b. Catatan Hutang:** Karena barang tersebut tidak diambil dari celengan stok riil, sistem akan mencatat tindakan ini sebagai "Hutang Barang" (minus) di buku kasir target. Ini berarti toko kita berutang stok barang tersebut pada laporan pajak.

### 9. Bayar Hutang (Self-Healing)
9. Sistem memiliki kecerdasan untuk melunasi hutang barang secara otomatis tanpa campur tangan pengguna saat ada kesempatan pemotongan omset berikutnya.
   - **a. Pelunasan Otomatis:** Apabila di masa mendatang (atau pada nota lain di rentang tanggal yang sama) terjadi pemotongan omset untuk barang yang sedang kita utangi, jumlah barang yang dipotong tersebut akan langsung dialokasikan untuk melunasi hutang terlebih dahulu.
   - **b. Bebas Hutang:** Setelah hutang lunas, sisa barang hasil pemotongan baru akan dimasukkan kembali sebagai celengan barang (plus) yang siap digunakan untuk penambahan omset berikutnya.

### 10. Distribusi Sisa Pembulatan (Global Gap)
10. Akibat pembulatan pecahan desimal dan batas minimal nota, terkadang masih tersisa sedikit selisih angka (gap) setelah penyesuaian utama selesai.
    - **a. Pembagian Selisih Kurang:** Jika omset masih kelebihan sedikit dari target, sistem akan memilih nota secara acak dan memotong barang berharga tinggi yang ada di dalamnya sampai target pas.
    - **b. Pembagian Selisih Tambah:** Jika omset masih kurang sedikit dari target, sistem akan memilih nota secara acak, mengambil sisa celengan yang masih ada, atau menyuntikkan barang dengan nilai terdekat agar selisih tersebut tertutup sempurna.

### 11. Fitur Gabungan Akun (Silang Subsidi)
11. Jika Anda memilih opsi "ALL - A1 & A3 (Gabungan)", sistem akan memproses kedua cabang secara bersamaan dengan keuntungan "Silang Subsidi":
    - **a. Berbagi Celengan:** Kelebihan atau sisa barang hasil pemotongan (celengan) dari cabang A1 dapat secara otomatis dipakai untuk menambal kekurangan target di nota cabang A3, begitu pula sebaliknya.
    - **b. Target Gabungan:** Anda hanya perlu memasukkan satu angka target pajak, dan sistem akan membaginya secara adil ke kedua cabang sesuai besar omset masing-masing.
    - **c. Penanda Log:** Pada hasil export laporan akhir (CSV), setiap baris tindakan akan diberi penanda `[A1]` atau `[A3]` agar Anda mudah melacak dari cabang mana transaksi tersebut berasal.
