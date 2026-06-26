import io
import json
import os
from datetime import datetime, timezone

from flask import (Flask, Response, redirect, render_template, request, url_for)
from flask_login import (LoginManager, current_user, login_required,
                         login_user, logout_user)

from models import ActivityLog, PredictionSave, User, db
from services.model_service import ModelService
from services.recommendation_service import RecommendationService

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "house-recommender-secret-key-change-in-production")
db_url = os.environ.get("DATABASE_URL", "sqlite:///house_recommender.db")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

model_service = ModelService()
recommendation_service = RecommendationService()


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def log_activity(action: str, detail: str | None = None):
    if current_user.is_authenticated:
        log = ActivityLog(user_id=current_user.id, action=action, detail=detail)
        db.session.add(log)
        db.session.commit()


def get_recent_activity(limit: int = 15):
    if current_user.is_authenticated:
        return (
            ActivityLog.query.filter_by(user_id=current_user.id)
            .order_by(ActivityLog.timestamp.desc())
            .limit(limit)
            .all()
        )
    return []


# ── Init DB ──
with app.app_context():
    db.create_all()


# ── Template Filters ──

@app.template_filter("rupiah")
def format_rupiah(value):
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"Rp {amount:,.0f}".replace(",", ".")


@app.template_filter("score_display")
def score_display(value, decimals=2):
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"{score:.{decimals}f}"


@app.template_filter("score_percent")
def score_percent(value):
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"{score * 100:.1f}%"


