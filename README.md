---
title: House Recommender AI
emoji: 🏠
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# 🏠 House Recommender AI

Sistem rekomendasi rumah berbasis AI yang menggabungkan **prediksi harga (Machine Learning)**, **penilaian kecocokan (Fuzzy Logic)**, dan **perangkingan keputusan (TOPSIS)** dalam satu aplikasi web berbasis Flask.

Aplikasi ini membantu pengguna memprediksi estimasi harga rumah, mendapatkan rekomendasi properti sesuai kriteria, serta melihat peringkat rumah terbaik dan analisis pasar properti.

---

## ✨ Fitur Utama

| Halaman | Route | Deskripsi |
|---------|-------|-----------|
| **Dashboard** | `/` | Ringkasan data: total rumah, rata-rata harga, rata-rata FuzzyScore & TOPSIS_Score, plus grafik volume & harga per kota. |
| **Prediksi** | `/prediksi` | Form input spesifikasi rumah → estimasi harga jual menggunakan model Random Forest. |
| **Rekomendasi** | `/rekomendasi` | Filter properti berdasarkan budget, kota, minimal kamar tidur/mandi, diurutkan berdasarkan TOPSIS_Score. |
| **TOPSIS** | `/topsis` | Peringkat 20 rumah terbaik berdasarkan skor TOPSIS. |
| **Analisis** | `/analisis` | Visualisasi: rata-rata harga per kota, distribusi FuzzyScore & TOPSIS_Score, korelasi luas bangunan vs harga. |

### Metrik yang digunakan
- **PredictedPrice** — Estimasi harga jual rumah hasil prediksi model ML.
- **FuzzyScore** — Skor kecocokan properti terhadap kriteria penilaian (semakin tinggi semakin sesuai).
- **TOPSIS_Score** — Skor akhir peringkat berdasarkan kedekatan ke "rumah ideal" (semakin tinggi semakin baik).

---

## 🛠️ Teknologi

- **Backend:** [Flask](https://flask.palletsprojects.com/) (Python)
- **Machine Learning:** [scikit-learn](https://scikit-learn.org/) `1.6.1` (Random Forest)
- **Pengolahan data:** [pandas](https://pandas.pydata.org/)
- **Serialisasi model:** [joblib](https://joblib.readthedocs.io/)
- **Visualisasi:** [Plotly Express](https://plotly.com/python/plotly-express/)
- **Frontend:** Bootstrap 5.3, Bootstrap Icons, Google Fonts (Inter)

---

## 📁 Struktur Proyek

```
house_recommender_ai/
├── app.py                          # Entry point Flask: routing & template filters
├── requirements.txt                # Daftar dependensi Python
├── services/
│   ├── model_service.py            # Memuat model & preprocessor, menyiapkan fitur, prediksi harga
│   └── recommendation_service.py   # Logika filter, rekomendasi, TOPSIS, & grafik analisis
├── models/
│   ├── model_rf.pkl                # Model Random Forest terlatih
│   └── preprocessor.pkl            # Preprocessor fitur
├── data/
│   └── hasil_rekomendasi_rumah.csv # Dataset rumah + hasil FuzzyScore & TOPSIS (±3.573 baris)
├── templates/
│   ├── base.html                   # Layout dasar (navbar, footer)
│   ├── dashboard.html
│   ├── prediksi.html
│   ├── rekomendasi.html
│   ├── topsis.html
│   └── analisis.html
└── static/
    └── css/
        └── style.css               # Styling kustom
```

> **Catatan:** `app.py` dan layanan membaca model dari folder `models/` dan dataset dari folder `data/`. File `model_rf.pkl`, `preprocessor.pkl`, dan `hasil_rekomendasi_rumah.csv` yang berada di root proyek hanyalah salinan dan tidak dipakai langsung oleh aplikasi.

---

## 🚀 Instalasi & Menjalankan

### 1. Prasyarat
- Python 3.12+ (proyek diuji dengan Python 3.12)
- `pip`

### 2. Buat & aktifkan virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependensi
```bash
pip install -r requirements.txt
```

> ⚠️ Versi `scikit-learn` dipatok ke `1.6.1` agar kompatibel dengan model `.pkl` yang sudah dilatih. Menggunakan versi lain dapat memunculkan peringatan atau error saat memuat model.

### 4. Jalankan aplikasi
```bash
python app.py
```

Aplikasi berjalan dalam mode debug di:
```
http://127.0.0.1:5000
```

---

## 📊 Dataset

Dataset (`data/hasil_rekomendasi_rumah.csv`) berisi data properti beserta hasil perhitungan, dengan kolom-kolom utama:

| Kategori | Kolom |
|----------|-------|
| **Identitas** | `url`, `title`, `address`, `district`, `city`, `lat`, `long`, `ads_id` |
| **Spesifikasi** | `bedrooms`, `bathrooms`, `land_size_m2`, `building_size_m2`, `carports`, `garages`, `floors`, `building_age`, `year_built`, `maid_bedrooms`, `maid_bathrooms` |
| **Atribut** | `certificate`, `electricity`, `property_type`, `property_condition`, `building_orientation`, `furnishing`, `facilities` |
| **Harga** | `price_in_rp`, `log_price`, `price_per_m2`, `land_building_ratio`, `total_room` |
| **Hasil model** | `PredictedPrice`, `FuzzyScore`, `Kategori`, `TOPSIS_Score`, `Ranking`, serta fitur ternormalisasi (`harga_norm`, `luas_norm`, `umur_norm`, `room_norm`) |

---

## 🧠 Cara Kerja

1. **Prediksi Harga (`/prediksi`)**
   Pengguna mengisi spesifikasi rumah → `ModelService.prepare_payload()` membersihkan input → `build_feature_frame()` menyusun fitur sesuai urutan yang diharapkan model → `model.predict()` menghasilkan estimasi harga. Jika model memprediksi dalam skala log, hasilnya dikembalikan dengan `np.expm1()`.

2. **Rekomendasi (`/rekomendasi`)**
   `RecommendationService` memfilter dataset berdasarkan budget, kota, dan minimal kamar, lalu mengurutkan berdasarkan `TOPSIS_Score` dan menetapkan ulang `Ranking`.

3. **TOPSIS (`/topsis`)**
   Menampilkan rumah dengan `TOPSIS_Score` tertinggi — gabungan dari prediksi harga, skor fuzzy, dan kriteria lain yang dinormalisasi.

4. **Analisis (`/analisis`)**
   Plotly menghasilkan grafik interaktif (bar, histogram, scatter) yang disematkan langsung ke halaman.

---

## 🧩 Template Filter Kustom (Jinja2)

Didefinisikan di `app.py`:

- `rupiah` — memformat angka menjadi `Rp 1.000.000`.
- `score_display` — menampilkan skor dengan jumlah desimal tertentu (default 2).
- `score_percent` — menampilkan skor dalam bentuk persentase.

---

## 📝 Catatan Pengembangan

- Aplikasi dijalankan dengan `debug=True` — **jangan gunakan konfigurasi ini di produksi.** Untuk produksi gunakan WSGI server seperti Gunicorn/Waitress dan matikan mode debug.
- Model dan preprocessor dimuat sekali saat startup melalui instance `ModelService` dan `RecommendationService`.

---

## 📄 Lisensi

Proyek ini dibuat untuk keperluan akademik/pembelajaran. Sesuaikan lisensi sesuai kebutuhan Anda.
