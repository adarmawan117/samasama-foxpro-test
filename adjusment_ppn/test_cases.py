# test_cases.py
# This module defines the 52 test cases for the PPN and Tabungan/Hutang Adjustment logic.

DEFAULT_BARANG = [
    {"ACC": "001", "KODE_BRG": "BRG001", "NAMA_BRG": "Baju", "PAJAK": 1, "HRG_JUAL": 10000.0, "HRG_BELI": 8000.0},
    {"ACC": "001", "KODE_BRG": "BRG002", "NAMA_BRG": "Sabun", "PAJAK": 1, "HRG_JUAL": 1000.0, "HRG_BELI": 800.0},
    {"ACC": "001", "KODE_BRG": "BRG003", "NAMA_BRG": "Celana", "PAJAK": 1, "HRG_JUAL": 50000.0, "HRG_BELI": 40000.0},
    {"ACC": "001", "KODE_BRG": "BRG004", "NAMA_BRG": "Daster", "PAJAK": 1, "HRG_JUAL": 20000.0, "HRG_BELI": 16000.0},
    {"ACC": "001", "KODE_BRG": "BRG005", "NAMA_BRG": "Sepatu", "PAJAK": 1, "HRG_JUAL": 60000.0, "HRG_BELI": 48000.0},
    {"ACC": "001", "KODE_BRG": "BRG006", "NAMA_BRG": "Buku", "PAJAK": 2, "HRG_JUAL": 15000.0, "HRG_BELI": 12000.0},
    {"ACC": "001", "KODE_BRG": "BRG007", "NAMA_BRG": "Pensil", "PAJAK": 0, "HRG_JUAL": 2000.0, "HRG_BELI": 1600.0}
]

TEST_CASES = []

# ==========================================
# TIER 1: FEATURE COVERAGE (21 Cases)
# ==========================================

# TC-T1-01: Basic reduction: exact match of target
TEST_CASES.append({
    "id": "TC-T1-01",
    "tier": 1,
    "category": "Feature Coverage - Reduction",
    "description": "Basic reduction: exact match of target. Reduces Sabun by 2 qty, removing its row.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-2000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 2.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG002", "qty": 2.0, "tipe": "tambah"}
        ]
    }
})

# TC-T1-02: Basic reduction: qty > 1 decreased
TEST_CASES.append({
    "id": "TC-T1-02",
    "tier": 1,
    "category": "Feature Coverage - Reduction",
    "description": "Basic reduction: qty > 1 decreased. Sabun reduced from 3 to 1.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-2000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 3.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG002", "qty": 2.0, "tipe": "tambah"}
        ]
    }
})

# TC-T1-03: Scanning order (bottom-to-top)
TEST_CASES.append({
    "id": "TC-T1-03",
    "tier": 1,
    "category": "Feature Coverage - Reduction",
    "description": "Scanning order bottom-to-top. Items closer to the bottom are cut first.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-2000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 5.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 3.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG002", "qty": 2.0, "tipe": "tambah"}
        ]
    }
})

# TC-T1-04: Anti-Struk Kosong (single-item skipped)
TEST_CASES.append({
    "id": "TC-T1-04",
    "tier": 1,
    "category": "Feature Coverage - Reduction",
    "description": "Anti-Struk Kosong: cannot delete the only item in a receipt.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-10000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG003", "JUMLAH": 1.0, "HRG_BELI": 40000.0, "HRG_JUAL": 50000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG003", "JUMLAH": 1.0, "HRG_BELI": 40000.0, "HRG_JUAL": 50000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    }
})

# TC-T1-05: Deleting item row when qty reaches 0
TEST_CASES.append({
    "id": "TC-T1-05",
    "tier": 1,
    "category": "Feature Coverage - Reduction",
    "description": "Deleting item row when quantity is reduced to 0.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-1000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG002", "qty": 1.0, "tipe": "tambah"}
        ]
    }
})

# TC-T1-06: Decreasing item qty without row deletion
TEST_CASES.append({
    "id": "TC-T1-06",
    "tier": 1,
    "category": "Feature Coverage - Reduction",
    "description": "Decreasing quantity without row deletion because qty remains > 0.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-1000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 2.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG002", "qty": 1.0, "tipe": "tambah"}
        ]
    }
})

