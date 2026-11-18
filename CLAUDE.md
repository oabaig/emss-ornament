# CLAUDE.md

This repo generates a 3D-printable Christmas ornament of the EMSS logo for a Bambu Lab P1S.

## Files

- `make_ornament.py` — generates the STL files. Pure Python standard library, no dependencies.
- `emss_ornament_base.stl` — backing plate with a hanging loop.
- `emss_ornament_logo.stl` — raised EMSS letters that sit on top of the plate.
- `emss_ornament_combined.stl` — base and logo in one file for single-color printing.
- `emss_logo.svg` — the original EMSS logo as a standalone SVG, converted from the Maestro `EMSSLogo` component. All shapes are filled white, so it looks blank on a white background.
- `check_stl.py` — checks that generated meshes are closed.

The STL files are committed so they can be opened in Bambu Studio on another machine without running the script.

## Regenerating

```bash
python3 make_ornament.py .
```

Rerun this and commit the updated STL files after changing any dimension.

## How the script works

- The logo path data in `LOGO_PATHS` is copied by hand from `emss_logo.svg` (`viewBox 0 0 97 18`). The SVG's one `<rect>` is written as an equivalent path. If the SVG changes, update `LOGO_PATHS` to match. The script parses only absolute `M`, `L`, `H`, `V`, `C`, and `Z` commands.
- Cubic Bezier curves are flattened into line segments, and the Y axis is flipped because SVG Y points down.
- Each logo shape is convex, so it is triangulated with a fan and extruded into a prism. `assert_convex` exits if a shape is not convex. Shapes that are not convex, such as the NASA meatball, would need a real polygon triangulation (for example, ear clipping) first.
- The hanging loop is a separate ring mesh that overlaps the plate edge. The slicer merges overlapping shells into one solid.

## Dimensions

All dimensions are constants at the top of `make_ornament.py`, in millimeters:

| Constant | Value | Meaning |
|---|---|---|
| `MILLIMETERS_PER_SVG_UNIT` | 0.9 | Overall scale. Logo is about 87 mm wide. |
| `PLATE_MARGIN` | 4.0 | Space between the logo and the plate edge |
| `PLATE_CORNER_RADIUS` | 4.0 | Plate corner rounding |
| `PLATE_THICKNESS` | 2.4 | Base plate thickness |
| `LOGO_RAISE_HEIGHT` | 1.2 | How far the letters stand above the plate |
| `LOOP_OUTER_RADIUS` | 4.5 | Hanging loop outer radius |
| `LOOP_HOLE_RADIUS` | 2.0 | Hanging loop hole radius (4 mm hole for wire or a hook) |

## Verifying changes

After regenerating, confirm that every mesh is closed:

```bash
python3 check_stl.py emss_ornament_base.stl emss_ornament_logo.stl
```

Each file should report `non-manifold directed edges: 0`. Also confirm that the printed plate size is what you expect.

## Printing in Bambu Studio

- **Two colors with an AMS:** import the base and logo STLs together and choose to load them as a single object with multiple parts. Assign the logo white and the base a dark color.
- **Two colors without an AMS:** print `emss_ornament_combined.stl` with a filament change at the first layer above 2.4 mm.
- **One color:** print `emss_ornament_combined.stl`.
- Print flat with the back face on the bed. No supports are needed.
