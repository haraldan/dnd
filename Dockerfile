FROM python:3.12-slim

# No venv needed inside the image — it is already an isolated environment.
# HOME=/tmp so an arbitrary (non-root, no-passwd-entry) uid has a writable home:
# gunicorn otherwise falls back to $HOME/.gunicorn/ (-> unwritable /.gunicorn),
# and it also covers ~-expanded fontconfig/MuPDF caches.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    XDG_RUNTIME_DIR=/tmp \
    SPELLHDR_CONFIG_PATH=/config/config.yaml \
    SPELLHDR_UPLOAD_DIR=/tmp/spellhdr-uploads

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY spellhdr ./spellhdr
COPY webapp ./webapp
COPY templates ./templates
COPY static ./static

# Let an arbitrary (non-root) uid read the baked-in assets. The /config volume
# supplies the writable path, ownership and permissions — so no VOLUME/USER here.
RUN chmod -R a+rX /app/static /app/templates

EXPOSE 8000

# Uploads live on disk (not in process memory), so multiple workers are safe;
# one worker with threads is a fine lightweight default.
CMD ["gunicorn", "-w", "1", "--threads", "4", "-b", "0.0.0.0:8000", "webapp.app:app"]