# TC-T1-07: Multiple reductions in one receipt
TEST_CASES.append({
    "id": "TC-T1-07",
    "tier": 1,
    "category": "Feature Coverage - Reduction",
    "description": "Multiple items reduced in a single invoice to meet reduction target.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-11000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 2.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "tambah"},
            {"acc": "001", "kode_brg": "BRG002", "qty": 1.0, "tipe": "tambah"}
        ]
    }
})

# TC-T1-08: Accumulate to global_gap due to rounding
TEST_CASES.append({
    "id": "TC-T1-08",
    "tier": 1,
    "category": "Feature Coverage - Reduction",
    "description": "Accumulating remainder to global_gap when exact reduction is impossible.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-2500"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    }
})

# TC-T1-09: Addition from savings: exact match (Price * Qty)
TEST_CASES.append({
    "id": "TC-T1-09",
    "tier": 1,
    "category": "Feature Coverage - Addition",
    "description": "Addition: Exact value matches and pulls Baju from savings.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "10000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "tambah"}
        ]
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    }
})

# TC-T1-10: Addition from savings: partial draw
TEST_CASES.append({
    "id": "TC-T1-10",
    "tier": 1,
    "category": "Feature Coverage - Addition",
    "description": "Addition from savings: pulls partial quantity of savings (2 out of 5 Baju).",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "20000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 5.0, "tipe": "tambah"}
        ]
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 2.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 3.0, "tipe": "tambah"}
        ]
    }
})

# TC-T1-11: Addition from savings: closest below target
TEST_CASES.append({
    "id": "TC-T1-11",
    "tier": 1,
    "category": "Feature Coverage - Addition",
    "description": "Addition: pulls closest possible below target. Target is 15000, draws 1 Baju (10000).",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "15000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "tambah"}
        ]
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 6.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG002", "qty": 5.0, "tipe": "kurang"}
        ]
    }
})

# TC-T1-12: Fictional injection: savings empty (increase existing qty)
TEST_CASES.append({
    "id": "TC-T1-12",
    "tier": 1,
    "category": "Feature Coverage - Addition",
    "description": "Fictional injection: savings empty. Increases Baju qty in receipt by 2.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "20000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 3.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 2.0, "tipe": "kurang"}
        ]
    }
})

# TC-T1-13: Fictional injection: savings empty (invent new item)
TEST_CASES.append({
    "id": "TC-T1-13",
    "tier": 1,
    "category": "Feature Coverage - Addition",
    "description": "Fictional injection: savings empty. Invents new item Sabun x3 from master barang.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "3000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 3.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG002", "qty": 3.0, "tipe": "kurang"}
        ]
    }
})

# TC-T1-14: Drain savings and transition to fictional
TEST_CASES.append({
    "id": "TC-T1-14",
    "tier": 1,
    "category": "Feature Coverage - Addition",
    "description": "Addition: Drains available savings Baju x1 and inserts fictional Sabun x9.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "19000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "tambah"}
        ]
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 10.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG002", "qty": 9.0, "tipe": "kurang"}
        ]
    }
})

# TC-T1-15: Addition uses latest master price
TEST_CASES.append({
    "id": "TC-T1-15",
    "tier": 1,
    "category": "Feature Coverage - Addition",
    "description": "Addition uses latest master price instead of historical transaction values.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "12000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "tambah"}
        ],
        "barang": [
            # Baju is now Rp12000 in Master
            {"ACC": "001", "KODE_BRG": "BRG001", "NAMA_BRG": "Baju", "PAJAK": 1, "HRG_JUAL": 12000.0, "HRG_BELI": 9000.0}
        ]
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 9000.0, "HRG_JUAL": 12000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    }
})

# TC-T1-16: Savings record deleted when qty = 0
TEST_CASES.append({
    "id": "TC-T1-16",
    "tier": 1,
    "category": "Feature Coverage - Addition",
    "description": "Savings record is fully deleted from tabungan_dan_hutang when remaining qty is 0.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "10000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "tambah"}
        ]
    },
    "expected": {
        "tabungan_dan_hutang": []
    }
})

