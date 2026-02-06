"""
6x6mm Sample Chip Design - Version 4

V4 Design Architecture:
-----------------------
Two-layer system for negative resist gold and positive resist platinum.

Layer 1/0 (Gold) - Negative Resist:
  - CPW signal lines and RF bond pads
  - Ground plane (drawn as "keep" regions)
  - DC contact pads (larger, more separated than V3)
  - Alignment marks
  - NOTE: Exposure = NO gold. Draw what you want to KEEP.

Layer 2/0 (Platinum) - Positive Resist:
  - PRT serpentine thermometer
  - PRT bond pads (larger than V3, further from DC contacts)
  - Ground plane separation between PRT and DC regions

Key V4 Changes from V3:
  - Dicing lanes are exposed (no gold between chips)
  - DC pads: 100 × 100 um, 150 um center spacing
  - PRT pads: 200 × 200 um (was 125 um)
  - PRT positioned further from DC contacts with ground separation

Author: Jeff Ahlers
Date: 2026-02-05
"""

import klayout.db as pya
import math
import os
from dataclasses import dataclass
from typing import Optional, Tuple, List


# =============================================================================
# CONFIGURATION CLASSES
# =============================================================================

@dataclass
class LayerConfig:
    """Layer definitions for V4 two-layer design."""
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
    chip_width: float = 6000.0      # um
    chip_height: float = 6000.0     # um
    
    # Dicing margins (exposed for gold removal)
    dicing_margin: float = 125.0    # um - no gold in this region
    
    # Database unit
    dbu: float = 0.001              # um per database unit


@dataclass 
class GoldLayerConfig:
    """Gold layer (1/0) design parameters - CPW, ground, DC contacts."""
    # RF Bond pads
    rf_pad_width: float = 600.0     # um (in Y direction)
    rf_pad_height: float = 800.0    # um (in X direction, along CPW)
    rf_pad_clearance: float = 50.0  # um from ground plane
    
    # CPW transmission line
    cpw_signal_width: float = 100.0 # um
    cpw_gap: float = 50.0           # um (each side)
    cpw_taper_length: float = 100.0 # um (taper from pad to CPW)
    
    # Central aperture (circular opening in ground plane)
    aperture_radius: float = 300.0  # um (adjustable per variant)
    
    # Omega resonator parameters
    omega_count: int = 4            # number of omega rings (arranged diagonally)
    omega_center_radius: float = 50.0  # um (center radius of omega ring)
    omega_trace_width: float = 8.0     # um (width of omega trace)
    omega_spacing: float = 50.0        # um (distance from center to ring center)
    omega_trace_gap: float = 25.0      # um (gap width to break ring loop)
    omega_taper_length: float = 100.0  # um (taper from CPW to omega trace width)
    omega_lateral_offset: float = 30.0      # um horizontal offset for diagonal arrangement
    # DC contact pads (larger than V3)
    dc_pad_size: float = 100.0      # um × um square
    dc_pad_spacing: float = 150.0   # um center-to-center
    dc_pad_count: int = 8           # number of DC pads per array
    dc_pad_y_offset: float = 1500.0 # um from chip center
    
    # Edge buffer for RF pads
    edge_buffer: float = 200.0      # um from chip edge to pad


@dataclass
class PlatinumConfig:
    """Platinum layer (2/0) design parameters - PRT thermometer."""
    # PRT bond pads (larger than V3)
    prt_pad_size: float = 200.0     # um × um square (was 125 um)
    
    # PRT serpentine trace
    prt_trace_width: float = 10.0   # um
    prt_trace_gap: float = 20.0     # um centerline-to-centerline
    
    # PRT region positioning (further from DC contacts)
    prt_region_width: float = 400.0 # um
    prt_region_height: float = 1200.0  # um
    prt_y_offset: float = 2000.0    # um from chip center (further than V3)
    
    # Ground plane separation
    prt_ground_clearance: float = 100.0  # um between PRT and DC regions


# =============================================================================
# CHIP DESIGNER CLASS
# =============================================================================

