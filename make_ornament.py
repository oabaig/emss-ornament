"""Generates STL files for an EMSS logo Christmas ornament.

Output:
  emss_ornament_base.stl        - backing plate with a pocket for each letter and a hanging loop
  emss_ornament_letter_1_E.stl  - the letters, one file each so each can be a different color.
  emss_ornament_letter_2_M.stl    Each letter sits in its pocket and stands above the plate.
  emss_ornament_letter_3_S.stl
  emss_ornament_letter_4_S.stl
  emss_ornament_combined.stl    - solid plate with raised letters for single-color printing
"""
import bisect
import math
import re
import struct
import sys

# EMSS logo paths copied from emss_logo.svg (viewBox 0 0 97 18), grouped by letter.
# The SVG's one <rect> is written as an equivalent path in the E. Its top edge is
# moved from y=10.9397 to 10.9379 to close a 0.0018-unit gap to the E's middle
# bar, so the bottom of the E prints as one piece.
SVG_HEIGHT = 18.0
LOGO_LETTERS = [
    ("E", [
        "M0.203125 4.08244C0.203125 2.1893 1.73782 0.654602 3.63097 0.654602H17.3758C19.2689 0.654602 20.8036 2.1893 20.8036 4.08244H0.203125Z",
        "M0.203125 7.51001H20.8036V10.9379H0.203125V7.51001Z",
        "M0.203125 10.9379H3.881785V14.36754H0.203125Z",
        "M0.203125 14.3658H20.8036C20.8036 16.2589 19.2689 17.7936 17.3758 17.7936H3.63097C1.73783 17.7936 0.203125 16.2589 0.203125 14.3658Z",
    ]),
    ("M", [
        "M26.6893 4.33295C26.6893 2.30129 28.3363 0.654297 30.368 0.654297V15.9542C30.368 16.97 29.5445 17.7935 28.5287 17.7935C27.5128 17.7935 26.6893 16.97 26.6893 15.9542V4.33295Z",
        "M34.0459 0.654297H37.7246V9.09849C37.7246 10.1143 36.9011 10.9378 35.8852 10.9378C34.8694 10.9378 34.0459 10.1143 34.0459 9.09849V0.654297Z",
        "M41.4069 0.654297C43.4385 0.654297 45.0855 2.30129 45.0855 4.33296V15.9542C45.0855 16.97 44.262 17.7935 43.2462 17.7935C42.2304 17.7935 41.4069 16.97 41.4069 15.9542V0.654297Z",
    ]),
    ("S", [
        "M50.2355 4.08214C50.2355 2.18899 51.7702 0.654297 53.6633 0.654297H67.4081C69.3013 0.654297 70.836 2.18899 70.836 4.08214H50.2355Z",
        "M50.2355 7.51001H67.1573V10.9379H53.6633C51.7702 10.9379 50.2355 9.40315 50.2355 7.51001Z",
        "M67.1526 7.51001C69.1843 7.51001 70.8312 9.157 70.8312 11.1887V14.1149C70.8312 16.1465 69.1843 17.7935 67.1526 17.7935V7.51001Z",
        "M50.2355 14.3658H67.1573V17.7936H53.6633C51.7702 17.7936 50.2355 16.2589 50.2355 14.3658Z",
    ]),
    ("S", [
        "M76.3558 4.08214C76.3558 2.18899 77.8905 0.654297 79.7837 0.654297H93.5285C95.4216 0.654297 96.9563 2.18899 96.9563 4.08214H76.3558Z",
        "M76.3558 7.51001H93.2777V10.9379H79.7837C77.8905 10.9379 76.3558 9.40315 76.3558 7.51001Z",
        "M93.2727 7.51001C95.3044 7.51001 96.9514 9.157 96.9514 11.1887V14.1149C96.9514 16.1465 95.3044 17.7935 93.2727 17.7935V7.51001Z",
        "M76.3558 14.3658H93.2777V17.7936H79.7837C77.8905 17.7936 76.3558 16.2589 76.3558 14.3658Z",
    ]),
]