# TC-T1-17: Global gap positive distribution (reduction)
TEST_CASES.append({
    "id": "TC-T1-17",
    "tier": 1,
    "category": "Feature Coverage - Global Gap",
    "description": "Global gap positive distribution: remaining reduction gap distributed to other invoice.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-12000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 2.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-16", "F_JUAL": "J20260616", "ACC": "001", "KODE_BRG": "BRG003", "JUMLAH": 1.0, "HRG_BELI": 40000.0, "HRG_JUAL": 50000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-16", "F_JUAL": "J20260616", "ACC": "001", "KODE_BRG": "BRG003", "JUMLAH": 1.0, "HRG_BELI": 40000.0, "HRG_JUAL": 50000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG002", "qty": 2.0, "tipe": "tambah"}
        ]
    }
})

# TC-T1-18: Global gap negative distribution (addition)
TEST_CASES.append({
    "id": "TC-T1-18",
    "tier": 1,
    "category": "Feature Coverage - Global Gap",
    "description": "Global gap negative distribution (addition matching & remainder).",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "10000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "tambah"}
        ]
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    }
})

# TC-T1-19: Tolerable minor gap ignored
TEST_CASES.append({
    "id": "TC-T1-19",
    "tier": 1,
    "category": "Feature Coverage - Global Gap",
    "description": "Tolerable minor gap is ignored without executing further reductions.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-500"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    }
})

# TC-T1-20: Self-Healing on reduction (debt exists)
TEST_CASES.append({
    "id": "TC-T1-20",
    "tier": 1,
    "category": "Feature Coverage - Self-Healing",
    "description": "Self-healing on reduction: reduces existing debt record instead of adding savings.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-10000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 2.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 5.0, "tipe": "kurang"}
        ]
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 4.0, "tipe": "kurang"}
        ]
    }
})

# TC-T1-21: Self-Healing full debt clearance
TEST_CASES.append({
    "id": "TC-T1-21",
    "tier": 1,
    "category": "Feature Coverage - Self-Healing",
    "description": "Self-healing on reduction: completely clears/deletes existing debt record.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-10000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 2.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "kurang"}
        ]
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    }
})


# ==========================================
# TIER 2: BOUNDARY & EDGE CASES (21 Cases)
# ==========================================

# TC-T2-01: Target change is 0%
TEST_CASES.append({
    "id": "TC-T2-01",
    "tier": 2,
    "category": "Boundary/Edge - Zero & Empty Values",
    "description": "Target adjustment is 0%, no database changes should occur.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "0"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    }
})

# TC-T2-02: Zero sales in month
TEST_CASES.append({
    "id": "TC-T2-02",
    "tier": 2,
    "category": "Boundary/Edge - Zero & Empty Values",
    "description": "Zero sales in targeted month, script executes without crashing.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "10000"
    },
    "initial": {
        "djual": [],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [],
        "tabungan_dan_hutang": []
    }
})

# TC-T2-03: Zero quantity in transaction
TEST_CASES.append({
    "id": "TC-T2-03",
    "tier": 2,
    "category": "Boundary/Edge - Zero & Empty Values",
    "description": "Transaction row has quantity=0. Ignored/skipped for adjustment.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-1000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 0.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 0.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    }
})

# TC-T2-04: Empty tabungan during addition
TEST_CASES.append({
    "id": "TC-T2-04",
    "tier": 2,
    "category": "Boundary/Edge - Zero & Empty Values",
    "description": "Empty tabungan during addition. Triggers fictional injection.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "10000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "kurang"}
        ]
    }
})

# TC-T2-05: Missing product price in Master
TEST_CASES.append({
    "id": "TC-T2-05",
    "tier": 2,
    "category": "Boundary/Edge - Zero & Empty Values",
    "description": "Product in tabungan is missing in Master BARANG. System skips it without crashing.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "10000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "MISSING_BRG", "qty": 1.0, "tipe": "tambah"}
        ]
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "MISSING_BRG", "qty": 1.0, "tipe": "tambah"},
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "kurang"}
        ]
    }
})

# TC-T2-06: Single item receipt (qty=1) under reduction
TEST_CASES.append({
    "id": "TC-T2-06",
    "tier": 2,
    "category": "Boundary/Edge - Single Item Receipts",
    "description": "Single item with qty=1 under reduction. Skipped to prevent empty invoice.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-10000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    }
})

