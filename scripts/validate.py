"""
validate.py — render templates to a scratch dir and diff each output against
the committed file in the repo using a normalized comparison.

- HTML: parse both with bs4+lxml, compare tree (tags/attrs/text). JSON-LD
  script blocks are parsed as JSON and deep-compared. `<style>` and
  non-JSON-LD `<script>` blocks are string-compared with whitespace
  normalization.
- JSON files: parse and deep-compare.
- sitemap.xml: parse XML with lxml and compare trees.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, List, Tuple

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:
    print("ERROR: beautifulsoup4 not installed. Run: pip install beautifulsoup4 lxml", file=sys.stderr)
    sys.exit(2)

try:
    from lxml import etree
except ImportError:
    print("ERROR: lxml not installed. Run: pip install lxml", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from render import render_all  # noqa: E402


HTML_FILES = [
    "index.html",
    "404.html",
    "pages/about.html",
    "pages/services.html",
    "pages/gallery.html",
    "pages/contact.html",
    "pages/tour.html",
    "pages/careers.html",
]
JSON_FILES = ["assets/data/jobs.json"]
XML_FILES = ["sitemap.xml"]


# --------------------------------------------------------------------------- #
# Normalization helpers                                                       #
# --------------------------------------------------------------------------- #

_WS_RE = re.compile(r"\s+")

def norm_ws(s: str) -> str:
    return _WS_RE.sub(" ", s or "").strip()


def is_meaningful_text(node: NavigableString) -> bool:
    return bool((node.string or "").strip())


def element_children(tag: Tag) -> List[Any]:
    """Return only meaningful children: Tags, and non-whitespace strings."""
    kids: List[Any] = []
    for c in tag.children:
        if isinstance(c, Tag):
            kids.append(c)
        elif isinstance(c, NavigableString):
            if (c.string or "").strip():
                kids.append(c)
    return kids


def norm_attrs(tag: Tag) -> dict:
    """Return attributes as a dict for comparison.

    BeautifulSoup returns multi-valued attributes (like `class`) as lists.
    We treat class as a set and other attrs as normalized strings.
    """
    out: dict = {}
    for k, v in tag.attrs.items():
        if isinstance(v, list):
            if k == "class":
                out[k] = frozenset(v)
            else:
                out[k] = tuple(v)
        else:
            out[k] = norm_ws(str(v))
    return out


# --------------------------------------------------------------------------- #
# HTML comparison                                                             #
# --------------------------------------------------------------------------- #

def path_str(path: List[str]) -> str:
    return "/".join(path) if path else "(root)"


def compare_html(expected: str, actual: str) -> List[str]:
    """Return list of human-readable mismatch strings."""
    diffs: List[str] = []
    e_soup = BeautifulSoup(expected, "lxml")
    a_soup = BeautifulSoup(actual, "lxml")
    e_root = e_soup.find("html") or e_soup
    a_root = a_soup.find("html") or a_soup
    _compare_tree(e_root, a_root, [e_root.name if isinstance(e_root, Tag) else "root"], diffs)
    return diffs


def _describe(tag: Tag) -> str:
    if not isinstance(tag, Tag):
        return f'text "{norm_ws(str(tag))[:60]}"'
    cls = tag.get("class")
    idv = tag.get("id")
    parts = [tag.name]
    if idv:
        parts.append(f"#{idv}")
    if cls:
        parts.append("." + ".".join(cls if isinstance(cls, list) else [cls]))
    return "<" + " ".join(parts) + ">"


def _script_type(tag: Tag) -> str:
    t = tag.get("type", "")
    return str(t)


def _compare_tree(e: Any, a: Any, path: List[str], diffs: List[str], depth: int = 0) -> None:
    # If types differ (Tag vs NavigableString).
    e_is_tag = isinstance(e, Tag)
    a_is_tag = isinstance(a, Tag)
    if e_is_tag != a_is_tag:
        diffs.append(f"{path_str(path)}: type mismatch (expected {_describe(e)}, got {_describe(a)})")
        return

    if not e_is_tag:
        # Both text nodes.
        e_t = norm_ws(str(e))
        a_t = norm_ws(str(a))
        if e_t != a_t:
            diffs.append(f'{path_str(path)}: text mismatch: expected "{e_t[:100]}" got "{a_t[:100]}"')
        return

    # Both tags.
    if e.name != a.name:
        diffs.append(f"{path_str(path)}: tag mismatch: expected <{e.name}> got <{a.name}>")
        return

    # Special-case: JSON-LD script block.
    if e.name == "script" and _script_type(e) == "application/ld+json":
        try:
            e_json = json.loads(e.string or e.get_text() or "null")
            a_json = json.loads(a.string or a.get_text() or "null")
        except Exception as ex:
            diffs.append(f"{path_str(path)}: JSON-LD parse error: {ex}")
            return
        if e_json != a_json:
            diffs.append(
                f"{path_str(path)}: JSON-LD mismatch\n"
                f"  expected: {json.dumps(e_json, sort_keys=True)[:400]}\n"
                f"  got     : {json.dumps(a_json, sort_keys=True)[:400]}"
            )
        # attrs still matter.
        _compare_attrs(e, a, path, diffs)
        return

    # Special-case: <style> — whitespace-normalized string compare.
    if e.name == "style":
        _compare_attrs(e, a, path, diffs)
        e_s = norm_ws(e.get_text())
        a_s = norm_ws(a.get_text())
        if e_s != a_s:
            # Print a compact diff.
            diffs.append(
                f"{path_str(path)}: <style> mismatch (length {len(e_s)} vs {len(a_s)})\n"
                f"  expected: {e_s[:200]}\n"
                f"  got     : {a_s[:200]}"
            )
        return

    # Special-case: <script> without JSON-LD — whitespace-normalized string compare.
    if e.name == "script":
        _compare_attrs(e, a, path, diffs)
        e_s = norm_ws(e.get_text())
        a_s = norm_ws(a.get_text())
        if e_s != a_s:
            diffs.append(
                f"{path_str(path)}: <script> mismatch (length {len(e_s)} vs {len(a_s)})\n"
                f"  expected: {e_s[:200]}\n"
                f"  got     : {a_s[:200]}"
            )
        return

    _compare_attrs(e, a, path, diffs)

    # Recurse over children.
    e_kids = element_children(e)
    a_kids = element_children(a)
    if len(e_kids) != len(a_kids):
        diffs.append(
            f"{path_str(path)}: child count mismatch under {_describe(e)}: "
            f"expected {len(e_kids)} got {len(a_kids)}\n"
            f"  expected kids: {[_describe(k)[:60] for k in e_kids[:12]]}\n"
            f"  got kids     : {[_describe(k)[:60] for k in a_kids[:12]]}"
        )
    for i, (ek, ak) in enumerate(zip(e_kids, a_kids)):
        _compare_tree(ek, ak, path + [_describe(ek if isinstance(ek, Tag) else Tag(name='text'))], diffs, depth + 1)


def _compare_attrs(e: Tag, a: Tag, path: List[str], diffs: List[str]) -> None:
    ea = norm_attrs(e)
    aa = norm_attrs(a)
    if ea != aa:
        e_only = {k: ea[k] for k in ea if k not in aa or aa[k] != ea[k]}
        a_only = {k: aa[k] for k in aa if k not in ea or ea[k] != aa[k]}
        diffs.append(
            f"{path_str(path)}: attr mismatch on <{e.name}>\n"
            f"  expected has: {e_only}\n"
            f"  got has     : {a_only}"
        )


# --------------------------------------------------------------------------- #
# JSON / XML / robots comparison                                              #
# --------------------------------------------------------------------------- #

def compare_json(expected: str, actual: str) -> List[str]:
    try:
        e = json.loads(expected)
        a = json.loads(actual)
    except Exception as ex:
        return [f"JSON parse error: {ex}"]
    if e != a:
        return [f"JSON mismatch\n  expected: {json.dumps(e, sort_keys=True)[:400]}\n  got     : {json.dumps(a, sort_keys=True)[:400]}"]
    return []


def _canon_xml(root: etree._Element) -> str:
    # Serialize with sorted attribute order & namespace canonicalization.
    return etree.tostring(root, method="c14n").decode("utf-8")


def compare_xml(expected: str, actual: str) -> List[str]:
    try:
        e = etree.fromstring(expected.encode("utf-8"))
        a = etree.fromstring(actual.encode("utf-8"))
    except Exception as ex:
        return [f"XML parse error: {ex}"]
    if _canon_xml(e) != _canon_xml(a):
        return ["XML tree mismatch"]
    return []


# --------------------------------------------------------------------------- #
# Driver                                                                      #
# --------------------------------------------------------------------------- #

def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="echelon-render-", dir=str(REPO_ROOT / ".render-cache") if (REPO_ROOT / ".render-cache").exists() else None))
    # Prefer .render-cache under the repo for CI cache-friendly location.
    cache = REPO_ROOT / ".render-cache"
    cache.mkdir(exist_ok=True)
    shutil.rmtree(tmp, ignore_errors=True)
    tmp = cache / "build"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    n, written = render_all(tmp)
    print(f"Rendered {n} files to {tmp}")

    total_diffs = 0
    for rel in HTML_FILES:
        expected = (REPO_ROOT / rel).read_text(encoding="utf-8")
        gen_path = tmp / rel
        if not gen_path.exists():
            print(f"[SKIP] {rel} — template not implemented yet")
            continue
        actual = gen_path.read_text(encoding="utf-8")
        diffs = compare_html(expected, actual)
        if diffs:
            print(f"\n=== MISMATCH: {rel} ({len(diffs)} diff(s)) ===")
            for d in diffs[:20]:
                print(d)
            if len(diffs) > 20:
                print(f"... and {len(diffs) - 20} more")
            total_diffs += len(diffs)
        else:
            print(f"[OK]   {rel}")

    for rel in JSON_FILES:
        expected = (REPO_ROOT / rel).read_text(encoding="utf-8")
        actual = (tmp / rel).read_text(encoding="utf-8")
        diffs = compare_json(expected, actual)
        if diffs:
            print(f"\n=== MISMATCH: {rel} ===")
            for d in diffs:
                print(d)
            total_diffs += len(diffs)
        else:
            print(f"[OK]   {rel}")

    for rel in XML_FILES:
        expected = (REPO_ROOT / rel).read_text(encoding="utf-8")
        actual = (tmp / rel).read_text(encoding="utf-8")
        diffs = compare_xml(expected, actual)
        if diffs:
            print(f"\n=== MISMATCH: {rel} ===")
            for d in diffs:
                print(d)
            total_diffs += len(diffs)
        else:
            print(f"[OK]   {rel}")

    print()
    if total_diffs:
        print(f"FAIL: {total_diffs} total diff(s).")
        return 1
    print("PASS: all outputs match committed HTML/JSON/XML.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
