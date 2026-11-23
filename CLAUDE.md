# CLAUDE.md

This repo generates 3D-printable Christmas ornaments of EMSS logos for a Bambu Lab P1S. There are two ornaments: the EMSS logo and the Talky Bot character.

## Files

- `check_stl.py` — checks that generated meshes are closed.
- `requirements.txt` — packages needed by `make_talkybot_ornament.py`.

EMSS logo:

- `make_ornament.py` — generates the EMSS STL files. Pure Python standard library, no dependencies.
- `emss_logo.svg` — the original EMSS logo as a standalone SVG, converted from the Maestro `EMSSLogo` component. All shapes are filled white, so it looks blank on a white background.
- `emss_ornament_base.stl` — backing plate with a hanging loop and a pocket under each letter.
- `emss_ornament_letter_1_E.stl`, `emss_ornament_letter_2_M.stl`, `emss_ornament_letter_3_S.stl`, `emss_ornament_letter_4_S.stl` — one file per letter, so each letter can be printed in its own color. Each letter sits in its pocket and stands above the plate. The two S files are identical apart from position, so they are interchangeable.
- `emss_ornament_combined.stl` — solid plate (no pockets) with raised letters, for single-color printing.

Talky Bot:

- `make_talkybot_ornament.py` — generates the Talky Bot STL files from `talky_the_bot.svg`.
- `talky_the_bot.svg` — copied unchanged from the talky-bot repo's default chat avatar (`apps/client/public/images/avatars/talky-the-bot.svg`). The talky-bot header uses a text wordmark, not an SVG logo, so this avatar is the closest thing to a logo.
- `talkybot_ornament_base.stl` — dark outline plate with a hanging loop.
- `talkybot_ornament_white.stl` — the bot's white parts, raised on top of the plate.
- `talkybot_ornament_combined.stl` — both in one file for single-color printing.

The STL files are committed so they can be opened in Bambu Studio on another machine without running the scripts.

## Regenerating

```bash
python3 make_ornament.py .

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python make_talkybot_ornament.py .
```

`.venv/` is gitignored. Rerun the script and commit the updated STL files after changing any dimension.

## How `make_ornament.py` works

- The logo path data in `LOGO_LETTERS` is copied by hand from `emss_logo.svg` (`viewBox 0 0 97 18`) and grouped by letter. The SVG's one `<rect>` is written as an equivalent path in the E, with its top edge moved by 0.0018 units to close a tiny gap in the SVG so that the bottom of the E prints as one piece. If the SVG changes, update `LOGO_LETTERS` to match. The script parses only absolute `M`, `L`, `H`, `V`, `C`, and `Z` commands.
- Cubic Bezier curves are flattened into line segments, and the Y axis is flipped because SVG Y points down.
- Each logo shape must be convex. `assert_convex` exits if one is not. Convexity is what lets `offset_convex_polygon` grow a shape outward to make its pocket, and it keeps the point-in-shape test simple. Shapes that are not convex, such as the NASA meatball, would need a different offset and containment test.
- `build_stepped_solid` builds every plate and letter mesh. It takes overlapping convex shapes, each with a top height, and returns one closed solid with a flat bottom and a stepped top. For example, the base is the plate at full thickness with the letter pockets at floor height. The solid is built from vertical slabs cut at every vertex and edge crossing, and coordinates are snapped to a 0.0001 mm grid so that shared vertices match exactly.
- Letters are placed at their in-pocket position (bottom at the pocket floor), so loading them as parts of the base lines them up.
- The hanging loop is a separate ring mesh that overlaps the plate edge. The slicer merges overlapping shells into one solid.

## How `make_talkybot_ornament.py` works

- It reads the SVG file directly. `svgelements` parses the path and circle geometry, and `shapely` handles the 2D region math. It supports only what this SVG uses: `path`, `circle`, `g`, `fill`, `stroke`, `stroke-width`, `mask`, and `clip-path`. It does not handle `transform`, `fill-rule`, or opacity.
- Shapes are painted in document order. Each shape removes its area from every other color's region, so the result is what is visible in the rendered image. Masks and clip paths are treated as the union of the shapes they contain. Strokes are made by buffering the outline by half the stroke width. Subpaths are combined with even-odd, which gives the same result as nonzero for this SVG.
- The bot's pieces do not all touch (the head and body are separate, for example), so the plate is the outline of everything painted, grown by `OUTLINE_MARGIN`, with holes filled. The black areas of the SVG are not printed as a separate part; they are the plate showing through.
- The hanging loop is unioned into the plate polygon above the plate's center of mass, so the ornament hangs straight. The script exits if the plate is not a single connected piece.
- Polygons with holes are triangulated with `mapbox_earcut` and extruded into prisms.

## Dimensions

All dimensions are constants at the top of each script, in millimeters.

`make_ornament.py`:

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

`make_talkybot_ornament.py`:

| Constant | Value | Meaning |
|---|---|---|
| `MILLIMETERS_PER_SVG_UNIT` | 0.4 | Overall scale. Plate is about 71 x 85 mm including the loop. Making it smaller thins the antenna, which is about 1 mm wide at this scale. |
| `OUTLINE_MARGIN` | 2.0 | Width of the dark border around the bot |
| `PLATE_THICKNESS` | 2.4 | Base plate thickness |
| `WHITE_RAISE_HEIGHT` | 1.2 | How far the white parts stand above the plate |
| `LOOP_OUTER_RADIUS` | 4.5 | Hanging loop outer radius |
| `LOOP_HOLE_RADIUS` | 2.0 | Hanging loop hole radius |
| `LOOP_OVERLAP` | 1.5 | How far the loop overlaps the top edge of the plate |

## Verifying changes

After regenerating, confirm that every mesh is closed:

```bash
python3 check_stl.py emss_ornament_base.stl emss_ornament_letter_*.stl emss_ornament_combined.stl
python3 check_stl.py talkybot_ornament_base.stl talkybot_ornament_white.stl
```

Each file should report `non-manifold directed edges: 0`. Also confirm that the printed plate size is what you expect.

## Printing in Bambu Studio

Print every part flat with its back face on the bed. No supports are needed.

EMSS logo:

- **Each letter a different color, printed separately:** print the base in one color. Then print each letter file in its own color; Bambu Studio drops each one to the bed on import. Press or glue each letter into its pocket. If the letters are too tight or too loose, change `POCKET_CLEARANCE` and reprint the base.
- **Each letter a different color, in one print with an AMS:** import the base and the four letter STLs together and choose to load them as a single object with multiple parts. Assign the base and each letter a filament.
- **Two colors without an AMS:** print `emss_ornament_combined.stl` with a filament change at the first layer above 2.4 mm.
- **One color:** print `emss_ornament_combined.stl`.

Talky Bot:

- **Two colors with an AMS:** import `talkybot_ornament_base.stl` and `talkybot_ornament_white.stl` together and choose to load them as a single object with multiple parts. Assign the white part white and the base a dark color.
- **Two colors without an AMS:** print `talkybot_ornament_combined.stl` with a filament change at the first layer above 2.4 mm.
- **One color:** print `talkybot_ornament_combined.stl`.