# ── Auth Routes ──

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            log_activity("Login", "Berhasil login")
            return redirect(url_for("dashboard"))
        error = "Username atau password salah."
    return render_template("login.html", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not username or not password:
            error = "Username dan password harus diisi."
        elif len(username) < 3:
            error = "Username minimal 3 karakter."
        elif len(password) < 4:
            error = "Password minimal 4 karakter."
        elif password != confirm:
            error = "Konfirmasi password tidak cocok."
        elif User.query.filter_by(username=username).first():
            error = f"Username '{username}' sudah digunakan."
        else:
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            log_activity("Register", f"Bergabung sebagai {username}")
            return redirect(url_for("dashboard"))
    return render_template("register.html", error=error)


@app.route("/logout")
@login_required
def logout():
    log_activity("Logout", "Berhasil logout")
    logout_user()
    return redirect(url_for("login"))


# ── Dashboard ──

@app.route("/")
@login_required
def dashboard():
    summary = recommendation_service.get_dashboard_summary()
    city_volume_chart = recommendation_service.build_city_volume_chart()
    city_price_chart = recommendation_service.build_city_price_chart()
    activity_logs = get_recent_activity()
    return render_template(
        "dashboard.html",
        summary=summary,
        city_volume_chart=city_volume_chart,
        city_price_chart=city_price_chart,
        activity_logs=activity_logs,
    )


# ── Prediksi ──

@app.route("/prediksi", methods=["GET", "POST"])
@login_required
def prediksi():
    prediction = None
    saved = PredictionSave.query.filter_by(user_id=current_user.id).order_by(PredictionSave.created_at.desc()).first()
    form_data = {
        "city": "",
        "bedrooms": "",
        "bathrooms": "",
        "land_size_m2": "",
        "building_size_m2": "",
        "carports": "",
        "garages": "",
        "floors": "",
        "building_age": "",
        "certificate": "",
        "property_condition": "",
        "furnishing": "",
    }

    if saved and request.method == "GET":
        try:
            saved_data = json.loads(saved.form_data) if saved.form_data else {}
            form_data.update(saved_data)
            prediction = saved.result
        except (json.JSONDecodeError, TypeError):
            pass

    prediction_fields = model_service.get_form_fields(
        city_options=recommendation_service.get_unique_options("city"),
        certificate_options=recommendation_service.get_unique_options("certificate"),
        property_condition_options=recommendation_service.get_unique_options("property_condition"),
        furnishing_options=recommendation_service.get_unique_options("furnishing"),
    )
    form_options = {
        "cities": recommendation_service.get_unique_options("city"),
        "certificates": recommendation_service.get_unique_options("certificate"),
        "conditions": recommendation_service.get_unique_options("property_condition"),
        "furnishings": recommendation_service.get_unique_options("furnishing"),
    }

    if request.method == "POST":
        form_data = {
            "city": request.form.get("city", ""),
            "bedrooms": request.form.get("bedrooms", ""),
            "bathrooms": request.form.get("bathrooms", ""),
            "land_size_m2": request.form.get("land_size_m2", ""),
            "building_size_m2": request.form.get("building_size_m2", ""),
            "carports": request.form.get("carports", ""),
            "garages": request.form.get("garages", ""),
            "floors": request.form.get("floors", ""),
            "building_age": request.form.get("building_age", ""),
            "certificate": request.form.get("certificate", ""),
            "property_condition": request.form.get("property_condition", ""),
            "furnishing": request.form.get("furnishing", ""),
        }
        payload = model_service.prepare_payload(form_data)
        prediction = model_service.predict_price(payload)

        if saved:
            saved.form_data = json.dumps(form_data)
            saved.result = prediction
            saved.created_at = datetime.now(timezone.utc)
        else:
            new_save = PredictionSave(
                user_id=current_user.id,
                form_data=json.dumps(form_data),
                result=prediction,
            )
            db.session.add(new_save)
        db.session.commit()
        log_activity("Prediksi", f"Estimasi harga: {prediction}")

    return render_template(
        "prediksi.html",
        prediction=prediction,
        form_options=form_options,
        prediction_fields=prediction_fields,
        form_data=form_data,
    )


# ── Rekomendasi ──

@app.route("/rekomendasi")
@login_required
def rekomendasi():
    filters = {
        "budget": request.args.get("budget", type=float),
        "city": request.args.get("city", default=""),
        "minimum_bedrooms": request.args.get("minimum_bedrooms", type=float),
        "minimum_bathrooms": request.args.get("minimum_bathrooms", type=float),
    }
    has_filters = any(
        value not in (None, "")
        for value in filters.values()
    )
    form_options = recommendation_service.get_form_options()

    if not has_filters:
        page = request.args.get("page", 1, type=int)
        per_page = 20
        data = recommendation_service.get_all_recommendations_paginated(page, per_page=per_page)
        showing_from = ((data["page"] - 1) * per_page) + 1
        showing_to = min(data["page"] * per_page, data["total_count"])
        return render_template("rekomendasi.html",
            results=data["rankings"],
            filters=filters,
            form_options=form_options,
            page=data["page"],
            total_pages=data["total_pages"],
            total_count=data["total_count"],
            per_page=per_page,
            showing_from=showing_from,
            showing_to=showing_to,
            filtered=False,
        )

    filtered_frame = recommendation_service.build_filtered_recommendation_frame(filters)
    results = recommendation_service.get_recommendations(filters, limit=20)
    recommendation_service.activate_topsis(filters=filters, user_id=current_user.id)
    log_activity("Rekomendasi", f"Filter: budget={filters.get('budget')}, kota={filters.get('city')}, KT>={filters.get('minimum_bedrooms')}, KM>={filters.get('minimum_bathrooms')}")
    return render_template("rekomendasi.html",
        results=results,
        filters=filters,
        form_options=form_options,
        filtered=True,
        shown_count=len(results),
        total_count=len(filtered_frame),
        page=None, total_pages=None, per_page=None, showing_from=None, showing_to=None,
    )


# ── Rangking Properti (formerly TOPSIS) ──

def _get_rangking_paginated(page=1, per_page=20):
    data = recommendation_service.get_all_rankings_paginated(page, per_page=per_page)
    showing_from = ((data["page"] - 1) * per_page) + 1
    showing_to = min(data["page"] * per_page, data["total_count"])
    return dict(
        top_rankings=data["rankings"],
        total_count=data["total_count"],
        page=data["page"],
        total_pages=data["total_pages"],
        per_page=per_page,
        showing_from=showing_from,
        showing_to=showing_to,
        activated=False,
    )


def _get_rangking_batch():
    batch = recommendation_service.get_topsis_batch(batch_size=20, user_id=current_user.id)
    return dict(
        top_rankings=batch["rankings"],
        showing_from=batch["showing_from"],
        showing_to=batch["showing_to"],
        total_count=batch["total_count"],
        activated=True,
        page=None,
        total_pages=None,
        has_filters=batch["has_filters"],
    )


@app.route("/rangking")
@login_required
def rangking():
    if not recommendation_service.is_topsis_activated(user_id=current_user.id):
        page = request.args.get("page", 1, type=int)
        ctx = _get_rangking_paginated(page=page)
    else:
        ctx = _get_rangking_batch()
    log_activity("Rangking", "Melihat peringkat properti")
    return render_template("rangking.html", **ctx)


@app.route("/rangking/reset")
@login_required
def rangking_reset():
    recommendation_service.reset_topsis_progress(user_id=current_user.id)
    return redirect(url_for("rangking"))


# ── PDF Export ──

@app.route("/rangking/pdf")
@login_required
def rangking_pdf():
    progress = recommendation_service._read_progress(user_id=current_user.id)
    stored_filters = progress.get("filters", {})
    rekom_total = 0
    if stored_filters:
        rekom_total = len(recommendation_service.build_filtered_recommendation_frame(stored_filters))
    data = recommendation_service.get_rangking_data_for_pdf(page=1, per_page=20, user_id=current_user.id)
    log_activity("Cetak PDF", "Mencetak peringkat properti")
    html = render_template("pdf_rangking.html",
        data=data,
        rekom_filters=stored_filters,
        rekom_total=rekom_total,
        username=current_user.username)
    return _pdf_response(html, "laporan_properti.pdf")


@app.route("/semua/pdf")
@login_required
def semua_pdf():
    progress = recommendation_service._read_progress(user_id=current_user.id)
    stored_filters = progress.get("filters", {})
    rekom_total = 0
    if stored_filters:
        rekom_total = len(recommendation_service.build_filtered_recommendation_frame(stored_filters))

    rangking_data = recommendation_service.get_rangking_data_for_pdf(page=1, per_page=20, user_id=current_user.id)

    log_activity("Cetak PDF", "Mencetak semua hasil (rekomendasi + rangking)")
    html = render_template("pdf_semua.html",
        rekom_filters=stored_filters, rekom_total=rekom_total,
        rangking_data=rangking_data,
        username=current_user.username)
    return _pdf_response(html, "semua_hasil.pdf")


def _pdf_response(html_string: str, filename: str):
    try:
        from xhtml2pdf import pisa
        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(io.BytesIO(html_string.encode("utf-8")), dest=pdf_buffer, encoding="utf-8")
        if pisa_status.err:
            raise RuntimeError("xhtml2pdf error")
        pdf = pdf_buffer.getvalue()
        pdf_buffer.close()
        return Response(pdf, mimetype="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename={filename}"})
    except Exception:
        return Response(html_string, mimetype="text/html",
                        headers={"Content-Disposition": f"inline; filename={filename}.html"})


# ── Context Processor ──

@app.context_processor
def inject_ui_context():
    return {
        "metric_help": {
            "predicted_price": "Estimasi harga jual rumah berdasarkan input yang Anda isi.",
            "fuzzy_score": "Skor kecocokan properti. Semakin tinggi, semakin sesuai dengan kriteria penilaian.",
            "topsis_score": "Skor akhir peringkat. Semakin tinggi, semakin dekat ke rumah ideal.",
        },
        "datetime": datetime,
    }


if __name__ == "__main__":
    app.run(debug=True)