class ChipDesigner:
    """
    V4 Chip Designer for 6×6 mm sample chips.
    
    Generates two-layer design:
      - Gold (1/0): CPW, ground plane, DC contacts (negative resist)
      - Platinum (2/0): PRT thermometer (positive resist)
    """
    
    def __init__(self, 
                 chip_config: Optional[ChipConfig] = None,
                 gold_config: Optional[GoldLayerConfig] = None,
                 platinum_config: Optional[PlatinumConfig] = None,
                 layer_config: Optional[LayerConfig] = None):
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
        Create RF bond pads on gold layer (left and right sides).
        
        Pads are rectangular, positioned at chip edges with edge_buffer clearance.
        
        Returns:
            Tuple of (left_pad_right_edge_x, right_pad_left_edge_x) for taper connections
        """
        chip_cx = self.chip.chip_width / 2.0
        chip_cy = self.chip.chip_height / 2.0
        
        # Left pad: positioned at left edge
        left_pad_x = self.gold.edge_buffer  # left edge of pad
        left_pad_box = pya.Box(
            self._um_to_dbu(left_pad_x),
            self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0),
            self._um_to_dbu(left_pad_x + self.gold.rf_pad_height),
            self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0)
        )
        cell.shapes(self.gold_layer_idx).insert(left_pad_box)
        
        # Right pad: positioned at right edge
        right_pad_x = self.chip.chip_width - self.gold.edge_buffer - self.gold.rf_pad_height
        right_pad_box = pya.Box(
            self._um_to_dbu(right_pad_x),
            self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0),
            self._um_to_dbu(right_pad_x + self.gold.rf_pad_height),
            self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0)
        )
        cell.shapes(self.gold_layer_idx).insert(right_pad_box)
        
        # Return pad edges for taper connections
        left_pad_right_x = left_pad_x + self.gold.rf_pad_height
        right_pad_left_x = right_pad_x
        
        return left_pad_right_x, right_pad_left_x
    
    def create_cpw_signal_path(self, cell: pya.Cell, 
                               left_pad_right_x: float, 
                               right_pad_left_x: float) -> None:
        """
        Create CPW signal line with tapers connecting pads to omegas.
        
        Signal path: Left Pad → Taper → CPW → Omegas → CPW → Taper → Right Pad
        
        Args:
            left_pad_right_x: x-coordinate of left pad's right edge
            right_pad_left_x: x-coordinate of right pad's left edge
        """
        chip_cx = self.chip.chip_width / 2.0
        chip_cy = self.chip.chip_height / 2.0
        
        # Calculate key x-positions
        left_taper_start_x = left_pad_right_x
        left_taper_end_x = left_taper_start_x + self.gold.cpw_taper_length
        
        right_taper_end_x = right_pad_left_x
        right_taper_start_x = right_taper_end_x - self.gold.cpw_taper_length
        
        # CPW ends at aperture edge
        left_cpw_end_x = chip_cx - self.gold.aperture_radius
        right_cpw_start_x = chip_cx + self.gold.aperture_radius
        
        # --- Left Taper (pad width → CPW width) ---
        left_taper = pya.Polygon([
            pya.Point(self._um_to_dbu(left_taper_start_x), 
                     self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0)),
            pya.Point(self._um_to_dbu(left_taper_start_x), 
                     self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0)),
            pya.Point(self._um_to_dbu(left_taper_end_x), 
                     self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0)),
            pya.Point(self._um_to_dbu(left_taper_end_x), 
                     self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0)),
        ])
        cell.shapes(self.gold_layer_idx).insert(left_taper)
        
        # --- Left CPW section (taper to aperture) ---
        if left_cpw_end_x > left_taper_end_x:
            left_cpw = pya.Box(
                self._um_to_dbu(left_taper_end_x),
                self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0),
                self._um_to_dbu(left_cpw_end_x),
                self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0)
            )
            cell.shapes(self.gold_layer_idx).insert(left_cpw)
        
        # --- Right CPW section (aperture to taper) ---
        if right_cpw_start_x < right_taper_start_x:
            right_cpw = pya.Box(
                self._um_to_dbu(right_cpw_start_x),
                self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0),
                self._um_to_dbu(right_taper_start_x),
                self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0)
            )
            cell.shapes(self.gold_layer_idx).insert(right_cpw)
        
        # --- Right Taper (CPW width → pad width) ---
        right_taper = pya.Polygon([
            pya.Point(self._um_to_dbu(right_taper_start_x), 
                     self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0)),
            pya.Point(self._um_to_dbu(right_taper_start_x), 
                     self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0)),
            pya.Point(self._um_to_dbu(right_taper_end_x), 
                     self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0)),
            pya.Point(self._um_to_dbu(right_taper_end_x), 
                     self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0)),
        ])
        cell.shapes(self.gold_layer_idx).insert(right_taper)
        
        # --- Create 4 Omega Resonators in center ---
        self.create_omega_resonators(cell, chip_cx, chip_cy)
    
    def create_omega_resonators(self, cell: pya.Cell, cx: float, cy: float) -> None:
        """
        Create 4 omega resonators arranged diagonally at chip center.
        
        Layout (V3-style):
        - 4 rings at diagonal positions from center
        - Top rings have gap at bottom, bottom rings have gap at top
        - Vertical connections between top/bottom pairs
        - Feed lines connect to horizontal CPW
        - Tapers from CPW signal width to omega trace width
        
        Args:
            cx: x-coordinate of chip center (um)
            cy: y-coordinate of chip center (um)
        """
        trace_width = self.gold.omega_trace_width
        center_radius = self.gold.omega_center_radius
        spacing = self.gold.omega_spacing
        trace_gap = self.gold.omega_trace_gap
        
        # Calculate inner and outer radii
        outer_radius = center_radius + trace_width / 2.0
        inner_radius = center_radius - trace_width / 2.0
        
        # Distance from center to each ring center (along diagonal)
        offset = outer_radius + spacing
        
        # Horizontal offset for top/bottom rings (for the gap alignment)
        h_offset = self.gold.omega_lateral_offset
        
        # Four diagonal positions with horizontal offsets
        # Top rings offset left, bottom rings offset right
        positions = [
            (cx + offset - h_offset, cy + offset, 'bottom'),  # Top-right, gap at bottom
            (cx - offset - h_offset, cy + offset, 'bottom'),  # Top-left, gap at bottom
            (cx - offset + h_offset, cy - offset, 'top'),     # Bottom-left, gap at top
            (cx + offset + h_offset, cy - offset, 'top'),     # Bottom-right, gap at top
        ]
        
        num_segments = 64
        
        for ring_cx, ring_cy, ring_type in positions:
            # Create outer circle points
            outer_points = []
            for i in range(num_segments):
                angle = 2.0 * math.pi * i / num_segments
                x = ring_cx + outer_radius * math.cos(angle)
                y = ring_cy + outer_radius * math.sin(angle)
                outer_points.append(pya.Point(self._um_to_dbu(x), self._um_to_dbu(y)))
            outer_polygon = pya.Polygon(outer_points)
            outer_region = pya.Region(outer_polygon)
            
            # Create inner circle points
            inner_points = []
            for i in range(num_segments):
                angle = 2.0 * math.pi * i / num_segments
                x = ring_cx + inner_radius * math.cos(angle)
                y = ring_cy + inner_radius * math.sin(angle)
                inner_points.append(pya.Point(self._um_to_dbu(x), self._um_to_dbu(y)))
            inner_polygon = pya.Polygon(inner_points)
            inner_region = pya.Region(inner_polygon)
            
            # Subtract inner from outer to create ring
            ring_region = outer_region - inner_region
            
            # Create gap rectangle to break the loop
            if ring_type == 'top':
                # Gap at top of ring
                gap_box = pya.Box(
                    self._um_to_dbu(ring_cx - trace_gap / 2.0),
                    self._um_to_dbu(ring_cy),
                    self._um_to_dbu(ring_cx + trace_gap / 2.0),
                    self._um_to_dbu(ring_cy + outer_radius + trace_width)
                )
            else:
                # Gap at bottom of ring
                gap_box = pya.Box(
                    self._um_to_dbu(ring_cx - trace_gap / 2.0),
                    self._um_to_dbu(ring_cy - outer_radius - trace_width),
                    self._um_to_dbu(ring_cx + trace_gap / 2.0),
                    self._um_to_dbu(ring_cy)
                )
            
            ring_region -= pya.Region(gap_box)
            cell.shapes(self.gold_layer_idx).insert(ring_region)
        
        # --- Signal Path (left to right): ---
        # 1. CPW left → UP+x to top-left omega
        # 2. Top-left → DOWN+x (left pair connection) to bottom-left omega
        # 3. Bottom-left → UP+x to middle trace
        # 4. Middle trace → UP+x to top-right omega
        # 5. Top-right → DOWN+x (right pair connection) to bottom-right omega
        # 6. Bottom-right → UP+x to CPW right
        
        # Ring center positions (matching the positions array above)
        top_left_ring_cx = cx - offset - h_offset
        top_left_ring_cy = cy + offset
        
        bottom_left_ring_cx = cx - offset + h_offset
        bottom_left_ring_cy = cy - offset
        
        top_right_ring_cx = cx + offset - h_offset
        top_right_ring_cy = cy + offset
        
        bottom_right_ring_cx = cx + offset + h_offset
        bottom_right_ring_cy = cy - offset
        
        # Gap positions are at ring center X, and at edge of ring Y
        # Top rings have gaps at BOTTOM (cy - outer_radius)
        # Bottom rings have gaps at TOP (cy + outer_radius)
        # Each gap has LEFT side (input) and RIGHT side (output) separated by trace_gap
        
        # Gap center positions
        top_left_gap_center_x = top_left_ring_cx
        top_left_gap_y = top_left_ring_cy - outer_radius + trace_width / 2.0
        
        bottom_left_gap_center_x = bottom_left_ring_cx
        bottom_left_gap_y = bottom_left_ring_cy + outer_radius - trace_width / 2.0
        
        top_right_gap_center_x = top_right_ring_cx
        top_right_gap_y = top_right_ring_cy - outer_radius + trace_width / 2.0
        
        bottom_right_gap_center_x = bottom_right_ring_cx
        bottom_right_gap_y = bottom_right_ring_cy + outer_radius - trace_width / 2.0
        
        # Gap half-width for input/output side offsets
        gap_shift = trace_gap/2+trace_width/2
        
        # Tilt offset - how much x shifts per vertical distance
        tilt_x = h_offset  # Use same as horizontal offset for consistent angle
        
        # --- Connection 1: CPW left → UP+x to top-left omega INPUT (left side of gap) ---
        # Starts at center level (cy), goes UP to top-left ring gap LEFT side, tilting +x
        feed1_bottom_x = top_left_gap_center_x - gap_shift - tilt_x  # Bottom shifted -x (so going up shifts +x)
        feed1_bottom_y = cy-trace_width/2
        feed1_top_x = top_left_gap_center_x - gap_shift  # Left side of gap (input)
        feed1_top_y = top_left_gap_y
        
        feed1_poly = pya.Polygon([
            pya.Point(self._um_to_dbu(feed1_bottom_x - trace_width / 2.0), 
                     self._um_to_dbu(feed1_bottom_y)),
            pya.Point(self._um_to_dbu(feed1_bottom_x + trace_width / 2.0), 
                     self._um_to_dbu(feed1_bottom_y)),
            pya.Point(self._um_to_dbu(feed1_top_x + trace_width / 2.0), 
                     self._um_to_dbu(feed1_top_y)),
            pya.Point(self._um_to_dbu(feed1_top_x - trace_width / 2.0), 
                     self._um_to_dbu(feed1_top_y)),
        ])
        cell.shapes(self.gold_layer_idx).insert(feed1_poly)
        
        # --- Connection 2: Top-left OUTPUT → DOWN+x to bottom-left INPUT (left pair) ---
        # Goes from top-left ring gap RIGHT side DOWN to bottom-left ring gap LEFT side, tilting +x
        conn2_top_x = top_left_gap_center_x + gap_shift  # Right side of top-left gap (output)
        conn2_top_y = top_left_gap_y
        conn2_bottom_x = bottom_left_gap_center_x - gap_shift  # Left side of bottom-left gap (input)
        conn2_bottom_y = bottom_left_gap_y
        
        conn2_poly = pya.Polygon([
            pya.Point(self._um_to_dbu(conn2_top_x - trace_width / 2.0), 
                     self._um_to_dbu(conn2_top_y)),
            pya.Point(self._um_to_dbu(conn2_top_x + trace_width / 2.0), 
                     self._um_to_dbu(conn2_top_y)),
            pya.Point(self._um_to_dbu(conn2_bottom_x + trace_width / 2.0), 
                     self._um_to_dbu(conn2_bottom_y)),
            pya.Point(self._um_to_dbu(conn2_bottom_x - trace_width / 2.0), 
                     self._um_to_dbu(conn2_bottom_y)),
        ])
        cell.shapes(self.gold_layer_idx).insert(conn2_poly)
        
        # --- Connection 3: Bottom-left OUTPUT → UP+x to middle trace ---
        # Goes from bottom-left ring gap RIGHT side UP to center level, tilting +x
        feed3_bottom_x = bottom_left_gap_center_x + gap_shift  # Right side of gap (output)
        feed3_bottom_y = bottom_left_gap_y
        feed3_top_x = bottom_left_gap_center_x + gap_shift + tilt_x  # +x as we go up
        feed3_top_y = cy+trace_width/2
        
        feed3_poly = pya.Polygon([
            pya.Point(self._um_to_dbu(feed3_bottom_x - trace_width / 2.0), 
                     self._um_to_dbu(feed3_bottom_y)),
            pya.Point(self._um_to_dbu(feed3_bottom_x + trace_width / 2.0), 
                     self._um_to_dbu(feed3_bottom_y)),
            pya.Point(self._um_to_dbu(feed3_top_x + trace_width / 2.0), 
                     self._um_to_dbu(feed3_top_y)),
            pya.Point(self._um_to_dbu(feed3_top_x - trace_width / 2.0), 
                     self._um_to_dbu(feed3_top_y)),
        ])
        cell.shapes(self.gold_layer_idx).insert(feed3_poly)
        
        # --- Connection 4: Middle trace → UP+x to top-right omega INPUT (left side of gap) ---
        # Goes from center level UP to top-right ring gap LEFT side, tilting +x
        feed4_bottom_x = top_right_gap_center_x - gap_shift - tilt_x  # -x at bottom (so going up shifts +x)
        feed4_bottom_y = cy-trace_width/2
        feed4_top_x = top_right_gap_center_x - gap_shift  # Left side of gap (input)
        feed4_top_y = top_right_gap_y
        
        feed4_poly = pya.Polygon([
            pya.Point(self._um_to_dbu(feed4_bottom_x - trace_width / 2.0), 
                     self._um_to_dbu(feed4_bottom_y)),
            pya.Point(self._um_to_dbu(feed4_bottom_x + trace_width / 2.0), 
                     self._um_to_dbu(feed4_bottom_y)),
            pya.Point(self._um_to_dbu(feed4_top_x + trace_width / 2.0), 
                     self._um_to_dbu(feed4_top_y)),
            pya.Point(self._um_to_dbu(feed4_top_x - trace_width / 2.0), 
                     self._um_to_dbu(feed4_top_y)),
        ])
        cell.shapes(self.gold_layer_idx).insert(feed4_poly)
        
        # --- Connection 5: Top-right OUTPUT → DOWN+x to bottom-right INPUT (right pair) ---
        # Goes from top-right ring gap RIGHT side DOWN to bottom-right ring gap LEFT side, tilting +x
        conn5_top_x = top_right_gap_center_x + gap_shift  # Right side of top-right gap (output)
        conn5_top_y = top_right_gap_y
        conn5_bottom_x = bottom_right_gap_center_x - gap_shift  # Left side of bottom-right gap (input)
        conn5_bottom_y = bottom_right_gap_y
        
        conn5_poly = pya.Polygon([
            pya.Point(self._um_to_dbu(conn5_top_x - trace_width / 2.0), 
                     self._um_to_dbu(conn5_top_y)),
            pya.Point(self._um_to_dbu(conn5_top_x + trace_width / 2.0), 
                     self._um_to_dbu(conn5_top_y)),
            pya.Point(self._um_to_dbu(conn5_bottom_x + trace_width / 2.0), 
                     self._um_to_dbu(conn5_bottom_y)),
            pya.Point(self._um_to_dbu(conn5_bottom_x - trace_width / 2.0), 
                     self._um_to_dbu(conn5_bottom_y)),
        ])
        cell.shapes(self.gold_layer_idx).insert(conn5_poly)
        
        # --- Connection 6: Bottom-right OUTPUT → UP+x to CPW right ---
        # Goes from bottom-right ring gap RIGHT side UP to center level, tilting +x
        feed6_bottom_x = bottom_right_gap_center_x + gap_shift  # Right side of gap (output)
        feed6_bottom_y = bottom_right_gap_y
        feed6_top_x = bottom_right_gap_center_x + gap_shift + tilt_x  # +x as we go up
        feed6_top_y = cy+trace_width/2
        
        feed6_poly = pya.Polygon([
            pya.Point(self._um_to_dbu(feed6_bottom_x - trace_width/2), 
                     self._um_to_dbu(feed6_bottom_y)),
            pya.Point(self._um_to_dbu(feed6_bottom_x + trace_width/2), 
                     self._um_to_dbu(feed6_bottom_y)),
            pya.Point(self._um_to_dbu(feed6_top_x + trace_width/2), 
                     self._um_to_dbu(feed6_top_y)),
            pya.Point(self._um_to_dbu(feed6_top_x - trace_width/2), 
                     self._um_to_dbu(feed6_top_y)),
        ])
        cell.shapes(self.gold_layer_idx).insert(feed6_poly)
        
        # --- Horizontal connectors at center level ---
        # Left CPW to feed1 bottom (overlaps with middle trace and feed1)
        cpw_end_left = cx - self.gold.aperture_radius
        left_cpw_box = pya.Box(
            self._um_to_dbu(cpw_end_left),
            self._um_to_dbu(cy - trace_width / 2.0),
            self._um_to_dbu(feed1_bottom_x + trace_width / 2.0),
            self._um_to_dbu(cy + trace_width / 2.0)
        )
        cell.shapes(self.gold_layer_idx).insert(left_cpw_box)
        
        # Right CPW from feed6 top (overlaps with feed6)
        cpw_end_right = cx + self.gold.aperture_radius
        right_cpw_box = pya.Box(
            self._um_to_dbu(feed6_top_x - trace_width / 2.0),
            self._um_to_dbu(cy - trace_width / 2.0),
            self._um_to_dbu(cpw_end_right),
            self._um_to_dbu(cy + trace_width / 2.0)
        )
        cell.shapes(self.gold_layer_idx).insert(right_cpw_box)
        
        # Middle connector (feed3 top to feed4 bottom at center level)
        middle_conn_box = pya.Box(
            self._um_to_dbu(feed3_top_x - trace_width / 2.0),
            self._um_to_dbu(cy - trace_width / 2.0),
            self._um_to_dbu(feed4_bottom_x + trace_width / 2.0),
            self._um_to_dbu(cy + trace_width / 2.0)
        )
        cell.shapes(self.gold_layer_idx).insert(middle_conn_box)
        
        # --- Tapers from CPW signal width to omega trace width ---
        taper_length = self.gold.omega_taper_length
        cpw_width = self.gold.cpw_signal_width
        
        # Left taper (CPW → omega trace)
        left_taper = pya.Polygon([
            pya.Point(self._um_to_dbu(cpw_end_left), 
                     self._um_to_dbu(cy - cpw_width / 2.0)),
            pya.Point(self._um_to_dbu(cpw_end_left + taper_length), 
                     self._um_to_dbu(cy - trace_width / 2.0)),
            pya.Point(self._um_to_dbu(cpw_end_left + taper_length), 
                     self._um_to_dbu(cy + trace_width / 2.0)),
            pya.Point(self._um_to_dbu(cpw_end_left), 
                     self._um_to_dbu(cy + cpw_width / 2.0)),
        ])
        cell.shapes(self.gold_layer_idx).insert(left_taper)
        
        # Right taper (omega trace → CPW)
        right_taper = pya.Polygon([
            pya.Point(self._um_to_dbu(cpw_end_right - taper_length), 
                     self._um_to_dbu(cy - trace_width / 2.0)),
            pya.Point(self._um_to_dbu(cpw_end_right), 
                     self._um_to_dbu(cy - cpw_width / 2.0)),
            pya.Point(self._um_to_dbu(cpw_end_right), 
                     self._um_to_dbu(cy + cpw_width / 2.0)),
            pya.Point(self._um_to_dbu(cpw_end_right - taper_length), 
                     self._um_to_dbu(cy + trace_width / 2.0)),
        ])
        cell.shapes(self.gold_layer_idx).insert(right_taper)
    
    def create_dc_contacts(self, cell: pya.Cell, y_offset: float) -> None:
        """Create DC contact pad array on gold layer."""
        # TODO: Implement DC contact pads
        pass
    
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
        ground_region = pya.Region(pya.Box(
            self._um_to_dbu(self.chip.dicing_margin),
            self._um_to_dbu(self.chip.dicing_margin),
            self._um_to_dbu(self.chip.chip_width - self.chip.dicing_margin),
            self._um_to_dbu(self.chip.chip_height - self.chip.dicing_margin)
        ))
        
        # === SUBTRACT RF BOND PADS WITH CLEARANCE ===
        # Left pad position
        left_pad_x = self.gold.edge_buffer
        left_pad_box = pya.Box(
            self._um_to_dbu(left_pad_x - pad_clearance),
            self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0 - pad_clearance),
            self._um_to_dbu(left_pad_x + self.gold.rf_pad_height + pad_clearance),
            self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0 + pad_clearance)
        )
        ground_region -= pya.Region(left_pad_box)
        
        # Right pad position
        right_pad_x = self.chip.chip_width - self.gold.edge_buffer - self.gold.rf_pad_height
        right_pad_box = pya.Box(
            self._um_to_dbu(right_pad_x - pad_clearance),
            self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0 - pad_clearance),
            self._um_to_dbu(right_pad_x + self.gold.rf_pad_height + pad_clearance),
            self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0 + pad_clearance)
        )
        ground_region -= pya.Region(right_pad_box)
        
        # === SUBTRACT LEFT TAPER GAP (pad width → CPW width) ===
        # Start taper at pad edge (aligned with signal taper)
        left_taper_start_x = left_pad_x + self.gold.rf_pad_height
        left_taper_end_x = left_taper_start_x + self.gold.cpw_taper_length
        
        # Top gap taper (wide at pad, narrow at CPW)
        left_gap_top = pya.Polygon([
            pya.Point(self._um_to_dbu(left_taper_start_x),
                     self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0 + pad_clearance)),
            pya.Point(self._um_to_dbu(left_taper_end_x),
                     self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0 + gap)),
            pya.Point(self._um_to_dbu(left_taper_end_x),
                     self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0)),
            pya.Point(self._um_to_dbu(left_taper_start_x),
                     self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0)),
        ])
        ground_region -= pya.Region(left_gap_top)
        
        # Bottom gap taper (symmetric)
        left_gap_bot = pya.Polygon([
            pya.Point(self._um_to_dbu(left_taper_start_x),
                     self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0 - pad_clearance)),
            pya.Point(self._um_to_dbu(left_taper_end_x),
                     self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0 - gap)),
            pya.Point(self._um_to_dbu(left_taper_end_x),
                     self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0)),
            pya.Point(self._um_to_dbu(left_taper_start_x),
                     self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0)),
        ])
        ground_region -= pya.Region(left_gap_bot)
        
        # === SUBTRACT LEFT CPW SECTION (taper end to aperture) ===
        cpw_end_left = chip_cx - self.gold.aperture_radius
        left_cpw_box = pya.Box(
            self._um_to_dbu(left_taper_end_x),
            self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0 - gap),
            self._um_to_dbu(cpw_end_left),
            self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0 + gap)
        )
        ground_region -= pya.Region(left_cpw_box)
        
        # === SUBTRACT RIGHT CPW SECTION (aperture to taper) ===
        cpw_end_right = chip_cx + self.gold.aperture_radius
        # Taper ends at pad edge (aligned with signal taper)
        right_taper_end_x = self.chip.chip_width - self.gold.edge_buffer - self.gold.rf_pad_height
        right_taper_start_x = right_taper_end_x - self.gold.cpw_taper_length
        right_cpw_box = pya.Box(
            self._um_to_dbu(cpw_end_right),
            self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0 - gap),
            self._um_to_dbu(right_taper_start_x),
            self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0 + gap)
        )
        ground_region -= pya.Region(right_cpw_box)
        
        # === SUBTRACT RIGHT TAPER GAP (CPW width → pad width) ===
        # Top gap taper (narrow at CPW, wide at pad)
        right_gap_top = pya.Polygon([
            pya.Point(self._um_to_dbu(right_taper_start_x),
                     self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0 + gap)),
            pya.Point(self._um_to_dbu(right_taper_end_x),
                     self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0 + pad_clearance)),
            pya.Point(self._um_to_dbu(right_taper_end_x),
                     self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0)),
            pya.Point(self._um_to_dbu(right_taper_start_x),
                     self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0)),
        ])
        ground_region -= pya.Region(right_gap_top)
        
        # Bottom gap taper (symmetric)
        right_gap_bot = pya.Polygon([
            pya.Point(self._um_to_dbu(right_taper_start_x),
                     self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0 - gap)),
            pya.Point(self._um_to_dbu(right_taper_end_x),
                     self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0 - pad_clearance)),
            pya.Point(self._um_to_dbu(right_taper_end_x),
                     self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0)),
            pya.Point(self._um_to_dbu(right_taper_start_x),
                     self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0)),
        ])
        ground_region -= pya.Region(right_gap_bot)
        
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
        
        # Merge and insert ground plane
        ground_region.merge()
        cell.shapes(self.gold_layer_idx).insert(ground_region)
    
    # -------------------------------------------------------------------------
    # PLATINUM LAYER COMPONENTS
    # -------------------------------------------------------------------------
    
    def create_prt_thermometer(self, cell: pya.Cell, y_offset: float) -> None:
        """Create PRT serpentine thermometer on platinum layer."""
        # TODO: Implement PRT thermometer
        pass
    
    # -------------------------------------------------------------------------
    # SHARED COMPONENTS
    # -------------------------------------------------------------------------
    
    def create_alignment_marks(self, cell: pya.Cell) -> None:
        """Create alignment marks on both layers."""
        # TODO: Implement alignment marks
        pass
    
    # -------------------------------------------------------------------------
    # MAIN GENERATION
    # -------------------------------------------------------------------------
    
    def create_chip(self, name: str = "chip_V4") -> pya.Cell:
        """
        Create complete chip design.
        
        Args:
            name: Cell name for the chip
            
        Returns:
            pya.Cell containing complete chip design
        """
        cell = self.layout.create_cell(name)
        
        # Gold layer components
        # 1. Create RF bond pads (returns pad edge positions for taper connections)
        left_pad_right_x, right_pad_left_x = self.create_rf_bond_pads(cell)
        
        # 2. Create CPW signal path with tapers and omega resonators
        self.create_cpw_signal_path(cell, left_pad_right_x, right_pad_left_x)
        
        # 3. DC contacts (TODO)
        self.create_dc_contacts(cell, self.gold.dc_pad_y_offset)   # Top
        self.create_dc_contacts(cell, -self.gold.dc_pad_y_offset)  # Bottom
        
        # 4. Ground plane (TODO)
        self.create_ground_plane(cell)
        
        # Platinum layer components (TODO)
        self.create_prt_thermometer(cell, self.platinum.prt_y_offset)   # Top
        self.create_prt_thermometer(cell, -self.platinum.prt_y_offset)  # Bottom
        
        # Alignment marks (TODO)
        self.create_alignment_marks(cell)
        
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
        print(f"  Chip size:         {self.chip.chip_width:.0f} × {self.chip.chip_height:.0f} um")
        print(f"  RF pad:            {self.gold.rf_pad_height:.0f} × {self.gold.rf_pad_width:.0f} um")
        print(f"  CPW signal width:  {self.gold.cpw_signal_width:.0f} um")
        print(f"  CPW gap:           {self.gold.cpw_gap:.0f} um")
        print(f"  Taper length:      {self.gold.cpw_taper_length:.0f} um")
        print(f"  Omega count:       {self.gold.omega_count}")
        print(f"  Omega radius:      {self.gold.omega_center_radius:.0f} um (innermost)")
        print(f"  Omega trace width: {self.gold.omega_trace_width:.0f} um")
        print(f"  Omega spacing:     {self.gold.omega_spacing:.0f} um")
        print(f"  Aperture radius:   {self.gold.aperture_radius:.0f} um")
        print()
        
        # Create chip
        print("Creating chip...")
        chip_cell = self.create_chip()
        print(f"  [OK] RF bond pads (left and right)")
        print(f"  [OK] CPW signal path with tapers")
        print(f"  [OK] {self.gold.omega_count} omega resonators")
        print(f"  [OK] Ground plane with cutouts")
        print()
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Export hierarchical (inspect) version
        inspect_path = os.path.join(output_dir, "6x6mm_sample_chip_V4_inspect.gds")
        self.layout.write(inspect_path)
        print(f"[OK] Hierarchical design: {inspect_path}")
        
        # Export flattened (prod) version
        prod_path = os.path.join(output_dir, "6x6mm_sample_chip_V4_prod.gds")
        chip_cell.flatten(True)
        self.layout.write(prod_path)
        print(f"[OK] Production design: {prod_path}")
        
        return inspect_path, prod_path


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Generate V4 chip design."""
    print("=" * 70)
    print("6x6mm Sample Chip V4 - Two-Layer Design")
    print("=" * 70)
    print()
    print("Layers:")
    print("  1/0 (Gold)     - CPW, Ground, DC Contacts (negative resist)")
    print("  2/0 (Platinum) - PRT Thermometer (positive resist)")
    print()
    
    # Create designer with default configuration
    designer = ChipDesigner()
    
    # Generate design
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    inspect_path, prod_path = designer.generate(output_dir)
    
    print()
    print("Design generation complete!")
    print()
    print("V4 Design Notes:")
    print("  - Gold layer uses NEGATIVE resist (exposure = no gold)")
    print("  - Dicing lanes are exposed (no gold between chips)")
    print("  - DC pads are larger and more separated")
    print("  - PRT pads are larger and further from DC contacts")


if __name__ == "__main__":
    main()