# TC-T2-07: Single item receipt (qty>1) under reduction
TEST_CASES.append({
    "id": "TC-T2-07",
    "tier": 2,
    "category": "Boundary/Edge - Single Item Receipts",
    "description": "Single item with qty>1 under reduction. Allowed to reduce up to qty=1.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-20000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 3.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 2.0, "tipe": "tambah"}
        ]
    }
})

# TC-T2-08: Extremely high reduction target (99%)
TEST_CASES.append({
    "id": "TC-T2-08",
    "tier": 2,
    "category": "Boundary/Edge - Maximum/Extreme Values",
    "description": "99% reduction target: must retain at least one item row with qty 1.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-54450"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 5.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 5.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 4.0, "tipe": "tambah"},
            {"acc": "001", "kode_brg": "BRG002", "qty": 5.0, "tipe": "tambah"}
        ]
    }
})

# TC-T2-09: Extremely high addition target (500%)
TEST_CASES.append({
    "id": "TC-T2-09",
    "tier": 2,
    "category": "Boundary/Edge - Maximum/Extreme Values",
    "description": "500% addition target: handles injecting massive quantity of fictional items.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "500000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 50.0, "tipe": "kurang"}
        ]
    }
})

# TC-T2-10: Max integer qty handling (overflow check)
TEST_CASES.append({
    "id": "TC-T2-10",
    "tier": 2,
    "category": "Boundary/Edge - Maximum/Extreme Values",
    "description": "Max integer qty: reduces successfully without integer overflow or crash.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-1000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 2147483647, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 2147483646, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG002", "qty": 1.0, "tipe": "tambah"}
        ]
    }
})

# TC-T2-11: Very high item price in Master
TEST_CASES.append({
    "id": "TC-T2-11",
    "tier": 2,
    "category": "Boundary/Edge - Maximum/Extreme Values",
    "description": "Very high item price (1 billion) in Master is skipped for addition because it exceeds target.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "1000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG_LUXURY", "qty": 1.0, "tipe": "tambah"}
        ],
        "barang": [
            {"ACC": "001", "KODE_BRG": "BRG_LUXURY", "NAMA_BRG": "Luxury Item", "PAJAK": 1, "HRG_JUAL": 1000000000.0, "HRG_BELI": 800000000.0}
        ]
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 2.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG_LUXURY", "qty": 1.0, "tipe": "tambah"},
            {"acc": "001", "kode_brg": "BRG002", "qty": 1.0, "tipe": "kurang"}
        ]
    }
})

# TC-T2-12: Very low item price (Rp 1) matching target
TEST_CASES.append({
    "id": "TC-T2-12",
    "tier": 2,
    "category": "Boundary/Edge - Maximum/Extreme Values",
    "description": "Very low item price (Rp 1) matching target. Draws large quantity (1000) of cheap item.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "1000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG_CHEAP", "qty": 10000.0, "tipe": "tambah"}
        ],
        "barang": [
            {"ACC": "001", "KODE_BRG": "BRG_CHEAP", "NAMA_BRG": "Cheap Candy", "PAJAK": 1, "HRG_JUAL": 1.0, "HRG_BELI": 0.8}
        ]
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG_CHEAP", "JUMLAH": 1000.0, "HRG_BELI": 0.8, "HRG_JUAL": 1.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG_CHEAP", "qty": 9000.0, "tipe": "tambah"}
        ]
    }
})

# TC-T2-13: Multiple items with qty=1 under reduction
TEST_CASES.append({
    "id": "TC-T2-13",
    "tier": 2,
    "category": "Boundary/Edge - Receipt Details & Constraints",
    "description": "Multiple items with qty=1 under reduction. Lowest item(s) cut, topmost PPN item kept.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-61000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG003", "JUMLAH": 1.0, "HRG_BELI": 40000.0, "HRG_JUAL": 50000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG003", "JUMLAH": 1.0, "HRG_BELI": 40000.0, "HRG_JUAL": 50000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "tambah"},
            {"acc": "001", "kode_brg": "BRG002", "qty": 1.0, "tipe": "tambah"}
        ]
    }
})

# TC-T2-14: Negative qty in tabungan correction
TEST_CASES.append({
    "id": "TC-T2-14",
    "tier": 2,
    "category": "Boundary/Edge - Receipt Details & Constraints",
    "description": "Negative qty in tabungan: script auto-corrects to absolute value during execution.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "10000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": -1.0, "tipe": "tambah"}
        ]
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    }
})

