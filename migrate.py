#!/usr/bin/env python3
"""
SabSys — Refined Slate template migration.

Applies the *mechanical, unambiguous* sweeps from the template review directly
to your Django templates. Idempotent: safe to run repeatedly. Designed to land a
clean, reviewable git diff.

What it does (each is a distinctive, exact-match transform — see review F-numbers):

  F2  Remove every `{% include "components/app_styles.html" %}` and collapse any
      `{% block extra_css %}…{% endblock %}` that becomes empty as a result.
  F1  `style="background:#1e2130;color:#fff"` (± `;border-color:#1e2130`) on a
      button/link  →  add the `.btn-brand` class, drop the inline style.
  F3  The repeated section-header inline string  →  `class="app-card-head"`
      (and the flex/space-between variant  →  `app-card-head app-card-head--row`).
  F12 `class="modal-header" style="background:#f9fafb;border-bottom:1px solid #e5e7eb"`
      →  `class="modal-header"` (components.css now styles it).
  F4  Pure semantic-colour inline styles  →  classes:
        style="color:#16a34a"  → .num-pos
        style="color:#dc2626"  → .num-neg     style="color:#b42318" → .num-neg
        style="color:#1e2130"  → .link-brand  (only on links, i.e. tags whose
                                               class already has text-decoration-none)
  F7  `<h4 class="app-header-title">…</h4>`  →  `<h1 …>…</h1>`  (one heading
      level per page; the visual size is owned by the class, not the tag).
  F8  `dt-kebab-btn` toggle  →  add aria-label="{% trans 'Acciones' %}".
      Bare trash button `<button class="btn btn-outline-danger btn-sm"><i bi-trash>`
      →  aria-label + title + aria-hidden icon.
  F10 base.html — trim the Cormorant Garamond request to the two weights actually
      used (600, 700). The serif stays app-wide; it is part of the document look.

What it deliberately does NOT touch (needs human judgement — do these by hand
using the shipped partials / existing components; see README):
  • templates/sales/email/*  (email needs inline styles — excluded entirely)
  • base_anon.html `<style>` block colours
  • combined/conditional inline styles  (e.g. style="font-size:.85rem;color:#1e2130",
    or {% if %}color:#dc2626{% else %}… — left as-is and reported)
  • F5  fold dashboard/detail KPIs onto the existing components/_kpi_cards.html
        (needs a `stats` list in the view — see MIGRATION-2 worked example)
  • F6  replace hand-rolled status if/elif with the existing
        sales/partials/status_badge.html  (see edited/dashboard.html)
  • F8  icon-only back-arrow links, and the navbar org pill (see edited/_navbar.html)
  • F11 <table>-for-layout meta blocks → <dl class="detail-dl"> + _detail_row.html

Usage:
    python migrate.py --root templates --dry-run     # preview, change nothing
    python migrate.py --root templates               # apply
    python migrate.py --root templates --base templates/base.html
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

# ── F1 / F4 — exact inline style value  →  class to add on that tag ──────────
STYLE_TO_CLASS = {
    "background:#1e2130;color:#fff": "btn-brand",
    "background:#1e2130;color:#fff;border-color:#1e2130": "btn-brand",
    "color:#16a34a": "num-pos",
    "color:#dc2626": "num-neg",
    "color:#b42318": "num-neg",
}
# color:#1e2130 is handled specially (link-brand, links only) below.

# ── F3 / F12 — whole exact substring  →  replacement (no class injection) ────
EXACT_REPLACEMENTS = [
    (
        'style="padding:10px 14px 9px;border-bottom:1px solid #e5e7eb;'
        'font-size:.7rem;font-weight:600;text-transform:uppercase;'
        'letter-spacing:.04em;color:#6b7280"',
        'class="app-card-head"',
    ),
    (
        'style="padding:10px 14px 9px;border-bottom:1px solid #e5e7eb;'
        'display:flex;align-items:center;justify-content:space-between"',
        'class="app-card-head app-card-head--row"',
    ),
    (
        'class="modal-header" style="background:#f9fafb;border-bottom:1px solid #e5e7eb"',
        'class="modal-header"',
    ),
]

# ── F10 — base.html font link ────────────────────────────────────────────────
FONT_FROM = (
    "family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;0,700;1,400;1,600"
)
FONT_TO = "family=Cormorant+Garamond:wght@600;700"

TAG_RE = re.compile(r"<(?:button|a|div|span|td|th|strong|p|i)\b[^>]*?>")
INCLUDE_RE = re.compile(r'\{%\s*include "components/app_styles\.html"\s*%\}')
EMPTY_BLOCK_RE = re.compile(r"\{%\s*block extra_css\s*%\}\s*\{%\s*endblock\s*%\}")
CLASS_RE = re.compile(r'class="([^"]*)"')

# ── F7 — page heading level: <h4 class="app-header-title">…</h4>  →  <h1> ─────
H4_TITLE_RE = re.compile(
    r'<h4(\s+class="app-header-title"[^>]*)>(.*?)</h4>', re.S
)
# ── F8 — kebab dropdown toggle needs an accessible name ──────────────────────
KEBAB_RE = re.compile(
    r'class="btn btn-link btn-sm p-0 dt-kebab-btn"(?! aria-label)'
)
KEBAB_DST = (
    "class=\"btn btn-link btn-sm p-0 dt-kebab-btn\" aria-label=\"{% trans 'Acciones' %}\""
)
# ── F8 — bare trash icon button on detail pages ──────────────────────────────
TRASH_SRC = '<button class="btn btn-outline-danger btn-sm"><i class="bi bi-trash"></i></button>'
TRASH_DST = (
    '<button class="btn btn-outline-danger btn-sm" '
    "aria-label=\"{% trans 'Eliminar' %}\" title=\"{% trans 'Eliminar' %}\">"
    '<i class="bi bi-trash" aria-hidden="true"></i></button>'
)


def add_class(tag: str, cls: str) -> str:
    """Add cls to the tag's class attribute (idempotently), creating one if absent."""
    m = CLASS_RE.search(tag)
    if m:
        classes = m.group(1).split()
        if cls in classes:
            return tag
        classes.append(cls)
        return tag[: m.start()] + 'class="' + " ".join(classes) + '"' + tag[m.end():]
    # no class attr — inject right after the tag name
    return re.sub(r"^(<[a-zA-Z]+)(\s|>)", rf'\1 class="{cls}"\2', tag, count=1)


