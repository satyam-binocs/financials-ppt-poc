#!/usr/bin/env python3
"""
audit_deck.py — post-build compliance audit for pe-deck-design.

layout_engine.py checks the plan. This checks the artefact. They are different
questions: a plan can be clean and the emitted XML still carry an autofit
shrink, a stray 6pt run, a title in Title Case, or a decorative stripe.

Read-only. Opens the .pptx as a zip and parses slide XML with ElementTree —
it never writes OOXML back, so it cannot corrupt namespace prefixes.

Run it after every build, and again after every fix:

    python3 scripts/audit_deck.py deck.pptx
    python3 scripts/audit_deck.py deck.pptx --json
    python3 scripts/audit_deck.py deck.pptx --max-chars 1200

Exit code 1 on any FAIL, so it drops straight into a build pipeline.
"""

import argparse
import json
import os
import re
import sys
import zipfile
from collections import defaultdict
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
TOKENS_PATH = os.path.join(HERE, "..", "assets", "design-tokens.json")

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
EMU = 914400.0

CITE_RE = re.compile(r"\[\s*\d+(?:\s*[,\u2013-]\s*\d+)*\s*\]")
URL_RE = re.compile(r"(https?://|www\.)", re.I)
# Source strings that belong in the appendix, not inside a component.
SOURCE_LEAK_RE = re.compile(
    r"\b(19|20)\d{2}\b\s*$|"
    r"\b(Gartner|McKinsey|Bain|BCG|Nielsen|IBISWorld|Euromonitor|Statista|PitchBook|"
    r"Capital IQ|Bloomberg|Reuters)\b", re.I)


def load_tokens(path=TOKENS_PATH):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


