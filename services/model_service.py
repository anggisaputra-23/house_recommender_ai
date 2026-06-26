from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from joblib import load


class ModelService:
    input_columns = [
        "city",
        "bedrooms",
        "bathrooms",
        "land_size_m2",
        "building_size_m2",
        "carports",
        "maid_bedrooms",
        "maid_bathrooms",
        "garages",
        "floors",
        "building_age",
        "certificate",
        "property_condition",
        "furnishing",
    ]

    numeric_columns = [
        "land_size_m2",
        "building_size_m2",
        "maid_bedrooms",
        "maid_bathrooms",
    ]

    discrete_select_columns = [
        "bedrooms",
        "bathrooms",
        "carports",
        "garages",
        "floors",
        "building_age",
    ]

    def __init__(self) -> None:
        self.base_dir = Path(__file__).resolve().parent.parent
        self.model_path = self.base_dir / "models" / "model_rf.pkl"
        self.preprocessor_path = self.base_dir / "models" / "preprocessor.pkl"
        self.data_path = self.base_dir / "data" / "hasil_rekomendasi_rumah.csv"
        self.reference_df = pd.read_csv(self.data_path)
        self.reference_df = self.reference_df.copy()
        for column in self.reference_df.select_dtypes(include="object").columns:
            self.reference_df[column] = self.reference_df[column].fillna("").astype(str).str.strip()
        for column in ["price_in_rp", "bedrooms", "bathrooms", "land_size_m2", "building_size_m2", "carports", "maid_bedrooms", "maid_bathrooms", "floors", "building_age", "garages", "total_room", "lat", "long", "price_per_m2", "land_building_ratio"]:
            if column in self.reference_df.columns:
                self.reference_df[column] = pd.to_numeric(self.reference_df[column], errors="coerce")
        self.model = load(self.model_path)
        self.preprocessor = load(self.preprocessor_path)
        self.model_feature_names = list(getattr(self.model, "feature_names_in_", self.input_columns))
        self.default_numeric_values = self._build_numeric_defaults()
        self.default_categorical_values = self._build_categorical_defaults()

    def _build_numeric_defaults(self) -> dict[str, float]:
        defaults = {}
        for column in ["maid_bedrooms", "maid_bathrooms"]:
            if column in self.reference_df.columns:
                defaults[column] = float(self.reference_df[column].median())
        return defaults

    def _build_categorical_defaults(self) -> dict[str, str]:
        defaults = {}
        for column in ["city", "district", "property_type", "certificate", "property_condition", "furnishing"]:
            if column in self.reference_df.columns:
                mode_values = self.reference_df[column].mode(dropna=True)
                defaults[column] = str(mode_values.iloc[0]) if not mode_values.empty else ""
        return defaults

    def prepare_payload(self, form_data: dict) -> dict:
        payload: dict[str, object] = {}
        for column in self.input_columns:
            value = form_data.get(column, "")
            if column in self.numeric_columns or column in self.discrete_select_columns:
                try:
                    payload[column] = float(str(value).replace(",", "."))
                except (TypeError, ValueError):
                    payload[column] = 0.0
            else:
                payload[column] = str(value).strip()
        return payload

    def build_feature_frame(self, payload: dict) -> pd.DataFrame:
        frame = pd.DataFrame([payload], columns=self.input_columns)
        for column in self.numeric_columns + self.discrete_select_columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
        for column in ["city", "certificate", "property_condition", "furnishing"]:
            frame[column] = frame[column].astype(str).str.strip()
        for column in ["maid_bedrooms", "maid_bathrooms"]:
            if column not in frame.columns:
                frame[column] = self.default_numeric_values.get(column, 0.0)
        frame = frame.loc[:, self.model_feature_names]
        return frame

    def _range_options(self, start: int, stop: int) -> list[int]:
        return list(range(start, stop + 1))

    def get_form_fields(
        self,
        city_options: list[str],
        certificate_options: list[str],
        property_condition_options: list[str],
        furnishing_options: list[str],
    ) -> list[dict]:
        return [
            {"name": "city", "label": "Kota", "type": "select", "options": city_options, "hint": "Pilih kota lokasi rumah."},
            {"name": "bedrooms", "label": "Kamar Tidur", "type": "select", "options": self._range_options(0, 10), "hint": "Jumlah kamar tidur."},
            {"name": "bathrooms", "label": "Kamar Mandi", "type": "select", "options": self._range_options(0, 10), "hint": "Jumlah kamar mandi."},
            {"name": "land_size_m2", "label": "Luas Tanah (m2)", "type": "number", "step": "0.1", "min": "0", "placeholder": "Contoh: 120", "hint": "Masukkan luas tanah secara perkiraan."},
            {"name": "building_size_m2", "label": "Luas Bangunan (m2)", "type": "number", "step": "0.1", "min": "0", "placeholder": "Contoh: 80", "hint": "Masukkan luas bangunan yang tersedia."},
            {"name": "carports", "label": "Carport", "type": "select", "options": self._range_options(0, 5), "hint": "Jumlah carport."},
            {"name": "garages", "label": "Garasi", "type": "select", "options": self._range_options(0, 5), "hint": "Jumlah garasi."},
            {"name": "floors", "label": "Jumlah Lantai", "type": "select", "options": self._range_options(1, 5), "hint": "Jumlah lantai bangunan."},
            {"name": "building_age", "label": "Umur Bangunan", "type": "select", "options": self._range_options(0, 50), "hint": "Perkiraan umur bangunan dalam tahun."},
            {"name": "certificate", "label": "Sertifikat", "type": "select", "options": certificate_options, "hint": "Pilih status sertifikat."},
            {"name": "property_condition", "label": "Kondisi Rumah", "type": "select", "options": property_condition_options, "hint": "Pilih kondisi bangunan saat ini."},
            {"name": "furnishing", "label": "Furnishing", "type": "select", "options": furnishing_options, "hint": "Pilih kondisi perabot."},
        ]

    def predict_price(self, payload: dict) -> str:
        feature_frame = self.build_feature_frame(payload)
        raw_prediction = float(self.model.predict(feature_frame)[0])
        prediction = float(np.expm1(raw_prediction)) if raw_prediction <= 1000 else raw_prediction
        return f"Rp {prediction:,.0f}".replace(",", ".")