def strip_style(tag: str, value: str) -> str:
    return tag.replace(f' style="{value}"', "").replace(f'style="{value}"', "")


def transform_tags(text: str, stats: dict) -> str:
    def repl(match: re.Match) -> str:
        tag = match.group(0)
        # F1 / F4 exact style→class
        for value, cls in STYLE_TO_CLASS.items():
            if f'style="{value}"' in tag:
                tag = add_class(strip_style(tag, value), cls)
                stats[cls] = stats.get(cls, 0) + 1
        # F4 link-brand — only genuine links (text-decoration-none present)
        if 'style="color:#1e2130"' in tag and "text-decoration-none" in tag:
            tag = add_class(strip_style(tag, "color:#1e2130"), "link-brand")
            stats["link-brand"] = stats.get("link-brand", 0) + 1
        return tag

    return TAG_RE.sub(repl, text)


def migrate_text(text: str, stats: dict) -> str:
    # F2 — remove includes, then collapse now-empty extra_css blocks
    n_inc = len(INCLUDE_RE.findall(text))
    if n_inc:
        text = INCLUDE_RE.sub("", text)
        stats["app_styles_include_removed"] = stats.get("app_styles_include_removed", 0) + n_inc
    n_blk = len(EMPTY_BLOCK_RE.findall(text))
    if n_blk:
        text = EMPTY_BLOCK_RE.sub("", text)
        stats["empty_extra_css_block_removed"] = stats.get("empty_extra_css_block_removed", 0) + n_blk
    # tidy a stray blank line left at the top of a kept extra_css block
    text = re.sub(r"(\{%\s*block extra_css\s*%\})\n\n+", r"\1\n", text)
    # collapse runs of blank lines left by removed includes/blocks
    if n_inc or n_blk:
        text = re.sub(r"\n{3,}", "\n\n", text)

    # F3 / F12 — exact substring replacements
    for src, dst in EXACT_REPLACEMENTS:
        c = text.count(src)
        if c:
            text = text.replace(src, dst)
            stats[dst] = stats.get(dst, 0) + c

    # F1 / F4 — tag-level class injection
    text = transform_tags(text, stats)

    # F7 — page heading <h4 class="app-header-title">…</h4> → <h1>…</h1>
    n_h = len(H4_TITLE_RE.findall(text))
    if n_h:
        text = H4_TITLE_RE.sub(r"<h1\1>\2</h1>", text)
        stats["h4_to_h1"] = stats.get("h4_to_h1", 0) + n_h

    # F8 — kebab toggle accessible name
    n_k = len(KEBAB_RE.findall(text))
    if n_k:
        text = KEBAB_RE.sub(KEBAB_DST, text)
        stats["kebab_aria"] = stats.get("kebab_aria", 0) + n_k

    # F8 — bare trash icon button
    n_t = text.count(TRASH_SRC)
    if n_t:
        text = text.replace(TRASH_SRC, TRASH_DST)
        stats["trash_aria"] = stats.get("trash_aria", 0) + n_t

    return text


