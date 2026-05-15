from __future__ import annotations

import math

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GObject, Gtk

from ..services.graph_service import GraphNode, GraphService


class GraphView(Gtk.Box):
    """
    Full-canvas graph view.  Documents are nodes; cross-references are edges.

    Signals
    -------
    navigate-document(doc_id: int)
        Emitted when the user single-clicks a node.
    """

    __gtype_name__ = "CodexGraphView"

    __gsignals__ = {
        "navigate-document": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    _MIN_R = 20.0
    _MAX_R = 50.0

    def __init__(self, graph_service: GraphService, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self._gs = graph_service

        self._nodes: list[GraphNode] = []
        self._edges: list[tuple[int, int]] = []
        self._pos: dict[int, list[float]] = {}  # node_id → [world_x, world_y]

        # View transform
        self._scale = 1.0
        self._offset_x = 0.0
        self._offset_y = 0.0

        # Interaction state
        self._hover_id: int | None = None
        self._drag_node_id: int | None = None
        self._drag_node_origin: tuple[float, float] | None = None
        self._pan_origin: tuple[float, float] | None = None

        self._build()
        self._load()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self._da = Gtk.DrawingArea()
        self._da.set_vexpand(True)
        self._da.set_hexpand(True)
        self._da.add_css_class("view")
        self._da.set_draw_func(self._on_draw)
        self.append(self._da)

        # Zoom via scroll wheel
        scroll = Gtk.EventControllerScroll(
            flags=Gtk.EventControllerScrollFlags.VERTICAL
        )
        scroll.connect("scroll", self._on_scroll)
        self._da.add_controller(scroll)

        # Drag: node drag or canvas pan; tiny drag = click
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self._da.add_controller(drag)

        # Hover: tooltip + highlight
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        self._da.add_controller(motion)

    # ── Data ─────────────────────────────────────────────────────────────────

    def _load(self) -> None:
        self._nodes, self._edges = self._gs.get_graph_data()
        self._init_positions()
        self._run_layout()
        self._da.queue_draw()

    def reload(self) -> None:
        """Reload graph data from the database and redraw."""
        self._load()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _init_positions(self) -> None:
        n = len(self._nodes)
        if n == 0:
            return
        radius = max(150.0, 60.0 * math.sqrt(n))
        for i, node in enumerate(self._nodes):
            angle = 2 * math.pi * i / n
            self._pos[node.id] = [radius * math.cos(angle), radius * math.sin(angle)]

    def _run_layout(self, iterations: int = 200) -> None:
        """Fruchterman-Reingold force-directed layout."""
        if len(self._nodes) < 2:
            return

        area = 600.0
        k = area / math.sqrt(len(self._nodes))
        ids = [n.id for n in self._nodes]

        for step in range(iterations):
            disp: dict[int, list[float]] = {nid: [0.0, 0.0] for nid in ids}

            # Repulsion between every pair
            for i, u in enumerate(ids):
                for v in ids[i + 1 :]:
                    dx = self._pos[u][0] - self._pos[v][0]
                    dy = self._pos[u][1] - self._pos[v][1]
                    dist = math.sqrt(dx * dx + dy * dy) or 0.01
                    f = k * k / dist
                    disp[u][0] += dx / dist * f
                    disp[u][1] += dy / dist * f
                    disp[v][0] -= dx / dist * f
                    disp[v][1] -= dy / dist * f

            # Attraction along edges
            for src, tgt in self._edges:
                if src not in self._pos or tgt not in self._pos:
                    continue
                dx = self._pos[src][0] - self._pos[tgt][0]
                dy = self._pos[src][1] - self._pos[tgt][1]
                dist = math.sqrt(dx * dx + dy * dy) or 0.01
                f = dist * dist / k
                disp[src][0] -= dx / dist * f
                disp[src][1] -= dy / dist * f
                disp[tgt][0] += dx / dist * f
                disp[tgt][1] += dy / dist * f

            # Apply with temperature cooling
            temp = area / 10.0 * (1.0 - step / iterations)
            for nid in ids:
                dx, dy = disp[nid]
                dist = math.sqrt(dx * dx + dy * dy) or 0.01
                self._pos[nid][0] += dx / dist * min(dist, temp)
                self._pos[nid][1] += dy / dist * min(dist, temp)

        # Center graph at origin
        if ids:
            cx = sum(self._pos[nid][0] for nid in ids) / len(ids)
            cy = sum(self._pos[nid][1] for nid in ids) / len(ids)
            for nid in ids:
                self._pos[nid][0] -= cx
                self._pos[nid][1] -= cy

    # ── Coordinate helpers ────────────────────────────────────────────────────

    def _to_screen(self, wx: float, wy: float, w: int, h: int) -> tuple[float, float]:
        return (
            wx * self._scale + self._offset_x + w / 2,
            wy * self._scale + self._offset_y + h / 2,
        )

    def _to_world(self, sx: float, sy: float, w: int, h: int) -> tuple[float, float]:
        return (
            (sx - self._offset_x - w / 2) / self._scale,
            (sy - self._offset_y - h / 2) / self._scale,
        )

    def _node_radius(self, node: GraphNode) -> float:
        return min(self._MAX_R, max(self._MIN_R, self._MIN_R + node.degree * 5.0))

    def _hit_test(self, sx: float, sy: float, w: int, h: int) -> int | None:
        for node in self._nodes:
            pos = self._pos.get(node.id)
            if not pos:
                continue
            nx, ny = self._to_screen(pos[0], pos[1], w, h)
            r = self._node_radius(node) * self._scale
            if (sx - nx) ** 2 + (sy - ny) ** 2 <= r * r:
                return node.id
        return None

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _on_draw(self, _da, cr, width: int, height: int) -> None:
        is_dark = Adw.StyleManager.get_default().get_dark()

        # ── Edges ────────────────────────────────────────────────────────────
        cr.set_line_width(1.0)
        cr.set_source_rgba(0.5, 0.5, 0.5, 0.35)
        for src_id, tgt_id in self._edges:
            if src_id not in self._pos or tgt_id not in self._pos:
                continue
            sx, sy = self._to_screen(*self._pos[src_id], width, height)
            tx, ty = self._to_screen(*self._pos[tgt_id], width, height)
            cr.move_to(sx, sy)
            cr.line_to(tx, ty)
            cr.stroke()

        # ── Nodes ────────────────────────────────────────────────────────────
        for node in self._nodes:
            pos = self._pos.get(node.id)
            if not pos:
                continue
            sx, sy = self._to_screen(pos[0], pos[1], width, height)
            r = self._node_radius(node) * self._scale
            is_hovered = node.id == self._hover_id

            # Circle fill
            cr.arc(sx, sy, r, 0, 2 * math.pi)
            alpha = 1.0 if is_hovered else 0.80
            cr.set_source_rgba(*node.color, alpha)
            cr.fill_preserve()

            # Circle border
            if is_hovered:
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.6)
                cr.set_line_width(2.5)
            else:
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.25)
                cr.set_line_width(1.2)
            cr.stroke()

            # Label (truncated to 18 chars)
            label = node.name[:18] + "…" if len(node.name) > 18 else node.name
            font_size = max(8.0, min(11.0, r * 0.38))
            cr.set_font_size(font_size)
            ext = cr.text_extents(label)
            text_color = (1.0, 1.0, 1.0) if is_dark else (0.1, 0.1, 0.1)
            cr.set_source_rgba(*text_color, 0.95)
            cr.move_to(sx - ext.width / 2, sy + ext.height / 2)
            cr.show_text(label)

        # ── Tooltip for hovered node ─────────────────────────────────────────
        if self._hover_id is not None:
            node = next((n for n in self._nodes if n.id == self._hover_id), None)
            if node and node.id in self._pos:
                sx, sy = self._to_screen(*self._pos[node.id], width, height)
                tip_y = sy + self._node_radius(node) * self._scale + 10
                self._draw_tooltip(
                    cr,
                    sx,
                    tip_y,
                    f"{node.name}\n{node.book_name} › {node.chapter_name}",
                    is_dark,
                )

    def _draw_tooltip(self, cr, cx: float, y: float, text: str, dark: bool) -> None:
        lines = text.split("\n")
        pad = 6
        line_h = 13
        cr.set_font_size(10)
        max_w = max(cr.text_extents(ln).width for ln in lines) + pad * 2
        total_h = len(lines) * line_h + pad * 2

        bg = (0.08, 0.08, 0.08, 0.88) if dark else (0.95, 0.95, 0.95, 0.92)
        fg = (0.92, 0.92, 0.92) if dark else (0.1, 0.1, 0.1)

        cr.set_source_rgba(*bg)
        cr.rectangle(cx - max_w / 2, y, max_w, total_h)
        cr.fill()

        cr.set_source_rgba(*fg, 1.0)
        for i, line in enumerate(lines):
            ext = cr.text_extents(line)
            cr.move_to(cx - ext.width / 2, y + pad + line_h * (i + 1) - 2)
            cr.show_text(line)

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_scroll(self, _ctrl, _dx, dy) -> bool:
        factor = 0.88 if dy > 0 else 1.12
        self._scale = max(0.1, min(8.0, self._scale * factor))
        self._da.queue_draw()
        return True

    def _on_drag_begin(self, _gesture, start_x: float, start_y: float) -> None:
        w = self._da.get_allocated_width()
        h = self._da.get_allocated_height()
        hit = self._hit_test(start_x, start_y, w, h)
        if hit is not None:
            self._drag_node_id = hit
            p = self._pos[hit]
            self._drag_node_origin = (p[0], p[1])
        else:
            self._drag_node_id = None
            self._pan_origin = (self._offset_x, self._offset_y)

    def _on_drag_update(self, _gesture, dx: float, dy: float) -> None:
        if self._drag_node_id is not None and self._drag_node_origin is not None:
            ox, oy = self._drag_node_origin
            self._pos[self._drag_node_id] = [
                ox + dx / self._scale,
                oy + dy / self._scale,
            ]
            self._da.queue_draw()
        elif self._pan_origin is not None:
            self._offset_x = self._pan_origin[0] + dx
            self._offset_y = self._pan_origin[1] + dy
            self._da.queue_draw()

    def _on_drag_end(self, _gesture, dx: float, dy: float) -> None:
        if self._drag_node_id is not None:
            # Tiny movement → treat as click
            if abs(dx) < 5 and abs(dy) < 5:
                self.emit("navigate-document", self._drag_node_id)
            self._drag_node_id = None
            self._drag_node_origin = None
        self._pan_origin = None

    def _on_motion(self, _ctrl, x: float, y: float) -> None:
        w = self._da.get_allocated_width()
        h = self._da.get_allocated_height()
        old = self._hover_id
        self._hover_id = self._hit_test(x, y, w, h)
        if self._hover_id != old:
            self._da.queue_draw()
