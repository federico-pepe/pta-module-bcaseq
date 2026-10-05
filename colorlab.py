"""colorlab.py - on-device tuning of track colors (Shift + Layout).

Pads show a track color next to its dim shade, as they look in the sequencer.
The screen shows the palette RGB, the tuned screen RGB and the dim RGB. Match
the screen swatch to what the pads look like, then press Save.
"""

import colortable
import engine as eng


class ColorLab:
    def __init__(self):
        self.pos = 0
        self.friction = eng.Friction()

    @property
    def color(self):
        return eng.TRACK_COLORS[self.pos]

    def dim_index(self):
        return colortable.dim(self.color)

    def rgb(self, palette):
        """Tuned screen RGB, or the palette RGB when untuned."""
        c = colortable.screen_rgb(self.color)
        if c is not None:
            return c
        e = palette["byIndex"][self.color]
        return (e["r"], e["g"], e["b"])

    def nudge(self, idx, delta, palette):
        if delta == 0:
            return
        if idx == 0:
            n = self.friction.feed("color", delta)
            self.pos = max(0, min(len(eng.TRACK_COLORS) - 1, self.pos + n))
        elif idx == 1:
            n = self.friction.feed("dim", delta, 2)
            colortable.set_entry(self.color, dim_idx=self.dim_index() + n)
        elif idx in (2, 3, 4):
            rgb = list(self.rgb(palette))
            rgb[idx - 2] = max(0, min(255, rgb[idx - 2] + 3 * delta))
            colortable.set_entry(self.color, rgb=rgb)
        elif idx == 5:
            colortable.clear_rgb(self.color)

    def pad_colors(self):
        """8x8 palette indices, row 0 = bottom."""
        full, dim = self.color, self.dim_index()
        g = [[0] * 8 for _ in range(8)]
        for row in range(8):
            for col in range(8):
                left = col < 4
                if row < 4:                       # solid blocks
                    g[row][col] = full if left else dim
                elif left:                        # checkerboard, like a step grid
                    g[row][col] = full if (row + col) % 2 == 0 else dim
                else:                             # selected / on / empty / playhead
                    g[row][col] = (120, full, dim, 126)[7 - row]
        return g
