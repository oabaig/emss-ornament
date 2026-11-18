"""Generates STL files for an EMSS logo Christmas ornament.

Output:
  emss_ornament_base.stl  - backing plate with hanging loop
  emss_ornament_logo.stl  - raised EMSS letters that sit on top of the plate
  emss_ornament_combined.stl - both in one file for single-color printing
"""
import math
import re
import struct
import sys

# EMSS logo paths copied from the Maestro top bar SVG component (viewBox 0 0 97 18).
SVG_HEIGHT = 18.0
LOGO_PATHS = [
    "M0.203125 4.08244C0.203125 2.1893 1.73782 0.654602 3.63097 0.654602H17.3758C19.2689 0.654602 20.8036 2.1893 20.8036 4.08244H0.203125Z",
    "M26.6893 4.33295C26.6893 2.30129 28.3363 0.654297 30.368 0.654297V15.9542C30.368 16.97 29.5445 17.7935 28.5287 17.7935C27.5128 17.7935 26.6893 16.97 26.6893 15.9542V4.33295Z",
    "M34.0459 0.654297H37.7246V9.09849C37.7246 10.1143 36.9011 10.9378 35.8852 10.9378C34.8694 10.9378 34.0459 10.1143 34.0459 9.09849V0.654297Z",
    "M41.4069 0.654297C43.4385 0.654297 45.0855 2.30129 45.0855 4.33296V15.9542C45.0855 16.97 44.262 17.7935 43.2462 17.7935C42.2304 17.7935 41.4069 16.97 41.4069 15.9542V0.654297Z",
    "M0.203125 7.51001H20.8036V10.9379H0.203125V7.51001Z",
    "M0.203125 10.9397H3.881785V14.36754H0.203125Z",
    "M0.203125 14.3658H20.8036C20.8036 16.2589 19.2689 17.7936 17.3758 17.7936H3.63097C1.73783 17.7936 0.203125 16.2589 0.203125 14.3658Z",
    "M50.2355 4.08214C50.2355 2.18899 51.7702 0.654297 53.6633 0.654297H67.4081C69.3013 0.654297 70.836 2.18899 70.836 4.08214H50.2355Z",
    "M50.2355 7.51001H67.1573V10.9379H53.6633C51.7702 10.9379 50.2355 9.40315 50.2355 7.51001Z",
    "M67.1526 7.51001C69.1843 7.51001 70.8312 9.157 70.8312 11.1887V14.1149C70.8312 16.1465 69.1843 17.7935 67.1526 17.7935V7.51001Z",
    "M50.2355 14.3658H67.1573V17.7936H53.6633C51.7702 17.7936 50.2355 16.2589 50.2355 14.3658Z",
    "M76.3558 4.08214C76.3558 2.18899 77.8905 0.654297 79.7837 0.654297H93.5285C95.4216 0.654297 96.9563 2.18899 96.9563 4.08214H76.3558Z",
    "M76.3558 7.51001H93.2777V10.9379H79.7837C77.8905 10.9379 76.3558 9.40315 76.3558 7.51001Z",
    "M93.2727 7.51001C95.3044 7.51001 96.9514 9.157 96.9514 11.1887V14.1149C96.9514 16.1465 95.3044 17.7935 93.2727 17.7935V7.51001Z",
    "M76.3558 14.3658H93.2777V17.7936H79.7837C77.8905 17.7936 76.3558 16.2589 76.3558 14.3658Z",
]

# Dimensions in millimeters.
MILLIMETERS_PER_SVG_UNIT = 0.9
PLATE_MARGIN = 4.0
PLATE_CORNER_RADIUS = 4.0
PLATE_THICKNESS = 2.4
LOGO_RAISE_HEIGHT = 1.2
LOOP_OUTER_RADIUS = 4.5
LOOP_HOLE_RADIUS = 2.0
CURVE_SEGMENT_COUNT = 16
ARC_SEGMENT_COUNT = 48


