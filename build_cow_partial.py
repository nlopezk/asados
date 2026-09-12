# =====================================================================
# build_cow_partial.py
# Turns the hand-drawn Inkscape file (vaca_svg.svg) into the Jinja
# partial the app actually renders (templates/_cow_diagram.html).
#
# WHY A BUILD STEP INSTEAD OF EDITING THE PARTIAL BY HAND: the drawing
# is going to change. Cuts get redrawn, Malaya eventually gets a region
# (see config.py). If the partial were hand-edited, every one of those
# edits would mean redoing the same fiddly conversion by hand, and the
# .svg in the repo would slowly stop matching what the app shows. This
# way vaca_svg.svg stays the single source of truth: open it in
# Inkscape, edit, save, re-run this, done.
#
#   python build_cow_partial.py [source.svg]
#
# What it changes, and why each one matters:
#
#   id="filete"  ->  data-corte="filete"
#       ids must be unique per document. If this partial were ever
#       included twice on one page, duplicate ids would break
#       getElementById and #id selectors SILENTLY, picking whichever
#       came first. data-* has no such rule, and gives one CSS rule
#       ([data-corte]) covering all 27 regions instead of 27 selectors.
#
#   inline style="fill:#782121" is STRIPPED
#       an inline style beats any stylesheet rule that isn't
#       !important. Leaving the fill in would mean the regions could
#       never change colour on hover or when selected, which is the
#       entire point of the diagram. Colour comes from style.css so it
#       follows the app's palette.
#
#   width/height in mm are DROPPED, viewBox is kept
#       the mm sizes would pin the drawing to one physical size; the
#       viewBox is what lets CSS scale it to fit a phone.
#
#   Inkscape/sodipodi metadata is DROPPED
#       editor bookkeeping that the browser ignores; it's most of the
#       difference between the 27 KB source and the output.
#
# The cut NAMES are not baked in: each <title> is emitted as a Jinja
# lookup, so renaming a cut in config.py updates the diagram's tooltips
# without re-running this script.
# =====================================================================

import io
import os
import re
import sys
import xml.etree.ElementTree as ET

from config import CORTES_VACUNO

SVG_NS = "{http://www.w3.org/2000/svg}"
DEFAULT_SOURCE = "vaca_svg.svg"
OUTPUT = os.path.join("templates", "_cow_svg.html")

HEADER = '''<!--
    _cow_svg.html - GENERATED FILE, DO NOT EDIT BY HAND.
    Built from vaca_svg.svg by build_cow_partial.py; re-run that after
    editing the drawing, or your change will be overwritten the next
    time someone does.

    This file is ONLY the markup. The wrapper, the caption and all the
    interaction live in _cow_diagram.html, which includes this - so
    redrawing the cow can never clobber the behaviour, and editing the
    behaviour never means hand-patching 27 generated <path> elements.
    Include _cow_diagram.html, never this file directly.

    INLINE svg, never <img src="...svg">. An SVG loaded through an
    <img> is an opaque, isolated document: no per-region events, no
    page CSS reaching inside it, and no access to the :root custom
    properties that give these regions their colours. Only inline SVG
    shares a document with the rest of the page. That is also why this
    project has no static/images/ directory.

    The regions are deliberately NOT individually focusable. 27 tab
    stops would be a miserable way through this form and would buy
    nothing: the cut dropdown beside the diagram offers every cut,
    including the five with no region drawn, so keyboard and screen
    reader users already have a complete and better path to the same
    result. The diagram is a visual shortcut, not the only way in.
-->
'''



# Inkscape writes 6+ decimal places. On a 141-unit viewBox that is far
# more precision than can ever be rendered - 0.0005 units is roughly
# 1/2000th of a pixel at any size this is displayed. Rounding to 3
# trims about 20% off a file that gets inlined into every asado form.
#
# 3 rather than 2 because this path data is mostly RELATIVE commands,
# where each coordinate is an offset from the last, so rounding error
# accumulates along the path instead of cancelling out. At 3 decimals
# the worst case over a long path is ~0.1 units (0.07% of the width);
# at 2 it could reach a visible ~1 unit.
#
# Applied ONLY to d= and transform= values, never to the whole file:
# a blind pass over the text could round a number inside a Jinja
# expression or an attribute name.
NUMBER = re.compile(r"-?\d*\.\d+(?:[eE][-+]?\d+)?")


