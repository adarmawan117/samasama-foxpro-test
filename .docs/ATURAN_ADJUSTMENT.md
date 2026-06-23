# Panduan Lengkap Aturan Penyesuaian Omset (Bahasa Awam)

Dokumen ini menjelaskan secara spesifik bagaimana sistem secara cerdas melakukan pemotongan (penurunan omset) dan penambahan (kenaikan omset) tanpa merusak keaslian nota dan nomor urut faktur pajak Anda.

## A. Aturan Pengurangan Omset (Target Turun)

Saat Anda ingin menurunkan omset, sistem tidak bisa asal menghapus data. Agar tidak ada nomor urut faktur yang hilang/bolong (yang bisa dicurigai oleh auditor), sistem melakukan 3 tahapan (Pass) secara berurutan:

### Tahap 1: Sunat Proporsional (Pass 1)
Sistem akan memangkas kuantitas (QTY) barang dari seluruh nota secara adil (persentase). 
Misal, barang A awalnya terjual 10 pcs, dipangkas menjadi 4 pcs. Barang yang dipangkas (6 pcs) akan masuk ke **Celengan** (Tabungan Barang).

### Tahap 2: Sunat Rata (Pass 2)
Jika omset masih belum cukup turun, sistem akan memangkas semua barang yang memiliki QTY lebih dari 1, dengan cara dikurangi 1 per 1 secara acak, hingga semua barang mentok di angka QTY = 1.

### Tahap 3: Hapus Fisik Terkendali (Pass 3)
Jika semua barang sudah mentok di QTY = 1 tapi target turun omset masih belum tercapai, sistem akan terpaksa menghapus barang tersebut dari nota. Namun, penghapusan ini tunduk pada 2 aturan ketat:

1. **Aturan Hapus Aman (Rule 1 / Pass 3a)**
   Sistem boleh menghapus sebuah barang dari nota **ASALKAN** di dalam nota tersebut masih ada barang lain. Artinya, nota tersebut tidak akan menjadi kosong (masih memiliki nilai jual lain).

2. **Aturan Hapus Mundur (Rule 2 / Pass 3b)**
   Jika sebuah nota HANYA berisi 1 barang saja, maka penghapusan barang tersebut akan menyebabkan nota menjadi kosong (menghilang).
   Sistem **hanya mengizinkan** ini jika nota tersebut adalah nota **paling terakhir** di bulan tersebut. Sistem akan menghapus dari belakang (nota tanggal 31 jam 23:59, lalu mundur ke jam sebelumnya).
   
   **HALT (Berhenti Paksa):**
   Jika sistem sedang mundur dan menemui nota tunggal di *tengah-tengah* bulan, sistem akan otomatis BERHENTI dan menolak melakukan penghapusan lebih lanjut. Mengapa? Karena menghapus nota di tengah bulan akan membuat nomor urut faktur melompat (misal faktur 001, 002, 004 -> faktur 003 hilang).

---

## B. Aturan Penambahan Omset (Target Naik)

Saat Anda ingin menaikkan omset, sistem akan menambahkan barang ke nota-nota yang sudah ada tanpa membuat nomor faktur baru dari nol.

### Tahap 1: Pencarian Celengan (Prioritas Tabungan)
Sistem akan melihat apakah kita memiliki sisa barang hasil pemotongan (celengan) dari bulan/transaksi lain. Jika ada, sistem akan memasukkan barang celengan tersebut ke faktur penjualan. Hal ini memprioritaskan "stok asli" yang pernah terpotong agar perputaran barang tetap logis.

### Tahap 2: Suntikan Barang Fiktif
Jika celengan kosong, sistem akan menyuntikkan (menambahkan) barang baru dari master barang ke dalam nota penjualan. Sistem menggunakan logika seperti pembeli asli:
- **Kategori Sama:** Barang PPN hanya disuntikkan ke nota PPN. Barang bebas pajak (BTKP) hanya disuntikkan ke nota BTKP.
- **Acak Kuantitas:** Pembelian disimulasikan secara acak (misal 2 pcs, 3 pcs) menggunakan harga satuan (`HARGA11`). Tidak asal beli 1 barang sebanyak 10.000 pcs.
- **Tanpa Diskon:** Barang yang disuntik tidak akan dikenakan diskon apapun untuk menghindari anomali harga.

### Tahap 3: Bayar Hutang (Self-Healing)
Karena suntikan fiktif menggunakan barang yang "tidak pernah terjual" (diadakan secara paksa), sistem akan mencatatnya sebagai "Hutang Barang" (Minus).
Jika di proses penyesuaian berikutnya omset harus diturunkan dan barang tersebut harus dipotong, hasil pemotongan tersebut tidak akan masuk ke celengan, melainkan **dipakai untuk melunasi hutang** terlebih dahulu.

---

## Ringkasan
- **Mau turun drastis?** Bisa, tapi hanya sampai batas di mana tidak ada nomor urut faktur tengah bulan yang hilang.
- **Mau naik drastis?** Bisa, sistem meminjam barang dan menyebarkannya dengan metode acak ke faktur-faktur acak agar tidak mencolok.