def parse_svg_path_to_polygon(path_data):
    tokens = re.findall(r"[MCHVLZ]|-?\d*\.?\d+(?:e-?\d+)?", path_data)
    polygon_points = []
    current_x = current_y = 0.0
    token_index = 0
    command = None
    while token_index < len(tokens):
        token = tokens[token_index]
        if token.isalpha():
            command = token
            token_index += 1
            if command == "Z":
                continue
        numbers_needed = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6}[command]
        numbers = [float(value) for value in tokens[token_index:token_index + numbers_needed]]
        token_index += numbers_needed
        if command in ("M", "L"):
            current_x, current_y = numbers
            polygon_points.append((current_x, current_y))
        elif command == "H":
            current_x = numbers[0]
            polygon_points.append((current_x, current_y))
        elif command == "V":
            current_y = numbers[0]
            polygon_points.append((current_x, current_y))
        elif command == "C":
            start_x, start_y = current_x, current_y
            control1_x, control1_y, control2_x, control2_y, end_x, end_y = numbers
            for segment_index in range(1, CURVE_SEGMENT_COUNT + 1):
                t = segment_index / CURVE_SEGMENT_COUNT
                inverse_t = 1 - t
                point_x = (inverse_t ** 3 * start_x + 3 * inverse_t ** 2 * t * control1_x
                           + 3 * inverse_t * t ** 2 * control2_x + t ** 3 * end_x)
                point_y = (inverse_t ** 3 * start_y + 3 * inverse_t ** 2 * t * control1_y
                           + 3 * inverse_t * t ** 2 * control2_y + t ** 3 * end_y)
                polygon_points.append((point_x, point_y))
            current_x, current_y = end_x, end_y
    return polygon_points


def remove_duplicate_points(polygon_points):
    cleaned_points = []
    for point in polygon_points:
        if not cleaned_points or math.dist(point, cleaned_points[-1]) > 1e-6:
            cleaned_points.append(point)
    if len(cleaned_points) > 1 and math.dist(cleaned_points[0], cleaned_points[-1]) <= 1e-6:
        cleaned_points.pop()
    return cleaned_points


def signed_area(polygon_points):
    total = 0.0
    for index, (x1, y1) in enumerate(polygon_points):
        x2, y2 = polygon_points[(index + 1) % len(polygon_points)]
        total += x1 * y2 - x2 * y1
    return total / 2


def make_counterclockwise(polygon_points):
    if signed_area(polygon_points) < 0:
        return list(reversed(polygon_points))
    return polygon_points


def assert_convex(polygon_points):
    point_count = len(polygon_points)
    for index in range(point_count):
        ax, ay = polygon_points[index]
        bx, by = polygon_points[(index + 1) % point_count]
        cx, cy = polygon_points[(index + 2) % point_count]
        cross_product = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
        if cross_product < -1e-6:
            sys.exit("Polygon is not convex; fan triangulation would be wrong")


def extrude_convex_polygon(polygon_points, bottom_z, top_z):
    """Returns triangles for a closed prism over a counterclockwise convex polygon."""
    triangles = []
    point_count = len(polygon_points)
    for index in range(1, point_count - 1):
        a, b, c = polygon_points[0], polygon_points[index], polygon_points[index + 1]
        triangles.append(((*a, top_z), (*b, top_z), (*c, top_z)))
        triangles.append(((*a, bottom_z), (*c, bottom_z), (*b, bottom_z)))
    for index in range(point_count):
        a = polygon_points[index]
        b = polygon_points[(index + 1) % point_count]
        triangles.append(((*a, bottom_z), (*b, bottom_z), (*b, top_z)))
        triangles.append(((*a, bottom_z), (*b, top_z), (*a, top_z)))
    return triangles


def extrude_ring(center_x, center_y, outer_radius, inner_radius, bottom_z, top_z):
    triangles = []
    for index in range(ARC_SEGMENT_COUNT):
        angle1 = 2 * math.pi * index / ARC_SEGMENT_COUNT
        angle2 = 2 * math.pi * (index + 1) / ARC_SEGMENT_COUNT
        outer1 = (center_x + outer_radius * math.cos(angle1), center_y + outer_radius * math.sin(angle1))
        outer2 = (center_x + outer_radius * math.cos(angle2), center_y + outer_radius * math.sin(angle2))
        inner1 = (center_x + inner_radius * math.cos(angle1), center_y + inner_radius * math.sin(angle1))
        inner2 = (center_x + inner_radius * math.cos(angle2), center_y + inner_radius * math.sin(angle2))
        # Top and bottom faces
        triangles.append(((*inner1, top_z), (*outer1, top_z), (*outer2, top_z)))
        triangles.append(((*inner1, top_z), (*outer2, top_z), (*inner2, top_z)))
        triangles.append(((*inner1, bottom_z), (*outer2, bottom_z), (*outer1, bottom_z)))
        triangles.append(((*inner1, bottom_z), (*inner2, bottom_z), (*outer2, bottom_z)))
        # Outer wall faces outward, inner wall faces toward the hole center
        triangles.append(((*outer1, bottom_z), (*outer2, bottom_z), (*outer2, top_z)))
        triangles.append(((*outer1, bottom_z), (*outer2, top_z), (*outer1, top_z)))
        triangles.append(((*inner2, bottom_z), (*inner1, bottom_z), (*inner1, top_z)))
        triangles.append(((*inner2, bottom_z), (*inner1, top_z), (*inner2, top_z)))
    return triangles