def round_numbers(text, places=3):
    if not text:
        return text
    return NUMBER.sub(lambda m: f"{round(float(m.group()), places):g}", text)


def is_hidden(element):
    """
    True for a path the author hid in Inkscape (display:none).

    These MUST be skipped, and the reason is the conversion itself: this
    script strips the drawing's inline styles so the app's CSS can own
    the colours. `display:none` lives in that same style attribute, so
    stripping it would RESURRECT a hidden path as a visible one — and
    since a hidden leftover has no matching cut, it would come through
    as an extra silhouette blob sitting on top of the cow. Hit for real:
    the 1.7.3 drawing carried two hidden leftovers (path20, path25).
    """
    style = element.get("style", "")
    return "display:none" in style.replace(" ", "") or element.get("display") == "none"


def effective_transform(group, path):
    """
    The transform to put on this path in the output.

    Inkscape puts the layer offset on the GROUP for some paths and on
    the PATH ITSELF for others, depending on how the artwork was built
    and edited - the same drawing can legitimately contain both. An
    earlier version of this script only read the group's, which silently
    dropped the offset on any path carrying its own and rendered it tens
    of units away from the rest of the cow.

    SVG composes a transform list left to right, outermost first, so
    emitting them space-separated in that order is exactly equivalent to
    the nesting the source file expressed.
    """
    parts = [group.get("transform", ""), path.get("transform", "")]
    return " ".join(round_numbers(p) for p in parts if p)


def main(source=DEFAULT_SOURCE):
    if not os.path.exists(source):
        print(f"ERROR: '{source}' not found.")
        return 1

    root = ET.parse(source).getroot()
    view_box = root.get("viewBox")
    if not view_box:
        print("ERROR: source SVG has no viewBox.")
        return 1

    expected = {slug: name for name, slug in CORTES_VACUNO.items() if slug}

    body = []      # the cow silhouette: paths with no recognised cut id
    regions = []   # (slug, path data), in document order

    skipped_hidden = []
    for group in root.iter(SVG_NS + "g"):
        for path in group.findall(SVG_NS + "path"):
            d = round_numbers(path.get("d"))
            if not d:
                continue
            name = path.get("data-corte") or path.get("id")
            if is_hidden(path):
                skipped_hidden.append(name or "(unnamed)")
                continue
            transform = effective_transform(group, path)
            if name in expected:
                regions.append((name, d, transform))
            else:
                # Anything that isn't a known cut is silhouette: the cow
                # outline, and the torso mass the cuts are tiled over.
                # Both are non-interactive and share one style.
                body.append((d, transform))

    missing = sorted(set(expected) - {slug for slug, _, _ in regions})
    if missing:
        print(f"ERROR: {len(missing)} cut(s) in config.py have no shape in "
              f"the drawing: {', '.join(missing)}")
        print("Fix the drawing (or set those to None in CORTES_VACUNO) and re-run.")
        return 1

    # Every group in this drawing carries the same transform. Rather
    # than assume that, each path keeps its own group's transform.
    out = [HEADER]
    out.append(f'<svg class="cow-diagram" viewBox="{view_box}" role="img"')
    out.append('     aria-label="Diagrama de los cortes de vacuno">')

    for d, transform in body:
        t = f' transform="{transform}"' if transform else ""
        # pointer-events:none in CSS - the silhouette must never
        # swallow a click meant for a region sitting on top of it.
        out.append(f'    <path class="cow-body"{t} d="{d}"/>')

    for slug, d, transform in regions:
        t = f' transform="{transform}"' if transform else ""
        out.append(f'    <path class="cow-region" data-corte="{slug}"{t} d="{d}">'
                   f'<title>{{{{ cortes_nombres["{slug}"] }}}}</title></path>')

    out.append('</svg>')

    io.open(OUTPUT, "w", encoding="utf-8").write("\n".join(out) + "\n")

    size_kb = os.path.getsize(OUTPUT) / 1024
    src_kb = os.path.getsize(source) / 1024
    print(f"Wrote {OUTPUT}")
    print(f"  {len(regions)} cut regions + {len(body)} silhouette path(s)")
    if skipped_hidden:
        print(f"  skipped {len(skipped_hidden)} hidden path(s): "
              f"{', '.join(skipped_hidden)}")
    print(f"  {src_kb:.1f} KB source -> {size_kb:.1f} KB partial")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SOURCE))
