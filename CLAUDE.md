# CLAUDE.md

This repo generates a 3D-printable Christmas ornament of the EMSS logo for a Bambu Lab P1S.

## Files

- `make_ornament.py` — generates the STL files. Pure Python standard library, no dependencies.
- `emss_ornament_base.stl` — backing plate with a hanging loop and a pocket under each letter.
- `emss_ornament_letter_1_E.stl`, `emss_ornament_letter_2_M.stl`, `emss_ornament_letter_3_S.stl`, `emss_ornament_letter_4_S.stl` — one file per letter, so each letter can be printed in its own color. Each letter sits in its pocket and stands above the plate. The two S files are identical apart from position, so they are interchangeable.
- `emss_ornament_combined.stl` — solid plate (no pockets) with raised letters, for single-color printing.
- `emss_logo.svg` — the original EMSS logo as a standalone SVG, converted from the Maestro `EMSSLogo` component. All shapes are filled white, so it looks blank on a white background.
- `check_stl.py` — checks that generated meshes are closed.

The STL files are committed so they can be opened in Bambu Studio on another machine without running the script.

## Regenerating

```bash
python3 make_ornament.py .
```

Rerun this and commit the updated STL files after changing any dimension.

## How the script works

- The logo path data in `LOGO_LETTERS` is copied by hand from `emss_logo.svg` (`viewBox 0 0 97 18`) and grouped by letter. The SVG's one `<rect>` is written as an equivalent path in the E, with its top edge moved by 0.0018 units to close a tiny gap in the SVG so that the bottom of the E prints as one piece. If the SVG changes, update `LOGO_LETTERS` to match. The script parses only absolute `M`, `L`, `H`, `V`, `C`, and `Z` commands.
- Cubic Bezier curves are flattened into line segments, and the Y axis is flipped because SVG Y points down.
- Each logo shape must be convex. `assert_convex` exits if one is not. Convexity is what lets `offset_convex_polygon` grow a shape outward to make its pocket, and it keeps the point-in-shape test simple. Shapes that are not convex, such as the NASA meatball, would need a different offset and containment test.
- `build_stepped_solid` builds every plate and letter mesh. It takes overlapping convex shapes, each with a top height, and returns one closed solid with a flat bottom and a stepped top. For example, the base is the plate at full thickness with the letter pockets at floor height. The solid is built from vertical slabs cut at every vertex and edge crossing, and coordinates are snapped to a 0.0001 mm grid so that shared vertices match exactly.
- Letters are placed at their in-pocket position (bottom at the pocket floor), so loading them as parts of the base lines them up.
- The hanging loop is a separate ring mesh that overlaps the plate edge. The slicer merges overlapping shells into one solid.

## Dimensions

All dimensions are constants at the top of `make_ornament.py`, in millimeters:

| Constant | Value | Meaning |
|---|---|---|
| `MILLIMETERS_PER_SVG_UNIT` | 0.9 | Overall scale. Logo is about 87 mm wide. |
| `PLATE_MARGIN` | 4.0 | Space between the logo and the plate edge |
| `PLATE_CORNER_RADIUS` | 4.0 | Plate corner rounding |
| `PLATE_THICKNESS` | 2.4 | Base plate thickness |
| `POCKET_DEPTH` | 1.2 | How deep the letter pockets go into the plate. The floor under them is `PLATE_THICKNESS - POCKET_DEPTH`. |
| `POCKET_CLEARANCE` | 0.15 | Gap between each letter and its pocket wall, per side, so separately printed letters fit |
| `LOGO_RAISE_HEIGHT` | 1.2 | How far the letters stand above the plate. Letters are `POCKET_DEPTH + LOGO_RAISE_HEIGHT` thick. |
| `LOOP_OUTER_RADIUS` | 4.5 | Hanging loop outer radius |
| `LOOP_HOLE_RADIUS` | 2.0 | Hanging loop hole radius (4 mm hole for wire or a hook) |

## Verifying changes

After regenerating, confirm that every mesh is closed:

```bash
python3 check_stl.py emss_ornament_base.stl emss_ornament_letter_*.stl emss_ornament_combined.stl
```

Each file should report `non-manifold directed edges: 0`. Also confirm that the printed plate size is what you expect.

## Printing in Bambu Studio

Print every part flat with its back face on the bed. No supports are needed.

- **Each letter a different color, printed separately:** print the base in one color. Then print each letter file in its own color; Bambu Studio drops each one to the bed on import. Press or glue each letter into its pocket. If the letters are too tight or too loose, change `POCKET_CLEARANCE` and reprint the base.
- **Each letter a different color, in one print with an AMS:** import the base and the four letter STLs together and choose to load them as a single object with multiple parts. Assign the base and each letter a filament.
- **Two colors without an AMS:** print `emss_ornament_combined.stl` with a filament change at the first layer above 2.4 mm.
- **One color:** print `emss_ornament_combined.stl`.
