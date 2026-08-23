"""
render.py — build HTML pages from content/*.json + templates/*.j2.

Deterministic renderer for the Echelon Day Care site. See PR1_NOTES.md for
schema/design details.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
except ImportError:
    print("ERROR: jinja2 not installed. Run: pip install jinja2 beautifulsoup4 lxml", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = REPO_ROOT / "content"
TEMPLATES_DIR = REPO_ROOT / "templates"


# --------------------------------------------------------------------------- #
# Content loading                                                             #
# --------------------------------------------------------------------------- #

def load_content() -> Dict[str, Any]:
    """Load every JSON file under content/ and return keyed by base name."""
    content: Dict[str, Any] = {}
    for path in sorted(CONTENT_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as f:
            content[path.stem] = json.load(f)
    return content


# --------------------------------------------------------------------------- #
# Schema builders (produce dicts that get serialised via `tojson` in Jinja)   #
# --------------------------------------------------------------------------- #

def build_postal_address(site: Dict[str, Any]) -> Dict[str, Any]:
    a = site["address"]
    return {
        "@type": "PostalAddress",
        "streetAddress": a["streetAddress"],
        "addressLocality": a["addressLocality"],
        "addressRegion": a["addressRegion"],
        "postalCode": a["postalCode"],
        "addressCountry": a["addressCountry"],
    }


def build_geo(site: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "@type": "GeoCoordinates",
        "latitude": site["geo"]["latitude"],
        "longitude": site["geo"]["longitude"],
    }


def build_area_served(entries: List[Dict[str, str]]) -> Any:
    """A single-city entry renders as a dict; multi-entry renders as a list."""
    if len(entries) == 1:
        e = entries[0]
        return {"@type": e["type"], "name": e["name"]}
    return [{"@type": e["type"], "name": e["name"]} for e in entries]


def build_childcare_schema(site: Dict[str, Any], area_served_entries: List[Dict[str, str]]) -> Dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "ChildCare",
        "name": site["name"],
        "url": f"{site['urls']['base']}/",
        "logo": site["urls"]["logo_absolute"],
        "image": site["urls"]["logo_absolute"],
        "telephone": site["phone"]["e164"],
        "email": site["email"],
        "address": build_postal_address(site),
        "geo": build_geo(site),
        "areaServed": build_area_served(area_served_entries),
        "sameAs": list(site["same_as"]),
    }


def build_breadcrumb_schema(entries: List[Dict[str, str]]) -> Dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": e["name"],
                "item": e["item"],
            }
            for i, e in enumerate(entries)
        ],
    }


def build_faq_schema(faq_items: List[Dict[str, str]]) -> Dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q["question"],
                "acceptedAnswer": {"@type": "Answer", "text": q["answer"]},
            }
            for q in faq_items
        ],
    }


def build_service_schema(site: Dict[str, Any], svc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "Service",
        "serviceType": svc["service_type"],
        "name": svc["name"],
        "provider": {
            "@type": "ChildCare",
            "name": site["name"],
            "url": f"{site['urls']['base']}/",
            "telephone": site["phone"]["e164"],
            "address": build_postal_address(site),
        },
        "areaServed": {"@type": "City", "name": "Vancouver"},
        "audience": {
            "@type": "PeopleAudience",
            "suggestedMinAge": svc["audience_min_age"],
            "suggestedMaxAge": svc["audience_max_age"],
        },
        "description": svc["description"],
    }


# --------------------------------------------------------------------------- #
# Per-page context                                                            #
# --------------------------------------------------------------------------- #

# Which nav.key each page marks as active.
PAGE_KEY_TO_NAV_KEY = {
    "index": "home",
    "about": "about",
    "services": "services",
    "gallery": "gallery",
    "contact": "contact",
    "tour": "tour",
    "careers": "careers",
    "not_found": None,
}


def compute_prefixes(page_path: str) -> Tuple[str, str, str]:
    """Return (asset_prefix, nav_prefix, contact_href, careers_href) — actually
    a tuple of (asset_prefix, nav_prefix, page_dir_up).
    """
    depth = page_path.count("/")
    up = "../" * depth
    return up, up


def nav_items_for(page_key: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build absolute-in-repo nav hrefs, resolved relative to `page_key`'s dir."""
    nav = []
    page_path = site["_page_paths"][page_key]
    page_dir = os.path.dirname(page_path)
    for item in site["nav"]:
        target = item["path"]  # e.g. "index.html" or "pages/about.html"
        href = os.path.relpath(target, page_dir).replace("\\", "/")
        nav.append({
            "label": item["label"],
            "href": href,
            "active": item["key"] == PAGE_KEY_TO_NAV_KEY.get(page_key),
        })
    return nav


def resolve_link(from_page: str, to_page_path: str) -> str:
    """Resolve a link like 'pages/careers.html' relative to `from_page`'s dir."""
    from_dir = os.path.dirname(from_page)
    return os.path.relpath(to_page_path, from_dir).replace("\\", "/") if from_dir else to_page_path