# Dimensions in millimeters.
MILLIMETERS_PER_SVG_UNIT = 0.9
PLATE_MARGIN = 4.0
PLATE_CORNER_RADIUS = 4.0
PLATE_THICKNESS = 2.4
POCKET_DEPTH = 1.2
POCKET_CLEARANCE = 0.15
LOGO_RAISE_HEIGHT = 1.2
LOOP_OUTER_RADIUS = 4.5
LOOP_HOLE_RADIUS = 2.0
CURVE_SEGMENT_COUNT = 16
ARC_SEGMENT_COUNT = 48
# Stepped solids snap every coordinate to this grid so that a vertex shared by
# several faces has exactly the same value in each of them.
GRID_SIZE = 0.0001


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
            sys.exit("Polygon is not convex; offsetting and containment tests would be wrong")


def offset_convex_polygon(polygon_points, distance):
    """Moves every edge of a counterclockwise convex polygon outward by distance."""
    point_count = len(polygon_points)
    shifted_edges = []
    for index in range(point_count):
        start_x, start_y = polygon_points[index]
        end_x, end_y = polygon_points[(index + 1) % point_count]
        direction_x, direction_y = end_x - start_x, end_y - start_y
        length = math.hypot(direction_x, direction_y)
        # The outward normal of a counterclockwise polygon's edge points to the edge's right.
        normal_x, normal_y = direction_y / length, -direction_x / length
        shifted_edges.append(((start_x + normal_x * distance, start_y + normal_y * distance),
                              (direction_x, direction_y)))
    offset_points = []
    for index in range(point_count):
        (incoming_x, incoming_y), (incoming_dx, incoming_dy) = shifted_edges[index - 1]
        (outgoing_x, outgoing_y), (outgoing_dx, outgoing_dy) = shifted_edges[index]
        cross_product = incoming_dx * outgoing_dy - incoming_dy * outgoing_dx
        if abs(cross_product) < 1e-9 * math.hypot(incoming_dx, incoming_dy) * math.hypot(outgoing_dx, outgoing_dy):
            # The two edges are in line, so the shifted vertex is where the outgoing edge starts.
            offset_points.append((outgoing_x, outgoing_y))
            continue
        t = ((outgoing_x - incoming_x) * outgoing_dy - (outgoing_y - incoming_y) * outgoing_dx) / cross_product
        offset_points.append((incoming_x + incoming_dx * t, incoming_y + incoming_dy * t))
    return offset_points


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


def snap(value):
    return round(value / GRID_SIZE) * GRID_SIZE


def snap_polygon(polygon_points):
    snapped_points = []
    for x, y in polygon_points:
        point = (snap(x), snap(y))
        if not snapped_points or point != snapped_points[-1]:
            snapped_points.append(point)
    if len(snapped_points) > 1 and snapped_points[0] == snapped_points[-1]:
        snapped_points.pop()
    return snapped_points


def polygon_contains(polygon_points, x, y):
    """True if (x, y) is strictly inside a counterclockwise convex polygon."""
    for index, (start_x, start_y) in enumerate(polygon_points):
        end_x, end_y = polygon_points[(index + 1) % len(polygon_points)]
        if (end_x - start_x) * (y - start_y) - (end_y - start_y) * (x - start_x) <= 0:
            return False
    return True


def edge_crossing_xs(edges):
    """Returns the x coordinate of every point where two edges cross each other."""
    crossing_xs = []
    for index, ((ax, ay), (bx, by)) in enumerate(edges):
        for (cx, cy), (dx, dy) in edges[index + 1:]:
            if cx >= bx or ax >= dx or max(cy, dy) < min(ay, by) or min(cy, dy) > max(ay, by):
                continue
            denominator = (bx - ax) * (dy - cy) - (by - ay) * (dx - cx)
            if denominator == 0:
                continue
            t = ((cx - ax) * (dy - cy) - (cy - ay) * (dx - cx)) / denominator
            u = ((cx - ax) * (by - ay) - (cy - ay) * (bx - ax)) / denominator
            if 0 < t < 1 and 0 < u < 1:
                crossing_xs.append(ax + t * (bx - ax))
    return crossing_xs


