"""Flask web layer: uploads, live band tuning, config persistence, PDF preview."""

from __future__ import annotations

import io
import os
import pathlib
import uuid

import pymupdf
from flask import (
    Flask,
    Response,
    jsonify,
    request,
    send_file,
    session,
)

from spellhdr import config as cfgmod
from spellhdr import merge
from webapp import uploads

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
INDEX_HTML = (BASE_DIR / "templates" / "index.html").read_text()

app = Flask(__name__, static_folder=str(BASE_DIR / "static"), static_url_path="/static")
# Session cookie only carries an opaque token; secret persists across restarts if set.
app.secret_key = os.environ.get("SPELLHDR_SECRET_KEY", "spellhdr-dev-secret")
app.config["MAX_CONTENT_LENGTH"] = int(
    os.environ.get("SPELLHDR_MAX_UPLOAD_BYTES", 64 * 1024 * 1024)
)


def _token() -> str:
    tok = session.get("tok")
    if not tok:
        tok = uuid.uuid4().hex
        session["tok"] = tok
    return tok


# --------------------------------------------------------------------------- pages
@app.get("/")
def index() -> Response:
    return Response(INDEX_HTML, mimetype="text/html")


@app.get("/healthz")
def healthz():
    return jsonify(status="ok")


# -------------------------------------------------------------------------- config
@app.get("/config")
def get_config():
    return jsonify(cfgmod.load_config().to_dict())


@app.put("/config")
def put_config():
    data = request.get_json(silent=True) or {}
    cfg = cfgmod.Config.from_dict({**cfgmod.load_config().to_dict(), **data})
    cfgmod.save_config(cfg)
    return jsonify(cfg.to_dict())


# ------------------------------------------------------------------------- uploads
def _handle_upload(kind: str):
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify(error="no file provided"), 400
    data = file.read()
    try:
        info = merge.header_page_info(data)
    except Exception:  # noqa: BLE001 — surface any parse failure as 400
        return jsonify(error="could not parse PDF"), 400
    uploads.save(_token(), kind, data)
    return jsonify(kind=kind, page_count=info["page_count"], pages=info["pages"])


@app.post("/upload/header")
def upload_header():
    return _handle_upload("header")


@app.post("/upload/spells")
def upload_spells():
    return _handle_upload("spells")


# --------------------------------------------------------------- header page image
@app.get("/header-page.png")
def header_page_png():
    data = uploads.load(_token(), "header")
    if data is None:
        return jsonify(error="no header PDF uploaded"), 400
    try:
        page_index = int(request.args.get("page", 0))
    except ValueError:
        page_index = 0
    try:
        dpi = int(request.args.get("dpi", 110))
    except ValueError:
        dpi = 110
    dpi = max(48, min(200, dpi))

    doc = pymupdf.open(stream=data, filetype="pdf")
    try:
        page_index = max(0, min(page_index, len(doc) - 1))
        page = doc.load_page(page_index)
        zoom = dpi / 72.0
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))  # type: ignore[attr-defined]
        png = pix.tobytes("png")
        resp = send_file(
            io.BytesIO(png),
            mimetype="image/png",
            max_age=0,
        )
        # Points-per-page so the browser can map pixels <-> PDF points.
        resp.headers["X-Page-Width"] = str(round(page.rect.width, 2))
        resp.headers["X-Page-Height"] = str(round(page.rect.height, 2))
        resp.headers["X-Page-Index"] = str(page_index)
        return resp
    finally:
        doc.close()


# -------------------------------------------------------------- render (preview/dl)
def _render(disposition: str, filename: str):
    token = _token()
    header = uploads.load(token, "header")
    spells = uploads.load(token, "spells")
    if header is None:
        return jsonify(error="upload a header PDF first"), 400
    if spells is None:
        return jsonify(error="upload a spells PDF first"), 400

    # Use posted (possibly-unsaved) config, falling back to persisted defaults.
    posted = request.get_json(silent=True) or {}
    cfg = cfgmod.Config.from_dict({**cfgmod.load_config().to_dict(), **posted})

    try:
        pdf = merge.build_output(header, spells, cfg)
    except Exception as exc:  # noqa: BLE001 — report render failure to the client
        return jsonify(error=f"render failed: {exc}"), 400

    resp = Response(pdf, mimetype="application/pdf")
    resp.headers["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    return resp


@app.post("/preview")
def preview():
    return _render("inline", "spellbook.pdf")


@app.post("/download")
def download():
    return _render("attachment", "spellbook.pdf")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
