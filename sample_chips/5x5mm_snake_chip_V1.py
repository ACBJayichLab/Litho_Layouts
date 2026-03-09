"""
5x5mm Snake Meander Chip Design - Version 1

V1 Design Architecture:
-----------------------
Two-layer system for negative resist gold and positive resist platinum.
Based on 5x5mm_sample_chip_V4.py but replaces omega resonators with a
long snake/meander trace that goes back and forth in a serpentine pattern
within the central aperture.

Layer 1/0 (Gold) - Negative Resist:
  - CPW signal lines and RF bond pads
  - Ground plane (drawn as "keep" regions)
  - Snake meander trace in central aperture
  - Alignment marks
  - NOTE: Exposure = NO gold. Draw what you want to KEEP.

Layer 2/0 (Platinum) - Positive Resist:
  - PRT serpentine thermometer
  - PRT bond pads

Key Changes from V4 (omega version):
  - Omega resonators replaced with snake meander trace
  - Rectangular meander fills the central aperture with uniform-length runs
  - Entry/exit elbows routed outside the meander area to avoid shorting
  - Configurable trace width, spacing, and meander dimensions
  - No DC access lines (removed)
  - CPW/taper moved outward from aperture

Author: Jeff Ahlers
Date: 2026-02-27
"""

import klayout.db as pya
import math
import os
from dataclasses import dataclass
from typing import Optional, Tuple


# =============================================================================
# CONFIGURATION CLASSES
# =============================================================================


@dataclass
class LayerConfig:
    """Layer definitions for two-layer design."""

    # Gold layer (negative resist - exposure = no gold)
    GOLD = pya.LayerInfo(1, 0)
    # Platinum layer (positive resist)
    PLATINUM = pya.LayerInfo(2, 0)

    # Layer names for GDS embedding
    LAYER_NAMES = {
        (1, 0): "gold",
        (2, 0): "platinum",
    }


@dataclass
class ChipConfig:
    """Chip-level dimensions and design rules."""

    # Chip dimensions
    chip_width: float = 5000.0  # um
    chip_height: float = 5000.0  # um

    # Dicing margins (exposed for gold removal)
    dicing_margin: float = 150.0  # um - no gold in this region

    # Database unit
    dbu: float = 0.001  # um per database unit


@dataclass
class GoldLayerConfig:
    """Gold layer (1/0) design parameters - CPW, ground plane, snake meander."""

    # RF Bond pads
    rf_pad_width: float = 800.0  # um (in Y direction)
    rf_pad_height: float = 800.0  # um (in X direction, along CPW)
    rf_pad_clearance: float = 50.0  # um from ground plane

    # CPW transmission line
    cpw_signal_width: float = 100.0  # um
    cpw_gap: float = 50.0  # um (each side)
    cpw_taper_length: float = 100.0  # um (taper from pad to CPW)

    # Central aperture (circular opening in ground plane)
    aperture_radius: float = 600.0  # um (adjustable per variant)

    # Snake meander parameters
    snake_trace_width: float = 10.0  # um (width of meander trace)
    snake_trace_spacing: float = 3.0  # um (gap between adjacent runs)
    snake_height: float = (
        500.0  # um (total Y extent of meander, should fit in aperture)
    )
    snake_margin: float = 20.0  # um (margin from aperture edge for turns)
    snake_taper_length: float = 250.0  # um (taper from CPW to snake trace width)
    snake_taper_cpw_inset: float = (
        400.0  # um how far taper starts into CPW (before aperture edge)
    )
    snake_width: float = 800.0  # um (total X extent of meander, should fit in aperture)

    # Alignment marks
    alignment_mark_offset: float = (
        1500.0  # um from chip center (placed at ±offset, ±offset)
    )
    alignment_mark_size: float = 250.0  # um cross arm length
    alignment_mark_width: float = 20.0  # um cross arm trace width

    # Edge buffer for RF pads
    edge_buffer: float = 200.0  # um from chip edge to pad


@dataclass
class PlatinumConfig:
    """Platinum layer (2/0) design parameters - PRT thermometer."""

    # Overall feature dimensions
    prt_width: float = 4600.0  # um total length (X)
    prt_height: float = 420.0  # um total height (Y)
    prt_cy: float = 2100.0  # um from chip center (placed at ±cy)

    # Bond pads at each end
    prt_pad_width: float = 700.0  # um (X extent)
    prt_pad_height: float = prt_height  # um (Y extent, matches prt_height)

    # Serpentine trace
    prt_trace_width: float = 8.0  # um line width
    prt_trace_spacing: float = 10.0  # um gap between lines
    prt_pad_spacing: float = 50.0  # um gap between Au bond pad and Pt serpentine


# =============================================================================
# CHIP DESIGNER CLASS
# =============================================================================


