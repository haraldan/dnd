# Spellbook Header Inserter

A small self-hostable web app that overlays banners clipped from a D&D character
sheet onto every page of a spellbook PDF. Upload a **header file** and a **spells
file**, pick which header page the banners come from, visually tune the vertical
range of two bands — a **spell-slots** band and a **modifiers** band — then preview
and download the merged PDF.

- The **modifiers** band is placed on the **first** page, and on **pages 2+** when
  that toggle is on.
- The **spell-slots** band is placed only on the **first** page (toggleable), sitting
  above the modifiers band.
- On pages 2+, a tunable **top margin** adds whitespace above the modifiers band.
- Content is pushed down by the **push offset** (points) below the top of the
  modifiers band, so page 1 (slots band above) and pages 2+ (top margin above)
  shift accordingly. A "restore default offsets" button resets these two values.

Built with Flask + [PyMuPDF](https://pymupdf.readthedocs.io/). Ships as a lightweight
Docker container.

## Run with Docker

```bash
mkdir -p config            # host-mounted settings live here
docker compose up --build  # or set `image:` in docker-compose.yml to the published one
```

Then open <http://localhost:8000>.

Your tuned settings persist to `./config/config.yaml` (atomically written, safe to
edit by hand). Uploaded PDFs are **not** persisted — they are stored as transient temp
files inside the container and swept after `SPELLHDR_UPLOAD_TTL` seconds (default 1h).

### Configuration (environment variables)

| Variable | Default | Purpose |
| --- | --- | --- |
| `SPELLHDR_CONFIG_PATH` | `/config/config.yaml` | Persistent settings file (mount this). |
| `SPELLHDR_UPLOAD_DIR` | `/tmp/spellhdr-uploads` | Where transient uploads are staged. |
| `SPELLHDR_UPLOAD_TTL` | `3600` | Seconds before an idle upload is swept. |
| `SPELLHDR_SECRET_KEY` | dev default | Session-cookie signing key; set in production. |
| `SPELLHDR_MAX_UPLOAD_BYTES` | `67108864` | Max upload size (64 MiB). |

## Local development

This project uses the `hom.office` virtualenv:

```bash
workon hom.office
pip install -r requirements.txt
SPELLHDR_CONFIG_PATH=./config/config.yaml \
  gunicorn -w 1 --threads 4 -b 0.0.0.0:8000 webapp.app:app
# or, for auto-reload:  python -m webapp.app
```

Run the tests:

```bash
pip install pytest
pytest
```

## Publishing

`.github/workflows/docker-publish.yml` builds and pushes the image to GHCR
(`ghcr.io/<owner>/<repo>`) on pushes to `main` and on `v*` tags. Point
`docker-compose.yml`'s `image:` at that tag to run the published build.

## CLI

The core library is usable without the web app:

```bash
python -m spellhdr.merge header.pdf spells.pdf -o out.pdf --page 0
```