# TC-T2-15: DBeli & DRBeli are untouched
TEST_CASES.append({
    "id": "TC-T2-15",
    "tier": 2,
    "category": "Boundary/Edge - Receipt Details & Constraints",
    "description": "Purchasing tables (DBELI and DRBELI) must never be modified by the script.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-2000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 2.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "dbeli": [
            {"NO_PB": "PB001", "TGL_BELI": "2026-06-10", "F_BELI": "B20260610", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 10.0, "HRG_BELI": 8000.0, "PPN": 10, "F_PPN": 10.0}
        ],
        "drbeli": [
            {"TGL_BELI": "2026-06-12", "F_BELI": "B20260612", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 2.0, "HRG_BELI": 800.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "dbeli": [
            {"NO_PB": "PB001", "TGL_BELI": "2026-06-10", "F_BELI": "B20260610", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 10.0, "HRG_BELI": 8000.0, "PPN": 10, "F_PPN": 10.0}
        ],
        "drbeli": [
            {"TGL_BELI": "2026-06-12", "F_BELI": "B20260612", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 2.0, "HRG_BELI": 800.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG002", "qty": 2.0, "tipe": "tambah"}
        ]
    }
})

# TC-T2-16: DRJual (Sales Return) presence
TEST_CASES.append({
    "id": "TC-T2-16",
    "tier": 2,
    "category": "Boundary/Edge - Receipt Details & Constraints",
    "description": "Sales returns (DRJUAL) presence affects target calculation (target = net sales).",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-4000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 5.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "drjual": [
            {"TGL_JUAL": "2026-06-16", "F_JUAL": "J20260616", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 4.0, "tipe": "tambah"}
        ]
    }
})

# TC-T2-17: Non-PPN items (Lain-lain) ignored
TEST_CASES.append({
    "id": "TC-T2-17",
    "tier": 2,
    "category": "Boundary/Edge - Receipt Details & Constraints",
    "description": "Non-PPN items (Lain-lain, PAJAK=0) are ignored and not cut during reduction.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-10000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG007", "JUMLAH": 5.0, "HRG_BELI": 1600.0, "HRG_JUAL": 2000.0, "F_PPN": 0.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG007", "JUMLAH": 5.0, "HRG_BELI": 1600.0, "HRG_JUAL": 2000.0, "F_PPN": 0.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "tambah"}
        ]
    }
})

# TC-T2-18: BTKP items ignored
TEST_CASES.append({
    "id": "TC-T2-18",
    "tier": 2,
    "category": "Boundary/Edge - Receipt Details & Constraints",
    "description": "BTKP items (PAJAK=2) are ignored and never selected for reduction.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-15000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG006", "JUMLAH": 5.0, "HRG_BELI": 12000.0, "HRG_JUAL": 15000.0, "F_PPN": 0.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG006", "JUMLAH": 5.0, "HRG_BELI": 12000.0, "HRG_JUAL": 15000.0, "F_PPN": 0.0}
        ],
        "tabungan_dan_hutang": []
    }
})

# TC-T2-19: Non-PPN items under Addition
TEST_CASES.append({
    "id": "TC-T2-19",
    "tier": 2,
    "category": "Boundary/Edge - Receipt Details & Constraints",
    "description": "Addition skips non-PPN items in tabungan and injects fictional PPN item.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "10000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG007", "JUMLAH": 5.0, "HRG_BELI": 1600.0, "HRG_JUAL": 2000.0, "F_PPN": 0.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG007", "qty": 5.0, "tipe": "tambah"} # Pensil is non-PPN
        ]
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG007", "JUMLAH": 5.0, "HRG_BELI": 1600.0, "HRG_JUAL": 2000.0, "F_PPN": 0.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG007", "qty": 5.0, "tipe": "tambah"},
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "kurang"}
        ]
    }
})

