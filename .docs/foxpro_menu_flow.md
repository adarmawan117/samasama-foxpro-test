# Alur Menu FoxPro untuk Form Data Omset (ISI_OMSET.SCX)

Berdasarkan analisis pada file struktur menu utama (`menut.mpr`), berikut adalah tahapan dan rute menu yang dilewati oleh user pada sistem FoxPro lama untuk mengakses form pengisian data omset (`isi_omset.scx`):

1. **Menu Utama (Menu Bar)**
   User membuka menu **`Utility`** (Shortcut: `Alt+U`).
   *(Didefinisikan pada baris 64: `DEFINE PAD _7EZ0SH22B OF (M.CMENUNAME) PROMPT '\<Utility'`)*

2. **Sub-Menu Level 1**
   Dari dalam menu *Utility*, user memilih menu **`Proses Omset`**.
   *(Didefinisikan pada baris 384: `DEFINE BAR 18 OF (A_MENUPOPS(18)) PROMPT 'Proses Omset'`)*

3. **Sub-Menu Level 2**
   Dari menu *Proses Omset* akan terbuka *popup* menu, lalu user mengklik **`Data Omset`**.
   *(Didefinisikan pada baris 476: `DEFINE BAR 3 OF (A_MENUPOPS(24)) PROMPT 'Data \<Omset'`)*

**Aksi Eksekusi:**
Ketika menu `Data Omset` diklik, sistem akan menjalankan form dengan perintah:
```foxpro
DO FORM ISI_OMSET.SCX
```
*(Didefinisikan pada baris 479: `ON SELECTION BAR 3 OF (A_MENUPOPS(24)) DO FORM ISI_OMSET.SCX`)*

---
**Ringkasan Hierarki Menu:**
`Utility` -> `Proses Omset` -> `Data Omset`
