"""Generates STL files for a Talky Bot Christmas ornament from talky_the_bot.svg.

Requires the packages in requirements.txt.

Output:
  talkybot_ornament_base.stl     - outline plate with hanging loop (prints in the dark color)
  talkybot_ornament_white.stl    - the white parts of the bot, raised on top of the plate
  talkybot_ornament_combined.stl - both in one file for single-color printing
"""
import math
import struct
import sys
import xml.etree.ElementTree as ElementTree

import mapbox_earcut
import numpy
import shapely
import svgelements
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.geometry.polygon import orient

SVG_NAMESPACE = "{http://www.w3.org/2000/svg}"
SVG_FILE_NAME = "talky_the_bot.svg"

# Dimensions in millimeters.
MILLIMETERS_PER_SVG_UNIT = 0.4
OUTLINE_MARGIN = 2.0
PLATE_THICKNESS = 2.4
WHITE_RAISE_HEIGHT = 1.2
LOOP_OUTER_RADIUS = 4.5
LOOP_HOLE_RADIUS = 2.0
LOOP_OVERLAP = 1.5
# Distance between sampled points along curves, in SVG units.
CURVE_SAMPLE_SPACING = 0.5
# Painted areas smaller than this are dropped, in square millimeters.
MINIMUM_REGION_AREA = 0.2


def element_shape_to_geometry(element):
    """Converts a path or circle element into a filled shapely geometry in SVG units."""
    tag = element.tag.replace(SVG_NAMESPACE, "")
    if tag == "path":
        svg_shape = svgelements.Path(element.get("d"))
    elif tag == "circle":
        svg_shape = svgelements.Circle(cx=float(element.get("cx")), cy=float(element.get("cy")),
                                       r=float(element.get("r")))
    else:
        return None
    filled_geometry = Polygon()
    outlines = []
    for subpath in svgelements.Path(svg_shape).as_subpaths():
        subpath = svgelements.Path(subpath)
        sample_count = max(8, int(subpath.length() / CURVE_SAMPLE_SPACING))
        sampled_points = [subpath.point(index / sample_count) for index in range(sample_count + 1)]
        coordinates = [(point.x, point.y) for point in sampled_points]
        outlines.append(LineString(coordinates))
        if len(coordinates) >= 3:
            # Even-odd combination of subpaths, which matches nonzero for the holes in this logo.
            filled_geometry = filled_geometry.symmetric_difference(shapely.make_valid(Polygon(coordinates)))
    return filled_geometry, outlines


def collect_definitions(root):
    definitions = {}
    for element in root.iter():
        element_id = element.get("id")
        if element_id is not None:
            definitions[element_id] = element
    return definitions


def region_from_reference(reference, definitions):
    """Returns the union of the filled shapes inside a mask or clipPath referenced as url(#id)."""
    definition = definitions[reference[len("url(#"):-1]]
    region = Polygon()
    for child in definition.iter():
        converted = element_shape_to_geometry(child)
        if converted is not None:
            region = region.union(converted[0])
    return region


def paint_svg(svg_path):
    """Applies shapes in document order and returns the final visible region of each color."""
    root = ElementTree.parse(svg_path).getroot()
    definitions = collect_definitions(root)
    regions_by_color = {}

    def paint(geometry, color):
        if geometry.is_empty:
            return
        for other_color in regions_by_color:
            if other_color != color:
                regions_by_color[other_color] = regions_by_color[other_color].difference(geometry)
        regions_by_color[color] = regions_by_color.get(color, Polygon()).union(geometry)

    def visit(element, inherited_fill, limiting_region):
        tag = element.tag.replace(SVG_NAMESPACE, "")
        if tag in ("defs", "mask", "clipPath"):
            return
        fill = element.get("fill", inherited_fill)
        for attribute in ("mask", "clip-path"):
            reference = element.get(attribute)
            if reference is not None:
                region = region_from_reference(reference, definitions)
                limiting_region = region if limiting_region is None else limiting_region.intersection(region)
        converted = element_shape_to_geometry(element)
        if converted is not None:
            filled_geometry, outlines = converted
            if fill not in (None, "none"):
                if limiting_region is not None:
                    filled_geometry = filled_geometry.intersection(limiting_region)
                paint(filled_geometry, fill)
            stroke = element.get("stroke")
            if stroke not in (None, "none"):
                stroke_width = float(element.get("stroke-width", "1"))
                stroke_geometry = shapely.union_all([outline.buffer(stroke_width / 2) for outline in outlines])
                if limiting_region is not None:
                    stroke_geometry = stroke_geometry.intersection(limiting_region)
                paint(stroke_geometry, stroke)
        for child in element:
            visit(child, fill, limiting_region)

    visit(root, None, None)
    view_box = [float(value) for value in root.get("viewBox").split()]
    return regions_by_color, view_box[3]


def svg_units_to_millimeters(geometry, svg_height):
    # Flip Y because SVG Y points down and the print bed Y points up.
    return shapely.transform(geometry, lambda coordinates: numpy.column_stack((
        coordinates[:, 0] * MILLIMETERS_PER_SVG_UNIT,
        (svg_height - coordinates[:, 1]) * MILLIMETERS_PER_SVG_UNIT)))


def polygons_of(geometry):
    if isinstance(geometry, Polygon):
        return [geometry]
    return [part for part in getattr(geometry, "geoms", []) if isinstance(part, Polygon)]


