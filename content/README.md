# `content/` — canonical editable content for the Echelon Day Care site

This directory holds the **source of truth** for every editable string, image
reference, list, FAQ item, and SEO field on the site. HTML in this repo is a
build artifact rendered from these JSON files + the templates in `templates/`.

Do **not** hand-edit `index.html`, `pages/*.html`, `404.html`, `sitemap.xml`,
or `assets/data/jobs.json`. Re-run the renderer instead:

```powershell
python scripts/render.py
```

CI runs `python scripts/validate.py` which re-renders and compares the output
against the committed HTML — if any content file drifts out of sync with the
generated HTML, the check fails.

## Files

| File                | Feeds…                                                            |
| ------------------- | ----------------------------------------------------------------- |
| `site.json`         | Global: brand, address, phone, email, nav, favicons, footer, a11y |
| `home.json`         | `index.html` hero, gallery preview, stats, FAQ                    |
| `about.json`        | `pages/about.html` intro, vision, mission, team, why-us, gallery, neighbourhoods |
| `services.json`     | `pages/services.html` daycare program copy, brochure link, waiting-list form URL, Service JSON-LD |
| `gallery.json`      | `pages/gallery.html` heading, search placeholder, caption pool (currently duplicated in inline JS — see PR1_NOTES.md) |
| `contact.json`      | `pages/contact.html` heading, map iframe title & embed URL, social icon labels |
| `tour.json`         | `pages/tour.html` heading, intro, video src/poster, fallback text |
| `careers.json`      | `pages/careers.html` copy, filter labels, apply-modal copy, **jobs list** (writes through to `assets/data/jobs.json`) |
| `seo.json`          | `<title>`, `<meta description>`, OG tags, canonical URL, breadcrumb list, and sitemap URL set for every page |

## Adding or editing items

- **Add a new job posting:** append an entry to `careers.json → jobs`. Give it
  a stable `id` (e.g. `J003`). Re-render — `assets/data/jobs.json` is regenerated
  and the existing careers page client-side loader will pick it up automatically.
- **Add a FAQ entry:** append to `home.json → faq.items` with a stable `id` like
  `faq_hours`. The page's `<details>` list AND the FAQPage JSON-LD schema are
  both generated from this list — you only edit it once.
- **Update the site phone number:** change `site.json → phone` in one place.
  Every page's `tel:` link, footer, sticky-call button, ChildCare JSON-LD, and
  copy that mentions the number will re-render consistently.
- **Add another neighbourhood to the home ChildCare schema:** append to
  `site.json → area_served`. It only appears on `index.html` today.

## Stable IDs

Every collection item has a stable string `id` so future renames don't break
schema references:

| Where            | ID pattern           |
| ---------------- | -------------------- |
| Jobs             | `J001`, `J002`, …    |
| FAQ items        | `faq_ages`, `faq_location`, `faq_waiting_list`, `faq_licensed`, `faq_typical_day`, `faq_contact` |
| About-page grid  | `about_p1`, …        |
| Home gallery     | `home_g1`, …         |

## Schema versioning

Every file has a top-level `schema_version` field. The renderer refuses to
build if it doesn't understand a schema version. Bump `manifests/renderer.json`
whenever a schema shape changes.

## Do NOT

- Store rendered JSON-LD payloads here. Templates generate JSON-LD from the
  underlying data (address, faq items, jobs, breadcrumb) via `tojson`. If you
  edit a JSON-LD block in the committed HTML by hand, CI will fail.
- Hardcode content strings inside templates. Bias toward "make it editable" —
  new strings go in `content/*.json`.
