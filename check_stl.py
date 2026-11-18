import struct, sys, collections
for path in sys.argv[1:]:
    data = open(path, "rb").read()
    count = struct.unpack("<I", data[80:84])[0]
    edges = collections.Counter()
    for i in range(count):
        values = struct.unpack("<12f", data[84 + i * 50: 84 + i * 50 + 48])
        vertices = [tuple(round(v, 4) for v in values[3 + j * 3: 6 + j * 3]) for j in range(3)]
        for j in range(3):
            edges[(vertices[j], vertices[(j + 1) % 3])] += 1
    bad = sum(1 for (a, b), n in edges.items() if n != 1 or edges.get((b, a), 0) != 1)
    print(path, count, "triangles, non-manifold directed edges:", bad)
