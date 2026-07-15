import re
import math
import heapq
import pcbnew

FP_DIR = r"C:\Program Files\KiCad\10.0\share\kicad\footprints"

VIA_DIA_MM = 0.6
VIA_DRILL_MM = 0.3

# ---------------------------------------------------------------------------
# Netlist parsing -- the schematic's exported netlist.net is the single source
# of truth for connectivity (already ERC-clean and cross-checked net-by-net,
# see PROJECT_NOTES.md). The PCB generator never re-derives connectivity by
# hand; it only adds physical placement on top of what the netlist says.
# ---------------------------------------------------------------------------

def parse_netlist(path):
    text = open(path, encoding="utf-8").read()
    footprints = dict(re.findall(
        r'\(comp\s*\(ref "([^"]+)"\)\s*\(value "[^"]*"\)\s*\(footprint "([^"]*)"\)', text))
    pad_to_net = {}
    for m in re.finditer(r'\(net\s*\(code "\d+"\)\s*\(name "([^"]*)"\)(.*?)\n\t\t\)', text, re.S):
        name = m.group(1)
        for ref, pin in re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', m.group(2)):
            pad_to_net[(ref, pin)] = name
    return footprints, pad_to_net


class PcbGen:
    def __init__(self, netlist_path):
        self.board = pcbnew.CreateEmptyBoard()
        self.footprints, self.pad_to_net = parse_netlist(netlist_path)
        self._nets = {}
        self._placed = {}       # ref -> FOOTPRINT
        self._track_segs = []   # (p1_mm, p2_mm, net_name, half_width_mm, layer_id)
        # Copper layers the ROUTER may use, outer-first. 2-layer default; set
        # to [F_Cu, In1_Cu, In2_Cu, B_Cu] (e.g. from route_loaded.py, matching
        # board.GetCopperLayerCount()) for the 4-layer board. THT pads block/
        # connect on ALL of these; SMD pads only on their own face; through
        # vias join every layer in the list.
        self.LAYERS = [pcbnew.F_Cu, pcbnew.B_Cu]
        self._vias = []         # (x_mm, y_mm, net_name, radius_mm)
        self._outline_pts = None
        self._unrouted = []     # (net_name, p1_mm, p2_mm, reason)
        self._pads_geo_cache = None
        self._static_cells_cache = {}

    def _mm(self, x, y):
        return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))

    def get_net(self, name):
        if name not in self._nets:
            n = pcbnew.NETINFO_ITEM(self.board, name)
            self.board.Add(n)
            self._nets[name] = n
        return self._nets[name]

    def place(self, ref, x, y, rot=0, value=None, flip=False):
        # Looks up the footprint assigned to `ref` in the schematic netlist --
        # never pass a footprint string by hand, so PCB and schematic can never
        # silently drift apart on which physical part a ref represents.
        # `flip=True` moves a THT part to the bottom side (B.Cu) -- used for
        # the line-sensor LED/phototransistor pairs, which need to look
        # straight down at the floor from the underside of the chassis board
        # (confirmed against real micromouse builds, e.g. UKMARSBOT mounts its
        # line sensors on the underside of the main PCB -- see PROJECT_NOTES.md).
        fp_id = self.footprints[ref]
        lib, name = fp_id.split(":", 1)
        fp = pcbnew.FootprintLoad(f"{FP_DIR}\\{lib}.pretty", name)
        if fp is None:
            raise ValueError(f"footprint not found: {fp_id} (ref {ref})")
        fp.SetReference(ref)
        if value:
            fp.SetValue(value)
        fp.SetPosition(self._mm(x, y))
        fp.SetOrientation(pcbnew.EDA_ANGLE(rot, pcbnew.DEGREES_T))
        self.board.Add(fp)
        if flip:
            # Must flip AFTER adding to the board -- flipping a footprint not
            # yet owned by a board segfaults (found the hard way).
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        self._placed[ref] = fp
        for pad in fp.Pads():
            key = (ref, pad.GetNumber())
            if key in self.pad_to_net:
                pad.SetNet(self.get_net(self.pad_to_net[key]))
        return fp

    def unplaced_refs(self):
        return sorted(set(self.footprints) - set(self._placed),
                      key=lambda r: (re.sub(r'\d+', '', r), int(re.search(r'\d+', r).group())))

    def add_outline(self, points, width_mm=0.15):
        self._outline_pts = list(points)
        n = len(points)
        for i in range(n):
            seg = pcbnew.PCB_SHAPE(self.board, pcbnew.SHAPE_T_SEGMENT)
            seg.SetStart(self._mm(*points[i]))
            seg.SetEnd(self._mm(*points[(i + 1) % n]))
            seg.SetLayer(pcbnew.Edge_Cuts)
            seg.SetWidth(pcbnew.FromMM(width_mm))
            self.board.Add(seg)

    def add_mounting_hole(self, center, drill_mm):
        # Unplated round hole cut from the board -- a closed circle on
        # Edge.Cuts. Used for motor-bracket and castor screws (M2.5/M3).
        c = pcbnew.PCB_SHAPE(self.board, pcbnew.SHAPE_T_CIRCLE)
        c.SetCenter(self._mm(*center))
        c.SetStart(self._mm(*center))
        c.SetEnd(self._mm(center[0] + drill_mm / 2, center[1]))
        c.SetLayer(pcbnew.Edge_Cuts)
        c.SetWidth(pcbnew.FromMM(0.15))
        self.board.Add(c)

    def add_edge_slot(self, rect):
        # Rectangular cutout in the board (closed rectangle on Edge.Cuts) --
        # used to notch the side edges so the drive wheels can protrude.
        x1, y1, x2, y2 = rect
        pts = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        for i in range(4):
            seg = pcbnew.PCB_SHAPE(self.board, pcbnew.SHAPE_T_SEGMENT)
            seg.SetStart(self._mm(*pts[i]))
            seg.SetEnd(self._mm(*pts[(i + 1) % 4]))
            seg.SetLayer(pcbnew.Edge_Cuts)
            seg.SetWidth(pcbnew.FromMM(0.15))
            self.board.Add(seg)

    def add_keepout(self, rect, allow_tracks=False, allow_footprints=False):
        # Rule-area zone reserving a physical volume (e.g. a motor body).
        # allow_tracks=True forbids only footprints/pads/vias but PERMITS flat
        # traces to pass underneath -- correct for a motor body, which sits on
        # a bracket/standoffs above the board, so copper traces under it are
        # fine; forbidding tracks there just wastes routing space on a dense
        # board (and Freerouting routes through it anyway via the DSN). Only
        # the via/component exclusion is mechanically meaningful.
        x1, y1, x2, y2 = rect
        z = pcbnew.ZONE(self.board)
        z.SetLayer(pcbnew.F_Cu)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowTracks(not allow_tracks)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(True)
        z.SetDoNotAllowZoneFills(True)
        z.SetDoNotAllowFootprints(not allow_footprints)
        outline = z.Outline()
        outline.NewOutline()
        for x, y in [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]:
            outline.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
        self.board.Add(z)
        # Only record TRACK-blocking keepouts as router obstacles.
        if not allow_tracks:
            self._extra_keepouts = getattr(self, "_extra_keepouts", [])
            self._extra_keepouts.append((x1, y1, x2, y2))

    def add_zone(self, net_name, layer, points):
        zone = pcbnew.ZONE(self.board)
        zone.SetLayer(layer)
        outline = zone.Outline()
        outline.NewOutline()
        for x, y in points:
            outline.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
        zone.SetNetCode(self.get_net(net_name).GetNetCode())
        zone.SetZoneName(net_name)
        self.board.Add(zone)
        return zone

    def add_track(self, p1, p2, layer, net_name, width_mm=0.3):
        t = pcbnew.PCB_TRACK(self.board)
        t.SetStart(self._mm(*p1))
        t.SetEnd(self._mm(*p2))
        t.SetLayer(layer)
        t.SetWidth(pcbnew.FromMM(width_mm))
        t.SetNet(self.get_net(net_name))
        self.board.Add(t)
        return t

    def add_via(self, p, net_name, size_mm=VIA_DIA_MM, drill_mm=VIA_DRILL_MM):
        v = pcbnew.PCB_VIA(self.board)
        v.SetPosition(self._mm(*p))
        v.SetWidth(pcbnew.FromMM(size_mm))
        v.SetDrill(pcbnew.FromMM(drill_mm))
        v.SetNet(self.get_net(net_name))
        self.board.Add(v)
        self._vias.append((p[0], p[1], net_name, size_mm / 2))
        return v

    # ------------------------------------------------------------------
    # Placement sanity checks
    # ------------------------------------------------------------------

    def _courtyard_bbox_mm(self, fp):
        courtyard_layer = "B.Courtyard" if fp.GetLayerName() == "B.Cu" else "F.Courtyard"
        boxes = [gi.GetBoundingBox() for gi in fp.GraphicalItems() if gi.GetLayerName() == courtyard_layer]
        if not boxes:
            boxes = [fp.GetBoundingBox()]
        x1 = min(pcbnew.ToMM(b.GetLeft()) for b in boxes)
        y1 = min(pcbnew.ToMM(b.GetTop()) for b in boxes)
        x2 = max(pcbnew.ToMM(b.GetRight()) for b in boxes)
        y2 = max(pcbnew.ToMM(b.GetBottom()) for b in boxes)
        return (x1, y1, x2, y2)

    def check_overlaps(self, margin_mm=0.3):
        # Same-side courtyard bbox overlap check -- fast placement iteration
        # without a full kicad-cli DRC round trip. Top vs bottom parts can't
        # collide (separated by the board substrate).
        boxes = {ref: self._courtyard_bbox_mm(fp) for ref, fp in self._placed.items()}
        layers = {ref: fp.GetLayerName() for ref, fp in self._placed.items()}
        refs = sorted(boxes)
        problems = []
        for i, r1 in enumerate(refs):
            x1a, y1a, x2a, y2a = boxes[r1]
            for r2 in refs[i + 1:]:
                if layers[r1] != layers[r2]:
                    continue
                x1b, y1b, x2b, y2b = boxes[r2]
                if (x1a - margin_mm < x2b and x2a + margin_mm > x1b and
                        y1a - margin_mm < y2b and y2a + margin_mm > y1b):
                    problems.append((r1, r2))
        return problems

    def pad_pos_mm(self, ref, pad_num):
        fp = self._placed[ref]
        for pad in fp.Pads():
            if pad.GetNumber() == pad_num:
                p = pad.GetPosition()
                return (pcbnew.ToMM(p.x), pcbnew.ToMM(p.y))
        raise ValueError(f"pad {pad_num} not found on {ref}")

    def save(self, path):
        self.board.Save(path)

    # ------------------------------------------------------------------
    # Geometry primitives (all in mm, all pure-python -- no pcbnew calls in
    # the hot path)
    # ------------------------------------------------------------------

    @staticmethod
    def _seg_point_dist(p1, p2, p):
        x1, y1 = p1; x2, y2 = p2; x0, y0 = p
        dx, dy = x2 - x1, y2 - y1
        l2 = dx * dx + dy * dy
        if l2 == 0:
            return math.hypot(x0 - x1, y0 - y1)
        t = max(0.0, min(1.0, ((x0 - x1) * dx + (y0 - y1) * dy) / l2))
        return math.hypot(x0 - (x1 + t * dx), y0 - (y1 + t * dy))

    @staticmethod
    def _seg_intersect(a1, a2, b1, b2):
        def ccw(A, B, C):
            return (C[1] - A[1]) * (B[0] - A[0]) - (B[1] - A[1]) * (C[0] - A[0])
        d1, d2 = ccw(b1, b2, a1), ccw(b1, b2, a2)
        d3, d4 = ccw(a1, a2, b1), ccw(a1, a2, b2)
        return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 != 0 and d2 != 0

    def _seg_seg_dist(self, a1, a2, b1, b2):
        if self._seg_intersect(a1, a2, b1, b2):
            return 0.0
        return min(
            self._seg_point_dist(a1, a2, b1), self._seg_point_dist(a1, a2, b2),
            self._seg_point_dist(b1, b2, a1), self._seg_point_dist(b1, b2, a2),
        )

    def _seg_rect_dist(self, p1, p2, rect):
        x1, y1, x2, y2 = rect
        def inside(p):
            return x1 <= p[0] <= x2 and y1 <= p[1] <= y2
        if inside(p1) or inside(p2):
            return 0.0
        corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        best = float("inf")
        for i in range(4):
            e1, e2 = corners[i], corners[(i + 1) % 4]
            if self._seg_intersect(p1, p2, e1, e2):
                return 0.0
            best = min(best, self._seg_seg_dist(p1, p2, e1, e2))
        return best

    @staticmethod
    def _pt_rect_dist(p, rect):
        x1, y1, x2, y2 = rect
        dx = max(x1 - p[0], 0.0, p[0] - x2)
        dy = max(y1 - p[1], 0.0, p[1] - y2)
        return math.hypot(dx, dy)

    def _outline_ok(self, p, margin):
        # Inside the board outline polygon AND at least `margin` from every
        # edge (matches kicad's copper-to-edge clearance constraint).
        pts = self._outline_pts
        n = len(pts)
        x0, y0 = p
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = pts[i]; xj, yj = pts[j]
            if (yi > y0) != (yj > y0) and x0 < (xj - xi) * (y0 - yi) / (yj - yi) + xi:
                inside = not inside
            j = i
        if not inside:
            return False
        for i in range(n):
            if self._seg_point_dist(pts[i], pts[(i + 1) % n], p) < margin:
                return False
        return True

    # ------------------------------------------------------------------
    # Obstacle model
    # ------------------------------------------------------------------

    def _pads_geo(self):
        # One entry per pad: absolute bounding rectangle (exact for the 0/90/
        # 270-degree rotations this board uses), net, and REAL copper layers
        # (an SMD pad on a flipped footprint exists only on B.Cu -- treating
        # every pad as front-side was the root cause of the first router
        # attempt's shorts and dangling tracks, confirmed via kicad-cli DRC).
        if self._pads_geo_cache is not None:
            return self._pads_geo_cache
        out = []
        for ref, fp in self._placed.items():
            for pad in fp.Pads():
                bb = pad.GetBoundingBox()
                rect = (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
                        pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))
                cx = (rect[0] + rect[2]) / 2
                cy = (rect[1] + rect[3]) / 2
                has_hole = pad.GetDrillSize().x > 0
                on_f = pad.IsOnLayer(pcbnew.F_Cu) or has_hole
                on_b = pad.IsOnLayer(pcbnew.B_Cu) or has_hole
                if has_hole:
                    lyrs = frozenset(self.LAYERS)      # THT pierces every layer
                else:
                    lyrs = frozenset(l for l, f in ((pcbnew.F_Cu, on_f), (pcbnew.B_Cu, on_b)) if f)
                out.append({
                    "ref": ref, "num": pad.GetNumber(), "net": pad.GetNetname(),
                    "rect": rect, "cx": cx, "cy": cy,
                    "on_f": on_f, "on_b": on_b, "hole": has_hole, "layers": lyrs,
                })
        self._pads_geo_cache = out
        return out

    def _keepout_rects(self):
        # Rule areas baked into footprints (the ESP32 module's antenna
        # keep-clear zone is one, with no-tracks/no-vias set). Treated as
        # both-layer no-go for tracks AND vias -- conservative and correct
        # for an RF keepout.
        rects = list(getattr(self, "_extra_keepouts", []))  # board-level (motor bodies)
        for ref, fp in self._placed.items():
            for z in fp.Zones():
                if z.GetIsRuleArea() and (z.GetDoNotAllowTracks() or z.GetDoNotAllowVias()):
                    bb = z.GetBoundingBox()
                    rects.append((pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
                                  pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())))
        # Board-level rule-area zones (motor keep-outs added via add_keepout,
        # and any the user drew) -- only the ones that forbid TRACKS.
        for z in self.board.Zones():
            if z.GetIsRuleArea() and z.GetDoNotAllowTracks():
                bb = z.GetBoundingBox()
                rects.append((pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
                              pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())))
        return rects

    def _cells_in_rect(self, rect, grow, grid, into):
        x1, y1, x2, y2 = rect
        x1 -= grow; y1 -= grow; x2 += grow; y2 += grow
        for cx in range(int(math.floor(x1 / grid)), int(math.ceil(x2 / grid)) + 1):
            px = cx * grid
            if px < x1 or px > x2:
                continue
            for cy in range(int(math.floor(y1 / grid)), int(math.ceil(y2 / grid)) + 1):
                py = cy * grid
                if y1 <= py <= y2:
                    into.add((cx, cy))

    def _cells_along_seg(self, p1, p2, grow, grid, into):
        dist = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        steps = max(1, int(dist / (grid / 2)))
        rc = int(math.ceil(grow / grid)) + 1
        for i in range(steps + 1):
            t = i / steps
            x = p1[0] + (p2[0] - p1[0]) * t
            y = p1[1] + (p2[1] - p1[1]) * t
            cx0, cy0 = round(x / grid), round(y / grid)
            for dx in range(-rc, rc + 1):
                for dy in range(-rc, rc + 1):
                    if math.hypot(cx0 * grid + dx * grid - x, cy0 * grid + dy * grid - y) <= grow:
                        into.add((cx0 + dx, cy0 + dy))

    def _static_cells(self, grid, edge_margin=0.7):
        # Cells outside the board (with copper-edge margin) plus keepout
        # areas -- identical for every net, computed once per grid size.
        key = (grid, edge_margin)
        if key in self._static_cells_cache:
            return self._static_cells_cache[key]
        blocked = set()
        xs = [p[0] for p in self._outline_pts]
        ys = [p[1] for p in self._outline_pts]
        for cx in range(int(math.floor(min(xs) / grid)) - 2, int(math.ceil(max(xs) / grid)) + 3):
            for cy in range(int(math.floor(min(ys) / grid)) - 2, int(math.ceil(max(ys) / grid)) + 3):
                if not self._outline_ok((cx * grid, cy * grid), edge_margin):
                    blocked.add((cx, cy))
        for rect in self._keepout_rects():
            self._cells_in_rect(rect, 0.3, grid, blocked)
        self._static_cells_cache[key] = blocked
        return blocked

    def _net_obstacles(self, net_name, half_w, clearance, grid):
        # Per-net blocked-cell sets in two tiers per copper layer:
        #   hard -- another net's actual copper (pad/track/via grown by our
        #           half-width + a whisker): NEVER traversable, not even in
        #           the fine-pitch escape zone near a route's endpoints.
        #           Without this tier, the escape allowance let A* propose a
        #           path straight across the neighboring pad of an 0805
        #           resistor (both pads inside the 1.8mm escape radius),
        #           which then always failed verification -- an unroutable
        #           loop found in the smoke test.
        #   soft -- comfort clearance + grid inflation (0.75*grid guards the
        #           diagonal corner-cutting failure mode found in the first
        #           router attempt): traversable only near endpoints, where
        #           fine-pitch pads (SSOP 0.65mm / ESP32 0.85mm) legitimately
        #           have overlapping clearance disks; the continuous-geometry
        #           verification afterwards is the actual judge for those.
        inflate = grid * 0.75
        static = self._static_cells(grid)
        hard = {L: set() for L in self.LAYERS}
        soft = {L: set(static) for L in self.LAYERS}
        via_hard = set(static)
        via_soft = set(static)
        via_r = VIA_DIA_MM / 2
        for pad in self._pads_geo():
            if pad["net"] == net_name:
                continue
            hard_t = half_w + 0.05
            grow_t = half_w + clearance + inflate
            hard_v = via_r + 0.05
            grow_v = via_r + clearance + inflate
            for layer in self.LAYERS:
                if layer in pad["layers"]:
                    self._cells_in_rect(pad["rect"], hard_t, grid, hard[layer])
                    self._cells_in_rect(pad["rect"], grow_t, grid, soft[layer])
            self._cells_in_rect(pad["rect"], hard_v, grid, via_hard)
            self._cells_in_rect(pad["rect"], grow_v, grid, via_soft)
        for (p1, p2, net, t_half_w, layer) in self._track_segs:
            if net == net_name:
                continue
            self._cells_along_seg(p1, p2, t_half_w + half_w + 0.05, grid, hard[layer])
            self._cells_along_seg(p1, p2, t_half_w + half_w + clearance + inflate, grid, soft[layer])
            self._cells_along_seg(p1, p2, t_half_w + via_r + 0.05, grid, via_hard)
            self._cells_along_seg(p1, p2, t_half_w + via_r + clearance + inflate, grid, via_soft)
        for (vx, vy, net, vr) in self._vias:
            if net == net_name:
                continue
            rect = (vx, vy, vx, vy)
            for layer in self.LAYERS:                  # through via blocks every layer
                self._cells_in_rect(rect, vr + half_w + 0.05, grid, hard[layer])
                self._cells_in_rect(rect, vr + half_w + clearance + inflate, grid, soft[layer])
            self._cells_in_rect(rect, vr + via_r + 0.05, grid, via_hard)
            self._cells_in_rect(rect, vr + via_r + clearance + inflate, grid, via_soft)
        return hard, soft, via_hard, via_soft

    # ------------------------------------------------------------------
    # A* router over a 2-layer grid
    # ------------------------------------------------------------------

    _DIRS8 = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    _DIRS4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    def _route_edge(self, start, s_layers, goal, g_layers, hard, soft, via_hard, via_soft,
                     grid, diag=True, max_expansions=80000, escape_mm=1.8, via_cost=4.0,
                     half_w_hint=0.15, net_hint=""):
        # Returns (segments [(p1, p2, layer)], via_points [p]) or None.
        # Fine-pitch escape: a pad in the middle of an SSOP/mux/ESP32 row has
        # its neighbors' inflated clearance disks overlapping its own center,
        # which would make the route unstartable -- so soft-blocked cells
        # within `escape_mm` of either endpoint stay traversable, and the
        # continuous-geometry verification afterwards (true clearances, no
        # grid inflation) is what actually guarantees the escape is legal.
        # Hard-blocked cells (another net's real copper) are never traversable.
        sc = (round(start[0] / grid), round(start[1] / grid))
        gc = (round(goal[0] / grid), round(goal[1] / grid))
        LAYERS = self.LAYERS
        # Alternating H/V preference by layer index (0=F horizontal, 1 vertical,
        # ...): classic multilayer discipline, keeps the euclidean h admissible.
        horiz_pref = {L: (i % 2 == 0) for i, L in enumerate(LAYERS)}

        def cell_ok(c, layer):
            if c in hard[layer]:
                return False
            if c not in soft[layer]:
                return True
            px, py = c[0] * grid, c[1] * grid
            return (math.hypot(px - start[0], py - start[1]) < escape_mm or
                    math.hypot(px - goal[0], py - goal[1]) < escape_mm)

        def via_ok(c):
            return c not in via_hard and c not in via_soft

        dirs = self._DIRS8 if diag else self._DIRS4
        counter = 0
        open_heap = []
        gscore = {}
        came = {}
        for L in s_layers:
            if cell_ok(sc, L):
                st = (sc, L)
                gscore[st] = 0.0
                heapq.heappush(open_heap, (0.0, counter, st))
                counter += 1
        visited = set()
        expansions = 0
        goal_state = None
        while open_heap and expansions < max_expansions:
            _, _, cur = heapq.heappop(open_heap)
            if cur in visited:
                continue
            visited.add(cur)
            expansions += 1
            c, L = cur
            if c == gc and L in g_layers:
                goal_state = cur
                break
            base_g = gscore[cur]
            for ddx, ddy in dirs:
                nc = (c[0] + ddx, c[1] + ddy)
                if not cell_ok(nc, L):
                    continue
                nst = (nc, L)
                # Mild H/V layer discipline: alternating layers prefer
                # horizontal vs vertical runs. Keeps long runs on different
                # layers from fencing each other into unroutable pockets.
                # Multiplier > 1 keeps the euclidean heuristic admissible.
                if horiz_pref[L]:
                    step = math.hypot(ddx * 1.0, ddy * 1.25)
                else:
                    step = math.hypot(ddx * 1.25, ddy * 1.0)
                ng = base_g + step * grid
                if nst not in gscore or ng < gscore[nst] - 1e-9:
                    gscore[nst] = ng
                    came[nst] = cur
                    h = math.hypot(nc[0] - gc[0], nc[1] - gc[1]) * grid
                    heapq.heappush(open_heap, (ng + h, counter, nst))
                    counter += 1
            if via_ok(c):
                for oL in LAYERS:
                    if oL == L or not cell_ok(c, oL):
                        continue
                    nst = (c, oL)
                    ng = base_g + via_cost
                    if nst not in gscore or ng < gscore[nst] - 1e-9:
                        gscore[nst] = ng
                        came[nst] = cur
                        h = math.hypot(c[0] - gc[0], c[1] - gc[1]) * grid
                        heapq.heappush(open_heap, (ng + h, counter, nst))
                        counter += 1
        if goal_state is None:
            return None

        # Reconstruct: list of (point, layer)
        states = [goal_state]
        node = goal_state
        while node in came:
            node = came[node]
            states.append(node)
        states.reverse()
        pts = [((c[0] * grid, c[1] * grid), L) for (c, L) in states]
        # Attach exact pad centers at the ends (same layer as the end states).
        full = [(start, pts[0][1])] + pts + [(goal, pts[-1][1])]

        # Split into same-layer runs (vias at the joints), then STRING-PULL
        # each run into professional 45-degree geometry: greedily replace the
        # staircase grid path with the canonical two-segment connection (one
        # diagonal + one straight -- standard pro-layout idiom), longest jump
        # first, each candidate verified against true clearances before
        # acceptance. Falls back to the raw grid step when nothing longer
        # verifies, so the result is never worse than the A* path.
        runs = []          # [(points, layer)]
        via_points = []
        cur_pts = [full[0][0]]
        cur_layer = full[0][1]
        for (pt, L) in full[1:]:
            if L != cur_layer:
                via_points.append(cur_pts[-1])
                runs.append((cur_pts, cur_layer))
                cur_pts = [cur_pts[-1]]
                cur_layer = L
            if pt != cur_pts[-1]:
                cur_pts.append(pt)
        runs.append((cur_pts, cur_layer))

        segments = []
        for pts_run, L in runs:
            segments.extend(self._string_pull(pts_run, L, half_w_hint, net_hint))
        return segments, via_points

    @staticmethod
    def _canon2(p, q):
        # Canonical 45-degree connection p->q: one diagonal for min(|dx|,|dy|),
        # then one axis-aligned straight. Returns 1 or 2 segments.
        dx, dy = q[0] - p[0], q[1] - p[1]
        adx, ady = abs(dx), abs(dy)
        if adx < 1e-9 or ady < 1e-9 or abs(adx - ady) < 1e-9:
            return [(p, q)]
        m = min(adx, ady)
        mid = (p[0] + (m if dx > 0 else -m), p[1] + (m if dy > 0 else -m))
        return [(p, mid), (mid, q)]

    def _string_pull(self, pts, layer, half_w, net_name):
        # Greedy longest-jump smoothing over one same-layer polyline.
        out = []
        i = 0
        n = len(pts)
        while i < n - 1:
            done = False
            j = n - 1
            while j > i + 1:
                cand = [(a, b, layer) for (a, b) in self._canon2(pts[i], pts[j])]
                if self._verify_geo(cand, [], net_name, half_w) is None:
                    out.extend(cand)
                    i = j
                    done = True
                    break
                j -= 1
            if not done:
                a, b = pts[i], pts[i + 1]
                if a != b:
                    out.append((a, b, layer))
                i += 1
        # merge collinear neighbours produced by the greedy pass
        merged = []
        for seg in out:
            if merged:
                (a1, b1, L1) = merged[-1]
                (a2, b2, L2) = seg
                if L1 == L2 and b1 == a2:
                    v1 = (b1[0] - a1[0], b1[1] - a1[1])
                    v2 = (b2[0] - a2[0], b2[1] - a2[1])
                    if abs(v1[0] * v2[1] - v1[1] * v2[0]) < 1e-9 and (v1[0] * v2[0] + v1[1] * v2[1]) > 0:
                        merged[-1] = (a1, b2, L1)
                        continue
            merged.append(seg)
        return merged

    def _verify_geo(self, segments, via_points, net_name, half_w, verify_clr=0.16,
                     edge_margin=0.7):
        # verify_clr sits just above the 0.15mm netclass clearance this board
        # registers in its design settings (see setup_design_rules) -- and is
        # comfortably within standard fab capability (JLCPCB min 0.127) and is
        # what makes fine-pitch escapes (SSOP-24 at 0.65mm pitch) legal.
        # Continuous-geometry re-check of a candidate route with TRUE
        # clearances (no grid, no inflation) -- the grid search is the
        # planner, this is the judge. Anything that fails here is rejected
        # outright rather than committed-and-caught-later by kicad DRC.
        pads = self._pads_geo()
        keepouts = self._keepout_rects()
        via_r = VIA_DIA_MM / 2
        for (p1, p2, layer) in segments:
            if not (self._outline_ok(p1, edge_margin - 0.1) and self._outline_ok(p2, edge_margin - 0.1)):
                return f"segment endpoint outside board margin near {p1}"
            for k in keepouts:
                if self._seg_rect_dist(p1, p2, k) < 0.1:
                    return f"segment enters keepout near {p1}"
            for pad in pads:
                if pad["net"] == net_name:
                    continue
                if layer not in pad["layers"]:
                    continue
                if self._seg_rect_dist(p1, p2, pad["rect"]) < half_w + verify_clr:
                    return f"segment too close to {pad['ref']}.{pad['num']} ({pad['net']})"
            for (t1, t2, net, t_half, t_layer) in self._track_segs:
                if net == net_name or t_layer != layer:
                    continue
                if self._seg_seg_dist(p1, p2, t1, t2) < half_w + t_half + verify_clr:
                    return f"segment too close to track of {net}"
            for (vx, vy, net, vr) in self._vias:
                if net == net_name:
                    continue
                if self._seg_point_dist(p1, p2, (vx, vy)) < half_w + vr + verify_clr:
                    return f"segment too close to via of {net}"
        for v in via_points:
            if not self._outline_ok(v, edge_margin - 0.1):
                return f"via outside board margin at {v}"
            for k in keepouts:
                if self._pt_rect_dist(v, k) < 0.1:
                    return f"via in keepout at {v}"
            for pad in pads:
                if pad["net"] == net_name:
                    continue
                if self._pt_rect_dist(v, pad["rect"]) < via_r + verify_clr:
                    return f"via too close to {pad['ref']}.{pad['num']}"
            for (t1, t2, net, t_half, t_layer) in self._track_segs:
                if net == net_name:
                    continue
                if self._seg_point_dist(t1, t2, v) < via_r + t_half + verify_clr:
                    return f"via too close to track of {net}"
            for (vx, vy, net, vr) in self._vias:
                if net == net_name:
                    continue
                if math.hypot(vx - v[0], vy - v[1]) < via_r + vr + verify_clr:
                    return f"via too close to via of {net}"
        return None

    def setup_design_rules(self):
        # Align the board's own DRC rules with what the router actually
        # enforces, so kicad-cli DRC and the router agree on legality:
        # 0.127mm clearance / 0.2mm min track / 0.6-0.3 vias / 0.2mm
        # hole-to-hole. All within routine fab capability (JLCPCB standard:
        # 0.127mm clearance, 0.127mm track, 0.3mm drill).
        bds = self.board.GetDesignSettings()
        bds.m_MinClearance = pcbnew.FromMM(0.127)
        bds.m_TrackMinWidth = pcbnew.FromMM(0.2)
        bds.m_ViasMinSize = pcbnew.FromMM(0.5)
        # 0.2 (not 0.3): the WROOM-1 and TPS63001 footprints carry 0.2-0.25mm
        # in-pad thermal vias, and GCT's USB-C pattern has tight NPTH spacing
        # -- all manufacturer land patterns, all standard fab capability.
        bds.m_MinThroughDrill = pcbnew.FromMM(0.2)
        try:
            # Copper-to-board-edge clearance. Default 0.5mm; Freerouting routes
            # nearer the interior wheel-slot cutout edges, so 0.3mm (still
            # fab-safe) avoids false edge-clearance errors around the slots.
            bds.m_CopperEdgeClearance = pcbnew.FromMM(0.3)
        except Exception:
            pass
        try:
            bds.m_HoleToHoleMin = pcbnew.FromMM(0.2)
        except Exception:
            pass
        try:
            bds.m_HoleClearance = pcbnew.FromMM(0.15)  # GCT USB-C NPTH-to-pad
        except Exception:
            pass
        # The DEFAULT NETCLASS clearance is what DRC actually enforces per-net
        # (it defaults to 0.2mm). Freerouting routes near ~0.15mm, so unless we
        # lower the netclass clearance to match, DRC flags every trace pair
        # (this caused 212 false clearance errors once). 0.15mm is within
        # routine fab capability (JLCPCB min 0.127mm). v10 API:
        # DesignSettings.m_NetSettings.GetDefaultNetclass().SetClearance().
        for setter in (
            lambda: bds.m_NetSettings.GetDefaultNetclass().SetClearance(pcbnew.FromMM(0.15)),
            lambda: [nc.SetClearance(pcbnew.FromMM(0.15))
                     for nc in self.board.GetAllNetClasses().values()],
        ):
            try:
                setter()
            except Exception:
                pass

    def route_net(self, net_name, width_mm=0.3, clearance_mm=0.18, grid_mm=0.5,
                   max_expansions=80000, min_edge_mm=None, max_edge_mm=None):
        # min/max_edge_mm filter which MST edges this call routes (the MST
        # itself is deterministic, so complementary filtered calls cover the
        # exact same edge set). Used for the micro-bridge pre-pass: doubled
        # package pins (TB6612 pairs its outputs on adjacent pins) need a
        # <1mm bridge that MUST hug the pad column -- if any other net routes
        # through that area first, the bridge becomes unroutable. Routing all
        # sub-2mm edges across ALL nets before anything else guarantees the
        # space directly at the pads is still free for them.
        pads = [p for p in self._pads_geo() if p["net"] == net_name]
        if len(pads) < 2:
            return True
        pts = [(p["cx"], p["cy"]) for p in pads]
        pad_layers = [list(p["layers"]) for p in pads]

        # Prim's MST over pad centers
        n = len(pts)
        in_tree = [False] * n
        in_tree[0] = True
        edges = []
        for _ in range(n - 1):
            best = None
            for i in range(n):
                if not in_tree[i]:
                    continue
                for j in range(n):
                    if in_tree[j]:
                        continue
                    d = math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1])
                    if best is None or d < best[0]:
                        best = (d, i, j)
            _, i, j = best
            in_tree[j] = True
            edges.append((i, j))
        def edge_len(e):
            return math.hypot(pts[e[0]][0] - pts[e[1]][0], pts[e[0]][1] - pts[e[1]][1])
        edges.sort(key=edge_len)
        if min_edge_mm is not None:
            edges = [e for e in edges if edge_len(e) >= min_edge_mm]
        if max_edge_mm is not None:
            edges = [e for e in edges if edge_len(e) < max_edge_mm]
        if not edges:
            return True

        half_w = width_mm / 2
        hard, soft, via_hard, via_soft = self._net_obstacles(net_name, half_w, clearance_mm, grid_mm)
        all_ok = True
        for (i, j) in edges:
            committed = False
            reason = "no path found"
            # Retry ladder: shrinking the escape radius forces the path to
            # respect the full soft-clearance zone progressively closer to
            # the endpoints -- a verify failure at one rung (path shaved an
            # obstacle inside the escape zone) usually passes at the next.
            for diag, escape in ((True, 1.8), (True, 1.0), (True, 0.6),
                                  (False, 1.8), (False, 1.0), (False, 0.6)):
                res = self._route_edge(pts[i], pad_layers[i], pts[j], pad_layers[j],
                                        hard, soft, via_hard, via_soft, grid_mm, diag=diag,
                                        escape_mm=escape, max_expansions=max_expansions,
                                        half_w_hint=half_w, net_hint=net_name)
                if res is None:
                    continue
                segments, via_points = res
                fail = self._verify_geo(segments, via_points, net_name, half_w)
                if fail is not None:
                    reason = fail
                    continue
                for (p1, p2, layer) in segments:
                    self.add_track(p1, p2, layer, net_name, width_mm)
                    self._track_segs.append((p1, p2, net_name, half_w, layer))
                for v in via_points:
                    self._commit_via(v, net_name, width_mm)
                # Newly committed copper is an obstacle for the REST of this
                # net's edges too only if a different net -- same net may
                # cross itself freely, so no blocked-set update needed here.
                committed = True
                break
            if not committed:
                all_ok = False
                self._unrouted.append((net_name, pts[i], pts[j], reason))
        return all_ok

    def _commit_via(self, v, net_name, width_mm):
        # Same-net vias closer than 0.55mm violate the 0.2mm hole-to-hole rule
        # (0.3mm drills). Exact duplicates are skipped outright; a NEAR
        # duplicate (0.1-0.85mm) is replaced by short stitch tracks on BOTH
        # layers to the existing via -- simply skipping it (the first
        # implementation) orphaned the other layer's segments and left
        # dangling tracks, caught by DRC.
        half_w = width_mm / 2
        nearest, nd = None, 1e9
        for (vx, vy, net, vr) in self._vias:
            if net != net_name:
                continue
            d = math.hypot(vx - v[0], vy - v[1])
            if d < nd:
                nearest, nd = (vx, vy), d
        if nd < 0.1:
            return
        if nd < 0.85:
            stitch = [(v, nearest, pcbnew.F_Cu), (v, nearest, pcbnew.B_Cu)]
            if self._verify_geo(stitch, [], net_name, half_w) is None:
                for (q1, q2, layer) in stitch:
                    self.add_track(q1, q2, layer, net_name, width_mm)
                    self._track_segs.append((q1, q2, net_name, half_w, layer))
                return
            # Stitch not legal here -- fall through and place the via anyway
            # (a hole-to-hole warning beats broken connectivity).
        self.add_via(v, net_name)

    def retry_edge(self, net_name, p1, p2, width_mm=0.3, clearance_mm=0.18,
                    grid_mm=0.5, max_expansions=250000):
        # Second-chance pass for a single failed MST edge, run after every
        # other net has been committed (obstacles rebuilt fresh) with a much
        # larger search budget. Returns True if the edge routed.
        pads = self._pads_geo()
        def layers_at(p):
            for pad in pads:
                if pad["net"] == net_name and abs(pad["cx"] - p[0]) < 0.01 and abs(pad["cy"] - p[1]) < 0.01:
                    return list(pad["layers"])
            return list(self.LAYERS)
        half_w = width_mm / 2
        hard, soft, via_hard, via_soft = self._net_obstacles(net_name, half_w, clearance_mm, grid_mm)
        for diag, escape in ((True, 1.8), (True, 1.0), (True, 0.6),
                              (False, 1.8), (False, 1.0), (False, 0.6)):
            res = self._route_edge(p1, layers_at(p1), p2, layers_at(p2),
                                    hard, soft, via_hard, via_soft, grid_mm, diag=diag,
                                    escape_mm=escape, max_expansions=max_expansions,
                                    half_w_hint=half_w, net_hint=net_name)
            if res is None:
                continue
            segments, via_points = res
            if self._verify_geo(segments, via_points, net_name, half_w) is not None:
                continue
            for (q1, q2, layer) in segments:
                self.add_track(q1, q2, layer, net_name, width_mm)
                self._track_segs.append((q1, q2, net_name, half_w, layer))
            for v in via_points:
                self._commit_via(v, net_name, width_mm)
            return True
        return False