def clean_geometry(geometry):
    cleaned_polygons = [polygon for polygon in polygons_of(shapely.make_valid(geometry).buffer(0))
                        if polygon.area >= MINIMUM_REGION_AREA]
    return MultiPolygon(cleaned_polygons).simplify(0.01)


def fill_holes(geometry):
    return shapely.union_all([Polygon(polygon.exterior) for polygon in polygons_of(geometry)])


def extrude_polygon(polygon, bottom_z, top_z):
    """Returns triangles for a closed prism over a polygon that may have holes."""
    polygon = orient(polygon, 1.0)
    rings = [list(polygon.exterior.coords)[:-1]] + [list(ring.coords)[:-1] for ring in polygon.interiors]
    flat_vertices = numpy.array([point for ring in rings for point in ring], dtype=numpy.float64)
    ring_end_indices = numpy.cumsum([len(ring) for ring in rings]).astype(numpy.uint32)
    triangle_indices = mapbox_earcut.triangulate_float64(flat_vertices, ring_end_indices).reshape(-1, 3)

    triangles = []
    for index_a, index_b, index_c in triangle_indices:
        a, b, c = (tuple(flat_vertices[index]) for index in (index_a, index_b, index_c))
        if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) < 0:
            b, c = c, b
        triangles.append(((*a, top_z), (*b, top_z), (*c, top_z)))
        triangles.append(((*a, bottom_z), (*c, bottom_z), (*b, bottom_z)))
    # The exterior is counterclockwise and holes are clockwise, so the same winding faces walls outward.
    for ring in rings:
        for index in range(len(ring)):
            a = ring[index]
            b = ring[(index + 1) % len(ring)]
            triangles.append(((*a, bottom_z), (*b, bottom_z), (*b, top_z)))
            triangles.append(((*a, bottom_z), (*b, top_z), (*a, top_z)))
    return triangles


def extrude_geometry(geometry, bottom_z, top_z):
    triangles = []
    for polygon in polygons_of(geometry):
        triangles += extrude_polygon(polygon, bottom_z, top_z)
    return triangles


def write_binary_stl(file_path, triangles):
    with open(file_path, "wb") as stl_file:
        stl_file.write(b"Talky Bot ornament".ljust(80, b" "))
        stl_file.write(struct.pack("<I", len(triangles)))
        for a, b, c in triangles:
            edge1 = [b[i] - a[i] for i in range(3)]
            edge2 = [c[i] - a[i] for i in range(3)]
            normal = [edge1[1] * edge2[2] - edge1[2] * edge2[1],
                      edge1[2] * edge2[0] - edge1[0] * edge2[2],
                      edge1[0] * edge2[1] - edge1[1] * edge2[0]]
            length = math.sqrt(sum(component ** 2 for component in normal)) or 1.0
            stl_file.write(struct.pack("<3f", *[component / length for component in normal]))
            for vertex in (a, b, c):
                stl_file.write(struct.pack("<3f", *vertex))
            stl_file.write(struct.pack("<H", 0))


def main():
    output_directory = sys.argv[1] if len(sys.argv) > 1 else "."

    regions_by_color, svg_height = paint_svg(f"{output_directory}/{SVG_FILE_NAME}")
    white_region = clean_geometry(svg_units_to_millimeters(regions_by_color["#fff"], svg_height))
    everything_painted = shapely.union_all([svg_units_to_millimeters(region, svg_height)
                                            for region in regions_by_color.values()])

    # The bot's pieces do not all touch, so the plate is an outline around them that holds them together.
    plate_region = fill_holes(everything_painted.buffer(OUTLINE_MARGIN))

    # Place the loop above the plate's center of mass so the ornament hangs straight.
    center_of_mass_x = plate_region.centroid.x
    vertical_line = LineString([(center_of_mass_x, -1000), (center_of_mass_x, 1000)])
    top_edge_y = vertical_line.intersection(plate_region).bounds[3]
    loop_center = Point(center_of_mass_x, top_edge_y + LOOP_OUTER_RADIUS - LOOP_OVERLAP)
    plate_region = plate_region.union(loop_center.buffer(LOOP_OUTER_RADIUS, 32))
    plate_region = plate_region.difference(loop_center.buffer(LOOP_HOLE_RADIUS, 32))
    plate_region = clean_geometry(plate_region)

    if len(polygons_of(plate_region)) != 1:
        sys.exit("Plate is not a single connected piece; increase OUTLINE_MARGIN")

    base_triangles = extrude_geometry(plate_region, 0.0, PLATE_THICKNESS)
    white_triangles = extrude_geometry(white_region, PLATE_THICKNESS, PLATE_THICKNESS + WHITE_RAISE_HEIGHT)

    write_binary_stl(f"{output_directory}/talkybot_ornament_base.stl", base_triangles)
    write_binary_stl(f"{output_directory}/talkybot_ornament_white.stl", white_triangles)
    write_binary_stl(f"{output_directory}/talkybot_ornament_combined.stl", base_triangles + white_triangles)

    min_x, min_y, max_x, max_y = plate_region.bounds
    print(f"Plate: {max_x - min_x:.1f} x {max_y - min_y:.1f} mm including loop, "
          f"thickness {PLATE_THICKNESS + WHITE_RAISE_HEIGHT:.1f} mm, "
          f"{len(polygons_of(white_region))} white pieces")


if __name__ == "__main__":
    main()
