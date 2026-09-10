# =====================================================================
# check_cow_svg.py
# Checks a hand-drawn cow diagram SVG against config.py's CORTES_VACUNO
# BEFORE it gets wired into the app.
#
# WHY THIS EXISTS: the diagram is only useful if every cut region is
# its own addressable element with a name the app recognises. That is
# easy to get subtly wrong in a drawing tool — one region accidentally
# merged into its neighbour, a layer left named "path4471", an accent
# typed into a slug — and each of those fails SILENTLY once it's in the
# app (the region just never lights up, with nothing in the console to
# say why). This script turns all of those into a message you can read
# before spending time on the wiring.
#
# It is a DEV TOOL, like create_user.py and seed_random_asados.py — the
# running app never imports it.
#
#   python check_cow_svg.py path/to/cow.svg
# =====================================================================

import os
import sys
import xml.etree.ElementTree as ET

from config import CORTES_VACUNO

SVG_NS = "{http://www.w3.org/2000/svg}"
# Elements that can sensibly BE a cut region (a closed, fillable shape).
SHAPE_TAGS = {"path", "polygon", "rect", "circle", "ellipse"}


def region_name(element):
    """A region is identified by data-corte if present, otherwise by id.
    Accepting plain `id` matters: drawing tools export layer/object
    names as ids, so naming a layer "lomo-vetado" is all the author has
    to do — the conversion to data-corte happens when this is wired in."""
    return element.get("data-corte") or element.get("id")


def main(path):
    if not os.path.exists(path):
        print(f"ERROR: '{path}' not found.")
        return 1

    size_kb = os.path.getsize(path) / 1024
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        print(f"ERROR: not valid XML/SVG — {exc}")
        return 1

    problems = []
    warnings = []

    # --- viewBox: what makes the drawing scale instead of being stuck
    # at one pixel size. Without it the diagram can't be responsive. ---
    if not root.get("viewBox"):
        problems.append("No viewBox on the root <svg>. Needed so the drawing can scale.")
    else:
        print(f"viewBox: {root.get('viewBox')}")

    # --- Collect every named shape in the document ---
    found = {}
    duplicates = []
    for element in root.iter():
        if not element.tag.startswith(SVG_NS):
            continue
        if element.tag[len(SVG_NS):] not in SHAPE_TAGS:
            continue
        name = region_name(element)
        if not name:
            continue
        if name in found:
            duplicates.append(name)
        found[name] = element

    expected = {slug for slug in CORTES_VACUNO.values() if slug}
    missing = sorted(expected - set(found))
    extra = sorted(n for n in found if n not in expected)

    print(f"file size: {size_kb:.1f} KB")
    print(f"named shapes found: {len(found)}   cuts expected: {len(expected)}")
    print()

    if missing:
        problems.append(f"{len(missing)} cut(s) have no matching shape: {', '.join(missing)}")
    if duplicates:
        problems.append(
            "Duplicate names (ids must be unique — duplicates break lookups "
            f"silently): {', '.join(sorted(set(duplicates)))}")
    if extra:
        # Not fatal: a silhouette/outline path is expected to be here and
        # unnamed-or-otherwise-named. Just report so nothing is a surprise.
        warnings.append(
            f"{len(extra)} named shape(s) aren't cuts (fine if these are the "
            f"outline, eye, horns, etc.): {', '.join(extra[:12])}"
            + (" ..." if len(extra) > 12 else ""))

    # --- An embedded bitmap would defeat the entire point: you can't
    # attach a hover to part of a picture. ---
    if any(el.tag == SVG_NS + "image" for el in root.iter()):
        problems.append(
            "Contains an embedded <image> (a bitmap). Regions must be real "
            "vector shapes — a traced or embedded photo can't be made clickable.")

    # --- Size: the SVG gets inlined into the page, so it ships on every
    # asado form load. Small is a feature, not a nicety. ---
    if size_kb > 60:
        warnings.append(
            f"{size_kb:.0f} KB is large for an inlined diagram. Under ~25 KB is "
            "comfortable; over ~60 KB is worth simplifying paths first.")

    if any(k.startswith("{http://www.inkscape.org") or k.startswith("{http://sodipodi")
           for el in root.iter() for k in el.attrib):
        warnings.append(
            "Inkscape editor metadata present. Re-saving as 'Plain SVG' "
            "(not 'Inkscape SVG') strips it and shrinks the file.")

    for w in warnings:
        print(f"NOTE     {w}\n")
    for p in problems:
        print(f"PROBLEM  {p}\n")

    if problems:
        print(f"{len(problems)} problem(s) to fix.")
        return 1
    print("OK — every cut has exactly one shape. Ready to wire in.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__ or "Usage: python check_cow_svg.py path/to/cow.svg")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