def simplify_profile(boundaries, heights):
    """Drops zero-width intervals and boundaries that separate equal heights."""
    kept_boundaries = []
    kept_heights = [heights[0]]
    for boundary, height_above in zip(boundaries, heights[1:]):
        if kept_boundaries and kept_boundaries[-1] == boundary:
            kept_boundaries.pop()
            kept_heights.pop()
        if kept_heights[-1] != height_above:
            kept_boundaries.append(boundary)
            kept_heights.append(height_above)
    return kept_boundaries, kept_heights


def zip_chains(left_chain, right_chain, up_axis):
    """Triangulates the strip between two chains of points that both run upward.

    The triangles wind counterclockwise as seen with the left chain on the left.
    """
    triangles = []
    left_index = right_index = 0
    while left_index < len(left_chain) - 1 or right_index < len(right_chain) - 1:
        advance_right = left_index == len(left_chain) - 1 or (
            right_index < len(right_chain) - 1
            and right_chain[right_index + 1][up_axis] <= left_chain[left_index + 1][up_axis])
        if advance_right:
            triangles.append((left_chain[left_index], right_chain[right_index], right_chain[right_index + 1]))
            right_index += 1
        else:
            triangles.append((left_chain[left_index], right_chain[right_index], left_chain[left_index + 1]))
            left_index += 1
    return triangles


