# Ephesian Tours

*An open door to the lands of the Bible.*

Small-group journeys to the lands of the New Testament for American church groups, personally escorted from Dallas–Fort Worth. Land arrangements are operated by Azim Tours (Kuşadası, Türkiye; TÜRSAB license no. 938).

**Status:** prototype. Preview builds use sample itineraries and pricing; every sample value is tracked in [PENDING.md](PENDING.md).

- Website: https://ephesiantours.com (coming soon)
- Preview: https://miela-labs.github.io/ephesian-tours-website/

Built by [Miela Labs](https://www.mielalabs.com).

---

## How it works

A static, single-page site generated from YAML. No framework and no JavaScript build step.

```
content/            all site content (edit these)
  site.yaml         brand, hero, section copy, how it works, partner, hosts, contact, feature flags
  journeys.yaml     the four journeys: price, highlights, route, day-by-day itinerary, inclusions
  sites.yaml        biblical sites: names, Scripture references, history, map coordinates
  faq.yaml          questions and answers
  booking.yaml      payment timeline, cancellation, insurance note
  media.yaml        every image and video, with source, author, and license
  pending.yaml      open items that will replace sample content
templates/          Jinja2 templates (base.html.j2 + partials/)
assets/             css/main.css, js/main.js, img/ (WebP photos, logo, favicon, OG image)
models.py           pydantic schemas for every content file
build.py            validate content -> render dist/index.html, write PENDING.md and credits.md
scripts/            fetch_images.py, make_brand.py, qa_screens.py, check_public.py
```

`build.py` fails loudly on any schema error (a typo in a key, a scripture reference with a hyphen instead of an en dash, an unknown site on a route, a pending value without a question). It also cross-checks the files against each other.

## Quick start

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python build.py
.venv/bin/python -m http.server 8000 --directory dist   # open http://localhost:8000
```

## Updating content

1. Edit the YAML in `content/`. Plain text values are fine; quotes and apostrophes can be typographic (“ ” ’).
2. Run `.venv/bin/python build.py`. Fix anything it reports.
3. Commit and push. GitHub Actions rebuilds and deploys automatically (see below).

### Prices

Each journey in `content/journeys.yaml` has `prices:` with `winter`, `spring_fall` and `summer` (USD per person, double occupancy, airfare from DFW included). The card shows “From” = the winter price (the build requires it to be the lowest). Season names and months, and the notes under the price table, are in `content/booking.yaml`. The FAQ “How much does a journey cost?” quotes the lowest prices in prose; the build fails if they no longer match.

Typical hotels are listed once per overnight city in `content/sites.yaml` (`hotels:`); the build fails if an itinerary overnights in a city without an entry.

### Sample (pending) values

Any price, term, or fact that is not yet confirmed carries provenance:

```yaml
from_price:
  value: 3895
  currency: USD
  basis: per person, double occupancy, land + DFW airfare
  status: pending          # confirmed | pending | proposed
  resolves_by: Q-PRICE-01  # an id in content/pending.yaml
```

When an answer arrives:

1. In `content/pending.yaml`, fill in `answer` and `answered_on` for that item.
2. Update every field it lists (see `PENDING.md`, which shows exactly which fields are tagged) with the real value and `status: confirmed`.
3. Run `build.py`. It warns about any field that still points at an answered question, and it refuses a field marked `confirmed` whose question has no answer yet.

## Switching preview mode off

`content/site.yaml`:

```yaml
site:
  preview_mode: false
```

This removes the “Sample” badges, the preview banner, and the `noindex, nofollow` robots tag (so search engines can index the site). Run `.venv/bin/python build.py --strict` first: in strict mode the build fails while anything is still pending, so nothing sample goes live by accident.

## Pastor’s info packet (PDF)

`.venv/bin/python build.py --packet` renders `templates/packet.html.j2` from the same `content/*.yaml` as the site and prints it to `dist/ephesian-tours-pastor-packet.pdf` (US Letter, about 10 pages) with Playwright/Chromium. Because it is generated from the same data, it cannot drift from the site:

- Prices: each journey page shows the three season prices; the Discover overview shows “From”. A journey whose prices are still `pending` shows “Pricing on request” instead. Other pending terms read “to be confirmed”. No Sample badges.
- While `preview_mode` is on, every page footer says “Preview edition · <month year>”. The footer also shows `site.base_url` and page numbers.
- Wording specific to the packet lives under `packet:` in `content/site.yaml`.

**Deploy:** the PDF is generated in GitHub Actions on every deploy (not committed), so a content change can never ship with a stale packet; if it cannot be generated, the deploy fails instead. Locally, `build.py` without `--packet` warns that the download link will 404 in that build.

## Hosts’ photos

Originals stay outside the repo in `internal/photos/` (gitignored). `scripts/process_host_photos.py` crops them, applies only a light global color balance (no retouching), converts to sRGB, and writes metadata-free WebP files to `assets/img/hosts/`. `scripts/check_public.py` fails if any `*-original.*` file is about to be committed, or if any public image still contains EXIF, GPS, or XMP data.

## Images, brand assets, and QA

Development tools live in `requirements-dev.txt`:

```sh
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m playwright install chromium
```

- **Images:** add an entry to `content/media.yaml` (Wikimedia Commons file page, author, license; only CC BY, CC BY-SA, CC0, public domain, or Azim Tours’ own photos), then run `scripts/fetch_images.py`. It writes responsive WebP files to `assets/img/` and records their sizes. `credits.md` and the footer credits are generated from the same file.
- **Brand:** `scripts/make_brand.py` regenerates `logo.svg`, `logo-dark.svg`, `favicon.svg`, `apple-touch-icon.png`, `og-image.jpg`, and the inline header mark from one definition.
- **QA:** `scripts/qa_screens.py` takes full-page screenshots at 375/768/1440 px in light and dark mode (into `qa/`, not committed) and reports horizontal overflow and console errors.
- **Before every push:** `scripts/check_public.py` checks that no private file is tracked and that no internal business terms appear in public files; `scripts/check_public.py --dist` scans the built page and PDF the same way. The deploy workflow runs both.
- **Private figures** (operator prices, pricing inputs) are never written in this repo, not even in the checker: they live in `internal/private-numbers.txt` (gitignored) and, for CI, in the repository secret `LEAK_PRIVATE_NUMBERS` (space-separated). Keep the two in sync. The check refuses to run without the list.

## Deployment (GitHub Pages)

`.github/workflows/deploy.yml` runs on every push to `main`: it installs `requirements.txt`, runs the leak check, builds with the Pages URL as the canonical/Open Graph base, and deploys `dist/`. Asset paths are relative (`./assets/...`), so the site works both under `/ephesian-tours-website/` and at a domain root. `build.py` adds `.nojekyll` to `dist/`.

To redeploy without a code change: **Actions → Deploy to GitHub Pages → Run workflow**.

## Pointing ephesiantours.com at the site

1. **DNS** at the domain registrar:
   - Apex `ephesiantours.com`: four `A` records to `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153` (optionally `AAAA` records to `2606:50c0:8000::153`, `2606:50c0:8001::153`, `2606:50c0:8002::153`, `2606:50c0:8003::153`).
   - `www`: a `CNAME` record to `miela-labs.github.io`.
2. **Verify the domain** for the MIELA-LABS organization (Organization settings → Pages → Add a domain). This prevents anyone else from claiming it.
3. **Attach it:** repository Settings → Pages → Custom domain → `ephesiantours.com`, save, wait for the DNS check, then tick **Enforce HTTPS**. (Command line: `gh api -X PUT repos/MIELA-LABS/ephesian-tours-website/pages -f cname=ephesiantours.com`.)
4. Re-run the deploy workflow. The Pages URL becomes `https://ephesiantours.com/`, so canonical and Open Graph tags switch to the domain automatically. `site.base_url` in `site.yaml` is the default for local builds.
5. If `ephesianjourneys.com` is bought, forward it (301) to `https://ephesiantours.com/` at the registrar.

No `CNAME` file is needed in the repo: with Actions-based deployment, the custom domain lives in the Pages settings.

## Credits and licenses

Photos: see [credits.md](credits.md) (Wikimedia Commons contributors, CC BY / CC BY-SA / CC0). Videos are embedded with Vimeo’s official player and credited to their author. Maps © OpenStreetMap contributors, via Leaflet. Fonts: Cormorant Garamond and Source Sans 3 (SIL Open Font License), via Google Fonts. Scripture quotations are from the ESV® Bible (The Holy Bible, English Standard Version®), © 2001 by Crossway, a publishing ministry of Good News Publishers. Used by permission. All rights reserved.