# TC-T2-20: Receipt containing only non-PPN under reduction
TEST_CASES.append({
    "id": "TC-T2-20",
    "tier": 2,
    "category": "Boundary/Edge - Receipt Details & Constraints",
    "description": "Invoice with only non-PPN/BTKP items under reduction: skipped, gap accumulated.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-5000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG007", "JUMLAH": 5.0, "HRG_BELI": 1600.0, "HRG_JUAL": 2000.0, "F_PPN": 0.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG006", "JUMLAH": 1.0, "HRG_BELI": 12000.0, "HRG_JUAL": 15000.0, "F_PPN": 0.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG007", "JUMLAH": 5.0, "HRG_BELI": 1600.0, "HRG_JUAL": 2000.0, "F_PPN": 0.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG006", "JUMLAH": 1.0, "HRG_BELI": 12000.0, "HRG_JUAL": 15000.0, "F_PPN": 0.0}
        ],
        "tabungan_dan_hutang": []
    }
})

# TC-T2-21: Receipt containing only non-PPN under addition
TEST_CASES.append({
    "id": "TC-T2-21",
    "tier": 2,
    "category": "Boundary/Edge - Receipt Details & Constraints",
    "description": "Invoice with only non-PPN items under addition. Baju (PPN) is successfully added.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "10000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG007", "JUMLAH": 5.0, "HRG_BELI": 1600.0, "HRG_JUAL": 2000.0, "F_PPN": 0.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "tambah"}
        ]
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG007", "JUMLAH": 5.0, "HRG_BELI": 1600.0, "HRG_JUAL": 2000.0, "F_PPN": 0.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    }
})


# ==========================================
# TIER 3: CROSS-FEATURE COMBINATIONS (5 Cases)
# ==========================================

# TC-T3-01: Reduction followed by Addition
TEST_CASES.append({
    "id": "TC-T3-01",
    "tier": 3,
    "category": "Combination - Sequences",
    "description": "Reduction in first invoice generates savings, which is then drawn to add to second invoice.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "0" # Net is 0: reduces Rp10000 from INV01, adds Rp10000 to INV02
    },
    "initial": {
        "djual": [
            # Invoice 1 (will be reduced)
            {"TGL_JUAL": "2026-06-10", "F_JUAL": "J20260610", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 2.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            # Invoice 2 (will be added to)
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-10", "F_JUAL": "J20260610", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    }
})

# TC-T3-02: Balancing + Global Gap
TEST_CASES.append({
    "id": "TC-T3-02",
    "tier": 3,
    "category": "Combination - Sequences",
    "description": "Reduction targets 15000. INV01 has 2 Baju, gets reduced by 1. excess 5000 goes to global_gap.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-15000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 2.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "kurang"}
        ]
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG002", "qty": 1.0, "tipe": "tambah"}
        ]
    }
})

# TC-T3-03: Fictional Injection + Partial Tabungan Match
TEST_CASES.append({
    "id": "TC-T3-03",
    "tier": 3,
    "category": "Combination - Sequences",
    "description": "Addition target 10000: draws 3 Sabun (3000) from savings, then injects fictional Sabun x7 (7000).",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "10000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG002", "qty": 3.0, "tipe": "tambah"}
        ]
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 11.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG002", "qty": 7.0, "tipe": "kurang"}
        ]
    }
})

# TC-T3-04: Mixed Receipt under Reduction
TEST_CASES.append({
    "id": "TC-T3-04",
    "tier": 3,
    "category": "Combination - Sequences",
    "description": "Invoice has Buku (BTKP) and Baju (PPN). Baju is cut, receipt left with only Buku (valid).",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-10000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG006", "JUMLAH": 1.0, "HRG_BELI": 12000.0, "HRG_JUAL": 15000.0, "F_PPN": 0.0},
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG006", "JUMLAH": 1.0, "HRG_BELI": 12000.0, "HRG_JUAL": 15000.0, "F_PPN": 0.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "tambah"}
        ]
    }
})