def build_stepped_solid(regions, bottom_z):
    """Returns triangles for a closed solid with a flat bottom and a stepped top.

    regions is a list of (counterclockwise convex polygons, top_z). Above each
    point of the XY plane the solid runs from bottom_z up to the top_z of the
    last region that has a polygon containing the point. Points outside every
    polygon are empty. Polygons may overlap.

    The plane is cut into vertical slabs at every polygon vertex and at every
    point where two polygon edges cross. Inside a slab the edges are straight,
    do not cross, and split the slab into a stack of trapezoids that each have
    one height, so the solid is a set of trapezoid columns. Faces are emitted
    wherever a column meets empty space or a column of a different height.
    Every face along a slab line includes every vertex on that line, so the
    mesh has no T-junctions.
    """
    snapped_regions = []
    edges = []
    slab_xs = set()
    for polygons, top_z in regions:
        snapped_polygons = []
        for polygon in polygons:
            polygon = snap_polygon(polygon)
            xs = [x for x, _ in polygon]
            ys = [y for _, y in polygon]
            snapped_polygons.append((polygon, (min(xs), min(ys), max(xs), max(ys))))
            for index, start in enumerate(polygon):
                end = polygon[(index + 1) % len(polygon)]
                slab_xs.add(start[0])
                if start[0] != end[0]:
                    edges.append((start, end) if start[0] < end[0] else (end, start))
        snapped_regions.append((snapped_polygons, top_z))
    slab_xs.update(snap(x) for x in edge_crossing_xs(edges))
    slab_xs = sorted(slab_xs)

    def height_at(x, y):
        for polygons, top_z in reversed(snapped_regions):
            for polygon, (min_x, min_y, max_x, max_y) in polygons:
                if min_x < x < max_x and min_y < y < max_y and polygon_contains(polygon, x, y):
                    return top_z
        return None

    # For each slab, the edges crossing it bottom to top as (y at left side, y at right side),
    # and the height of the solid between each pair of neighboring edges.
    profiles = []
    for left_x, right_x in zip(slab_xs, slab_xs[1:]):
        segments = set()
        for (start_x, start_y), (end_x, end_y) in edges:
            if start_x <= left_x and right_x <= end_x:
                slope = (end_y - start_y) / (end_x - start_x)
                segments.add((snap(start_y + slope * (left_x - start_x)),
                              snap(start_y + slope * (right_x - start_x))))
        if not segments:
            profiles.append(([], [None]))
            continue
        segments = sorted(segments, key=lambda segment: (segment[0] + segment[1], segment[0]))
        middle_x = (left_x + right_x) / 2
        heights = [None]
        for lower, upper in zip(segments, segments[1:]):
            heights.append(height_at(middle_x, (lower[0] + lower[1] + upper[0] + upper[1]) / 4))
        heights.append(None)
        # Snapping can leave neighboring edges crossed by a grid step or two at a slab side.
        boundaries = []
        for left_y, right_y in segments:
            if boundaries:
                left_y = max(left_y, boundaries[-1][0])
                right_y = max(right_y, boundaries[-1][1])
            boundaries.append((left_y, right_y))
        profiles.append(simplify_profile(boundaries, heights))

    # Every y where an edge meets each slab line, from the slabs on both sides.
    line_ys = []
    for line_index in range(len(slab_xs)):
        ys = set()
        if line_index > 0:
            ys.update(right_y for _, right_y in profiles[line_index - 1][0])
        if line_index < len(profiles):
            ys.update(left_y for left_y, _ in profiles[line_index][0])
        line_ys.append(sorted(ys))

    z_levels = sorted({bottom_z} | {top_z for _, top_z in regions})

    def level(height):
        return bottom_z if height is None else height

    def column(x, y, low_z, high_z):
        return [(x, y, z) for z in z_levels if low_z <= z <= high_z]

    def chain(line_index, low_y, high_y, z):
        ys = line_ys[line_index]
        first = bisect.bisect_left(ys, low_y)
        last = bisect.bisect_right(ys, high_y)
        return [(slab_xs[line_index], y, z) for y in ys[first:last]]

    triangles = []
    for slab_index, (boundaries, heights) in enumerate(profiles):
        left_x, right_x = slab_xs[slab_index], slab_xs[slab_index + 1]
        run_start = None
        for interval_index in range(1, len(heights)):
            top_z = heights[interval_index]
            if top_z is not None:
                lower, upper = boundaries[interval_index - 1], boundaries[interval_index]
                triangles += zip_chains(chain(slab_index, lower[0], upper[0], top_z),
                                        chain(slab_index + 1, lower[1], upper[1], top_z), 1)
                if run_start is None:
                    run_start = interval_index - 1
            elif run_start is not None:
                # One bottom face spans each run of neighboring solid intervals.
                lower, upper = boundaries[run_start], boundaries[interval_index - 1]
                bottom_triangles = zip_chains(chain(slab_index, lower[0], upper[0], bottom_z),
                                              chain(slab_index + 1, lower[1], upper[1], bottom_z), 1)
                triangles += [(a, c, b) for a, b, c in bottom_triangles]
                run_start = None
        for boundary_index, (left_y, right_y) in enumerate(boundaries):
            below, above = level(heights[boundary_index]), level(heights[boundary_index + 1])
            low_z, high_z = min(below, above), max(below, above)
            left_column = column(left_x, left_y, low_z, high_z)
            right_column = column(right_x, right_y, low_z, high_z)
            # A wall faces the lower of the two columns it separates.
            if above > below:
                triangles += zip_chains(left_column, right_column, 2)
            else:
                triangles += zip_chains(right_column, left_column, 2)

    for line_index, x in enumerate(slab_xs):
        left_boundaries, left_heights = profiles[line_index - 1] if line_index > 0 else ([], [None])
        right_boundaries, right_heights = profiles[line_index] if line_index < len(profiles) else ([], [None])
        left_ends = [right_y for _, right_y in left_boundaries]
        right_ends = [left_y for left_y, _ in right_boundaries]
        ys = line_ys[line_index]
        for low_y, high_y in zip(ys, ys[1:]):
            left_level = level(left_heights[bisect.bisect_right(left_ends, low_y)])
            right_level = level(right_heights[bisect.bisect_right(right_ends, low_y)])
            if left_level == right_level:
                continue
            low_z, high_z = min(left_level, right_level), max(left_level, right_level)
            lower_column = column(x, low_y, low_z, high_z)
            upper_column = column(x, high_y, low_z, high_z)
            if left_level > right_level:
                triangles += zip_chains(lower_column, upper_column, 2)
            else:
                triangles += zip_chains(upper_column, lower_column, 2)
    return triangles


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

    letters = []
    for letter_name, letter_paths in LOGO_LETTERS:
        letter_polygons = []
        for path_data in letter_paths:
            svg_points = remove_duplicate_points(parse_svg_path_to_polygon(path_data))
            # Flip Y because SVG Y points down and the print bed Y points up.
            millimeter_points = [(x * MILLIMETERS_PER_SVG_UNIT, (SVG_HEIGHT - y) * MILLIMETERS_PER_SVG_UNIT)
                                 for x, y in svg_points]
            polygon = make_counterclockwise(millimeter_points)
            assert_convex(polygon)
            letter_polygons.append(polygon)
        letters.append((letter_name, letter_polygons))
    all_letter_polygons = [polygon for _, letter_polygons in letters for polygon in letter_polygons]

    all_x = [x for polygon in all_letter_polygons for x, _ in polygon]
    all_y = [y for polygon in all_letter_polygons for _, y in polygon]
    plate_min_x = min(all_x) - PLATE_MARGIN
    plate_max_x = max(all_x) + PLATE_MARGIN
    plate_min_y = min(all_y) - PLATE_MARGIN
    plate_max_y = max(all_y) + PLATE_MARGIN
    plate_outline = rounded_rectangle(plate_min_x, plate_min_y, plate_max_x, plate_max_y, PLATE_CORNER_RADIUS)

    # The loop overlaps the plate edge so the slicer merges them into one solid.
    loop_center_x = (plate_min_x + plate_max_x) / 2
    loop_center_y = plate_max_y + LOOP_HOLE_RADIUS + 0.8
    loop_triangles = extrude_ring(loop_center_x, loop_center_y, LOOP_OUTER_RADIUS, LOOP_HOLE_RADIUS,
                                  0.0, PLATE_THICKNESS)

    pocket_floor_z = PLATE_THICKNESS - POCKET_DEPTH
    letter_top_z = PLATE_THICKNESS + LOGO_RAISE_HEIGHT
    pocket_polygons = [offset_convex_polygon(polygon, POCKET_CLEARANCE) for polygon in all_letter_polygons]

    base_triangles = build_stepped_solid(
        [([plate_outline], PLATE_THICKNESS), (pocket_polygons, pocket_floor_z)], 0.0)
    write_binary_stl(f"{output_directory}/emss_ornament_base.stl", base_triangles + loop_triangles)

    # Letters are placed where they sit in their pockets. Bambu Studio keeps that position
    # when they are loaded as parts of the base, and drops them to the bed when loaded alone.
    for letter_number, (letter_name, letter_polygons) in enumerate(letters, start=1):
        letter_triangles = build_stepped_solid([(letter_polygons, letter_top_z)], pocket_floor_z)
        write_binary_stl(f"{output_directory}/emss_ornament_letter_{letter_number}_{letter_name}.stl",
                         letter_triangles)

    combined_triangles = build_stepped_solid(
        [([plate_outline], PLATE_THICKNESS), (all_letter_polygons, letter_top_z)], 0.0)
    write_binary_stl(f"{output_directory}/emss_ornament_combined.stl", combined_triangles + loop_triangles)

    total_height = loop_center_y + LOOP_OUTER_RADIUS - plate_min_y
    print(f"Plate: {plate_max_x - plate_min_x:.1f} x {plate_max_y - plate_min_y:.1f} mm, "
          f"overall height with loop {total_height:.1f} mm, "
          f"thickness {letter_top_z:.1f} mm")
    print(f"Pockets: {POCKET_DEPTH:.1f} mm deep, {POCKET_CLEARANCE:.2f} mm clearance per side; "
          f"letters: {letter_top_z - pocket_floor_z:.1f} mm thick")


if __name__ == "__main__":
    main()