def make_page_context(
    page_key: str,
    content: Dict[str, Any],
    seo_page: Dict[str, Any],
    area_served_entries: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    site = content["site"]
    page_path = seo_page["path"]
    depth = page_path.count("/")
    asset_prefix = "../" * depth  # from page dir, up to repo root
    # Resolve inter-page hrefs.
    from_dir = os.path.dirname(page_path)

    def link_to(target_path: str) -> str:
        return os.path.relpath(target_path, from_dir).replace("\\", "/") if from_dir else target_path

    # nav items with proper hrefs.
    nav_items = []
    for item in site["nav"]:
        nav_items.append({
            "label": item["label"],
            "href": link_to(item["path"]),
            "active": item["key"] == PAGE_KEY_TO_NAV_KEY.get(page_key),
        })

    contact_href = link_to("pages/contact.html")
    careers_href = link_to("pages/careers.html")

    ctx: Dict[str, Any] = {
        "site": site,
        "seo": seo_page,
        "asset_prefix": asset_prefix,
        "nav_items": nav_items,
        "contact_href": contact_href,
        "careers_href": careers_href,
    }

    # ChildCare schema (used on all standard pages).
    if area_served_entries is None:
        area_served_entries = [{"type": "City", "name": "Vancouver"}]
    ctx["childcare_schema"] = build_childcare_schema(site, area_served_entries)

    # Breadcrumb.
    if seo_page.get("breadcrumb"):
        ctx["breadcrumb_schema"] = build_breadcrumb_schema(seo_page["breadcrumb"])

    # Per-page content bag.
    if page_key == "index":
        ctx["home"] = content["home"]
        ctx["faq_schema"] = build_faq_schema(content["home"]["faq"]["items"])
    elif page_key == "about":
        ctx["about"] = content["about"]
    elif page_key == "services":
        ctx["services"] = content["services"]
        ctx["service_schema"] = build_service_schema(site, content["services"]["service_schema"])
    elif page_key == "gallery":
        ctx["gallery"] = content["gallery"]
    elif page_key == "contact":
        ctx["contact"] = content["contact"]
    elif page_key == "tour":
        ctx["tour"] = content["tour"]
    elif page_key == "careers":
        ctx["careers"] = content["careers"]
    return ctx


# --------------------------------------------------------------------------- #
# Sitemap / jobs / robots                                                     #
# --------------------------------------------------------------------------- #

def render_sitemap(content: Dict[str, Any]) -> str:
    urls = content["seo"]["sitemap_urls"]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        lines.append("  <url>")
        lines.append(f"    <loc>{u['loc']}</loc>")
        lines.append(f"    <changefreq>{u['changefreq']}</changefreq>")
        lines.append(f"    <priority>{u['priority']}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def render_jobs_json(content: Dict[str, Any]) -> str:
    """Regenerate assets/data/jobs.json from content/careers.json.

    Uses the same 2-space indent + trailing newline as the current file.
    """
    jobs = content["careers"]["jobs"]
    # Order fields as the current file to keep diffs minimal.
    ordered = []
    field_order = ["id", "title", "category", "type", "location", "short", "details", "datePosted"]
    for j in jobs:
        ordered.append({k: j[k] for k in field_order if k in j})
    return json.dumps(ordered, indent=2, ensure_ascii=False) + "\n"


# --------------------------------------------------------------------------- #
# Main render                                                                 #
# --------------------------------------------------------------------------- #

def area_served_for(page_key: str, content: Dict[str, Any]) -> List[Dict[str, str]]:
    """Only index.html uses the expanded neighborhoods list."""
    if page_key == "index":
        return content["site"]["area_served"]
    return [{"type": "City", "name": "Vancouver"}]


def render_all(out_dir: Path) -> Tuple[int, List[str]]:
    content = load_content()
    site = content["site"]
    # Attach an internal _page_paths lookup for convenience.
    site["_page_paths"] = {k: v["path"] for k, v in content["seo"]["pages"].items()}

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(enabled_extensions=("html", "j2")),
        undefined=StrictUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=False,
    )

    # Standard pages: template name -> page_key.
    page_map = [
        ("index",     "index.html.j2",           "index.html"),
        ("about",     "pages/about.html.j2",     "pages/about.html"),
        ("services",  "pages/services.html.j2",  "pages/services.html"),
        ("gallery",   "pages/gallery.html.j2",   "pages/gallery.html"),
        ("contact",   "pages/contact.html.j2",   "pages/contact.html"),
        ("tour",      "pages/tour.html.j2",      "pages/tour.html"),
        ("careers",   "pages/careers.html.j2",   "pages/careers.html"),
        ("not_found", "404.html.j2",             "404.html"),
    ]

    written: List[str] = []
    for page_key, tmpl_name, rel_out in page_map:
        seo_page = content["seo"]["pages"][page_key]
        ctx = make_page_context(page_key, content, seo_page, area_served_for(page_key, content))
        try:
            tmpl = env.get_template(tmpl_name)
        except Exception:
            # Skip templates that don't exist yet (during incremental build-out).
            continue
        html = tmpl.render(**ctx)
        # Enforce LF newlines.
        html = html.replace("\r\n", "\n")
        if not html.endswith("\n"):
            html += "\n"
        out_path = out_dir / rel_out
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(html.encode("utf-8"))
        written.append(rel_out)

    # sitemap.xml.
    sitemap = render_sitemap(content)
    (out_dir / "sitemap.xml").write_bytes(sitemap.encode("utf-8"))
    written.append("sitemap.xml")

    # assets/data/jobs.json (mirror content/careers.jobs).
    jobs_out = out_dir / "assets" / "data" / "jobs.json"
    jobs_out.parent.mkdir(parents=True, exist_ok=True)
    jobs_out.write_bytes(render_jobs_json(content).encode("utf-8"))
    written.append("assets/data/jobs.json")

    return len(written), written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO_ROOT), help="Output directory (default: repo root)")
    args = ap.parse_args()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    n, written = render_all(out_dir)
    pages = sum(1 for w in written if w.endswith(".html"))
    data  = sum(1 for w in written if w.endswith(".json"))
    other = n - pages - data
    print(f"Rendered {pages} pages, {data} data file, {other} sitemap. Total {n} files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