# TC-T3-05: Global Gap Obfuscation + Self-Healing
TEST_CASES.append({
    "id": "TC-T3-05",
    "tier": 3,
    "category": "Combination - Sequences",
    "description": "Addition target creates negative global gap distributed, triggering self-healing of debt.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-12000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-16", "F_JUAL": "J20260616", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 2.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "kurang"}
        ]
    },
    "expected": {
        "djual": [
            {"TGL_JUAL": "2026-06-15", "F_JUAL": "J20260615", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 1.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-16", "F_JUAL": "J20260616", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    }
})


# ==========================================
# TIER 4: REAL-WORLD MONTHLY SCENARIOS (5 Cases)
# ==========================================

# TC-T4-01: Surplus Month (High Sales, Low Tax Target)
TEST_CASES.append({
    "id": "TC-T4-01",
    "tier": 4,
    "category": "Real-world - Month Scenarios",
    "description": "Surplus Month (High Sales, Low Tax Target): high-volume reductions with multiple invoices.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-35000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-01", "F_JUAL": "J20260601", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-02", "F_JUAL": "J20260602", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-03", "F_JUAL": "J20260603", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-04", "F_JUAL": "J20260604", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-05", "F_JUAL": "J20260605", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-06", "F_JUAL": "J20260606", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 2.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-06", "F_JUAL": "J20260606", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 5.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-07", "F_JUAL": "J20260607", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 2.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-07", "F_JUAL": "J20260607", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 5.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-08", "F_JUAL": "J20260608", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 2.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-08", "F_JUAL": "J20260608", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 5.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-09", "F_JUAL": "J20260609", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 2.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-09", "F_JUAL": "J20260609", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 5.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-10", "F_JUAL": "J20260610", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 2.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-10", "F_JUAL": "J20260610", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 5.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG002", "qty": 25.0, "tipe": "tambah"},
            {"acc": "001", "kode_brg": "BRG001", "qty": 1.0, "tipe": "tambah"}
        ]
    }
})

# TC-T4-02: Deficit Month with Available Savings (Low Sales, High Tax Target)
TEST_CASES.append({
    "id": "TC-T4-02",
    "tier": 4,
    "category": "Real-world - Month Scenarios",
    "description": "Deficit Month: uses active savings to add PPN items to multiple transactions.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "22000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-01", "F_JUAL": "J20260601", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 2.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-02", "F_JUAL": "J20260602", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 2.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-03", "F_JUAL": "J20260603", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 2.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-04", "F_JUAL": "J20260604", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 2.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-05", "F_JUAL": "J20260605", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 2.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG002", "qty": 20.0, "tipe": "tambah"},
            {"acc": "001", "kode_brg": "BRG001", "qty": 2.0, "tipe": "tambah"}
        ]
    },
    "expected": {
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 2.0, "tipe": "tambah"},
            {"acc": "001", "kode_brg": "BRG002", "qty": 2.0, "tipe": "kurang"}
        ]
    }
})

# TC-T4-03: Deficit Month with Empty Savings (Fictional Injection)
TEST_CASES.append({
    "id": "TC-T4-03",
    "tier": 4,
    "category": "Real-world - Month Scenarios",
    "description": "Deficit Month with empty savings: triggers fictional injections (debts) across multiple invoices.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "20000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-01", "F_JUAL": "J20260601", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-02", "F_JUAL": "J20260602", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-03", "F_JUAL": "J20260603", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-04", "F_JUAL": "J20260604", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-05", "F_JUAL": "J20260605", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG002", "qty": 20.0, "tipe": "kurang"}
        ]
    }
})

# TC-T4-04: Fluctuating Month with Active Self-Healing
TEST_CASES.append({
    "id": "TC-T4-04",
    "tier": 4,
    "category": "Real-world - Month Scenarios",
    "description": "Fluctuating month: reductions heal previous debts from multiple products.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-25000"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-01", "F_JUAL": "J20260601", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 2.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-01", "F_JUAL": "J20260601", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 5.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-02", "F_JUAL": "J20260602", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 2.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-02", "F_JUAL": "J20260602", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 5.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-03", "F_JUAL": "J20260603", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 2.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-03", "F_JUAL": "J20260603", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 5.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-04", "F_JUAL": "J20260604", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 2.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-04", "F_JUAL": "J20260604", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 5.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-05", "F_JUAL": "J20260605", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 2.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-05", "F_JUAL": "J20260605", "ACC": "001", "KODE_BRG": "BRG002", "JUMLAH": 5.0, "HRG_BELI": 800.0, "HRG_JUAL": 1000.0, "F_PPN": 10.0}
        ],
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 5.0, "tipe": "kurang"},
            {"acc": "001", "kode_brg": "BRG002", "qty": 10.0, "tipe": "kurang"}
        ]
    },
    "expected": {
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 5.0, "tipe": "kurang"},
            {"acc": "001", "kode_brg": "BRG002", "qty": 15.0, "tipe": "tambah"}
        ]
    }
})