class SnakeChipDesigner:
    """
    V1 Snake Meander Chip Designer for 5×5 mm sample chips.

    Generates two-layer design:
      - Gold (1/0): CPW, ground plane, snake meander (negative resist)
      - Platinum (2/0): PRT thermometer (positive resist)
    """

    def __init__(
        self,
        chip_config: Optional[ChipConfig] = None,
        gold_config: Optional[GoldLayerConfig] = None,
        platinum_config: Optional[PlatinumConfig] = None,
        layer_config: Optional[LayerConfig] = None,
    ):
        """Initialize designer with configuration."""
        self.chip = chip_config or ChipConfig()
        self.gold = gold_config or GoldLayerConfig()
        self.platinum = platinum_config or PlatinumConfig()
        self.layers = layer_config or LayerConfig()

        # Layout will be created in generate()
        self.layout: Optional[pya.Layout] = None
        self.gold_layer_idx: Optional[int] = None
        self.platinum_layer_idx: Optional[int] = None

    def _um_to_dbu(self, um: float) -> int:
        """Convert micrometers to database units."""
        return int(round(um / self.chip.dbu))

    # -------------------------------------------------------------------------
    # GOLD LAYER COMPONENTS
    # -------------------------------------------------------------------------

    def create_rf_bond_pads(self, cell: pya.Cell) -> Tuple[float, float]:
        """
        Create RF bond pads with integrated tapers on gold layer (left and right sides).

        Each pad is a combined polygon: rectangular pad + trapezoidal taper.
        This eliminates duplicate geometry between pad and CPW taper.

        Returns:
            Tuple of (left_taper_end_x, right_taper_start_x) for CPW connections
        """
        chip_cy = self.chip.chip_height / 2.0

        # Left pad: positioned at left edge with integrated taper
        left_pad_x = self.gold.edge_buffer  # left edge of pad
        left_pad_right_x = left_pad_x + self.gold.rf_pad_height
        left_taper_end_x = left_pad_right_x + self.gold.cpw_taper_length

        # Combined left pad + taper polygon (6 vertices)
        left_pad_with_taper = pya.Polygon(
            [
                # Rectangular pad portion (counter-clockwise from bottom-left)
                pya.Point(
                    self._um_to_dbu(left_pad_x),
                    self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0),
                ),
                pya.Point(
                    self._um_to_dbu(left_pad_x),
                    self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0),
                ),
                # Taper portion (continues from top of pad to narrow CPW end)
                pya.Point(
                    self._um_to_dbu(left_pad_right_x),
                    self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0),
                ),
                pya.Point(
                    self._um_to_dbu(left_taper_end_x),
                    self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0),
                ),
                pya.Point(
                    self._um_to_dbu(left_taper_end_x),
                    self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0),
                ),
                pya.Point(
                    self._um_to_dbu(left_pad_right_x),
                    self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0),
                ),
            ]
        )
        cell.shapes(self.gold_layer_idx).insert(left_pad_with_taper)

        # Right pad: positioned at right edge with integrated taper
        right_pad_x = (
            self.chip.chip_width - self.gold.edge_buffer - self.gold.rf_pad_height
        )
        right_taper_start_x = right_pad_x - self.gold.cpw_taper_length

        # Combined right pad + taper polygon (6 vertices)
        right_pad_with_taper = pya.Polygon(
            [
                # Taper portion (starts narrow at CPW, widens to pad)
                pya.Point(
                    self._um_to_dbu(right_taper_start_x),
                    self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0),
                ),
                pya.Point(
                    self._um_to_dbu(right_taper_start_x),
                    self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0),
                ),
                pya.Point(
                    self._um_to_dbu(right_pad_x),
                    self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0),
                ),
                # Rectangular pad portion
                pya.Point(
                    self._um_to_dbu(right_pad_x + self.gold.rf_pad_height),
                    self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0),
                ),
                pya.Point(
                    self._um_to_dbu(right_pad_x + self.gold.rf_pad_height),
                    self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0),
                ),
                pya.Point(
                    self._um_to_dbu(right_pad_x),
                    self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0),
                ),
            ]
        )
        cell.shapes(self.gold_layer_idx).insert(right_pad_with_taper)

        # Return taper end positions for CPW connections
        return left_taper_end_x, right_taper_start_x

    def create_cpw_signal_path(
        self, cell: pya.Cell, left_taper_end_x: float, right_taper_start_x: float
    ) -> None:
        """
        Create CPW signal line sections connecting bond pad tapers to snake meander.

        Signal path: Left Pad+Taper → CPW → Snake Meander → CPW → Taper+Right Pad

        Note: Pad-to-CPW tapers are now integrated into create_rf_bond_pads().
        This function creates only the CPW sections between tapers and aperture.

        Args:
            left_taper_end_x: x-coordinate where left taper ends (CPW starts)
            right_taper_start_x: x-coordinate where right taper starts (CPW ends)
        """
        chip_cx = self.chip.chip_width / 2.0
        chip_cy = self.chip.chip_height / 2.0

        # CPW ends where the snake taper wide end starts (inset from aperture edge)
        left_cpw_end_x = chip_cx - self.gold.snake_width
        right_cpw_start_x = chip_cx + self.gold.snake_width

        # --- Left CPW section (from taper end to aperture) ---
        if left_cpw_end_x > left_taper_end_x:
            left_cpw = pya.Box(
                self._um_to_dbu(left_taper_end_x),
                self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0),
                self._um_to_dbu(left_cpw_end_x),
                self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0),
            )
            cell.shapes(self.gold_layer_idx).insert(left_cpw)

        # --- Right CPW section (from aperture to taper start) ---
        if right_cpw_start_x < right_taper_start_x:
            right_cpw = pya.Box(
                self._um_to_dbu(right_cpw_start_x),
                self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0),
                self._um_to_dbu(right_taper_start_x),
                self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0),
            )
            cell.shapes(self.gold_layer_idx).insert(right_cpw)

        # --- Create Snake Meander in center ---
        self.create_snake_meander(cell, chip_cx, chip_cy)

    def create_snake_meander(self, cell: pya.Cell, cx: float, cy: float) -> None:
        """
        Create a rectangular snake/meander trace pattern within the central aperture.

        The meander is a rectangular grid of equal-length horizontal runs connected
        by U-turns on alternating sides.  Entry and exit elbows are routed OUTSIDE
        the meander rectangle to avoid shorting against the snake traces.

        Signal path:
          Left taper → horizontal feed at cy → vertical elbow down to bottom run
          → snake meander (bottom to top) → vertical elbow down to cy →
          horizontal feed at cy → right taper

        Args:
            cx: x-coordinate of chip center (um)
            cy: y-coordinate of chip center (um)
        """
        g = self.gold
        tw = g.snake_trace_width
        ts = g.snake_trace_spacing
        pitch = tw + ts  # center-to-center distance between runs

        r = g.snake_width / 2
        margin = g.snake_margin
        taper_length = g.snake_taper_length
        cpw_width = g.cpw_signal_width

        # Region to collect all meander geometry
        meander_region = pya.Region()

        # --- Tapers from CPW signal width to snake trace width ---
        cpw_end_left = cx - r
        cpw_end_right = cx + r

        # Left taper (CPW → snake trace)
        left_taper_start_x = cpw_end_left - g.snake_taper_cpw_inset
        left_taper_end_x = left_taper_start_x + taper_length
        left_taper = pya.Polygon(
            [
                pya.Point(
                    self._um_to_dbu(left_taper_start_x),
                    self._um_to_dbu(cy - cpw_width / 2.0),
                ),
                pya.Point(
                    self._um_to_dbu(left_taper_end_x), self._um_to_dbu(cy - tw / 2.0)
                ),
                pya.Point(
                    self._um_to_dbu(left_taper_end_x), self._um_to_dbu(cy + tw / 2.0)
                ),
                pya.Point(
                    self._um_to_dbu(left_taper_start_x),
                    self._um_to_dbu(cy + cpw_width / 2.0),
                ),
            ]
        )
        meander_region.insert(left_taper)

        # Right taper (snake trace → CPW)
        right_taper_end_x = cpw_end_right + g.snake_taper_cpw_inset
        right_taper_start_x = right_taper_end_x - taper_length
        right_taper = pya.Polygon(
            [
                pya.Point(
                    self._um_to_dbu(right_taper_start_x), self._um_to_dbu(cy - tw / 2.0)
                ),
                pya.Point(
                    self._um_to_dbu(right_taper_end_x),
                    self._um_to_dbu(cy - cpw_width / 2.0),
                ),
                pya.Point(
                    self._um_to_dbu(right_taper_end_x),
                    self._um_to_dbu(cy + cpw_width / 2.0),
                ),
                pya.Point(
                    self._um_to_dbu(right_taper_start_x), self._um_to_dbu(cy + tw / 2.0)
                ),
            ]
        )
        meander_region.insert(right_taper)

        # --- Rectangular meander area ---
        meander_left = cx - r + margin
        meander_right = cx + r - margin
        half_height = g.snake_height / 2.0

        # Number of runs (always odd for symmetry about cy)
        n_above = int(half_height // pitch)
        n_runs = 1 + 2 * n_above

        # Run Y positions (bottom to top)
        run_ys = [cy - n_above * pitch + i * pitch for i in range(n_runs)]

        # All runs have identical horizontal extent (rectangular snake)
        valid_runs = [(ry, meander_left, meander_right) for ry in run_ys]

        if len(valid_runs) == 0:
            # Fallback: straight connection
            meander_region.insert(
                pya.Box(
                    self._um_to_dbu(left_taper_end_x),
                    self._um_to_dbu(cy - tw / 2.0),
                    self._um_to_dbu(right_taper_start_x),
                    self._um_to_dbu(cy + tw / 2.0),
                )
            )
            meander_region.merge()
            cell.shapes(self.gold_layer_idx).insert(meander_region)
            return

        # Draw all horizontal runs (uniform length)
        for run_y, left_x, right_x in valid_runs:
            meander_region.insert(
                pya.Box(
                    self._um_to_dbu(left_x),
                    self._um_to_dbu(run_y - tw / 2.0),
                    self._um_to_dbu(right_x),
                    self._um_to_dbu(run_y + tw / 2.0),
                )
            )

        # Draw U-turn connections between adjacent runs
        # Even-indexed gaps connect on right, odd-indexed on left
        for i in range(len(valid_runs) - 1):
            run_y_bot = valid_runs[i][0]
            run_y_top = valid_runs[i + 1][0]

            if i % 2 == 0:
                # Connect on the right side
                meander_region.insert(
                    pya.Box(
                        self._um_to_dbu(meander_right - tw),
                        self._um_to_dbu(run_y_bot - tw / 2.0),
                        self._um_to_dbu(meander_right),
                        self._um_to_dbu(run_y_top + tw / 2.0),
                    )
                )
            else:
                # Connect on the left side
                meander_region.insert(
                    pya.Box(
                        self._um_to_dbu(meander_left),
                        self._um_to_dbu(run_y_bot - tw / 2.0),
                        self._um_to_dbu(meander_left + tw),
                        self._um_to_dbu(run_y_top + tw / 2.0),
                    )
                )

        # --- Entry/exit elbows OUTSIDE the meander rectangle ---
        # Place elbows so the inner edge of the elbow trace is at least
        # one trace-spacing away from the meander edge, preventing shorts
        # even when snake_trace_spacing is very small.
        elbow_left_x = meander_left - ts - tw  # center of left elbow trace
        elbow_right_x = meander_right + ts + tw  # center of right elbow trace

        bottom_run_y = valid_runs[0][0]
        top_run_y = valid_runs[-1][0]
        n_valid = len(valid_runs)

        if n_valid == 1:
            # Single run: straight feed from tapers to run ends
            meander_region.insert(
                pya.Box(
                    self._um_to_dbu(left_taper_end_x),
                    self._um_to_dbu(cy - tw / 2.0),
                    self._um_to_dbu(meander_left),
                    self._um_to_dbu(cy + tw / 2.0),
                )
            )
            meander_region.insert(
                pya.Box(
                    self._um_to_dbu(meander_right),
                    self._um_to_dbu(cy - tw / 2.0),
                    self._um_to_dbu(right_taper_start_x),
                    self._um_to_dbu(cy + tw / 2.0),
                )
            )
        else:
            # n_runs is always odd (≥ 3), so the last U-turn index is
            # always odd → exit is always on the right side.
            # Entry: bottom-left.  Exit: top-right.

            # == LEFT ENTRY ELBOW ==
            # 1. Horizontal feed at cy from taper end to elbow
            meander_region.insert(
                pya.Box(
                    self._um_to_dbu(left_taper_end_x),
                    self._um_to_dbu(cy - tw / 2.0),
                    self._um_to_dbu(elbow_left_x + tw / 2.0),
                    self._um_to_dbu(cy + tw / 2.0),
                )
            )
            # 2. Vertical drop from cy to bottom run
            meander_region.insert(
                pya.Box(
                    self._um_to_dbu(elbow_left_x - tw / 2.0),
                    self._um_to_dbu(bottom_run_y - tw / 2.0),
                    self._um_to_dbu(elbow_left_x + tw / 2.0),
                    self._um_to_dbu(cy + tw / 2.0),
                )
            )
            # 3. Horizontal bridge from elbow to meander left edge
            meander_region.insert(
                pya.Box(
                    self._um_to_dbu(elbow_left_x - tw / 2.0),
                    self._um_to_dbu(bottom_run_y - tw / 2.0),
                    self._um_to_dbu(meander_left + tw),
                    self._um_to_dbu(bottom_run_y + tw / 2.0),
                )
            )

            # == RIGHT EXIT ELBOW ==
            # 1. Horizontal bridge from meander right edge to elbow
            meander_region.insert(
                pya.Box(
                    self._um_to_dbu(meander_right - tw),
                    self._um_to_dbu(top_run_y - tw / 2.0),
                    self._um_to_dbu(elbow_right_x + tw / 2.0),
                    self._um_to_dbu(top_run_y + tw / 2.0),
                )
            )
            # 2. Vertical drop from top run to cy
            meander_region.insert(
                pya.Box(
                    self._um_to_dbu(elbow_right_x - tw / 2.0),
                    self._um_to_dbu(cy - tw / 2.0),
                    self._um_to_dbu(elbow_right_x + tw / 2.0),
                    self._um_to_dbu(top_run_y + tw / 2.0),
                )
            )
            # 3. Horizontal feed from elbow to right taper
            meander_region.insert(
                pya.Box(
                    self._um_to_dbu(elbow_right_x - tw / 2.0),
                    self._um_to_dbu(cy - tw / 2.0),
                    self._um_to_dbu(right_taper_start_x),
                    self._um_to_dbu(cy + tw / 2.0),
                )
            )

        # Merge and insert
        meander_region.merge()
        cell.shapes(self.gold_layer_idx).insert(meander_region)

    def create_ground_plane(self, cell: pya.Cell) -> None:
        """
        Create ground plane with cutouts for signal path on gold layer.

        Cutouts include:
        - RF bond pads with clearance
        - CPW signal path with gap (including tapered sections)
        - Central aperture (circular)

        Uses region Boolean operations for robust geometry.
        """
        chip_cx = self.chip.chip_width / 2.0
        chip_cy = self.chip.chip_height / 2.0
        gap = self.gold.cpw_gap
        pad_clearance = self.gold.rf_pad_clearance

        # Start with full chip minus dicing margin
        ground_region = pya.Region(
            pya.Box(
                self._um_to_dbu(self.chip.dicing_margin),
                self._um_to_dbu(self.chip.dicing_margin),
                self._um_to_dbu(self.chip.chip_width - self.chip.dicing_margin),
                self._um_to_dbu(self.chip.chip_height - self.chip.dicing_margin),
            )
        )

        # === SUBTRACT RF BOND PADS WITH CLEARANCE ===
        # Left pad position - ground plane removed from pad outer edge to chip edge
        left_pad_x = self.gold.edge_buffer
        left_pad_box = pya.Box(
            self._um_to_dbu(self.chip.dicing_margin),
            self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0 - pad_clearance),
            self._um_to_dbu(left_pad_x + self.gold.rf_pad_height),  # Stop at pad edge
            self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0 + pad_clearance),
        )
        ground_region -= pya.Region(left_pad_box)

        # Right pad position - ground plane removed from pad outer edge to chip edge
        right_pad_x = (
            self.chip.chip_width - self.gold.edge_buffer - self.gold.rf_pad_height
        )
        right_pad_box = pya.Box(
            self._um_to_dbu(right_pad_x),  # Stop at pad edge
            self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0 - pad_clearance),
            self._um_to_dbu(self.chip.chip_width - self.chip.dicing_margin),
            self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0 + pad_clearance),
        )
        ground_region -= pya.Region(right_pad_box)

        # === SUBTRACT LEFT TAPER GAP (pad width → CPW width) ===
        # Calculate perpendicular offset for constant gap normal to taper edge
        left_taper_start_x = left_pad_x + self.gold.rf_pad_height
        left_taper_end_x = left_taper_start_x + self.gold.cpw_taper_length

        # Taper edge vector (top edge, from wide to narrow)
        taper_dx = self.gold.cpw_taper_length
        taper_dy = (
            self.gold.cpw_signal_width - self.gold.rf_pad_width
        ) / 2.0  # negative (narrows)
        taper_length = math.sqrt(taper_dx**2 + taper_dy**2)

        # Perpendicular unit vector (outward from top edge)
        # Rotate taper vector 90° CCW: (dx, dy) → (-dy, dx), then normalize
        perp_x = -taper_dy / taper_length
        perp_y = taper_dx / taper_length

        # Perpendicular offset for pad_clearance gap
        offset_x = pad_clearance * perp_x
        offset_y = pad_clearance * perp_y

        # Single tapered cutout for signal + gap (top half)
        left_taper_cutout_top = pya.Polygon(
            [
                pya.Point(
                    self._um_to_dbu(left_taper_start_x),
                    self._um_to_dbu(
                        chip_cy + self.gold.rf_pad_width / 2.0 + pad_clearance
                    ),
                ),
                pya.Point(
                    self._um_to_dbu(left_taper_start_x + offset_x),
                    self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0 + offset_y),
                ),
                pya.Point(
                    self._um_to_dbu(left_taper_end_x + offset_x),
                    self._um_to_dbu(
                        chip_cy + self.gold.cpw_signal_width / 2.0 + offset_y
                    ),
                ),
                pya.Point(
                    self._um_to_dbu(left_taper_end_x),
                    self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0),
                ),
                pya.Point(
                    self._um_to_dbu(left_taper_start_x),
                    self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0),
                ),
            ]
        )
        ground_region -= pya.Region(left_taper_cutout_top)

        # Single tapered cutout for signal + gap (bottom half)
        left_taper_cutout_bot = pya.Polygon(
            [
                pya.Point(
                    self._um_to_dbu(left_taper_start_x),
                    self._um_to_dbu(
                        chip_cy - self.gold.rf_pad_width / 2.0 - pad_clearance
                    ),
                ),
                pya.Point(
                    self._um_to_dbu(left_taper_start_x + offset_x),
                    self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0 - offset_y),
                ),
                pya.Point(
                    self._um_to_dbu(left_taper_end_x + offset_x),
                    self._um_to_dbu(
                        chip_cy - self.gold.cpw_signal_width / 2.0 - offset_y
                    ),
                ),
                pya.Point(
                    self._um_to_dbu(left_taper_end_x),
                    self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0),
                ),
                pya.Point(
                    self._um_to_dbu(left_taper_start_x),
                    self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0),
                ),
            ]
        )
        ground_region -= pya.Region(left_taper_cutout_bot)

        # === SUBTRACT LEFT CPW SECTION (taper end to aperture) ===
        cpw_end_left = chip_cx - self.gold.aperture_radius
        cpw_half_height = self.gold.cpw_signal_width / 2.0 + gap
        r = self.gold.aperture_radius
        circle_inset = r - math.sqrt(r**2 - cpw_half_height**2)
        left_cpw_box = pya.Box(
            self._um_to_dbu(left_taper_end_x),
            self._um_to_dbu(chip_cy - cpw_half_height),
            self._um_to_dbu(cpw_end_left + circle_inset),
            self._um_to_dbu(chip_cy + cpw_half_height),
        )
        ground_region -= pya.Region(left_cpw_box)

        # === SUBTRACT RIGHT CPW SECTION (aperture to taper) ===
        cpw_end_right = chip_cx + self.gold.aperture_radius
        right_taper_end_x = (
            self.chip.chip_width - self.gold.edge_buffer - self.gold.rf_pad_height
        )
        right_taper_start_x = right_taper_end_x - self.gold.cpw_taper_length
        right_cpw_box = pya.Box(
            self._um_to_dbu(cpw_end_right - circle_inset),
            self._um_to_dbu(chip_cy - cpw_half_height),
            self._um_to_dbu(right_taper_start_x),
            self._um_to_dbu(chip_cy + cpw_half_height),
        )
        ground_region -= pya.Region(right_cpw_box)

        # === SUBTRACT RIGHT TAPER GAP (CPW width → pad width) ===
        right_taper_dx = self.gold.cpw_taper_length
        right_taper_dy = (self.gold.rf_pad_width - self.gold.cpw_signal_width) / 2.0
        right_taper_length = math.sqrt(right_taper_dx**2 + right_taper_dy**2)

        right_perp_x = right_taper_dy / right_taper_length
        right_perp_y = right_taper_dx / right_taper_length

        right_offset_x = pad_clearance * right_perp_x
        right_offset_y = pad_clearance * right_perp_y

        right_taper_cutout_top = pya.Polygon(
            [
                pya.Point(
                    self._um_to_dbu(right_taper_start_x),
                    self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0),
                ),
                pya.Point(
                    self._um_to_dbu(right_taper_start_x - right_offset_x),
                    self._um_to_dbu(
                        chip_cy + self.gold.cpw_signal_width / 2.0 + right_offset_y
                    ),
                ),
                pya.Point(
                    self._um_to_dbu(right_taper_end_x - right_offset_x),
                    self._um_to_dbu(
                        chip_cy + self.gold.rf_pad_width / 2.0 + right_offset_y
                    ),
                ),
                pya.Point(
                    self._um_to_dbu(right_taper_end_x),
                    self._um_to_dbu(
                        chip_cy + self.gold.rf_pad_width / 2.0 + pad_clearance
                    ),
                ),
                pya.Point(
                    self._um_to_dbu(right_taper_end_x),
                    self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0),
                ),
            ]
        )
        ground_region -= pya.Region(right_taper_cutout_top)

        right_taper_cutout_bot = pya.Polygon(
            [
                pya.Point(
                    self._um_to_dbu(right_taper_start_x),
                    self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0),
                ),
                pya.Point(
                    self._um_to_dbu(right_taper_start_x - right_offset_x),
                    self._um_to_dbu(
                        chip_cy - self.gold.cpw_signal_width / 2.0 - right_offset_y
                    ),
                ),
                pya.Point(
                    self._um_to_dbu(right_taper_end_x - right_offset_x),
                    self._um_to_dbu(
                        chip_cy - self.gold.rf_pad_width / 2.0 - right_offset_y
                    ),
                ),
                pya.Point(
                    self._um_to_dbu(right_taper_end_x),
                    self._um_to_dbu(
                        chip_cy - self.gold.rf_pad_width / 2.0 - pad_clearance
                    ),
                ),
                pya.Point(
                    self._um_to_dbu(right_taper_end_x),
                    self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0),
                ),
            ]
        )
        ground_region -= pya.Region(right_taper_cutout_bot)

        # === SUBTRACT CENTRAL APERTURE (circular) ===
        num_segments = 128
        aperture_points = []
        for i in range(num_segments):
            angle = 2.0 * math.pi * i / num_segments
            x = chip_cx + self.gold.aperture_radius * math.cos(angle)
            y = chip_cy + self.gold.aperture_radius * math.sin(angle)
            aperture_points.append(pya.Point(self._um_to_dbu(x), self._um_to_dbu(y)))
        aperture_polygon = pya.Polygon(aperture_points)
        ground_region -= pya.Region(aperture_polygon)

        # === SUBTRACT ALIGNMENT MARK CLEARANCES ===
        am_off = self.gold.alignment_mark_offset
        am_size = self.gold.alignment_mark_size
        am_clr = self.gold.rf_pad_clearance  # reuse pad clearance
        for sx in [+1, -1]:
            for sy in [+1, -1]:
                mx = chip_cx + sx * am_off
                my = chip_cy + sy * am_off
                ground_region -= pya.Region(
                    pya.Box(
                        self._um_to_dbu(mx - am_size / 2.0 - am_clr),
                        self._um_to_dbu(my - am_size / 2.0 - am_clr),
                        self._um_to_dbu(mx + am_size / 2.0 + am_clr),
                        self._um_to_dbu(my + am_size / 2.0 + am_clr),
                    )
                )

        # === SUBTRACT SMALL ALIGNMENT MARK CLEARANCES ===
        small_am_offset = 400.0
        small_am_half = 7.5
        small_am_clr = 30.0  # µm clearance around small marks
        for sx in [+1, -1]:
            for sy in [+1, -1]:
                smx = chip_cx + sx * small_am_offset
                smy = chip_cy + sy * small_am_offset
                ground_region -= pya.Region(
                    pya.Box(
                        self._um_to_dbu(smx - small_am_half - small_am_clr),
                        self._um_to_dbu(smy - small_am_half - small_am_clr),
                        self._um_to_dbu(smx + small_am_half + small_am_clr),
                        self._um_to_dbu(smy + small_am_half + small_am_clr),
                    )
                )

        # === SUBTRACT PRT THERMOMETER CLEARANCES ===
        prt_clr = 50.0  # um clearance around PRT features
        for sign in [+1, -1]:
            prt_cx = chip_cx
            prt_cy = chip_cy + sign * self.platinum.prt_cy
            inner_y = prt_cy - sign * (self.platinum.prt_height / 2.0 + prt_clr)
            outer_y = (
                (self.chip.chip_height - self.chip.dicing_margin)
                if sign > 0
                else self.chip.dicing_margin
            )
            ground_region -= pya.Region(
                pya.Box(
                    self._um_to_dbu(prt_cx - self.platinum.prt_width / 2.0 - prt_clr),
                    self._um_to_dbu(min(inner_y, outer_y)),
                    self._um_to_dbu(prt_cx + self.platinum.prt_width / 2.0 + prt_clr),
                    self._um_to_dbu(max(inner_y, outer_y)),
                )
            )

        # === SUBTRACT VERNIER ALIGNMENT MARK CLEARANCE ===
        vernier_clr = 50.0  # µm clearance around vernier marks
        vx = chip_cx + 2100.0
        vy = chip_cy + 1400.0
        v_hw = 170.0  # half-width
        v_hh = 170.0  # half-height (use symmetric envelope)
        ground_region -= pya.Region(
            pya.Box(
                self._um_to_dbu(vx - v_hw - vernier_clr),
                self._um_to_dbu(vy - v_hh - vernier_clr),
                self._um_to_dbu(vx + v_hw + vernier_clr),
                self._um_to_dbu(vy + v_hh + vernier_clr),
            )
        )

        # Merge and insert ground plane
        ground_region.merge()
        cell.shapes(self.gold_layer_idx).insert(ground_region)

    def create_alignment_marks(self, cell: pya.Cell) -> None:
        """
        Create cross-shaped alignment marks at ±offset, ±offset from chip center.

        Each mark is two overlapping rectangles forming a + shape.
        """
        chip_cx = self.chip.chip_width / 2.0
        chip_cy = self.chip.chip_height / 2.0
        off = self.gold.alignment_mark_offset
        size = self.gold.alignment_mark_size
        w = self.gold.alignment_mark_width

        for sx in [+1, -1]:
            for sy in [+1, -1]:
                cx = chip_cx + sx * off
                cy = chip_cy + sy * off

                # Horizontal bar
                cell.shapes(self.gold_layer_idx).insert(
                    pya.Box(
                        self._um_to_dbu(cx - size / 2.0),
                        self._um_to_dbu(cy - w / 2.0),
                        self._um_to_dbu(cx + size / 2.0),
                        self._um_to_dbu(cy + w / 2.0),
                    )
                )

                # Vertical bar
                cell.shapes(self.gold_layer_idx).insert(
                    pya.Box(
                        self._um_to_dbu(cx - w / 2.0),
                        self._um_to_dbu(cy - size / 2.0),
                        self._um_to_dbu(cx + w / 2.0),
                        self._um_to_dbu(cy + size / 2.0),
                    )
                )

    def create_small_alignment_marks(self, cell: pya.Cell) -> None:
        """Create small cross alignment marks at ±400, ±400 µm from chip center.

        Each mark has arm half-length = 25 µm with 4 µm trace width.
        Placed on the gold layer at 4 positions near the chip center.
        """
        chip_cx = self.chip.chip_width / 2.0
        chip_cy = self.chip.chip_height / 2.0
        offset = 400.0  # µm from center
        arm_half = 25  # µm
        tw = 4.0  # µm trace width

        for sx in [+1, -1]:
            for sy in [+1, -1]:
                cx = chip_cx + sx * offset
                cy = chip_cy + sy * offset

                # Horizontal bar
                cell.shapes(self.gold_layer_idx).insert(
                    pya.Box(
                        self._um_to_dbu(cx - arm_half),
                        self._um_to_dbu(cy - tw / 2.0),
                        self._um_to_dbu(cx + arm_half),
                        self._um_to_dbu(cy + tw / 2.0),
                    )
                )

                # Vertical bar
                cell.shapes(self.gold_layer_idx).insert(
                    pya.Box(
                        self._um_to_dbu(cx - tw / 2.0),
                        self._um_to_dbu(cy - arm_half),
                        self._um_to_dbu(cx + tw / 2.0),
                        self._um_to_dbu(cy + arm_half),
                    )
                )

    def create_vernier_marks(self, cell: pya.Cell) -> None:
        """Import vernier/alignment marks from external GDS onto each chip.

        Reads Contact-AlignMarks_Vernier_DemisDJohn_v5.gds:
          - AlignLyr1 (layer 1/0) → gold layer
          - AlignLyr2 (layer 2/0) → platinum layer

        Placed at chip_center + (2100, 1400) µm.
        Ground plane cutout is handled in create_ground_plane().
        """
        gds_path = os.path.join(
            os.path.dirname(__file__), "Contact-AlignMarks_Vernier_DemisDJohn_v5.gds"
        )

        # Load external GDS
        ext_layout = pya.Layout()
        ext_layout.read(gds_path)

        align_lyr1_src = ext_layout.cell("AlignLyr1")
        align_lyr2_src = ext_layout.cell("AlignLyr2")

        if align_lyr1_src is None or align_lyr2_src is None:
            print("  WARNING: Could not find AlignLyr1/AlignLyr2 in alignment GDS")
            return

        ext_gold_idx = ext_layout.layer(pya.LayerInfo(1, 0))
        ext_plat_idx = ext_layout.layer(pya.LayerInfo(2, 0))

        # Collect flattened geometry from each source cell
        gold_region = pya.Region(align_lyr1_src.begin_shapes_rec(ext_gold_idx))
        plat_region = pya.Region(align_lyr2_src.begin_shapes_rec(ext_plat_idx))

        # Placement position (chip-local coordinates)
        chip_cx = self.chip.chip_width / 2.0
        chip_cy = self.chip.chip_height / 2.0
        vx = chip_cx + 2100.0
        vy = chip_cy + 1400.0

        # Translate to placement position and insert
        shift = pya.ICplxTrans(1, 0, False, self._um_to_dbu(vx), self._um_to_dbu(vy))
        cell.shapes(self.gold_layer_idx).insert(gold_region.transformed(shift))
        cell.shapes(self.platinum_layer_idx).insert(plat_region.transformed(shift))

    # -------------------------------------------------------------------------
    # PLATINUM LAYER COMPONENTS
    # -------------------------------------------------------------------------

    def create_prt_thermometers(self, cell: pya.Cell) -> None:
        """
        Create PRT serpentine thermometers on the platinum layer.

        Placed at chip center X, at ±prt_cy from chip center Y.
        Each thermometer: pad | serpentine body | pad
        Serpentine consists of horizontal lines snaking back and forth.
        """
        p = self.platinum
        chip_cx = self.chip.chip_width / 2.0
        chip_cy = self.chip.chip_height / 2.0

        tw = p.prt_trace_width
        ts = p.prt_trace_spacing
        pitch = tw + ts  # centerline-to-centerline

        # Body dimensions (between the two pads)
        body_width = p.prt_width - 2.0 * p.prt_pad_width

        # Number of horizontal traces that fit in the height
        n_lines = int(p.prt_height // pitch)
        # Center the serpentine vertically within prt_height
        serpentine_total = n_lines * tw + (n_lines - 1) * ts
        y_margin = (p.prt_height - serpentine_total) / 2.0

        ps = p.prt_pad_spacing  # gap between Au pad edge and Pt serpentine

        for sign in [+1, -1]:
            # Feature center
            feat_cx = chip_cx
            feat_cy = chip_cy + sign * p.prt_cy
            feat_left = feat_cx - p.prt_width / 2.0
            feat_bottom = feat_cy - p.prt_height / 2.0

            # Left bond pad (gold layer)
            cell.shapes(self.gold_layer_idx).insert(
                pya.Box(
                    self._um_to_dbu(feat_left),
                    self._um_to_dbu(feat_cy - p.prt_pad_height / 2.0),
                    self._um_to_dbu(feat_left + p.prt_pad_width),
                    self._um_to_dbu(feat_cy + p.prt_pad_height / 2.0),
                )
            )

            # Right bond pad (gold layer)
            cell.shapes(self.gold_layer_idx).insert(
                pya.Box(
                    self._um_to_dbu(feat_left + p.prt_width - p.prt_pad_width),
                    self._um_to_dbu(feat_cy - p.prt_pad_height / 2.0),
                    self._um_to_dbu(feat_left + p.prt_width),
                    self._um_to_dbu(feat_cy + p.prt_pad_height / 2.0),
                )
            )

            # Serpentine body (platinum layer)
            body_left = feat_left + p.prt_pad_width
            body_right = body_left + body_width

            for j in range(n_lines):
                line_bottom = feat_bottom + y_margin + j * pitch
                line_top = line_bottom + tw

                # Bottom line touches left pad only; top line touches right pad only;
                # interior traces are inset by pad_spacing on pad sides
                if j == 0:
                    trace_left = body_left
                    trace_right = body_right - ps
                elif j == n_lines - 1:
                    trace_left = body_left + ps
                    trace_right = body_right
                else:
                    trace_left = body_left + ps
                    trace_right = body_right - ps

                # Horizontal trace
                cell.shapes(self.platinum_layer_idx).insert(
                    pya.Box(
                        self._um_to_dbu(trace_left),
                        self._um_to_dbu(line_bottom),
                        self._um_to_dbu(trace_right),
                        self._um_to_dbu(line_top),
                    )
                )

                # Vertical connecting stub to next line
                if j < n_lines - 1:
                    next_bottom = line_top + ts
                    # Even lines connect on right, odd on left
                    # Stubs are inset by pad_spacing to match shortened traces
                    if j % 2 == 0:
                        stub_x = body_right - ps - tw
                    else:
                        stub_x = body_left + ps

                    cell.shapes(self.platinum_layer_idx).insert(
                        pya.Box(
                            self._um_to_dbu(stub_x),
                            self._um_to_dbu(line_top),
                            self._um_to_dbu(stub_x + tw),
                            self._um_to_dbu(next_bottom),
                        )
                    )

            # Connect first line to left pad, last line to right pad
            first_line_bottom = feat_bottom + y_margin
            last_line_bottom = feat_bottom + y_margin + (n_lines - 1) * pitch

            # Left pad connects to first (bottom) line — Pt trace overlaps Au pad
            cell.shapes(self.platinum_layer_idx).insert(
                pya.Box(
                    self._um_to_dbu(body_left - p.prt_pad_width),
                    self._um_to_dbu(first_line_bottom),
                    self._um_to_dbu(body_left),
                    self._um_to_dbu(first_line_bottom + tw),
                )
            )

            # Right pad connects to last line — Pt trace overlaps Au pad
            if (n_lines - 1) % 2 == 0:
                cell.shapes(self.platinum_layer_idx).insert(
                    pya.Box(
                        self._um_to_dbu(body_right),
                        self._um_to_dbu(last_line_bottom),
                        self._um_to_dbu(body_right + p.prt_pad_width),
                        self._um_to_dbu(last_line_bottom + tw),
                    )
                )
            else:
                cell.shapes(self.platinum_layer_idx).insert(
                    pya.Box(
                        self._um_to_dbu(body_right),
                        self._um_to_dbu(last_line_bottom),
                        self._um_to_dbu(body_right + p.prt_pad_width),
                        self._um_to_dbu(last_line_bottom + tw),
                    )
                )

    # -------------------------------------------------------------------------
    # LABELS
    # -------------------------------------------------------------------------

    def create_labels(self, cell: pya.Cell) -> None:
        """
        Create polygon-based text labels on the gold layer.

        Uses KLayout's TextGenerator to render text as bold polygon shapes.
        Surrounding gold is removed with a clearance margin so text is
        readable against the cleared substrate.

        Labels the chip with "SNK" (snake) identifier.
        """
        chip_cx = self.chip.chip_width / 2.0
        chip_cy = self.chip.chip_height / 2.0

        label_x = chip_cx - 2100
        label_y = chip_cy + 800.0

        label_text = "SNK"

        # Generate text as polygons using KLayout built-in font
        gen = pya.TextGenerator.default_generator()
        target_height = 400.0  # um — character height
        text_region = gen.text(label_text, self.layout.dbu, target_height)

        # Thicken for bold appearance
        bold = self._um_to_dbu(3.0)
        text_region = text_region.sized(bold)

        # Move text to desired position
        text_region.move(self._um_to_dbu(label_x), self._um_to_dbu(label_y))

        # Clear surrounding gold with margin so text is visible
        clearance = self._um_to_dbu(30.0)
        text_bbox = text_region.bbox()
        clear_box = pya.Region(
            pya.Box(
                text_bbox.left - clearance,
                text_bbox.bottom - clearance,
                text_bbox.right + clearance,
                text_bbox.top + clearance,
            )
        )

        # Read existing gold, subtract clearance, add text back
        existing_gold = pya.Region(cell.shapes(self.gold_layer_idx))
        existing_gold -= clear_box
        existing_gold += text_region
        existing_gold.merge()

        cell.shapes(self.gold_layer_idx).clear()
        cell.shapes(self.gold_layer_idx).insert(existing_gold)

    # -------------------------------------------------------------------------
    # MAIN GENERATION
    # -------------------------------------------------------------------------

    def create_chip(self, name: str = "snake_chip_V1") -> pya.Cell:
        """
        Create complete chip design.

        Args:
            name: Cell name for the chip

        Returns:
            pya.Cell containing complete chip design
        """
        cell = self.layout.create_cell(name)

        # Gold layer components
        # 1. Create RF bond pads with integrated tapers (returns taper end positions)
        left_taper_end_x, right_taper_start_x = self.create_rf_bond_pads(cell)

        # 2. Create CPW signal path sections and snake meander
        self.create_cpw_signal_path(cell, left_taper_end_x, right_taper_start_x)

        # 3. Alignment marks
        self.create_alignment_marks(cell)

        # 3a. Small alignment marks near center
        self.create_small_alignment_marks(cell)

        # 3b. Vernier alignment marks (imported from external GDS)
        self.create_vernier_marks(cell)

        # 4. Ground plane with all cutouts
        self.create_ground_plane(cell)

        # 5. Labels
        self.create_labels(cell)

        # Platinum layer components
        # 6. PRT serpentine thermometers
        self.create_prt_thermometers(cell)

        return cell

    def generate(self, output_dir: str = "output") -> Tuple[str, str]:
        """
        Generate complete chip design and export to GDS.

        Args:
            output_dir: Directory for output files

        Returns:
            Tuple of (inspect_path, prod_path)
        """
        # Create layout
        self.layout = pya.Layout()
        self.layout.dbu = self.chip.dbu

        # Register layers
        self.gold_layer_idx = self.layout.layer(self.layers.GOLD)
        self.platinum_layer_idx = self.layout.layer(self.layers.PLATINUM)

        # Print design parameters
        print("Design Parameters:")
        print(
            f"  Chip size:           {self.chip.chip_width:.0f} × {self.chip.chip_height:.0f} um"
        )
        print(
            f"  RF pad:              {self.gold.rf_pad_height:.0f} × {self.gold.rf_pad_width:.0f} um"
        )
        print(f"  CPW signal width:    {self.gold.cpw_signal_width:.0f} um")
        print(f"  CPW gap:             {self.gold.cpw_gap:.0f} um")
        print(f"  Taper length:        {self.gold.cpw_taper_length:.0f} um")
        print(f"  Snake trace width:   {self.gold.snake_trace_width:.0f} um")
        print(f"  Snake trace spacing: {self.gold.snake_trace_spacing:.0f} um")
        print(f"  Snake height:        {self.gold.snake_height:.0f} um")
        print(f"  Snake margin:        {self.gold.snake_margin:.0f} um")
        print(f"  Aperture radius:     {self.gold.aperture_radius:.0f} um")
        print()

        # Create chip
        print("Creating chip...")
        chip_cell = self.create_chip()
        print("  [OK] RF bond pads (left and right)")
        print("  [OK] CPW signal path with tapers")
        print("  [OK] Snake meander trace")
        print("  [OK] Ground plane with cutouts")
        print()

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Export hierarchical (inspect) version
        inspect_path = os.path.join(output_dir, "5x5mm_snake_chip_V1_inspect.gds")
        self.layout.write(inspect_path)
        print(f"[OK] Hierarchical design: {inspect_path}")

        # Export flattened (prod) version
        prod_path = os.path.join(output_dir, "5x5mm_snake_chip_V1_prod.gds")
        chip_cell.flatten(True)
        self.layout.write(prod_path)
        print(f"[OK] Production design: {prod_path}")

        return inspect_path, prod_path


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def main():
    """Generate V1 snake meander chip design."""
    print("=" * 70)
    print("5x5mm Snake Meander Chip V1 - Two-Layer Design")
    print("=" * 70)
    print()
    print("Layers:")
    print("  1/0 (Gold)     - CPW, Ground, Snake Meander (negative resist)")
    print("  2/0 (Platinum) - PRT Thermometer (positive resist)")
    print()

    # Create designer with default configuration
    designer = SnakeChipDesigner()

    # Generate design
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    inspect_path, prod_path = designer.generate(output_dir)

    print()
    print("Design generation complete!")
    print()
    print("V1 Snake Design Notes:")
    print("  - Gold layer uses NEGATIVE resist (exposure = no gold)")
    print("  - Dicing lanes are exposed (no gold between chips)")
    print("  - Snake meander replaces omega resonators")
    print("  - Rectangular meander with external entry/exit elbows")
    print("  - No DC access lines")
    print("  - CPW/taper moved outward from aperture")


if __name__ == "__main__":
    main()