def report_leftovers(text: str) -> list[str]:
    """Flag patterns this script intentionally leaves for manual handling."""
    notes = []
    if re.search(r'style="[^"]*color:#1e2130[^"]*"', text):
        # only count the ones we did NOT convert (combined / non-link)
        notes.append("residual color:#1e2130 (combined or non-link) — review for link-brand/num/etc.")
    if re.search(r"\{%\s*if[^%]*%\}color:#", text):
        notes.append("conditional inline colour — convert by hand")
    if "background:#1e2130;color:#fff" in text:
        notes.append("brand button not converted (unusual tag) — check manually")
    return notes


def main() -> int:
    ap = argparse.ArgumentParser(description="SabSys Refined Slate template migration")
    ap.add_argument("--root", default="templates", help="templates directory (default: templates)")
    ap.add_argument("--base", default=None, help="path to base.html for the F10 font trim (default: <root>/base.html)")
    ap.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2

    base = Path(args.base) if args.base else root / "base.html"
    totals: dict[str, int] = {}
    changed_files = 0
    flagged: dict[str, list[str]] = {}

    for path in sorted(root.rglob("*.html")):
        # F-scope exclusions
        if "email" in path.parts or path.name.endswith("_email.html"):
            continue
        original = path.read_text(encoding="utf-8")
        stats: dict[str, int] = {}
        migrated = migrate_text(original, stats)

        notes = report_leftovers(migrated)
        if notes:
            flagged[str(path)] = notes

        if migrated != original:
            changed_files += 1
            for k, v in stats.items():
                totals[k] = totals.get(k, 0) + v
            rel = path
            if args.dry_run:
                print(f"[dry-run] would update {rel}  " + ", ".join(f"{k}×{v}" for k, v in stats.items()))
            else:
                path.write_text(migrated, encoding="utf-8")
                print(f"updated {rel}  " + ", ".join(f"{k}×{v}" for k, v in stats.items()))

    # F10 — base.html font trim
    if base.is_file():
        btext = base.read_text(encoding="utf-8")
        if FONT_FROM in btext:
            if args.dry_run:
                print(f"[dry-run] would trim Cormorant weights in {base}")
            else:
                base.write_text(btext.replace(FONT_FROM, FONT_TO), encoding="utf-8")
                print(f"updated {base}  (F10 font weights 600;700)")
            totals["font_trim"] = totals.get("font_trim", 0) + 1
        elif FONT_TO in btext:
            pass  # already trimmed
        else:
            print(f"note: Cormorant font string not found verbatim in {base} — trim by hand (F10)")

    print("\n── summary ────────────────────────────────")
    print(f"files {'to change' if args.dry_run else 'changed'}: {changed_files}")
    for k in sorted(totals):
        print(f"  {k}: {totals[k]}")
    if flagged:
        print("\n── needs manual review (left untouched) ──")
        for f, notes in flagged.items():
            print(f"  {f}")
            for n in notes:
                print(f"      · {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