# TC-T4-05: End-of-Year Mixed PPN/Non-PPN Reconciliation
TEST_CASES.append({
    "id": "TC-T4-05",
    "tier": 4,
    "category": "Real-world - Month Scenarios",
    "description": "End-of-Year: mixed PPN/Non-PPN reconciliation ensures only PPN items are adjusted.",
    "params": {
        "--acc": "001",
        "--start-date": "2026-06-01",
        "--end-date": "2026-06-30",
        "--target-ppn": "-20250"
    },
    "initial": {
        "djual": [
            {"TGL_JUAL": "2026-06-01", "F_JUAL": "J20260601", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-01", "F_JUAL": "J20260601", "ACC": "001", "KODE_BRG": "BRG006", "JUMLAH": 1.0, "HRG_BELI": 12000.0, "HRG_JUAL": 15000.0, "F_PPN": 0.0},
            {"TGL_JUAL": "2026-06-01", "F_JUAL": "J20260601", "ACC": "001", "KODE_BRG": "BRG007", "JUMLAH": 1.0, "HRG_BELI": 1600.0, "HRG_JUAL": 2000.0, "F_PPN": 0.0},
            
            {"TGL_JUAL": "2026-06-02", "F_JUAL": "J20260602", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-02", "F_JUAL": "J20260602", "ACC": "001", "KODE_BRG": "BRG006", "JUMLAH": 1.0, "HRG_BELI": 12000.0, "HRG_JUAL": 15000.0, "F_PPN": 0.0},
            {"TGL_JUAL": "2026-06-02", "F_JUAL": "J20260602", "ACC": "001", "KODE_BRG": "BRG007", "JUMLAH": 1.0, "HRG_BELI": 1600.0, "HRG_JUAL": 2000.0, "F_PPN": 0.0},
            
            {"TGL_JUAL": "2026-06-03", "F_JUAL": "J20260603", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-03", "F_JUAL": "J20260603", "ACC": "001", "KODE_BRG": "BRG006", "JUMLAH": 1.0, "HRG_BELI": 12000.0, "HRG_JUAL": 15000.0, "F_PPN": 0.0},
            {"TGL_JUAL": "2026-06-03", "F_JUAL": "J20260603", "ACC": "001", "KODE_BRG": "BRG007", "JUMLAH": 1.0, "HRG_BELI": 1600.0, "HRG_JUAL": 2000.0, "F_PPN": 0.0},
            
            {"TGL_JUAL": "2026-06-04", "F_JUAL": "J20260604", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-04", "F_JUAL": "J20260604", "ACC": "001", "KODE_BRG": "BRG006", "JUMLAH": 1.0, "HRG_BELI": 12000.0, "HRG_JUAL": 15000.0, "F_PPN": 0.0},
            {"TGL_JUAL": "2026-06-04", "F_JUAL": "J20260604", "ACC": "001", "KODE_BRG": "BRG007", "JUMLAH": 1.0, "HRG_BELI": 1600.0, "HRG_JUAL": 2000.0, "F_PPN": 0.0},
            
            {"TGL_JUAL": "2026-06-05", "F_JUAL": "J20260605", "ACC": "001", "KODE_BRG": "BRG001", "JUMLAH": 1.0, "HRG_BELI": 8000.0, "HRG_JUAL": 10000.0, "F_PPN": 10.0},
            {"TGL_JUAL": "2026-06-05", "F_JUAL": "J20260605", "ACC": "001", "KODE_BRG": "BRG006", "JUMLAH": 1.0, "HRG_BELI": 12000.0, "HRG_JUAL": 15000.0, "F_PPN": 0.0},
            {"TGL_JUAL": "2026-06-05", "F_JUAL": "J20260605", "ACC": "001", "KODE_BRG": "BRG007", "JUMLAH": 1.0, "HRG_BELI": 1600.0, "HRG_JUAL": 2000.0, "F_PPN": 0.0}
        ],
        "tabungan_dan_hutang": []
    },
    "expected": {
        "tabungan_dan_hutang": [
            {"acc": "001", "kode_brg": "BRG001", "qty": 2.0, "tipe": "tambah"}
        ]
    }
})

def get_test_cases():
    return TEST_CASES