def rounded_rectangle(min_x, min_y, max_x, max_y, corner_radius):
    corner_centers_and_start_angles = [
        ((max_x - corner_radius, min_y + corner_radius), -math.pi / 2),
        ((max_x - corner_radius, max_y - corner_radius), 0.0),
        ((min_x + corner_radius, max_y - corner_radius), math.pi / 2),
        ((min_x + corner_radius, min_y + corner_radius), math.pi),
    ]
    points_per_corner = ARC_SEGMENT_COUNT // 4
    polygon_points = []
    for (center_x, center_y), start_angle in corner_centers_and_start_angles:
        for step in range(points_per_corner + 1):
            angle = start_angle + (math.pi / 2) * step / points_per_corner
            polygon_points.append((center_x + corner_radius * math.cos(angle),
                                   center_y + corner_radius * math.sin(angle)))
    return remove_duplicate_points(polygon_points)


def write_binary_stl(file_path, triangles):
    with open(file_path, "wb") as stl_file:
        stl_file.write(b"EMSS ornament".ljust(80, b" "))
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

    logo_polygons = []
    for path_data in LOGO_PATHS:
        svg_points = remove_duplicate_points(parse_svg_path_to_polygon(path_data))
        # Flip Y because SVG Y points down and the print bed Y points up.
        millimeter_points = [(x * MILLIMETERS_PER_SVG_UNIT, (SVG_HEIGHT - y) * MILLIMETERS_PER_SVG_UNIT)
                             for x, y in svg_points]
        polygon = make_counterclockwise(millimeter_points)
        assert_convex(polygon)
        logo_polygons.append(polygon)

    all_x = [x for polygon in logo_polygons for x, _ in polygon]
    all_y = [y for polygon in logo_polygons for _, y in polygon]
    logo_min_x, logo_max_x = min(all_x), max(all_x)
    logo_min_y, logo_max_y = min(all_y), max(all_y)

    plate_min_x = logo_min_x - PLATE_MARGIN
    plate_max_x = logo_max_x + PLATE_MARGIN
    plate_min_y = logo_min_y - PLATE_MARGIN
    plate_max_y = logo_max_y + PLATE_MARGIN

    base_triangles = extrude_convex_polygon(
        rounded_rectangle(plate_min_x, plate_min_y, plate_max_x, plate_max_y, PLATE_CORNER_RADIUS),
        0.0, PLATE_THICKNESS)
    # The loop overlaps the plate edge so the slicer merges them into one solid.
    loop_center_x = (plate_min_x + plate_max_x) / 2
    loop_center_y = plate_max_y + LOOP_HOLE_RADIUS + 0.8
    base_triangles += extrude_ring(loop_center_x, loop_center_y, LOOP_OUTER_RADIUS, LOOP_HOLE_RADIUS,
                                   0.0, PLATE_THICKNESS)

    logo_triangles = []
    for polygon in logo_polygons:
        logo_triangles += extrude_convex_polygon(polygon, PLATE_THICKNESS,
                                                 PLATE_THICKNESS + LOGO_RAISE_HEIGHT)

    write_binary_stl(f"{output_directory}/emss_ornament_base.stl", base_triangles)
    write_binary_stl(f"{output_directory}/emss_ornament_logo.stl", logo_triangles)
    write_binary_stl(f"{output_directory}/emss_ornament_combined.stl", base_triangles + logo_triangles)

    total_height = loop_center_y + LOOP_OUTER_RADIUS - plate_min_y
    print(f"Plate: {plate_max_x - plate_min_x:.1f} x {plate_max_y - plate_min_y:.1f} mm, "
          f"overall height with loop {total_height:.1f} mm, "
          f"thickness {PLATE_THICKNESS + LOGO_RAISE_HEIGHT:.1f} mm")


if __name__ == "__main__":
    main()