class Finding:
    __slots__ = ("level", "slide", "rule", "message")

    def __init__(self, level, slide, rule, message):
        self.level, self.slide, self.rule, self.message = level, slide, rule, message

    def as_dict(self):
        return {"level": self.level, "slide": self.slide,
                "rule": self.rule, "message": self.message}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def slide_parts(zf):
    names = [n for n in zf.namelist()
             if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
    return sorted(names, key=lambda n: int(re.search(r"(\d+)", os.path.basename(n)).group(1)))


def runs(root):
    """Yield (run_element, rPr_element_or_None, text) for every text run."""
    for r in root.iter(A + "r"):
        rpr = r.find(A + "rPr")
        t = r.find(A + "t")
        yield r, rpr, (t.text or "" if t is not None else "")


def all_text(root):
    return "".join((t.text or "") for t in root.iter(A + "t"))


def emu_in(value):
    try:
        return int(value) / EMU
    except (TypeError, ValueError):
        return None


def shape_name(sp):
    """<p:cNvPr name=...> — how the renderer labels a shape's PURPOSE."""
    cnv = sp.find(f".//{P}cNvPr")
    return (cnv.get("name") or "") if cnv is not None else ""


def is_structural(sp):
    """
    Structure is not decoration. A matrix axis, a timeline rail and a tracker
    divider are load-bearing parts of a component; an accent stripe under a
    title is the AI-slide tell the spec bans. The renderer marks the first kind
    `structure:*`, and only that mark exempts a textless bar from the stripe
    rule. Nothing infers the exemption from geometry.
    """
    return shape_name(sp).startswith("structure:")


def visual_bounds(xfrm):
    """
    Bounds as DRAWN, not as stored. A text box rotated 90 or 270 degrees keeps
    its unrotated x/y/cx/cy in the XML while PowerPoint draws it swapped about
    its centre — a vertical axis label reads as off-slide unless the rotation is
    applied here first.
    """
    off, ext = xfrm.find(A + "off"), xfrm.find(A + "ext")
    if off is None or ext is None:
        return None
    x, y = emu_in(off.get("x")), emu_in(off.get("y"))
    w, h = emu_in(ext.get("cx")), emu_in(ext.get("cy"))
    if None in (x, y, w, h):
        return None
    try:
        rot = (int(xfrm.get("rot") or 0) / 60000.0) % 360
    except (TypeError, ValueError):
        rot = 0
    if 45 <= rot < 135 or 225 <= rot < 315:
        cx, cy = x + w / 2, y + h / 2
        w, h = h, w
        x, y = cx - w / 2, cy - h / 2
    return x, y, w, h


def is_divider_slide(root):
    """A section divider: marked by the renderer, exempt from density checks."""
    return any(shape_name(sp).startswith("structure:divider")
               for sp in root.iter(P + "sp"))


def is_references_slide(root):
    """
    The References/Appendix slide is the one place where full source strings and
    7pt metadata type are correct. Exempt it from the checks that exist purely to
    push that content here.
    """
    head = all_text(root)[:160].lower()
    return any(k in head for k in ("references", "source list", "appendix", "bibliography"))


def is_title_case(text):
    """Heuristic: most words capitalised in a multi-word string."""
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'\-]*", text) if len(w) > 3]
    if len(words) < 4:
        return False
    caps = sum(1 for w in words if w[0].isupper())
    return caps / len(words) > 0.7


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------

def check_typography(root, sn, tokens, out, exempt=False):
    tt = tokens["type"]
    floor, ceiling = tt["footnote_floor_pt"], tt["max_pt"]
    content_floor = tt["min_pt"]
    allowed_fonts = {tt["fonts"]["header"], tt["fonts"]["body"],
                     tt["fonts"]["header_fallback"]}
    seen_fonts = set()
    sizes = []

    for _, rpr, text in runs(root):
        if rpr is None:
            continue
        sz = rpr.get("sz")
        if sz:
            pt = int(sz) / 100.0
            sizes.append(pt)
            if pt < floor:
                out.append(Finding("FAIL", sn, "type.min",
                                   f"{pt:g}pt run below the {floor}pt absolute floor: "
                                   f"{text[:44]!r}"))
            elif pt < content_floor and len(text.strip()) > 60 and not exempt:
                out.append(Finding("WARN", sn, "type.min",
                                   f"{pt:g}pt used for {len(text.strip())} characters of copy. "
                                   f"{floor}pt is reserved for source/footnote metadata; "
                                   f"content floor is {content_floor}pt."))
            if pt > ceiling:
                out.append(Finding("FAIL", sn, "type.max",
                                   f"{pt:g}pt run exceeds the {ceiling}pt maximum: "
                                   f"{text[:44]!r}"))
        for latin in rpr.iter(A + "latin"):
            face = latin.get("typeface")
            if face:
                seen_fonts.add(face)

    stray = {f for f in seen_fonts if f not in allowed_fonts and not f.startswith("+")}
    if stray:
        out.append(Finding("WARN", sn, "type.family",
                           f"Fonts outside the {tt['fonts']['header']}/{tt['fonts']['body']} "
                           f"pair: {sorted(stray)}"))

    # Distortion: PowerPoint's autofit shrink IS horizontal/vertical font scaling.
    for af in root.iter(A + "normAutofit"):
        fs, ls = af.get("fontScale"), af.get("lnSpcReduction")
        if fs or ls:
            out.append(Finding(
                "FAIL", sn, "type.distortion",
                f"normAutofit is shrinking text (fontScale={fs}, lnSpcReduction={ls}). "
                f"The spec forbids scaling the font to force a fit — resize the box, "
                f"cut copy, or move content to another slide."))

    # Line spacing bands.
    for lnspc in root.iter(A + "lnSpc"):
        pct = lnspc.find(A + "spcPct")
        if pct is None:
            continue
        val = int(pct.get("val", 0)) / 1000.0
        lo = tt["line_spacing_multiple"]["header_min"] * 100
        hi = tt["line_spacing_multiple"]["body_max"] * 100
        if not (lo - 0.5 <= val <= hi + 0.5):
            out.append(Finding("WARN", sn, "type.leading",
                               f"Line spacing {val:g}% sits outside the permitted "
                               f"{lo:g}-{hi:g}% window."))
    return sizes


def check_case(root, sn, tokens, out, exempt=False):
    maxcaps = tokens["type"]["case"]["allcaps_max_chars"]
    for _, rpr, text in runs(root):
        stripped = text.strip()
        if not stripped:
            continue
        letters = [c for c in stripped if c.isalpha()]
        if letters and all(c.isupper() for c in letters) and len(stripped) > maxcaps:
            out.append(Finding("FAIL", sn, "case.allcaps",
                               f"ALL CAPS run of {len(stripped)} chars. Caps are permitted "
                               f"only for labels/tags up to {maxcaps} chars: {stripped[:44]!r}"))
        elif is_title_case(stripped) and len(stripped) > 24:
            if exempt:
                continue
            out.append(Finding("WARN", sn, "case.titlecase",
                               f"Looks like Title Case; the spec requires sentence case: "
                               f"{stripped[:52]!r}"))


def check_geometry(root, sn, tokens, out):
    g, c = tokens["grid"], tokens["canvas"]
    left, right = g["margin_left_in"], c["width_in"] - g["margin_right_in"]
    top, bottom = 0.25, c["height_in"] - 0.18

    for sp in list(root.iter(P + "sp")) + list(root.iter(P + "pic")) + \
              list(root.iter(P + "graphicFrame")):
        xfrm = sp.find(f".//{A}xfrm")
        if xfrm is None:
            continue
        bounds = visual_bounds(xfrm)
        if bounds is None:
            continue
        x, y, w, h = bounds

        if x < left - 0.02 or x + w > right + 0.02:
            out.append(Finding("FAIL", sn, "grid.margin",
                               f"Shape spans {x:.2f}in-{x+w:.2f}in, outside the "
                               f"{left:.2f}-{right:.2f}in content band."))
        if y < top or y + h > bottom + 0.02:
            out.append(Finding("FAIL", sn, "grid.vertical",
                               f"Shape spans {y:.2f}in-{y+h:.2f}in vertically, outside the "
                               f"{top:.2f}-{bottom:.2f}in band — content is running off-slide."))

        # Decorative stripes / accent bars: banned as an AI-slide tell.
        has_text = sp.find(f".//{A}t") is not None
        if is_structural(sp):
            continue
        if not has_text and h < 0.09 and w > 2.5:
            out.append(Finding("WARN", sn, "decoration.stripe",
                               f"Thin horizontal bar ({w:.1f}in x {h:.2f}in) with no text. "
                               f"Accent rules and colour stripes are banned — use whitespace."))
        if not has_text and w < 0.09 and h > 1.5:
            out.append(Finding("WARN", sn, "decoration.stripe",
                               f"Vertical stripe ({w:.2f}in x {h:.1f}in) with no text. "
                               f"Edge stripes are banned."))


def check_citations(root, sn, tokens, out, exempt=False):
    text = all_text(root)
    if URL_RE.search(text):
        out.append(Finding("FAIL", sn, "cite.url",
                           "Raw URL on the slide. Citations are numbered [n]; full sources "
                           "belong in the References appendix."))

    nums = set()
    for m in CITE_RE.finditer(text):
        nums.update(int(n) for n in re.findall(r"\d+", m.group()))
    if len(nums) > tokens["citation"]["appendix_threshold"] and not exempt:
        out.append(Finding("WARN", sn, "cite.density",
                           f"{len(nums)} distinct sources cited. Keep [n] markers on the slide "
                           f"and move the full list to the References appendix."))

    # Citation runs must be muted and unemphasised.
    for _, rpr, rtext in runs(root):
        if not CITE_RE.fullmatch(rtext.strip() or "x"):
            continue
        if rpr is not None and rpr.get("b") == "1":
            out.append(Finding("FAIL", sn, "cite.weight",
                               f"Bold citation {rtext.strip()!r}. Citations stay visually "
                               f"subordinate: regular weight, muted colour."))

    for _, _, rtext in runs(root):
        s = rtext.strip()
        if len(s) > 20 and SOURCE_LEAK_RE.search(s) and not CITE_RE.search(s):
            out.append(Finding("INFO", sn, "cite.leak",
                               f"Possible full source name inside a component: {s[:52]!r}. "
                               f"Use [n] here and the full entry in References."))
            break
    return nums


def check_density(root, sn, tokens, out):
    text = all_text(root)
    chars = len(CITE_RE.sub("", text).strip())
    d = tokens["density"]
    if chars > d["hard_max"]:
        out.append(Finding("FAIL", sn, "density.hard",
                           f"{chars} characters exceeds the {d['hard_max']} hard maximum. "
                           f"Recompose or split at a logical content boundary."))
    elif chars > d["soft_max"]:
        out.append(Finding("WARN", sn, "density.soft",
                           f"{chars} characters is past the {d['soft_max']} soft maximum. "
                           f"Reflow, consolidate, shorten, deprioritise — in that order."))
    elif chars < 200 and chars > 0:
        out.append(Finding("INFO", sn, "density.sparse",
                           f"Only {chars} characters. Scale typography up, or pull related "
                           f"content forward so the slide reads as complete."))
    return chars


def check_tables(root, sn, tokens, out):
    for tbl in root.iter(A + "tbl"):
        rows = list(tbl.iter(A + "tr"))
        if not rows:
            continue

        # Zebra detection: alternating body-row fills.
        fills = []
        for tr in rows[1:]:
            colors = set()
            for tc in tr.iter(A + "tc"):
                tcpr = tc.find(A + "tcPr")
                if tcpr is not None:
                    for sf in tcpr.iter(A + "srgbClr"):
                        colors.add(sf.get("val"))
            fills.append(tuple(sorted(colors)))
        zebra = (len(fills) >= 4 and
                 len({f for f in fills[0::2]}) == 1 and
                 len({f for f in fills[1::2]}) == 1 and
                 set(fills[0::2]) != set(fills[1::2]))

        # Tag/pill detection: short, emphasised, repeated first-column-ish labels.
        tagish = 0
        for tr in rows[1:]:
            cells = list(tr.iter(A + "tc"))
            for tc in cells[1:2]:
                txt = "".join((t.text or "") for t in tc.iter(A + "t")).strip()
                if 0 < len(txt) <= 12 and " " not in txt:
                    tagish += 1
        has_tags = tagish >= max(2, len(rows) // 2)

        if zebra and has_tags:
            out.append(Finding(
                "FAIL", sn, "table.zebra",
                f"Zebra striping on a table whose rows carry short labels/tags "
                f"({tagish} detected). The spec bans this pairing — keep the background "
                f"uniform and let the tags create the differentiation."))

        # Wrap pressure.
        for ri, tr in enumerate(rows[1:], start=1):
            for tc in tr.iter(A + "tc"):
                txt = "".join((t.text or "") for t in tc.iter(A + "t"))
                if len(txt) > 260:
                    out.append(Finding(
                        "WARN", sn, "table.wrap",
                        f"Row {ri} holds a {len(txt)}-character cell — it will exceed the "
                        f"2-line ceiling. Restructure the table rather than shrinking type."))
                    break

        # Heavy gridlines.
        heavy = 0
        for ln in tbl.iter(A + "lnL"):
            if ln.find(A + "noFill") is None:
                heavy += 1
        for ln in tbl.iter(A + "lnR"):
            if ln.find(A + "noFill") is None:
                heavy += 1
        if heavy > len(rows):
            out.append(Finding("WARN", sn, "table.borders",
                               f"{heavy} vertical cell borders. Prefer subtle horizontal "
                               f"dividers; avoid boxing every cell."))


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------

def audit(pptx_path, tokens):
    out = []
    stats = {}
    with zipfile.ZipFile(pptx_path) as zf:
        parts = slide_parts(zf)
        if not parts:
            out.append(Finding("FAIL", 0, "package", "No slides found in the package."))
            return out, stats
        for part in parts:
            sn = int(re.search(r"(\d+)", os.path.basename(part)).group(1))
            root = ET.fromstring(zf.read(part))
            exempt = is_references_slide(root)
            divider = is_divider_slide(root)
            sizes = check_typography(root, sn, tokens, out, exempt)
            check_case(root, sn, tokens, out, exempt)
            check_geometry(root, sn, tokens, out)
            nums = check_citations(root, sn, tokens, out, exempt)
            # Covers, dividers and trackers are navigation, not content: the
            # character budget does not apply to them and never did.
            chars = check_density(root, sn, tokens, out) if not (divider or exempt) \
                else len(all_text(root))
            check_tables(root, sn, tokens, out)
            stats[sn] = {
                "references_slide": exempt,
                "divider_slide": divider,
                "chars": chars,
                "sources": sorted(nums),
                "min_pt": min(sizes) if sizes else None,
                "max_pt": max(sizes) if sizes else None,
            }
    return out, stats


def render(findings, stats, pptx_path):
    by_slide = defaultdict(list)
    for f in findings:
        by_slide[f.slide].append(f)

    counts = defaultdict(int)
    for f in findings:
        counts[f.level] += 1

    lines = [f"audit: {os.path.basename(pptx_path)}", "=" * 72]
    for sn in sorted(stats):
        st = stats[sn]
        rng = (f"{st['min_pt']:g}-{st['max_pt']:g}pt"
               if st["min_pt"] is not None else "no text")
        lines.append(f"\nslide {sn}  |  {st['chars']} chars  |  {rng}  |  "
                     f"{len(st['sources'])} sources")
        for f in sorted(by_slide.get(sn, []), key=lambda x: x.level):
            lines.append(f"  [{f.level}] {f.rule}: {f.message}")
        if not by_slide.get(sn):
            lines.append("  clean")

    lines.append("\n" + "-" * 72)
    lines.append(f"FAIL {counts['FAIL']}   WARN {counts['WARN']}   INFO {counts['INFO']}")
    lines.append("verdict: " + ("FAIL" if counts["FAIL"] else
                                "PASS (with warnings)" if counts["WARN"] else "PASS"))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="pe-deck-design compliance audit")
    ap.add_argument("pptx")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--tokens", default=TOKENS_PATH)
    ap.add_argument("--strict", action="store_true", help="treat WARN as failure")
    args = ap.parse_args()

    tokens = load_tokens(args.tokens)
    findings, stats = audit(args.pptx, tokens)

    if args.json:
        print(json.dumps({"file": args.pptx,
                          "findings": [f.as_dict() for f in findings],
                          "stats": stats}, indent=2))
    else:
        print(render(findings, stats, args.pptx))

    levels = {f.level for f in findings}
    if "FAIL" in levels or (args.strict and "WARN" in levels):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
