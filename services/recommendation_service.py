from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px


class RecommendationService:
    def __init__(self) -> None:
        self.base_dir = Path(__file__).resolve().parent.parent
        self.data_path = self.base_dir / "data" / "hasil_rekomendasi_rumah.csv"
        self.topsis_progress_path = self.base_dir / "data" / "topsis_progress.json"
        self.df = pd.read_csv(self.data_path)
        self.df = self._prepare_dataframe(self.df)
        self.df["_row_id"] = range(len(self.df))
        self._sorted_indices = None

    def _get_topsis_ordered(self) -> pd.DataFrame:
        ordered = self.df.sort_values(["TOPSIS_Score", "FuzzyScore", "_row_id"], ascending=[False, False, True]).reset_index(drop=True)
        ordered["Ranking"] = range(1, len(ordered) + 1)
        return ordered

    def get_total_count(self) -> int:
        return len(self.df)

    def _progress_path_for(self, user_id: int | None) -> Path:
        if user_id is None:
            return self.topsis_progress_path
        return self.topsis_progress_path.parent / f"topsis_progress_{user_id}.json"

    def _read_progress(self, user_id: int | None = None) -> dict:
        path = self._progress_path_for(user_id)
        try:
            with open(path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"offset": 0, "activated": False}

    def _save_progress(self, offset: int, activated: bool | None = None, filters: dict | None = None, user_id: int | None = None) -> None:
        path = self._progress_path_for(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        current = self._read_progress(user_id)
        current["offset"] = offset
        if activated is not None:
            current["activated"] = activated
        if filters is not None:
            cleaned = {k: v for k, v in filters.items() if v not in (None, "")}
            current["filters"] = cleaned if cleaned else {}
        with open(path, "w") as f:
            json.dump(current, f)

    def is_topsis_activated(self, user_id: int | None = None) -> bool:
        return self._read_progress(user_id).get("activated", False)

    def activate_topsis(self, filters: dict | None = None, user_id: int | None = None) -> None:
        self._save_progress(offset=0, activated=True, filters=filters if filters is not None else {}, user_id=user_id)

    def deactivate_topsis(self, user_id: int | None = None) -> None:
        self._save_progress(offset=0, activated=False, user_id=user_id)

    def get_topsis_batch(self, batch_size: int = 20, user_id: int | None = None) -> dict:
        progress = self._read_progress(user_id)
        stored_filters = progress.get("filters", {})
        columns = ["Ranking", "title", "city", "PredictedPrice", "FuzzyScore", "TOPSIS_Score"]

        if stored_filters:
            ordered = self.build_filtered_recommendation_frame(stored_filters)
            total = len(ordered)
        else:
            ordered = self._get_topsis_ordered()
            total = self.get_total_count()

        offset = progress.get("offset", 0)
        if offset >= total:
            offset = 0

        batch = ordered.iloc[offset:offset + batch_size]
        results = batch[columns].fillna("-").to_dict(orient="records")
        showing_from = offset + 1
        showing_to = min(offset + batch_size, total)

        next_offset = offset + batch_size
        if next_offset >= total:
            next_offset = 0
        self._save_progress(next_offset, user_id=user_id)

        return {
            "rankings": results,
            "showing_from": showing_from,
            "showing_to": showing_to,
            "total_count": total,
            "activated": True,
            "has_filters": bool(stored_filters),
        }

    def get_all_rankings_paginated(self, page: int = 1, per_page: int = 20) -> dict:
        ordered = self._get_topsis_ordered()
        total = len(ordered)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        batch = ordered.iloc[start:start + per_page]
        columns = ["Ranking", "title", "city", "PredictedPrice", "FuzzyScore", "TOPSIS_Score"]
        return {
            "rankings": batch[columns].fillna("-").to_dict(orient="records"),
            "page": page,
            "per_page": per_page,
            "total_count": total,
            "total_pages": total_pages,
        }

    def reset_topsis_progress(self, user_id: int | None = None) -> None:
        self._save_progress(offset=0, activated=False, user_id=user_id)

    def _prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        cleaned = df.copy()
        for column in ["price_in_rp", "bedrooms", "bathrooms", "PredictedPrice", "FuzzyScore", "TOPSIS_Score", "Ranking"]:
            if column in cleaned.columns:
                cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
        for column in cleaned.select_dtypes(include="object").columns:
            cleaned[column] = cleaned[column].fillna("").astype(str).str.strip()
        return cleaned

    def _format_currency(self, value: float) -> str:
        if pd.isna(value):
            return "-"
        return f"Rp {value:,.0f}".replace(",", ".")

    def get_dashboard_summary(self) -> dict:
        prices = self.df["price_in_rp"].dropna()
        fuzzy = self.df["FuzzyScore"].dropna()
        topsis = self.df["TOPSIS_Score"].dropna()

        city_counts = self.df.groupby("city", dropna=False).size().sort_values(ascending=False)
        top_cities_list = [
            {"name": str(city), "count": int(count), "pct": round(count / len(self.df) * 100, 1)}
            for city, count in city_counts.head(3).items()
        ]

        avg_fuzzy = float(fuzzy.mean())
        avg_topsis = float(topsis.mean())

        return {
            "total_houses": int(len(self.df)),
            "cities_count": int(len(city_counts)),
            "top_cities": top_cities_list,
            "average_price": self._format_currency(prices.mean()),
            "median_price": self._format_currency(prices.median()),
            "min_price": self._format_currency(prices.min()),
            "max_price": self._format_currency(prices.max()),
            "price_q25": self._format_currency(prices.quantile(0.25)),
            "price_q75": self._format_currency(prices.quantile(0.75)),
            "average_fuzzy_score": round(avg_fuzzy, 2),
            "max_fuzzy_score": round(float(fuzzy.max()), 2),
            "min_fuzzy_score": round(float(fuzzy.min()), 2),
            "average_topsis_score": round(avg_topsis, 4),
            "average_topsis_percent": round(avg_topsis * 100, 1),
            "max_topsis_score": round(float(topsis.max()), 4),
            "min_topsis_score": round(float(topsis.min()), 4),
        }

    def get_form_options(self) -> dict:
        prices = self.df["PredictedPrice"]
        return {
            "cities": sorted(self.df["city"].dropna().astype(str).str.strip().replace({"": "Tidak diketahui"}).unique().tolist()),
            "certificates": sorted(self.df["certificate"].dropna().astype(str).str.strip().replace({"": "Tidak diketahui"}).unique().tolist()),
            "conditions": sorted(self.df["property_condition"].dropna().astype(str).str.strip().replace({"": "Tidak diketahui"}).unique().tolist()),
            "furnishings": sorted(self.df["furnishing"].dropna().astype(str).str.strip().replace({"": "Tidak diketahui"}).unique().tolist()),
            "max_price": int(prices.max()),
            "max_price_fmt": self._format_currency(prices.max()),
        }

    def get_unique_options(self, column: str) -> list[str]:
        if column not in self.df.columns:
            return []
        values = (
            self.df[column]
            .dropna()
            .astype(str)
            .str.strip()
            .replace({"": "Tidak diketahui"})
            .unique()
            .tolist()
        )
        return sorted(values)

    def build_filtered_recommendation_frame(self, filters: dict) -> pd.DataFrame:
        filtered = self.df.copy()

        budget = filters.get("budget")
        if budget is not None:
            filtered = filtered[filtered["PredictedPrice"] <= budget]

        city = filters.get("city")
        if city:
            filtered = filtered[filtered["city"].astype(str).str.lower() == city.strip().lower()]

        minimum_bedrooms = filters.get("minimum_bedrooms")
        if minimum_bedrooms is not None:
            filtered = filtered[filtered["bedrooms"] >= minimum_bedrooms]

        minimum_bathrooms = filters.get("minimum_bathrooms")
        if minimum_bathrooms is not None:
            filtered = filtered[filtered["bathrooms"] >= minimum_bathrooms]

        ordered = filtered.sort_values(["TOPSIS_Score", "FuzzyScore", "_row_id"], ascending=[False, False, True]).reset_index(drop=True)
        ordered["Ranking"] = range(1, len(ordered) + 1)
        return ordered

    def build_city_volume_chart(self) -> str:
        city_counts = self.df.groupby("city", dropna=False).size().reset_index(name="total")
        fig = px.bar(city_counts, x="city", y="total", title="Jumlah Rumah per Kota", text_auto=True)
        fig.update_layout(margin=dict(l=20, r=20, t=50, b=20))
        return fig.to_html(full_html=False, include_plotlyjs="cdn")

    def build_city_price_chart(self) -> str:
        city_price = self.df.groupby("city", dropna=False)["price_in_rp"].mean().reset_index()
        fig = px.bar(city_price, x="city", y="price_in_rp", title="Rata-rata Harga per Kota")
        fig.update_layout(margin=dict(l=20, r=20, t=50, b=20), yaxis_title="Harga (Rp)")
        return fig.to_html(full_html=False, include_plotlyjs="cdn")

    def get_recommendations(self, filters: dict, limit: int | None = None) -> list[dict]:
        ordered = self.build_filtered_recommendation_frame(filters)
        if limit is not None:
            ordered = ordered.head(limit)
        columns = ["title", "city", "district", "bedrooms", "bathrooms", "PredictedPrice", "FuzzyScore", "TOPSIS_Score", "Ranking"]
        return ordered[columns].fillna("-").to_dict(orient="records")

    def get_all_recommendations_paginated(self, page: int = 1, per_page: int = 20) -> dict:
        ordered = self.df.sort_values(["TOPSIS_Score", "FuzzyScore", "_row_id"], ascending=[False, False, True]).reset_index(drop=True)
        ordered["Ranking"] = range(1, len(ordered) + 1)
        total = len(ordered)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        batch = ordered.iloc[start:start + per_page]
        columns = ["title", "city", "district", "bedrooms", "bathrooms", "PredictedPrice", "FuzzyScore", "TOPSIS_Score", "Ranking"]
        return {
            "rankings": batch[columns].fillna("-").to_dict(orient="records"),
            "page": page,
            "per_page": per_page,
            "total_count": total,
            "total_pages": total_pages,
        }

    def get_top_ranking(self, limit: int = 20, offset: int = 0) -> list[dict]:
        columns = ["Ranking", "title", "city", "PredictedPrice", "FuzzyScore", "TOPSIS_Score"]
        ordered = self._get_topsis_ordered()
        batch = ordered.iloc[offset:offset + limit]
        return batch[columns].fillna("-").to_dict(orient="records")

    def get_rangking_data_for_pdf(self, page: int = 1, per_page: int = 20, user_id: int | None = None) -> dict:
        progress = self._read_progress(user_id)
        stored_filters = progress.get("filters", {})

        if stored_filters:
            ordered = self.build_filtered_recommendation_frame(stored_filters)
        else:
            ordered = self._get_topsis_ordered()

        total = len(ordered)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        batch = ordered.iloc[start:start + per_page]
        columns = ["Ranking", "title", "city", "district", "bedrooms", "bathrooms", "PredictedPrice", "FuzzyScore", "TOPSIS_Score"]
        return {
            "rankings": batch[columns].fillna("-").to_dict(orient="records"),
            "page": page,
            "total_pages": total_pages,
            "total_count": total,
            "showing_from": start + 1,
            "showing_to": min(start + per_page, total),
            "has_filters": bool(stored_filters),
            "filters": stored_filters,
        }

