"""
5x5mm Sample Chip Design - Version 4

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
from typing import Optional, Tuple


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
    chip_width: float = 5000.0      # um
    chip_height: float = 5000.0     # um
    
    # Dicing margins (exposed for gold removal)
    dicing_margin: float = 150.0    # um - no gold in this region
    
    # Database unit
    dbu: float = 0.001              # um per database unit


@dataclass 
class GoldLayerConfig:
    """Gold layer (1/0) design parameters - CPW, ground, DC contacts."""
    # RF Bond pads
    rf_pad_width: float = 800.0     # um (in Y direction)
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
    omega_taper_length: float = 250.0  # um (taper from CPW to omega trace width)
    omega_taper_cpw_inset: float = 150.0    # um how far taper starts into CPW (before aperture edge)
    omega_lateral_offset: float = 30.0      # um horizontal offset for diagonal arrangement
    
    # DC access system (above and below aperture, mirrored ±Y)
    # All Y offsets are from chip center; geometry is mirrored to both sides.
    #
    # --- Cutout rectangle (ground plane opening) ---
    dc_cutout_cy: float = 1400.0        # um from chip center to cutout center Y
    dc_cutout_width: float = 2100.0     # um
    dc_cutout_height: float = 500.0     # um
    dc_cutout_aperture_width: float = 50.0  # um width where cutout goes vertical
    dc_cutout_taper_angle: float = 50.0      # degrees from vertical for cutout taper
    
    # --- DC bond pads ---
    dc_pad_cy: float = 1400.0          # um from chip center to innermost pad center Y
    dc_pad_width: float = 250.0        # um
    dc_pad_height: float = 250.0       # um
    dc_pad_count: int = 6              # pads per side
    dc_pad_pitch: float = 350.0        # um X spacing center-to-center
    dc_pad_stagger: float = 0.0      # um max Y offset (outer pads shift toward chip center)
    
    # --- Taper (pad bottom → feedline) ---
    dc_taper_height: float = 200.0     # um vertical extent
    dc_taper_angle: float = 25.0       # degrees from vertical (X shift of narrow end)
    
    # --- Feedlines (taper tip → vertical → through aperture → fan-out) ---
    dc_feedline_width: float = 10.0    # um trace width
    dc_feedline_pitch: float = 20.0    # um X spacing at vertical section and beyond
    dc_feedline_clearance: float = 15.0  # um ground plane gap around feedlines
    dc_feedline_vertical_cy: float = 500.0  # um from chip center where feedlines go vertical
    
    # --- Fan-out (inside aperture) ---
    dc_fanout_straight: float = 40.0   # um vertical run inside aperture before fan-out
    dc_fanout_height: float = 60.0     # um total penetration past aperture edge
    dc_fanout_pitch: float = 36.0      # um X spacing at fan-out tips
    
    # Alignment marks
    alignment_mark_offset: float = 1500.0   # um from chip center (placed at ±offset, ±offset)
    alignment_mark_size: float = 250.0      # um cross arm length
    alignment_mark_width: float = 20.0      # um cross arm trace width
    
    # Edge buffer for RF pads
    edge_buffer: float = 200.0      # um from chip edge to pad


@dataclass
class PlatinumConfig:
    """Platinum layer (2/0) design parameters - PRT thermometer."""
    # Overall feature dimensions
    prt_width: float = 4600.0       # um total length (X)
    prt_height: float = 420.0       # um total height (Y)
    prt_cy: float = 2100.0          # um from chip center (placed at ±cy)
    
    # Bond pads at each end
    prt_pad_width: float = 700.0    # um (X extent)
    prt_pad_height: float = prt_height   # um (Y extent, matches prt_height)
    
    # Serpentine trace
    prt_trace_width: float = 8.0   # um line width
    prt_trace_spacing: float = 10.0 # um gap between lines
    prt_pad_spacing: float = 50.0   # um gap between Au bond pad and Pt serpentine


# =============================================================================
# CHIP DESIGNER CLASS
# =============================================================================

class ChipDesigner:
    """
    V4 Chip Designer for 5×5 mm sample chips.
    
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
        left_pad_with_taper = pya.Polygon([
            # Rectangular pad portion (counter-clockwise from bottom-left)
            pya.Point(self._um_to_dbu(left_pad_x),
                     self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0)),
            pya.Point(self._um_to_dbu(left_pad_x),
                     self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0)),
            # Taper portion (continues from top of pad to narrow CPW end)
            pya.Point(self._um_to_dbu(left_pad_right_x),
                     self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0)),
            pya.Point(self._um_to_dbu(left_taper_end_x),
                     self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0)),
            pya.Point(self._um_to_dbu(left_taper_end_x),
                     self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0)),
            pya.Point(self._um_to_dbu(left_pad_right_x),
                     self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0)),
        ])
        cell.shapes(self.gold_layer_idx).insert(left_pad_with_taper)
        
        # Right pad: positioned at right edge with integrated taper
        right_pad_x = self.chip.chip_width - self.gold.edge_buffer - self.gold.rf_pad_height
        right_taper_start_x = right_pad_x - self.gold.cpw_taper_length
        
        # Combined right pad + taper polygon (6 vertices)
        right_pad_with_taper = pya.Polygon([
            # Taper portion (starts narrow at CPW, widens to pad)
            pya.Point(self._um_to_dbu(right_taper_start_x),
                     self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0)),
            pya.Point(self._um_to_dbu(right_taper_start_x),
                     self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0)),
            pya.Point(self._um_to_dbu(right_pad_x),
                     self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0)),
            # Rectangular pad portion
            pya.Point(self._um_to_dbu(right_pad_x + self.gold.rf_pad_height),
                     self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0)),
            pya.Point(self._um_to_dbu(right_pad_x + self.gold.rf_pad_height),
                     self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0)),
            pya.Point(self._um_to_dbu(right_pad_x),
                     self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0)),
        ])
        cell.shapes(self.gold_layer_idx).insert(right_pad_with_taper)
        
        # Return taper end positions for CPW connections
        return left_taper_end_x, right_taper_start_x
    
    def create_cpw_signal_path(self, cell: pya.Cell, 
                               left_taper_end_x: float, 
                               right_taper_start_x: float) -> None:
        """
        Create CPW signal line sections connecting bond pad tapers to omega resonators.
        
        Signal path: Left Pad+Taper → CPW → Omegas → CPW → Taper+Right Pad
        
        Note: Pad-to-CPW tapers are now integrated into create_rf_bond_pads().
        This function creates only the CPW sections between tapers and aperture.
        
        Args:
            left_taper_end_x: x-coordinate where left taper ends (CPW starts)
            right_taper_start_x: x-coordinate where right taper starts (CPW ends)
        """
        chip_cx = self.chip.chip_width / 2.0
        chip_cy = self.chip.chip_height / 2.0
        
        # CPW ends where the omega taper wide end starts (inset from aperture edge)
        left_cpw_end_x = chip_cx - self.gold.aperture_radius - self.gold.omega_taper_cpw_inset
        right_cpw_start_x = chip_cx + self.gold.aperture_radius + self.gold.omega_taper_cpw_inset
        
        # --- Left CPW section (from taper end to aperture) ---
        if left_cpw_end_x > left_taper_end_x:
            left_cpw = pya.Box(
                self._um_to_dbu(left_taper_end_x),
                self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0),
                self._um_to_dbu(left_cpw_end_x),
                self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0)
            )
            cell.shapes(self.gold_layer_idx).insert(left_cpw)
        
        # --- Right CPW section (from aperture to taper start) ---
        if right_cpw_start_x < right_taper_start_x:
            right_cpw = pya.Box(
                self._um_to_dbu(right_cpw_start_x),
                self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0),
                self._um_to_dbu(right_taper_start_x),
                self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0)
            )
            cell.shapes(self.gold_layer_idx).insert(right_cpw)
        
        # --- Create Omega Resonators in center (if any) ---
        if self.gold.omega_count > 0:
            self.create_omega_resonators(cell, chip_cx, chip_cy)
        else:
            # No omegas: draw tapers from CPW width that taper down and end
            taper_length = self.gold.omega_taper_length
            cpw_width = self.gold.cpw_signal_width
            cpw_end_left = chip_cx - self.gold.aperture_radius
            cpw_end_right = chip_cx + self.gold.aperture_radius
            taper_end_width = 10.0  # um — taper narrows to this
            
            # Left taper (CPW → narrow end, pointing right)
            left_taper_start_x = cpw_end_left - self.gold.omega_taper_cpw_inset
            left_taper_end_x = left_taper_start_x + taper_length
            left_taper = pya.Polygon([
                pya.Point(self._um_to_dbu(left_taper_start_x),
                         self._um_to_dbu(chip_cy - cpw_width / 2.0)),
                pya.Point(self._um_to_dbu(left_taper_end_x),
                         self._um_to_dbu(chip_cy - taper_end_width / 2.0)),
                pya.Point(self._um_to_dbu(left_taper_end_x),
                         self._um_to_dbu(chip_cy + taper_end_width / 2.0)),
                pya.Point(self._um_to_dbu(left_taper_start_x),
                         self._um_to_dbu(chip_cy + cpw_width / 2.0)),
            ])
            cell.shapes(self.gold_layer_idx).insert(left_taper)
            
            # Right taper (narrow end → CPW, pointing left)
            right_taper_end_x = cpw_end_right + self.gold.omega_taper_cpw_inset
            right_taper_start_x = right_taper_end_x - taper_length
            right_taper = pya.Polygon([
                pya.Point(self._um_to_dbu(right_taper_start_x),
                         self._um_to_dbu(chip_cy - taper_end_width / 2.0)),
                pya.Point(self._um_to_dbu(right_taper_end_x),
                         self._um_to_dbu(chip_cy - cpw_width / 2.0)),
                pya.Point(self._um_to_dbu(right_taper_end_x),
                         self._um_to_dbu(chip_cy + cpw_width / 2.0)),
                pya.Point(self._um_to_dbu(right_taper_start_x),
                         self._um_to_dbu(chip_cy + taper_end_width / 2.0)),
            ])
            cell.shapes(self.gold_layer_idx).insert(right_taper)
    
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
        
        # Horizontal offset scales with outer_radius for proper alignment at all sizes
        h_offset = outer_radius * 0.6
        
        # Four diagonal positions with horizontal offsets
        # Top rings offset left, bottom rings offset right
        positions = [
            (cx + offset - h_offset, cy + offset, 'bottom'),  # Top-right, gap at bottom
            (cx - offset - h_offset, cy + offset, 'bottom'),  # Top-left, gap at bottom
            (cx - offset + h_offset, cy - offset, 'top'),     # Bottom-left, gap at top
            (cx + offset + h_offset, cy - offset, 'top'),     # Bottom-right, gap at top
        ]
        
        num_segments = 64
        
        # Collect all omega geometry into a region, then cut gaps at the end
        omega_region = pya.Region()
        gap_boxes = []  # Store gap rectangles to subtract after all geometry is placed
        
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
            
            # Subtract inner from outer to create ring (no gap yet)
            omega_region += outer_region - inner_region
            
            # Store gap rectangle for later subtraction
            if ring_type == 'top':
                gap_boxes.append(pya.Box(
                    self._um_to_dbu(ring_cx - trace_gap / 2.0),
                    self._um_to_dbu(ring_cy),
                    self._um_to_dbu(ring_cx + trace_gap / 2.0),
                    self._um_to_dbu(ring_cy + outer_radius + trace_width)
                ))
            else:
                gap_boxes.append(pya.Box(
                    self._um_to_dbu(ring_cx - trace_gap / 2.0),
                    self._um_to_dbu(ring_cy - outer_radius - trace_width),
                    self._um_to_dbu(ring_cx + trace_gap / 2.0),
                    self._um_to_dbu(ring_cy)
                ))
        
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
        tw_dbu = self._um_to_dbu(trace_width)
        
        def make_path(x0, y0, x1, y1, extend=True):
            """Create a path polygon from (x0,y0) to (x1,y1) with trace_width.
            
            Uses pya.Path with round ends and extends endpoints by trace_width/2
            for robust overlap at connection points.
            """
            ext = self._um_to_dbu(trace_width / 2.0) if extend else 0
            path = pya.Path([
                pya.Point(self._um_to_dbu(x0), self._um_to_dbu(y0)),
                pya.Point(self._um_to_dbu(x1), self._um_to_dbu(y1)),
            ], tw_dbu, ext, ext)
            return path
        
        # --- Connection 1: CPW left → UP+x to top-left omega INPUT (left side of gap) ---
        feed1_bottom_x = top_left_gap_center_x - gap_shift - tilt_x
        feed1_bottom_y = cy
        feed1_top_x = top_left_gap_center_x - gap_shift
        feed1_top_y = top_left_gap_y
        omega_region.insert(
            make_path(feed1_bottom_x, feed1_bottom_y, feed1_top_x, feed1_top_y))
        
        # --- Connection 2: Top-left OUTPUT → DOWN+x to bottom-left INPUT (left pair) ---
        conn2_top_x = top_left_gap_center_x + gap_shift
        conn2_top_y = top_left_gap_y
        conn2_bottom_x = bottom_left_gap_center_x - gap_shift
        conn2_bottom_y = bottom_left_gap_y
        omega_region.insert(
            make_path(conn2_top_x, conn2_top_y, conn2_bottom_x, conn2_bottom_y))
        
        # --- Connection 3: Bottom-left OUTPUT → UP+x to middle trace ---
        feed3_bottom_x = bottom_left_gap_center_x + gap_shift
        feed3_bottom_y = bottom_left_gap_y
        feed3_top_x = bottom_left_gap_center_x + gap_shift + tilt_x
        feed3_top_y = cy
        omega_region.insert(
            make_path(feed3_bottom_x, feed3_bottom_y, feed3_top_x, feed3_top_y))
        
        # --- Connection 4: Middle trace → UP+x to top-right omega INPUT (left side of gap) ---
        feed4_bottom_x = top_right_gap_center_x - gap_shift - tilt_x
        feed4_bottom_y = cy
        feed4_top_x = top_right_gap_center_x - gap_shift
        feed4_top_y = top_right_gap_y
        omega_region.insert(
            make_path(feed4_bottom_x, feed4_bottom_y, feed4_top_x, feed4_top_y))
        
        # --- Connection 5: Top-right OUTPUT → DOWN+x to bottom-right INPUT (right pair) ---
        conn5_top_x = top_right_gap_center_x + gap_shift
        conn5_top_y = top_right_gap_y
        conn5_bottom_x = bottom_right_gap_center_x - gap_shift
        conn5_bottom_y = bottom_right_gap_y
        omega_region.insert(
            make_path(conn5_top_x, conn5_top_y, conn5_bottom_x, conn5_bottom_y))
        
        # --- Connection 6: Bottom-right OUTPUT → UP+x to CPW right ---
        feed6_bottom_x = bottom_right_gap_center_x + gap_shift
        feed6_bottom_y = bottom_right_gap_y
        feed6_top_x = bottom_right_gap_center_x + gap_shift + tilt_x
        feed6_top_y = cy
        omega_region.insert(
            make_path(feed6_bottom_x, feed6_bottom_y, feed6_top_x, feed6_top_y))
        
        # Middle connector (feed3 top to feed4 bottom at center level)
        omega_region.insert(
            make_path(feed3_top_x, cy, feed4_bottom_x, cy))
        
        # --- Tapers from CPW signal width to omega trace width ---
        # (The small cpw boxes that were here have been removed as they
        # were overlapping with and redundant to these tapers)
        taper_length = self.gold.omega_taper_length
        cpw_width = self.gold.cpw_signal_width
        cpw_end_left = cx - self.gold.aperture_radius
        cpw_end_right = cx + self.gold.aperture_radius
        
        # Left taper (CPW → omega trace)
        # Wide end starts inset into CPW, narrow end inside aperture
        left_taper_start_x = cpw_end_left - self.gold.omega_taper_cpw_inset
        left_taper_end_x = left_taper_start_x + taper_length
        left_taper = pya.Polygon([
            pya.Point(self._um_to_dbu(left_taper_start_x), 
                     self._um_to_dbu(cy - cpw_width / 2.0)),
            pya.Point(self._um_to_dbu(left_taper_end_x), 
                     self._um_to_dbu(cy - trace_width / 2.0)),
            pya.Point(self._um_to_dbu(left_taper_end_x), 
                     self._um_to_dbu(cy + trace_width / 2.0)),
            pya.Point(self._um_to_dbu(left_taper_start_x), 
                     self._um_to_dbu(cy + cpw_width / 2.0)),
        ])
        omega_region.insert(left_taper)
        
        # Right taper (omega trace → CPW)
        # Narrow end inside aperture, wide end extends into CPW
        right_taper_end_x = cpw_end_right + self.gold.omega_taper_cpw_inset
        right_taper_start_x = right_taper_end_x - taper_length
        right_taper = pya.Polygon([
            pya.Point(self._um_to_dbu(right_taper_start_x), 
                     self._um_to_dbu(cy - trace_width / 2.0)),
            pya.Point(self._um_to_dbu(right_taper_end_x), 
                     self._um_to_dbu(cy - cpw_width / 2.0)),
            pya.Point(self._um_to_dbu(right_taper_end_x), 
                     self._um_to_dbu(cy + cpw_width / 2.0)),
            pya.Point(self._um_to_dbu(right_taper_start_x), 
                     self._um_to_dbu(cy + trace_width / 2.0)),
        ])
        omega_region.insert(right_taper)
        
        # --- Connecting wires from taper end to omega feed lines ---
        # Extend trace_width/2 past the meeting point for good electrical contact
        # Left: from taper narrow end past feed1 bottom position
        left_wire_start_x = left_taper_end_x
        left_wire_end_x = feed1_bottom_x + trace_width / 2.0
        if left_wire_end_x > left_wire_start_x:
            left_wire = pya.Box(
                self._um_to_dbu(left_wire_start_x),
                self._um_to_dbu(cy - trace_width / 2.0),
                self._um_to_dbu(left_wire_end_x),
                self._um_to_dbu(cy + trace_width / 2.0)
            )
            omega_region.insert(left_wire)
        
        # Right: from past feed6 top position to taper narrow end
        right_wire_start_x = feed6_top_x - trace_width / 2.0
        right_wire_end_x = right_taper_start_x
        if right_wire_end_x > right_wire_start_x:
            right_wire = pya.Box(
                self._um_to_dbu(right_wire_start_x),
                self._um_to_dbu(cy - trace_width / 2.0),
                self._um_to_dbu(right_wire_end_x),
                self._um_to_dbu(cy + trace_width / 2.0)
            )
            omega_region.insert(right_wire)
        
        # --- Final step: subtract gap rectangles AFTER all geometry is placed ---
        # This guarantees clean rectangular gaps regardless of path extensions
        omega_region.merge()
        for gap_box in gap_boxes:
            omega_region -= pya.Region(gap_box)
        
        cell.shapes(self.gold_layer_idx).insert(omega_region)
    
    def _dc_pad_geometry(self, sign: float) -> list:
        """
        Compute DC pad positions and feedline routing for one side.
        
        Path per pad: pad → taper → angled feedline → vertical feedline →
                      vertical through aperture → straight run → fan-out
        
        Args:
            sign: +1 for top side, -1 for bottom side
            
        Returns:
            List of dicts, one per pad, with keys:
                pad_cx, pad_cy, taper_start_y,
                taper_end_x, taper_end_y,
                vertical_x, vertical_y,    (where angled becomes vertical)
                aperture_y,                (aperture edge crossing)
                fanout_start_y,            (end of straight run, start of fan-out)
                fanout_x, fanout_y         (fan-out tip)
        """
        chip_cx = self.chip.chip_width / 2.0
        chip_cy = self.chip.chip_height / 2.0
        g = self.gold
        n = g.dc_pad_count
        r = g.aperture_radius
        
        tan_a = math.tan(math.radians(g.dc_taper_angle))
        
        pads = []
        for i in range(n):
            idx = i - (n - 1) / 2.0  # centered index
            pad_cx = chip_cx + idx * g.dc_pad_pitch
            
            # Stagger: outer pads shift toward chip center
            frac = abs(idx) / ((n - 1) / 2.0)
            pad_cy_abs = g.dc_pad_cy - frac * g.dc_pad_stagger
            pad_cy = chip_cy + sign * pad_cy_abs
            
            # Taper: pad inner edge → feedline width
            taper_start_y = pad_cy - sign * g.dc_pad_height / 2.0
            taper_dx = g.dc_taper_height * tan_a
            taper_end_x = pad_cx - math.copysign(taper_dx, pad_cx - chip_cx)
            taper_end_y = taper_start_y - sign * g.dc_taper_height
            
            # Vertical transition point: feedline goes vertical at this height
            vertical_x = chip_cx + idx * g.dc_feedline_pitch
            vertical_y = chip_cy + sign * g.dc_feedline_vertical_cy
            
            # Aperture edge crossing (vertical feedline)
            aperture_y = chip_cy + sign * r
            
            # Straight vertical run inside aperture before fan-out
            fanout_start_y = chip_cy + sign * (r - g.dc_fanout_straight)
            
            # Fan-out tip
            fanout_x = chip_cx + idx * g.dc_fanout_pitch
            fanout_y = chip_cy + sign * (r - g.dc_fanout_height)
            
            pads.append(dict(
                pad_cx=pad_cx, pad_cy=pad_cy,
                taper_start_y=taper_start_y,
                taper_end_x=taper_end_x, taper_end_y=taper_end_y,
                vertical_x=vertical_x, vertical_y=vertical_y,
                aperture_y=aperture_y,
                fanout_start_y=fanout_start_y,
                fanout_x=fanout_x, fanout_y=fanout_y,
            ))
        return pads
    
    def create_dc_access_pads(self, cell: pya.Cell) -> None:
        """
        Create DC bond pads, tapers, feedlines, and fan-outs on both sides.
        
        For each pad (per side):
          1. Rectangular bond pad at (pad_cx, pad_cy)
          2. Trapezoidal taper from pad width → feedline width
          3. Angled feedline from taper tip → vertical transition point
          4. Vertical feedline from transition → through aperture → straight run
          5. Fan-out segment from straight run end → fan-out tip
        """
        g = self.gold
        fw = g.dc_feedline_width
        
        for sign in [+1, -1]:
            for p in self._dc_pad_geometry(sign):
                # 1. Bond pad
                cell.shapes(self.gold_layer_idx).insert(pya.Box(
                    self._um_to_dbu(p['pad_cx'] - g.dc_pad_width / 2.0),
                    self._um_to_dbu(p['pad_cy'] - g.dc_pad_height / 2.0),
                    self._um_to_dbu(p['pad_cx'] + g.dc_pad_width / 2.0),
                    self._um_to_dbu(p['pad_cy'] + g.dc_pad_height / 2.0)
                ))
                
                # 2. Taper (pad width → feedline width)
                cell.shapes(self.gold_layer_idx).insert(pya.Polygon([
                    pya.Point(self._um_to_dbu(p['pad_cx'] - g.dc_pad_width / 2.0),
                             self._um_to_dbu(p['taper_start_y'])),
                    pya.Point(self._um_to_dbu(p['pad_cx'] + g.dc_pad_width / 2.0),
                             self._um_to_dbu(p['taper_start_y'])),
                    pya.Point(self._um_to_dbu(p['taper_end_x'] + fw / 2.0),
                             self._um_to_dbu(p['taper_end_y'])),
                    pya.Point(self._um_to_dbu(p['taper_end_x'] - fw / 2.0),
                             self._um_to_dbu(p['taper_end_y'])),
                ]))
                
                # 3. Angled feedline (taper tip → vertical transition)
                cell.shapes(self.gold_layer_idx).insert(pya.Polygon([
                    pya.Point(self._um_to_dbu(p['taper_end_x'] - fw / 2.0),
                             self._um_to_dbu(p['taper_end_y'])),
                    pya.Point(self._um_to_dbu(p['taper_end_x'] + fw / 2.0),
                             self._um_to_dbu(p['taper_end_y'])),
                    pya.Point(self._um_to_dbu(p['vertical_x'] + fw / 2.0),
                             self._um_to_dbu(p['vertical_y'])),
                    pya.Point(self._um_to_dbu(p['vertical_x'] - fw / 2.0),
                             self._um_to_dbu(p['vertical_y'])),
                ]))
                
                # 4. Vertical feedline (transition → through aperture → straight run)
                cell.shapes(self.gold_layer_idx).insert(pya.Box(
                    self._um_to_dbu(p['vertical_x'] - fw / 2.0),
                    self._um_to_dbu(min(p['vertical_y'], p['fanout_start_y'])),
                    self._um_to_dbu(p['vertical_x'] + fw / 2.0),
                    self._um_to_dbu(max(p['vertical_y'], p['fanout_start_y']))
                ))
                
                # 5. Fan-out (straight run end → fan-out tip)
                cell.shapes(self.gold_layer_idx).insert(pya.Polygon([
                    pya.Point(self._um_to_dbu(p['vertical_x'] - fw / 2.0),
                             self._um_to_dbu(p['fanout_start_y'])),
                    pya.Point(self._um_to_dbu(p['vertical_x'] + fw / 2.0),
                             self._um_to_dbu(p['fanout_start_y'])),
                    pya.Point(self._um_to_dbu(p['fanout_x'] + fw / 2.0),
                             self._um_to_dbu(p['fanout_y'])),
                    pya.Point(self._um_to_dbu(p['fanout_x'] - fw / 2.0),
                             self._um_to_dbu(p['fanout_y'])),
                ]))
    
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
        # Left pad position - ground plane removed from pad outer edge to chip edge
        left_pad_x = self.gold.edge_buffer
        left_pad_box = pya.Box(
            self._um_to_dbu(self.chip.dicing_margin),
            self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0 - pad_clearance),
            self._um_to_dbu(left_pad_x + self.gold.rf_pad_height),  # Stop at pad edge
            self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0 + pad_clearance)
        )
        ground_region -= pya.Region(left_pad_box)
        
        # Right pad position - ground plane removed from pad outer edge to chip edge
        right_pad_x = self.chip.chip_width - self.gold.edge_buffer - self.gold.rf_pad_height
        right_pad_box = pya.Box(
            self._um_to_dbu(right_pad_x),  # Stop at pad edge
            self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0 - pad_clearance),
            self._um_to_dbu(self.chip.chip_width - self.chip.dicing_margin),
            self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0 + pad_clearance)
        )
        ground_region -= pya.Region(right_pad_box)
        
        # === SUBTRACT LEFT TAPER GAP (pad width → CPW width) ===
        # Calculate perpendicular offset for constant gap normal to taper edge
        left_taper_start_x = left_pad_x + self.gold.rf_pad_height
        left_taper_end_x = left_taper_start_x + self.gold.cpw_taper_length
        
        # Taper edge vector (top edge, from wide to narrow)
        taper_dx = self.gold.cpw_taper_length
        taper_dy = (self.gold.cpw_signal_width - self.gold.rf_pad_width) / 2.0  # negative (narrows)
        taper_length = math.sqrt(taper_dx**2 + taper_dy**2)
        
        # Perpendicular unit vector (outward from top edge)
        # Rotate taper vector 90° CCW: (dx, dy) → (-dy, dx), then normalize
        perp_x = -taper_dy / taper_length
        perp_y = taper_dx / taper_length
        
        # Perpendicular offset for pad_clearance gap
        offset_x = pad_clearance * perp_x
        offset_y = pad_clearance * perp_y
        
        # Single tapered cutout for signal + gap (top half)
        # 5-point polygon: meets pad clearance horizontal line at pad edge,
        # follows angled outer edge (parallel to signal taper at pad_clearance),
        # then returns along signal taper inner edge back to pad
        left_taper_cutout_top = pya.Polygon([
            # Pad edge at pad clearance Y (meets horizontal pad clearance line)
            pya.Point(self._um_to_dbu(left_taper_start_x),
                     self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0 + pad_clearance)),
            # Outer edge at pad end (perpendicular offset from signal taper corner)
            pya.Point(self._um_to_dbu(left_taper_start_x + offset_x),
                     self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0 + offset_y)),
            # Outer edge at CPW end (perpendicular offset)
            pya.Point(self._um_to_dbu(left_taper_end_x + offset_x),
                     self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0 + offset_y)),
            # Inner edge at CPW end (signal taper edge)
            pya.Point(self._um_to_dbu(left_taper_end_x),
                     self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0)),
            # Inner edge at pad end (signal taper edge = bond pad edge)
            pya.Point(self._um_to_dbu(left_taper_start_x),
                     self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0)),
        ])
        ground_region -= pya.Region(left_taper_cutout_top)
        
        # Single tapered cutout for signal + gap (bottom half)
        left_taper_cutout_bot = pya.Polygon([
            # Pad edge at pad clearance Y (meets horizontal pad clearance line)
            pya.Point(self._um_to_dbu(left_taper_start_x),
                     self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0 - pad_clearance)),
            # Outer edge at pad end (perpendicular offset from signal taper corner)
            pya.Point(self._um_to_dbu(left_taper_start_x + offset_x),
                     self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0 - offset_y)),
            # Outer edge at CPW end (perpendicular offset)
            pya.Point(self._um_to_dbu(left_taper_end_x + offset_x),
                     self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0 - offset_y)),
            # Inner edge at CPW end (signal taper edge)
            pya.Point(self._um_to_dbu(left_taper_end_x),
                     self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0)),
            # Inner edge at pad end (signal taper edge = bond pad edge)
            pya.Point(self._um_to_dbu(left_taper_start_x),
                     self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0)),
        ])
        ground_region -= pya.Region(left_taper_cutout_bot)
        
        # === SUBTRACT LEFT CPW SECTION (taper end to aperture) ===
        cpw_end_left = chip_cx - self.gold.aperture_radius
        # Extend cutout past aperture radius to fully overlap with circle edge
        # At CPW gap height h, circle edge is at x = sqrt(r^2 - h^2) from center,
        # so we need to extend by r - sqrt(r^2 - h^2) to ensure full overlap
        cpw_half_height = self.gold.cpw_signal_width / 2.0 + gap
        r = self.gold.aperture_radius
        circle_inset = r - math.sqrt(r**2 - cpw_half_height**2)
        left_cpw_box = pya.Box(
            self._um_to_dbu(left_taper_end_x),
            self._um_to_dbu(chip_cy - cpw_half_height),
            self._um_to_dbu(cpw_end_left + circle_inset),
            self._um_to_dbu(chip_cy + cpw_half_height)
        )
        ground_region -= pya.Region(left_cpw_box)
        
        # === SUBTRACT RIGHT CPW SECTION (aperture to taper) ===
        cpw_end_right = chip_cx + self.gold.aperture_radius
        # Taper gap aligns with signal taper (ends at pad edge)
        right_taper_end_x = self.chip.chip_width - self.gold.edge_buffer - self.gold.rf_pad_height
        right_taper_start_x = right_taper_end_x - self.gold.cpw_taper_length
        right_cpw_box = pya.Box(
            self._um_to_dbu(cpw_end_right - circle_inset),
            self._um_to_dbu(chip_cy - cpw_half_height),
            self._um_to_dbu(right_taper_start_x),
            self._um_to_dbu(chip_cy + cpw_half_height)
        )
        ground_region -= pya.Region(right_cpw_box)
        
        # === SUBTRACT RIGHT TAPER GAP (CPW width → pad width) ===
        # Calculate perpendicular offset (same geometry, mirrored)
        # Right taper edge vector (top edge, from narrow to wide)
        right_taper_dx = self.gold.cpw_taper_length
        right_taper_dy = (self.gold.rf_pad_width - self.gold.cpw_signal_width) / 2.0  # positive (widens)
        right_taper_length = math.sqrt(right_taper_dx**2 + right_taper_dy**2)
        
        # Perpendicular unit vector (outward from top edge)
        right_perp_x = right_taper_dy / right_taper_length
        right_perp_y = right_taper_dx / right_taper_length
        
        # Perpendicular offset for pad_clearance gap
        right_offset_x = pad_clearance * right_perp_x
        right_offset_y = pad_clearance * right_perp_y
        
        # Single tapered cutout for signal + gap (top half)
        # 5-point polygon: meets pad clearance horizontal line at pad edge,
        # follows angled outer edge, returns along signal taper inner edge
        right_taper_cutout_top = pya.Polygon([
            # Inner edge at CPW end (signal taper edge)
            pya.Point(self._um_to_dbu(right_taper_start_x),
                     self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0)),
            # Outer edge at CPW end (perpendicular offset)
            pya.Point(self._um_to_dbu(right_taper_start_x - right_offset_x),
                     self._um_to_dbu(chip_cy + self.gold.cpw_signal_width / 2.0 + right_offset_y)),
            # Outer edge at pad end (perpendicular offset from signal taper corner)
            pya.Point(self._um_to_dbu(right_taper_end_x - right_offset_x),
                     self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0 + right_offset_y)),
            # Pad edge at pad clearance Y (meets horizontal pad clearance line)
            pya.Point(self._um_to_dbu(right_taper_end_x),
                     self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0 + pad_clearance)),
            # Inner edge at pad end (signal taper edge = bond pad edge)
            pya.Point(self._um_to_dbu(right_taper_end_x),
                     self._um_to_dbu(chip_cy + self.gold.rf_pad_width / 2.0)),
        ])
        ground_region -= pya.Region(right_taper_cutout_top)
        
        # Single tapered cutout for signal + gap (bottom half)
        right_taper_cutout_bot = pya.Polygon([
            # Inner edge at CPW end (signal taper edge)
            pya.Point(self._um_to_dbu(right_taper_start_x),
                     self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0)),
            # Outer edge at CPW end (perpendicular offset)
            pya.Point(self._um_to_dbu(right_taper_start_x - right_offset_x),
                     self._um_to_dbu(chip_cy - self.gold.cpw_signal_width / 2.0 - right_offset_y)),
            # Outer edge at pad end (perpendicular offset from signal taper corner)
            pya.Point(self._um_to_dbu(right_taper_end_x - right_offset_x),
                     self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0 - right_offset_y)),
            # Pad edge at pad clearance Y (meets horizontal pad clearance line)
            pya.Point(self._um_to_dbu(right_taper_end_x),
                     self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0 - pad_clearance)),
            # Inner edge at pad end (signal taper edge = bond pad edge)
            pya.Point(self._um_to_dbu(right_taper_end_x),
                     self._um_to_dbu(chip_cy - self.gold.rf_pad_width / 2.0)),
        ])
        ground_region -= pya.Region(right_taper_cutout_bot)
        
        # === SUBTRACT DC CUTOUT + FEEDLINE CLEARANCE CHANNELS ===
        g = self.gold
        fw = g.dc_feedline_width
        clr = g.dc_feedline_clearance
        
        # Cutout taper: from dc_cutout_width at the rectangle inner edge,
        # taper at dc_cutout_taper_angle until reaching ±dc_cutout_aperture_width/2,
        # then go vertical to the aperture edge. Past the aperture edge, add
        # a rectangular extension (fanout_height + fanout_straight) deep to
        # fully clear the opening for DC lines.
        aw_half = g.dc_cutout_aperture_width / 2.0
        tan_cut = math.tan(math.radians(g.dc_cutout_taper_angle))
        # Vertical distance for taper to narrow from cutout_width/2 to aperture_width/2
        dx_taper = g.dc_cutout_width / 2.0 - aw_half
        taper_dy = dx_taper / tan_cut if tan_cut > 0 else 0
        extension = g.dc_fanout_height + g.dc_fanout_straight
        
        for sign in [+1, -1]:  # +1 = top, -1 = bottom
            cutout_cy = chip_cy + sign * g.dc_cutout_cy
            
            # Rectangular cutout
            ground_region -= pya.Region(pya.Box(
                self._um_to_dbu(chip_cx - g.dc_cutout_width / 2.0),
                self._um_to_dbu(cutout_cy - g.dc_cutout_height / 2.0),
                self._um_to_dbu(chip_cx + g.dc_cutout_width / 2.0),
                self._um_to_dbu(cutout_cy + g.dc_cutout_height / 2.0)
            ))
            
            # Trapezoidal taper: cutout inner edge → aperture_width
            cutout_inner_y = cutout_cy - sign * g.dc_cutout_height / 2.0
            taper_end_y = cutout_inner_y - sign * taper_dy
            ground_region -= pya.Region(pya.Polygon([
                pya.Point(self._um_to_dbu(chip_cx - g.dc_cutout_width / 2.0),
                         self._um_to_dbu(cutout_inner_y)),
                pya.Point(self._um_to_dbu(chip_cx + g.dc_cutout_width / 2.0),
                         self._um_to_dbu(cutout_inner_y)),
                pya.Point(self._um_to_dbu(chip_cx + aw_half),
                         self._um_to_dbu(taper_end_y)),
                pya.Point(self._um_to_dbu(chip_cx - aw_half),
                         self._um_to_dbu(taper_end_y)),
            ]))
            
            # Vertical section: aperture_width straight down to aperture edge
            aperture_edge_y = chip_cy + sign * r
            ground_region -= pya.Region(pya.Box(
                self._um_to_dbu(chip_cx - aw_half),
                self._um_to_dbu(min(taper_end_y, aperture_edge_y)),
                self._um_to_dbu(chip_cx + aw_half),
                self._um_to_dbu(max(taper_end_y, aperture_edge_y))
            ))
            
            # Extension past aperture edge to clear out fanout region
            ext_y = aperture_edge_y - sign * extension
            ground_region -= pya.Region(pya.Box(
                self._um_to_dbu(chip_cx - aw_half),
                self._um_to_dbu(min(aperture_edge_y, ext_y)),
                self._um_to_dbu(chip_cx + aw_half),
                self._um_to_dbu(max(aperture_edge_y, ext_y))
            ))
            
            # Feedline clearance channels (mirrors create_dc_access_pads + clearance)
            for p in self._dc_pad_geometry(sign):
                # Taper clearance
                ground_region -= pya.Region(pya.Polygon([
                    pya.Point(self._um_to_dbu(p['pad_cx'] - g.dc_pad_width / 2.0 - clr),
                             self._um_to_dbu(p['taper_start_y'])),
                    pya.Point(self._um_to_dbu(p['pad_cx'] + g.dc_pad_width / 2.0 + clr),
                             self._um_to_dbu(p['taper_start_y'])),
                    pya.Point(self._um_to_dbu(p['taper_end_x'] + fw / 2.0 + clr),
                             self._um_to_dbu(p['taper_end_y'])),
                    pya.Point(self._um_to_dbu(p['taper_end_x'] - fw / 2.0 - clr),
                             self._um_to_dbu(p['taper_end_y'])),
                ]))
                
                # Angled feedline clearance (taper tip → vertical transition)
                ground_region -= pya.Region(pya.Polygon([
                    pya.Point(self._um_to_dbu(p['taper_end_x'] - fw / 2.0 - clr),
                             self._um_to_dbu(p['taper_end_y'])),
                    pya.Point(self._um_to_dbu(p['taper_end_x'] + fw / 2.0 + clr),
                             self._um_to_dbu(p['taper_end_y'])),
                    pya.Point(self._um_to_dbu(p['vertical_x'] + fw / 2.0 + clr),
                             self._um_to_dbu(p['vertical_y'])),
                    pya.Point(self._um_to_dbu(p['vertical_x'] - fw / 2.0 - clr),
                             self._um_to_dbu(p['vertical_y'])),
                ]))
                
                # Vertical feedline clearance (transition → through aperture → fanout tip)
                ground_region -= pya.Region(pya.Box(
                    self._um_to_dbu(p['vertical_x'] - fw / 2.0 - clr),
                    self._um_to_dbu(min(p['vertical_y'], p['fanout_y'])),
                    self._um_to_dbu(p['vertical_x'] + fw / 2.0 + clr),
                    self._um_to_dbu(max(p['vertical_y'], p['fanout_y']))
                ))
        
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
                ground_region -= pya.Region(pya.Box(
                    self._um_to_dbu(mx - am_size / 2.0 - am_clr),
                    self._um_to_dbu(my - am_size / 2.0 - am_clr),
                    self._um_to_dbu(mx + am_size / 2.0 + am_clr),
                    self._um_to_dbu(my + am_size / 2.0 + am_clr)
                ))
        
        # === SUBTRACT SMALL ALIGNMENT MARK CLEARANCES ===
        small_am_offset = 400.0
        small_am_half = 7.5
        small_am_clr = 30.0  # µm clearance around small marks
        for sx in [+1, -1]:
            for sy in [+1, -1]:
                smx = chip_cx + sx * small_am_offset
                smy = chip_cy + sy * small_am_offset
                ground_region -= pya.Region(pya.Box(
                    self._um_to_dbu(smx - small_am_half - small_am_clr),
                    self._um_to_dbu(smy - small_am_half - small_am_clr),
                    self._um_to_dbu(smx + small_am_half + small_am_clr),
                    self._um_to_dbu(smy + small_am_half + small_am_clr)
                ))
        
        # === SUBTRACT PRT THERMOMETER CLEARANCES ===
        # Inner edge (toward chip center) has normal clearance;
        # outer edge (toward chip boundary) extends to chip edge (no ground).
        prt_clr = 50.0  # um clearance around PRT features
        for sign in [+1, -1]:
            prt_cx = chip_cx
            prt_cy = chip_cy + sign * self.platinum.prt_cy
            inner_y = prt_cy - sign * (self.platinum.prt_height / 2.0 + prt_clr)
            outer_y = (self.chip.chip_height - self.chip.dicing_margin) if sign > 0 else self.chip.dicing_margin
            ground_region -= pya.Region(pya.Box(
                self._um_to_dbu(prt_cx - self.platinum.prt_width / 2.0 - prt_clr),
                self._um_to_dbu(min(inner_y, outer_y)),
                self._um_to_dbu(prt_cx + self.platinum.prt_width / 2.0 + prt_clr),
                self._um_to_dbu(max(inner_y, outer_y))
            ))
        
        # === SUBTRACT VERNIER ALIGNMENT MARK CLEARANCE ===
        vernier_clr = 50.0  # µm clearance around vernier marks
        vx = chip_cx + 2100.0
        vy = chip_cy + 1400.0
        # Vernier combined bbox (from imported GDS): ~340 × 275 µm centered at mark origin
        v_hw = 170.0  # half-width
        v_hh = 170.0  # half-height (use symmetric envelope)
        ground_region -= pya.Region(pya.Box(
            self._um_to_dbu(vx - v_hw - vernier_clr),
            self._um_to_dbu(vy - v_hh - vernier_clr),
            self._um_to_dbu(vx + v_hw + vernier_clr),
            self._um_to_dbu(vy + v_hh + vernier_clr)
        ))
        
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
                cell.shapes(self.gold_layer_idx).insert(pya.Box(
                    self._um_to_dbu(cx - size / 2.0),
                    self._um_to_dbu(cy - w / 2.0),
                    self._um_to_dbu(cx + size / 2.0),
                    self._um_to_dbu(cy + w / 2.0)
                ))
                
                # Vertical bar
                cell.shapes(self.gold_layer_idx).insert(pya.Box(
                    self._um_to_dbu(cx - w / 2.0),
                    self._um_to_dbu(cy - size / 2.0),
                    self._um_to_dbu(cx + w / 2.0),
                    self._um_to_dbu(cy + size / 2.0)
                ))
    
    def create_small_alignment_marks(self, cell: pya.Cell) -> None:
        """Create small cross alignment marks at ±800, ±800 µm from chip center.
        
        Each mark is 15 µm overall (arm half-length = 7.5 µm) with 5 µm trace width.
        Placed on the gold layer at 4 positions near the chip center.
        """
        chip_cx = self.chip.chip_width / 2.0
        chip_cy = self.chip.chip_height / 2.0
        offset = 400.0       # µm from center
        arm_half = 25       # µm (15 µm overall / 2)
        tw = 4.0             # µm trace width
        
        for sx in [+1, -1]:
            for sy in [+1, -1]:
                cx = chip_cx + sx * offset
                cy = chip_cy + sy * offset
                
                # Horizontal bar
                cell.shapes(self.gold_layer_idx).insert(pya.Box(
                    self._um_to_dbu(cx - arm_half),
                    self._um_to_dbu(cy - tw / 2.0),
                    self._um_to_dbu(cx + arm_half),
                    self._um_to_dbu(cy + tw / 2.0)
                ))
                
                # Vertical bar
                cell.shapes(self.gold_layer_idx).insert(pya.Box(
                    self._um_to_dbu(cx - tw / 2.0),
                    self._um_to_dbu(cy - arm_half),
                    self._um_to_dbu(cx + tw / 2.0),
                    self._um_to_dbu(cy + arm_half)
                ))

    def create_vernier_marks(self, cell: pya.Cell) -> None:
        """Import vernier/alignment marks from external GDS onto each chip.
        
        Reads Contact-AlignMarks_Vernier_DemisDJohn_v5.gds:
          - AlignLyr1 (layer 1/0) → gold layer
          - AlignLyr2 (layer 2/0) → platinum layer
        
        Placed at chip_center + (2200, 1000) µm.
        Ground plane cutout is handled in create_ground_plane().
        """
        gds_path = os.path.join(
            os.path.dirname(__file__),
            "Contact-AlignMarks_Vernier_DemisDJohn_v5.gds"
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
        shift = pya.ICplxTrans(1, 0, False,
                               self._um_to_dbu(vx), self._um_to_dbu(vy))
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
            cell.shapes(self.gold_layer_idx).insert(pya.Box(
                self._um_to_dbu(feat_left),
                self._um_to_dbu(feat_cy - p.prt_pad_height / 2.0),
                self._um_to_dbu(feat_left + p.prt_pad_width),
                self._um_to_dbu(feat_cy + p.prt_pad_height / 2.0)
            ))
            
            # Right bond pad (gold layer)
            cell.shapes(self.gold_layer_idx).insert(pya.Box(
                self._um_to_dbu(feat_left + p.prt_width - p.prt_pad_width),
                self._um_to_dbu(feat_cy - p.prt_pad_height / 2.0),
                self._um_to_dbu(feat_left + p.prt_width),
                self._um_to_dbu(feat_cy + p.prt_pad_height / 2.0)
            ))
            
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
                cell.shapes(self.platinum_layer_idx).insert(pya.Box(
                    self._um_to_dbu(trace_left),
                    self._um_to_dbu(line_bottom),
                    self._um_to_dbu(trace_right),
                    self._um_to_dbu(line_top)
                ))
                
                # Vertical connecting stub to next line
                if j < n_lines - 1:
                    next_bottom = line_top + ts
                    # Even lines connect on right, odd on left
                    # Stubs are inset by pad_spacing to match shortened traces
                    if j % 2 == 0:
                        stub_x = body_right - ps - tw
                    else:
                        stub_x = body_left + ps
                    
                    cell.shapes(self.platinum_layer_idx).insert(pya.Box(
                        self._um_to_dbu(stub_x),
                        self._um_to_dbu(line_top),
                        self._um_to_dbu(stub_x + tw),
                        self._um_to_dbu(next_bottom)
                    ))
            
            # Connect first line to left pad, last line to right pad
            first_line_bottom = feat_bottom + y_margin
            last_line_bottom = feat_bottom + y_margin + (n_lines - 1) * pitch
            
            # Left pad connects to first (bottom) line — Pt trace overlaps Au pad
            cell.shapes(self.platinum_layer_idx).insert(pya.Box(
                self._um_to_dbu(body_left - p.prt_pad_width),
                self._um_to_dbu(first_line_bottom),
                self._um_to_dbu(body_left),
                self._um_to_dbu(first_line_bottom + tw)
            ))
            
            # Right pad connects to last line — Pt trace overlaps Au pad
            if (n_lines - 1) % 2 == 0:
                cell.shapes(self.platinum_layer_idx).insert(pya.Box(
                    self._um_to_dbu(body_right),
                    self._um_to_dbu(last_line_bottom),
                    self._um_to_dbu(body_right + p.prt_pad_width),
                    self._um_to_dbu(last_line_bottom + tw)
                ))
            else:
                cell.shapes(self.platinum_layer_idx).insert(pya.Box(
                    self._um_to_dbu(body_right),
                    self._um_to_dbu(last_line_bottom),
                    self._um_to_dbu(body_right + p.prt_pad_width),
                    self._um_to_dbu(last_line_bottom + tw)
                ))
    
    # -------------------------------------------------------------------------
    # LABELS
    # -------------------------------------------------------------------------
    
    def create_labels(self, cell: pya.Cell) -> None:
        """
        Create polygon-based text labels on the gold layer.
        
        Uses KLayout's TextGenerator to render text as bold polygon shapes.
        Surrounding gold is removed with a clearance margin so text is
        readable against the cleared substrate.
        
        Currently places the omega diameter value at (-1500, +850) from chip center.
        """
        chip_cx = self.chip.chip_width / 2.0
        chip_cy = self.chip.chip_height / 2.0
        
        # Omega diameter label
        omega_diameter = 2.0 * self.gold.omega_center_radius
        label_x = chip_cx - 2100
        label_y = chip_cy + 800.0
        
        if self.gold.omega_count == 0:
            return  # no label for blank chips
        
        label_text = f"{omega_diameter:.0f}"
        
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
        clear_box = pya.Region(pya.Box(
            text_bbox.left - clearance,
            text_bbox.bottom - clearance,
            text_bbox.right + clearance,
            text_bbox.top + clearance
        ))
        
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
        # 1. Create RF bond pads with integrated tapers (returns taper end positions)
        left_taper_end_x, right_taper_start_x = self.create_rf_bond_pads(cell)
        
        # 2. Create CPW signal path sections and omega resonators
        self.create_cpw_signal_path(cell, left_taper_end_x, right_taper_start_x)
        
        # 3. DC access pads (above and below aperture)
        self.create_dc_access_pads(cell)
        
        # 4. Alignment marks
        self.create_alignment_marks(cell)
        
        # 4a. Small alignment marks near center
        self.create_small_alignment_marks(cell)
        
        # 4b. Vernier alignment marks (imported from external GDS)
        self.create_vernier_marks(cell)
        
        # 5. Ground plane with all cutouts
        self.create_ground_plane(cell)
        
        # 6. Labels
        self.create_labels(cell)
        
        # Platinum layer components
        # 7. PRT serpentine thermometers
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
        print(f"  DC cutout:         {self.gold.dc_cutout_width:.0f} × {self.gold.dc_cutout_height:.0f} um at cy={self.gold.dc_cutout_cy:.0f}")
        print(f"  DC pads:           {self.gold.dc_pad_count} × {self.gold.dc_pad_width:.0f}×{self.gold.dc_pad_height:.0f} um, pitch={self.gold.dc_pad_pitch:.0f}")
        print(f"  DC feedline width: {self.gold.dc_feedline_width:.0f} um")
        print()
        
        # Create chip
        print("Creating chip...")
        chip_cell = self.create_chip()
        print("  [OK] RF bond pads (left and right)")
        print("  [OK] CPW signal path with tapers")
        print(f"  [OK] {self.gold.omega_count} omega resonators")
        print(f"  [OK] DC access pads ({self.gold.dc_pad_count} per side, top and bottom)")
        print("  [OK] Ground plane with cutouts")
        print()
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Export hierarchical (inspect) version
        inspect_path = os.path.join(output_dir, "5x5mm_sample_chip_V4_inspect.gds")
        self.layout.write(inspect_path)
        print(f"[OK] Hierarchical design: {inspect_path}")
        
        # Export flattened (prod) version
        prod_path = os.path.join(output_dir, "5x5mm_sample_chip_V4_prod.gds")
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
    print("5x5mm Sample Chip V4 - Two-Layer Design")
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
