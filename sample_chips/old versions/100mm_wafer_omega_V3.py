#!/usr/bin/env python3
"""
100 mm wafer layout with 4x omega chip array.

Design specification:
- 100 mm diameter wafer
- 4x 6x6 mm chips arranged in 2x2 grid at wafer center
- Each chip contains CPW transmission line with central aperture
- Inner design (omega resonators) to be added in aperture region

Version: V3
Author: Jayich Lab
"""

import klayout.db as pya
import math
import os
from pathlib import Path

# Import the chip designer module
import importlib.util

# Load the chip module dynamically (handles filename with numbers)
chip_module_path = Path(__file__).parent / "6x6mm_sample_chip_V3.py"
spec = importlib.util.spec_from_file_location("chip_module", chip_module_path)
chip_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chip_module)

# Import the classes and functions we need
ChipDesigner = chip_module.ChipDesigner
create_chip_cell = chip_module.create_chip_cell


class ChipConfig:
    """
    Chip design parameters - local copy for wafer-level customization.
    
    This class mirrors DesignConfig from 6x6mm_sample_chip_V3.py to allow
    per-chip customization of parameters like aperture_radius when creating
    the wafer array. Both classes define the same parameters to maintain
    compatibility with the chip generation code.
    """
    
    # Database unit: 0.01 µm = 10 nm
    dbu = 0.01  # 1 DBU = 10 nm
    
    # Layer definitions
    METAL_LAYER = pya.LayerInfo(1, 0)  # Metal/conductor layer (mw_metal)
    DC_PAD_LAYER = pya.LayerInfo(3, 0)  # DC pads and traces layer (dc_pads)
    
    # Chip dimensions (includes 200 µm edge buffer)
    chip_width = 6000.0      # 6 mm total width
    chip_height = 6000.0     # 6 mm total height
    edge_buffer = 400.0      # 400 µm edge buffer
    
    # CPW (Coplanar Waveguide) specifications
    cpw_signal_width = 100.0  # Center trace width (µm)
    cpw_gap = 50.0            # Gap from signal to ground plane (µm) → 50 Ω impedance
    cpw_ground_width = (chip_width - cpw_signal_width) / 2.0  # Fill remaining width
    
    # Bond pad specifications
    pad_width = 400.0         # Horizontal dimension (µm)
    pad_height = 800.0        # Vertical dimension (µm)
    
    # Taper specifications
    taper_length = 125.0      # Length of rapid taper from pad to CPW (µm)
    
    # Aperture (circular hole for interior design)
    aperture_radius = 400.0   # Radius of circular center aperture (µm)
    aperture_taper_angle = 5.0  # Taper angle in degrees for CPW gap into aperture
    aperture_taper_length = 200.0  # Length of taper into aperture (µm)
    
    # Clearances and margins
    pad_to_ground_clearance = 150.0  # 3x CPW gap for bond pad and taper clearance (µm)
    signal_to_ground_gap = cpw_gap  # Same as CPW gap
    dicing_margin = 100.0           # Margin from chip edge where no metal is placed (µm)
    
    # DC bond pad array (top and bottom)
    dc_pad_width = 125.0             # DC pad width (µm)
    dc_pad_height = 125.0            # DC pad height (µm)
    dc_pad_count = 6                 # Number of DC pads per array
    dc_pad_y_offset = 1500.0         # Distance from chip center to DC pad array center (µm)
    dc_pad_arc_radius = 1500.0       # Radius of arc for DC pad placement (µm)
    dc_pad_arc_angle = 60.0          # Total angular spread for DC pad placement (degrees)
    dc_pad_clearance = 100.0          # Clearance around DC pads (µm)
    dc_cutout_width = dc_pad_clearance*(dc_pad_count+1)+dc_pad_width*dc_pad_count
    dc_cutout_height = dc_pad_clearance*4+dc_pad_height
    dc_pad_entrance_width = 250.0    # Width at narrow end of taper to aperture (µm)
    dc_pad_entrance_height = aperture_radius + 50.0  # Height of tapered entrance section (µm)
    dc_trace_width = 12.0            # Width of DC traces after taper (µm)
    dc_trace_taper_length = 80.0     # Length of taper from pad to trace (µm)
    dc_trace_aperture_penetration = 80.0  # How far DC traces extend into aperture (µm)
    dc_trace_fanout_arc_radius = 250.0  # Radius of arc for trace fanout inside aperture (µm)
    dc_trace_fanout_arc_angle = 40.0   # Total angular spread for trace fanout (degrees)
    dc_aperture_triangle_base = 100.0  # Length along circle edge for triangular cutout (µm)
    dc_aperture_triangle_height = 20.0  # Depth of triangular cutout into aperture (µm)
    
    # Alignment crosses
    cross_size = 250.0               # Total size of alignment cross (µm)
    cross_linewidth = 20.0           # Linewidth of cross arms (µm)
    cross_offset = 2000.0            # Diagonal offset from chip center (µm)
    cross_clearance = 100.0           # Clearance around alignment cross in ground plane (µm)
    
    # Text label parameters
    text_label_height = 200.0        # Height of text label (µm)
    text_label_y_offset = 2150.0     # Y offset from chip center for text label (µm)
    text_label_clearance = 50.0      # Clearance around text for ground plane (µm)
    
    # Electroplating parameters
    electroplating = True           # Enable electroplating tabs
    electroplating_tab_width = 25.0  # Width of electroplating tabs (µm)
    electroplating_tab_clearance = 50.0  # Clearance around signal tab in ground plane (µm)


class OmegaConfig:
    """Configuration for omega resonator design."""
    
    # Layer definitions
    METAL_LAYER = pya.LayerInfo(1, 0)  # Metal/conductor layer
    
    # Omega resonator parameters
    center_radius = 50.0             # Center radius of omega rings (µm)
    trace_width = 10.0               # Width of ring trace (µm)
    omega_spacing = 50.0             # Spacing between omega rings (µm)
    omega_trace_gap = 15.0           # Gap width to break the ring loop (µm)
    omega_taper_length = 100.0        # Taper length from CPW width to omega trace width (µm)
    
    def __init__(self, center_radius=None, trace_width=None, omega_spacing=None, 
                 omega_trace_gap=None, omega_taper_length=None):
        """
        Initialize OmegaConfig with optional parameter overrides.
        
        Args:
            center_radius: Override center_radius (µm)
            trace_width: Override trace_width (µm)
            omega_spacing: Override omega_spacing (µm)
            omega_trace_gap: Override omega_trace_gap (µm)
            omega_taper_length: Override omega_taper_length (µm)
        """
        if center_radius is not None:
            self.center_radius = center_radius
        if trace_width is not None:
            self.trace_width = trace_width
        if omega_spacing is not None:
            self.omega_spacing = omega_spacing
        if omega_trace_gap is not None:
            self.omega_trace_gap = omega_trace_gap
        if omega_taper_length is not None:
            self.omega_taper_length = omega_taper_length


class WaferConfig:
    """Configuration for 100 mm wafer layout."""
    
    # Database unit (must match chip design)
    dbu = 0.01  # 1 DBU = 10 nm
    
    # Layer definitions with names
    METAL_LAYER = pya.LayerInfo(1, 0)  # Metal/conductor layer (mw_metal)
    GUIDE_LAYER = pya.LayerInfo(2, 0)  # Guide/alignment layer (wafer_outline)
    DC_PAD_LAYER = pya.LayerInfo(3, 0)  # DC pads and traces layer (dc_pads)
    
    # Layer names (for GDS export)
    LAYER_NAMES = {
        (1, 0): "mw_metal",
        (2, 0): "wafer_outline",
        (3, 0): "dc_pads",
    }
    
    # Wafer dimensions
    wafer_diameter = 100000.0  # 100 mm in µm
    wafer_radius = wafer_diameter / 2.0
    wafer_buffer = 3000.0     # Buffer from wafer edge (µm) - usable area is diameter - 2*buffer
    
    # Chip array configuration (for the 2x3 unit cell)
    chip_count_x = 2  # 2x3 array unit
    chip_count_y = 3
    chip_spacing = 0  # Gap between chips (µm) - dicing lanes
    
    # Electroplating
    electroplating = False    # Enable electroplating traces along dicing lanes
    electroplating_tab_width = 50.0  # Width of electroplating traces (µm)
    
    # Wafer flat (for orientation)
    flat_length = 32500.0  # Standard 100mm wafer flat length (µm)
    flat_depth = 2500.0    # Depth of flat from circle edge (µm)
    
    # Wafer edge contacts (within buffer zone)
    edge_contact_width = 10000.0   # Width of contact rectangles in long direction (µm)
    edge_contact_height = 4000.0   # Height/depth of contacts into buffer (µm)
    edge_contact_count = 1         # Number of contacts per edge (left, right, top)


class WaferDesigner:
    """Designer class for wafer-level layout with chip array."""
    
    def __init__(self, wafer_config=None, chip_configs=None, omega_configs=None):
        """
        Initialize wafer designer.
        
        Args:
            wafer_config: WaferConfig instance or None for defaults
            chip_configs: List of ChipConfig instances (one per chip) or None for defaults
            omega_configs: List of OmegaConfig instances (one per chip) or None for defaults
                          Use None in list position for blank chip (no omega)
        """
        self.wafer_config = wafer_config if wafer_config is not None else WaferConfig()
        
        # Create default chip and omega configs for 2x3 array (6 chips total) if not provided
        if chip_configs is None or omega_configs is None:
            # Create matched pairs of chip configs and omega configs
            # Each variant can have different aperture size and trace width
            
            # Chip 0: 60 µm omega, aperture 250, trace 10
            chip0 = ChipConfig()
            chip0.aperture_radius = 250.0
            chip0.dc_trace_fanout_arc_radius = chip0.aperture_radius - 50.0
            chip0.dc_trace_fanout_arc_angle = 60.0
            omega0 = OmegaConfig(center_radius=30.0, trace_width=10.0, omega_trace_gap=10)
            
            # Chip 1: 100 µm omega, aperture 300, trace 10
            chip1 = ChipConfig()
            chip1.aperture_radius = 300.0
            chip1.dc_trace_fanout_arc_radius = chip1.aperture_radius - 50.0
            chip1.dc_trace_fanout_arc_angle = 50.0
            omega1 = OmegaConfig(center_radius=50.0, trace_width=10.0, omega_trace_gap=10)
            
            # Chip 2: 150 µm omega, aperture 350, trace 12.5
            chip2 = ChipConfig()
            chip2.aperture_radius = 350.0
            chip2.dc_trace_fanout_arc_radius = chip2.aperture_radius - 50.0
            chip2.dc_trace_fanout_arc_angle = 60.0
            omega2 = OmegaConfig(center_radius=75.0, trace_width=12.5)
            
            # Chip 3: 200 µm omega, aperture 450, trace 15
            chip3 = ChipConfig()
            chip3.aperture_radius = 450.0
            chip3.dc_trace_fanout_arc_radius = chip3.aperture_radius - 60.0
            chip3.dc_trace_fanout_arc_angle = 70.0
            omega3 = OmegaConfig(center_radius=100.0, trace_width=15.0)
            
            # Chip 4: 250 µm omega, aperture 600, trace 20
            chip4 = ChipConfig()
            chip4.aperture_radius = 550.0
            chip4.dc_trace_fanout_arc_radius = chip4.aperture_radius - 80.0
            chip4.dc_trace_fanout_arc_angle = 60.0
            omega4 = OmegaConfig(center_radius=125.0, trace_width=20.0)
            
            # Chip 5: Blank (no omega), default aperture
            chip5 = ChipConfig()
            chip5.dc_trace_fanout_arc_radius = 180
            chip5.dc_trace_fanout_arc_angle = 140.0
            omega5 = None
            
            chip_configs = [chip0, chip1, chip2, chip3, chip4, chip5]
            omega_configs = [omega0, omega1, omega2, omega3, omega4, omega5]
        
        self.chip_configs = chip_configs
        self.omega_configs = omega_configs
        
        # Ensure DBU matches for all chip configs
        for chip_config in self.chip_configs:
            chip_config.dbu = self.wafer_config.dbu
        
        self.layout = pya.Layout()
        self.layout.dbu = self.wafer_config.dbu
    
    def _um_to_dbu(self, um_value):
        """Convert micrometers to database units."""
        return int(round(um_value / self.wafer_config.dbu))
    
    def create_omega(self, cell, x_center, y_center, omega_config=None, chip_config=None):
        """
        Create omega resonator design inside the chip aperture.
        
        Places 4 rings at diagonal positions from the center,
        separated by (outer_radius + omega_spacing) from center.
        Each ring has a gap cut at top (for top rings) or bottom (for bottom rings)
        to break the loop. Top rings are offset left, bottom rings offset right.
        
        Args:
            cell: KLayout cell to insert design into
            x_center: x-coordinate of aperture center (µm)
            y_center: y-coordinate of aperture center (µm)
            omega_config: OmegaConfig instance for omega parameters
            chip_config: ChipConfig instance for chip parameters (aperture size)
        
        Returns:
            None (modifies cell in place)
        """
        if omega_config is None:
            raise ValueError("omega_config must be provided")
        if chip_config is None:
            chip_config = self.chip_configs[0]  # Use first chip config as default
        
        center_radius = omega_config.center_radius
        trace_width = omega_config.trace_width
        spacing = omega_config.omega_spacing
        trace_gap = omega_config.omega_trace_gap
        
        # Calculate inner and outer radii from center_radius and trace_width
        outer_radius = center_radius + trace_width / 2.0
        inner_radius = center_radius - trace_width / 2.0
        
        # Distance from center to each ring center (along diagonal)
        # Each ring is placed so its outer edge is omega_spacing from center
        offset = outer_radius + spacing
        
        # Horizontal offset for top/bottom rings
        h_offset = trace_gap / 2.0 + trace_width / 2.0
        
        # Four diagonal positions with horizontal offsets:
        # Top rings offset left, bottom rings offset right
        positions = [
            (x_center + offset - h_offset, y_center + offset, 'bottom'),
            (x_center - offset - h_offset, y_center + offset, 'bottom'),
            (x_center - offset + h_offset, y_center - offset, 'top'),
            (x_center + offset + h_offset, y_center - offset, 'top'), 
        ]
        
        layer_idx = self.layout.layer(omega_config.METAL_LAYER)
        num_segments = 64  # Circle approximation segments
        
        for cx, cy, ring_type in positions:
            # Create outer circle
            outer_points = []
            for i in range(num_segments):
                angle = 2.0 * math.pi * i / num_segments
                x = self._um_to_dbu(cx + outer_radius * math.cos(angle))
                y = self._um_to_dbu(cy + outer_radius * math.sin(angle))
                outer_points.append(pya.Point(x, y))
            outer_polygon = pya.Polygon(outer_points)
            outer_region = pya.Region(outer_polygon)
            
            # Create inner circle
            inner_points = []
            for i in range(num_segments):
                angle = 2.0 * math.pi * i / num_segments
                x = self._um_to_dbu(cx + inner_radius * math.cos(angle))
                y = self._um_to_dbu(cy + inner_radius * math.sin(angle))
                inner_points.append(pya.Point(x, y))
            inner_polygon = pya.Polygon(inner_points)
            inner_region = pya.Region(inner_polygon)
            
            # Subtract inner from outer to create ring
            ring_region = outer_region - inner_region
            
            # Create gap rectangle to break the loop
            # Gap is at top for top rings, at bottom for bottom rings
            if ring_type == 'top':
                # Gap at top of ring
                gap_box = pya.Box(
                    self._um_to_dbu(cx - trace_gap / 2.0),
                    self._um_to_dbu(cy),  # From center to top
                    self._um_to_dbu(cx + trace_gap / 2.0),
                    self._um_to_dbu(cy + outer_radius + trace_width)  # Extend past outer edge
                )
            else:
                # Gap at bottom of ring
                gap_box = pya.Box(
                    self._um_to_dbu(cx - trace_gap / 2.0),
                    self._um_to_dbu(cy - outer_radius - trace_width),  # Extend past outer edge
                    self._um_to_dbu(cx + trace_gap / 2.0),
                    self._um_to_dbu(cy)  # From bottom to center
                )
            
            gap_region = pya.Region(gap_box)
            ring_region -= gap_region
            
            cell.shapes(layer_idx).insert(ring_region)
        
        # Create vertical rectangles connecting each top/bottom pair
        # Rectangle goes from right of top ring to left of bottom ring
        # Offset from center by h_offset, width = trace_width
        
        # Right pair: connects top-right to bottom-right
        # Top ring center: (x_center + offset - h_offset, y_center + offset)
        # Bottom ring center: (x_center + offset + h_offset, y_center - offset)
        # Connection is at x = x_center + offset (between the two ring centers)
        right_conn_x = x_center + offset
        right_conn_box = pya.Box(
            self._um_to_dbu(right_conn_x - trace_width / 2.0),
            self._um_to_dbu(y_center - offset + outer_radius - trace_width),  # Bottom of top ring
            self._um_to_dbu(right_conn_x + trace_width / 2.0),
            self._um_to_dbu(y_center + offset - outer_radius + trace_width)   # Top of bottom ring
        )
        cell.shapes(layer_idx).insert(right_conn_box)
        
        # Left pair: connects top-left to bottom-left
        # Top ring center: (x_center - offset - h_offset, y_center + offset)
        # Bottom ring center: (x_center - offset + h_offset, y_center - offset)
        # Connection is at x = x_center - offset (between the two ring centers)
        left_conn_x = x_center - offset
        left_conn_box = pya.Box(
            self._um_to_dbu(left_conn_x - trace_width / 2.0),
            self._um_to_dbu(y_center - offset + outer_radius - trace_width),  # Bottom of top ring
            self._um_to_dbu(left_conn_x + trace_width / 2.0),
            self._um_to_dbu(y_center + offset - outer_radius + trace_width)   # Top of bottom ring
        )
        cell.shapes(layer_idx).insert(left_conn_box)
        
        # Create vertical rectangles from the other ring ends (left side) to center y level
        # These connect the left openings of top rings and right openings of bottom rings to y_center
        
        # Top-right ring (left opening at x = x_center + offset - h_offset)
        top_right_feed_x = x_center + offset - 2*h_offset
        top_right_feed_box = pya.Box(
            self._um_to_dbu(top_right_feed_x - trace_width / 2.0),
            self._um_to_dbu(y_center),  # Center level
            self._um_to_dbu(top_right_feed_x + trace_width / 2.0),
            self._um_to_dbu(y_center + offset - outer_radius + trace_width)  # Bottom of top ring
        )
        cell.shapes(layer_idx).insert(top_right_feed_box)
        
        # Top-left ring (left opening at x = x_center - offset - h_offset)
        top_left_feed_x = x_center - offset - 2*h_offset
        top_left_feed_box = pya.Box(
            self._um_to_dbu(top_left_feed_x - trace_width / 2.0),
            self._um_to_dbu(y_center),  # Center level
            self._um_to_dbu(top_left_feed_x + trace_width / 2.0),
            self._um_to_dbu(y_center + offset - outer_radius + trace_width)  # Bottom of top ring
        )
        cell.shapes(layer_idx).insert(top_left_feed_box)
        
        # Bottom-right ring (right opening at x = x_center + offset + h_offset)
        bottom_right_feed_x = x_center + offset + 2*h_offset
        bottom_right_feed_box = pya.Box(
            self._um_to_dbu(bottom_right_feed_x - trace_width / 2.0),
            self._um_to_dbu(y_center - offset + outer_radius - trace_width),  # Top of bottom ring
            self._um_to_dbu(bottom_right_feed_x + trace_width / 2.0),
            self._um_to_dbu(y_center)  # Center level
        )
        cell.shapes(layer_idx).insert(bottom_right_feed_box)
        
        # Bottom-left ring (right opening at x = x_center - offset + h_offset)
        bottom_left_feed_x = x_center - offset + 2*h_offset
        bottom_left_feed_box = pya.Box(
            self._um_to_dbu(bottom_left_feed_x - trace_width / 2.0),
            self._um_to_dbu(y_center - offset + outer_radius - trace_width),  # Top of bottom ring
            self._um_to_dbu(bottom_left_feed_x + trace_width / 2.0),
            self._um_to_dbu(y_center)  # Center level
        )
        cell.shapes(layer_idx).insert(bottom_left_feed_box)
        
        # Create rectangles connecting CPW ends to the feed lines
        # CPW ends are at x = ±aperture_radius from center
        # The three rectangles connect left CPW end to left feeds, 
        # and right CPW end to right feeds, plus middle connector
        
        cpw_end_left = x_center - chip_config.aperture_radius
        cpw_end_right = x_center + chip_config.aperture_radius
        
        # Left CPW to left feeds
        # Connects from cpw_end_left to top_left_feed and bottom_left_feed
        # Create a rectangle from CPW end to just past the middle of top-left feed
        top_left_cpw_box = pya.Box(
            self._um_to_dbu(cpw_end_left),
            self._um_to_dbu(y_center-trace_width/2),  # Center level
            self._um_to_dbu(top_left_feed_x + trace_width / 2.0),  # Go trace_width/2 past center
            self._um_to_dbu(y_center + trace_width/2)  # Height = trace_width
        )
        cell.shapes(layer_idx).insert(top_left_cpw_box)
        
        # Right CPW to right feeds
        # Connects from cpw_end_right to top_right_feed and bottom_right_feed
        # Create a rectangle from CPW end to just past the middle of top-right feed
        top_right_cpw_box = pya.Box(
            self._um_to_dbu(bottom_right_feed_x - trace_width / 2.0),  # Go trace_width/2 past center
            self._um_to_dbu(y_center - trace_width/2),  # Center level
            self._um_to_dbu(cpw_end_right),
            self._um_to_dbu(y_center + trace_width/2)  # Height = trace_width
        )
        cell.shapes(layer_idx).insert(top_right_cpw_box)
        
        # Middle connector between left and right feed lines
        # Connects from bottom_left_feed to bottom_right_feed
        # (or equivalently between the two vertical sections in the middle)
        middle_connector_box = pya.Box(
            self._um_to_dbu(bottom_left_feed_x - trace_width / 2.0),  # Go trace_width/2 past left feed
            self._um_to_dbu(y_center - trace_width/2),  # Below center level
            self._um_to_dbu(top_right_feed_x + trace_width / 2.0),  # Go trace_width/2 past right feed
            self._um_to_dbu(y_center + trace_width/2)  # Up to center level
        )
        cell.shapes(layer_idx).insert(middle_connector_box)
        
        # Create tapers from CPW width to omega trace width
        # Left taper: from CPW signal width to omega trace width
        cpw_signal_width = chip_config.cpw_signal_width
        taper_length = omega_config.omega_taper_length
        
        # Left CPW taper (from cpw_end_left going inward to x_center)
        # Tapers from cpw_signal_width to trace_width
        left_taper_vertices = [
            pya.Point(self._um_to_dbu(cpw_end_left), self._um_to_dbu(y_center - cpw_signal_width / 2.0)),
            pya.Point(self._um_to_dbu(cpw_end_left + taper_length), self._um_to_dbu(y_center - trace_width / 2.0)),
            pya.Point(self._um_to_dbu(cpw_end_left + taper_length), self._um_to_dbu(y_center + trace_width / 2.0)),
            pya.Point(self._um_to_dbu(cpw_end_left), self._um_to_dbu(y_center + cpw_signal_width / 2.0)),
        ]
        left_taper_polygon = pya.Polygon(left_taper_vertices)
        cell.shapes(layer_idx).insert(left_taper_polygon)
        
        # Right CPW taper (from cpw_end_right going inward to x_center)
        # Tapers from cpw_signal_width to trace_width
        right_taper_vertices = [
            pya.Point(self._um_to_dbu(cpw_end_right - taper_length), self._um_to_dbu(y_center - trace_width / 2.0)),
            pya.Point(self._um_to_dbu(cpw_end_right), self._um_to_dbu(y_center - cpw_signal_width / 2.0)),
            pya.Point(self._um_to_dbu(cpw_end_right), self._um_to_dbu(y_center + cpw_signal_width / 2.0)),
            pya.Point(self._um_to_dbu(cpw_end_right - taper_length), self._um_to_dbu(y_center + trace_width / 2.0)),
        ]
        right_taper_polygon = pya.Polygon(right_taper_vertices)
        cell.shapes(layer_idx).insert(right_taper_polygon)
        
        print(f"  → Omega design: 4 rings (r={center_radius:.0f} µm, w={trace_width:.0f} µm, gap={trace_gap:.0f} µm) at ({x_center:.0f}, {y_center:.0f}) µm")
    
    def create_wafer_outline(self, cell):
        """
        Create wafer outline with flat (for reference, not metal).
        
        Args:
            cell: KLayout cell to insert outline into
        
        Returns:
            pya.Region representing the wafer area
        """
        config = self.wafer_config
        
        # Create circular wafer outline
        num_segments = 256  # High precision circle
        wafer_points = []
        
        # Wafer center at origin
        center_x = 0
        center_y = 0
        
        for i in range(num_segments):
            angle = 2.0 * math.pi * i / num_segments
            x = center_x + self._um_to_dbu(config.wafer_radius * math.cos(angle))
            y = center_y + self._um_to_dbu(config.wafer_radius * math.sin(angle))
            wafer_points.append(pya.Point(x, y))
        
        wafer_polygon = pya.Polygon(wafer_points)
        wafer_region = pya.Region(wafer_polygon)
        
        # Subtract flat at bottom of wafer
        # Flat is a horizontal cut at y = -wafer_radius + flat_depth
        flat_y = -config.wafer_radius + config.flat_depth
        flat_box = pya.Box(
            self._um_to_dbu(-config.flat_length / 2.0),
            self._um_to_dbu(-config.wafer_radius - 1000),  # Extend below wafer
            self._um_to_dbu(config.flat_length / 2.0),
            self._um_to_dbu(flat_y)
        )
        wafer_region -= pya.Region(flat_box)
        
        return wafer_region
    
    def create_wafer_guide(self, cell):
        """
        Create wafer outline guide with flat on the GUIDE_LAYER.
        This provides an alignment reference showing the full wafer size.
        
        Args:
            cell: KLayout cell to insert guide into
        """
        config = self.wafer_config
        guide_layer_idx = self.layout.layer(config.GUIDE_LAYER)
        
        # Create circular wafer outline
        num_segments = 360  # High precision circle
        wafer_points = []
        
        # Wafer center at origin
        center_x = 0
        center_y = 0
        
        for i in range(num_segments):
            angle = 2.0 * math.pi * i / num_segments
            x = center_x + self._um_to_dbu(config.wafer_radius * math.cos(angle))
            y = center_y + self._um_to_dbu(config.wafer_radius * math.sin(angle))
            wafer_points.append(pya.Point(x, y))
        
        wafer_polygon = pya.Polygon(wafer_points)
        wafer_region = pya.Region(wafer_polygon)
        
        # Subtract flat at bottom of wafer
        # Flat is a horizontal cut at y = -wafer_radius + flat_depth
        flat_y = -config.wafer_radius + config.flat_depth
        flat_box = pya.Box(
            self._um_to_dbu(-config.flat_length / 2.0),
            self._um_to_dbu(-config.wafer_radius - 1000),  # Extend below wafer
            self._um_to_dbu(config.flat_length / 2.0),
            self._um_to_dbu(flat_y)
        )
        wafer_region -= pya.Region(flat_box)
        
        # Insert wafer outline on guide layer
        cell.shapes(guide_layer_idx).insert(wafer_region)
        
        print(f"  Added wafer guide outline with flat on layer {config.GUIDE_LAYER}")
    
    def create_wafer_edge_contacts(self, cell):
        """
        Create contact rectangles on left, right, and top edges of the wafer.
        Contacts fill the buffer zone from usable area to wafer edge.
        
        Args:
            cell: KLayout cell to insert contacts into
        """
        config = self.wafer_config
        metal_layer_idx = self.layout.layer(config.METAL_LAYER)
        
        contact_w = config.edge_contact_width  # Width along the edge (10mm)
        contact_inset = 5000.0  # Move contacts in by 5 mm from usable boundary
        outer_inset = 3300.0    # Move outer edge in by 4 mm from wafer edge
        inner_inset = 3000.0
        flat_exclusion_zone = 2250.0  # 2.25mm exclusion zone from flat
        flat_y = -config.wafer_radius + config.flat_depth
        
        # Usable radius defines inner boundary; contacts go between usable_radius and wafer_radius
        usable_radius = (config.wafer_diameter - 2 * config.wafer_buffer) / 2.0
        wafer_r = config.wafer_radius
        
        contacts_added = 0
        
        # TOP contact - centered at top of wafer
        # Extends from (usable_radius - contact_inset - 3000) to (wafer edge - 3mm)
        x_center = 0
        y_inner = usable_radius - contact_inset + inner_inset  # Inner edge moved in by 8mm total
        y_outer = wafer_r - outer_inset  # Outer edge 3mm in from wafer edge
        box = pya.Box(
            self._um_to_dbu(x_center - contact_w / 2),
            self._um_to_dbu(y_inner),
            self._um_to_dbu(x_center + contact_w / 2),
            self._um_to_dbu(y_outer)
        )
        cell.shapes(metal_layer_idx).insert(box)
        contacts_added += 1
        top_depth = y_outer - y_inner
        
        # LEFT contact - centered at left of wafer (only if not too close to flat)
        # Extends from -(usable_radius - contact_inset) to (wafer edge - 3mm)
        y_center = 0
        x_inner = -(usable_radius - contact_inset)  # Inner edge moved in by 5mm
        x_outer = -(wafer_r - outer_inset)  # Outer edge 3mm in from wafer edge
        
        # Check if contact would be too close to flat
        if y_center - contact_w / 2 >= flat_y + flat_exclusion_zone:
            box = pya.Box(
                self._um_to_dbu(x_outer),
                self._um_to_dbu(y_center - contact_w / 2),
                self._um_to_dbu(x_inner),
                self._um_to_dbu(y_center + contact_w / 2)
            )
            cell.shapes(metal_layer_idx).insert(box)
            contacts_added += 1
        left_depth = x_inner - x_outer
        
        # RIGHT contact - centered at right of wafer (only if not too close to flat)
        # Extends from (usable_radius - contact_inset) to (wafer edge - 3mm)
        y_center = 0
        x_inner = usable_radius - contact_inset  # Inner edge moved in by 5mm
        x_outer = wafer_r - outer_inset  # Outer edge 3mm in from wafer edge
        
        # Check if contact would be too close to flat
        if y_center - contact_w / 2 >= flat_y + flat_exclusion_zone:
            box = pya.Box(
                self._um_to_dbu(x_inner),
                self._um_to_dbu(y_center - contact_w / 2),
                self._um_to_dbu(x_outer),
                self._um_to_dbu(y_center + contact_w / 2)
            )
            cell.shapes(metal_layer_idx).insert(box)
            contacts_added += 1
        right_depth = x_outer - x_inner
        
        print(f"  Added {contacts_added} wafer edge contacts ({contact_w/1000:.0f} mm wide, ~{top_depth/1000:.1f} mm deep)")

    def create_wafer_ring_guide(self, cell):
        """
        Add a 1mm wide ring at 94mm diameter on the METAL_LAYER.
        Excludes portion within 2.25mm of wafer flat.
        """
        config = self.wafer_config
        metal_layer_idx = self.layout.layer(config.METAL_LAYER)
        outer_radius = 94000.0 / 2.0  # 94mm diameter
        inner_radius = outer_radius - 500.0  # 0.5mm wide ring
        flat_exclusion_zone = 2250.0  # 2.25mm exclusion zone from flat
        flat_y = -config.wafer_radius + config.flat_depth
        
        num_segments = 360
        center_x = 0
        center_y = 0
        
        # Create outer circle
        outer_points = []
        for i in range(num_segments):
            angle = 2 * math.pi * i / num_segments
            outer_x = center_x + outer_radius * math.cos(angle)
            outer_y = center_y + outer_radius * math.sin(angle)
            outer_points.append(pya.Point(
                self._um_to_dbu(outer_x),
                self._um_to_dbu(outer_y)))
        outer_polygon = pya.Polygon(outer_points)
        outer_region = pya.Region(outer_polygon)
        
        # Create inner circle
        inner_points = []
        for i in range(num_segments):
            angle = 2 * math.pi * i / num_segments
            inner_x = center_x + inner_radius * math.cos(angle)
            inner_y = center_y + inner_radius * math.sin(angle)
            inner_points.append(pya.Point(
                self._um_to_dbu(inner_x),
                self._um_to_dbu(inner_y)))
        inner_polygon = pya.Polygon(inner_points)
        inner_region = pya.Region(inner_polygon)
        
        # Subtract inner from outer to get ring
        ring_region = outer_region - inner_region
        
        # Subtract exclusion zone near flat (everything below exclusion_y)
        exclusion_y = flat_y + flat_exclusion_zone
        exclusion_box = pya.Box(
            self._um_to_dbu(-outer_radius - 1000),
            self._um_to_dbu(-outer_radius - 1000),
            self._um_to_dbu(outer_radius + 1000),
            self._um_to_dbu(exclusion_y)
        )
        ring_region -= pya.Region(exclusion_box)
        
        cell.shapes(metal_layer_idx).insert(ring_region)
        
        # Add horizontal connector at the base of the ring (just above exclusion zone)
        # This connects the two cut ends of the ring
        # Calculate x positions where the ring intersects the exclusion line
        # At y = exclusion_y, we need to find x values on the outer and inner circles
        ring_width = outer_radius - inner_radius
        
        # For outer circle: x = sqrt(r^2 - y^2)
        if abs(exclusion_y) < outer_radius:
            outer_x_extent = math.sqrt(outer_radius * outer_radius - exclusion_y * exclusion_y)
        else:
            outer_x_extent = 0
        
        if abs(exclusion_y) < inner_radius:
            inner_x_extent = math.sqrt(inner_radius * inner_radius - exclusion_y * exclusion_y)
        else:
            inner_x_extent = 0
        
        # Create horizontal connector bar just above exclusion zone
        # Bar connects from -outer_x_extent to +outer_x_extent at the ring width
        connector_height = ring_width  # Same thickness as ring
        connector_box = pya.Box(
            self._um_to_dbu(-outer_x_extent),
            self._um_to_dbu(exclusion_y),
            self._um_to_dbu(outer_x_extent),
            self._um_to_dbu(exclusion_y + connector_height)
        )
        cell.shapes(metal_layer_idx).insert(connector_box)
        
        print("  Added 0.5mm wide ring at 94mm diameter on METAL_LAYER (excluding flat zone, with base connector)")
    
    def chip_fits_in_wafer(self, chip_x, chip_y, chip_width, chip_height, usable_radius):
        """
        Check if a chip rectangle fits entirely within the usable wafer circle.
        
        Args:
            chip_x: x-coordinate of chip bottom-left corner (µm)
            chip_y: y-coordinate of chip bottom-left corner (µm)
            chip_width: chip width (µm)
            chip_height: chip height (µm)
            usable_radius: radius of usable wafer area (µm)
        
        Returns:
            bool: True if all 4 corners of chip are within the circle
        """
        # Check all 4 corners of the chip
        corners = [
            (chip_x, chip_y),                           # Bottom-left
            (chip_x + chip_width, chip_y),              # Bottom-right
            (chip_x, chip_y + chip_height),             # Top-left
            (chip_x + chip_width, chip_y + chip_height) # Top-right
        ]
        
        for cx, cy in corners:
            # Distance from wafer center (0, 0) to corner
            dist = math.sqrt(cx * cx + cy * cy)
            if dist > usable_radius:
                return False
        return True
    
    def chip_too_close_to_flat(self, chip_x, chip_y, chip_width, chip_height):
        """
        Check if a chip is within 2.25mm of the wafer flat.
        
        Args:
            chip_x: x-coordinate of chip bottom-left corner (µm)
            chip_y: y-coordinate of chip bottom-left corner (µm)
            chip_width: chip width (µm)
            chip_height: chip height (µm)
        
        Returns:
            True if chip is too close to flat (within 2.25mm)
        """
        config = self.wafer_config
        flat_y = -config.wafer_radius + config.flat_depth
        flat_exclusion_zone = 2250.0  # 2.25mm exclusion zoneone
        
        # Bottom edge of chip
        chip_bottom = chip_y
        # Top edge of chip
        chip_top = chip_y + chip_height
        
        # Check if any part of the chip is within 2mm of the flat
        # The flat is at flat_y, so exclude chips with bottom edge < flat_y + 2mm
        if chip_bottom < flat_y + flat_exclusion_zone:
            return True
        return False
    
    def calculate_full_wafer_chip_positions(self):
        """
        Calculate all chip positions that fit within the usable wafer area.
        
        The 2x3 unit cell is repeated across the wafer, and only chips that
        fully fit within (wafer_diameter - 2*wafer_buffer)/2 radius are included.
        
        Returns:
            List of (chip_x, chip_y, unit_row, unit_col) tuples for all valid chip positions
        """
        config = self.wafer_config
        base_chip_config = self.chip_configs[0]
        
        chip_width = base_chip_config.chip_width
        chip_height = base_chip_config.chip_height
        spacing = config.chip_spacing
        
        # Usable wafer radius
        usable_radius = (config.wafer_diameter - 2 * config.wafer_buffer) / 2.0
        
        # Size of the 2x3 unit cell
        unit_width = config.chip_count_x * chip_width + (config.chip_count_x - 1) * spacing
        unit_height = config.chip_count_y * chip_height + (config.chip_count_y - 1) * spacing
        
        # Calculate how many unit cells could potentially fit
        # Use generous bounds to ensure we check all possible positions
        max_units_x = int(math.ceil(config.wafer_diameter / unit_width)) + 1
        max_units_y = int(math.ceil(config.wafer_diameter / unit_height)) + 1
        
        # Center the grid on the wafer
        # Start position for unit cell (0, 0) - centered on wafer
        grid_start_x = -unit_width / 2.0
        grid_start_y = -unit_height / 2.0
        
        valid_positions = []
        
        # Iterate over all possible unit cell positions
        for unit_row in range(-max_units_y // 2, max_units_y // 2 + 1):
            for unit_col in range(-max_units_x // 2, max_units_x // 2 + 1):
                # Calculate unit cell origin
                unit_x = grid_start_x + unit_col * unit_width
                unit_y = grid_start_y + unit_row * unit_height
                
                # Check each chip in the 2x3 unit cell
                for row in range(config.chip_count_y):
                    for col in range(config.chip_count_x):
                        chip_x = unit_x + col * (chip_width + spacing)
                        chip_y = unit_y + row * (chip_height + spacing)
                        
                        if (self.chip_fits_in_wafer(chip_x, chip_y, chip_width, chip_height, usable_radius) and
                            not self.chip_too_close_to_flat(chip_x, chip_y, chip_width, chip_height)):
                            # Store position along with which chip in the 2x3 pattern
                            chip_index = row * config.chip_count_x + col
                            valid_positions.append((chip_x, chip_y, chip_index))
        
        return valid_positions
    
    def create_electroplating_dicing_traces(self, wafer_cell, chip_positions):
        """
        Create electroplating traces along dicing lanes between chips.
        
        Traces run along the horizontal and vertical dicing lanes, extending
        to the edge of the usable wafer area.
        
        Args:
            wafer_cell: Parent cell for the wafer
            chip_positions: List of (chip_x, chip_y, chip_index) tuples
        """
        config = self.wafer_config
        base_chip_config = self.chip_configs[0]
        
        chip_width = base_chip_config.chip_width
        chip_height = base_chip_config.chip_height
        tab_width = config.electroplating_tab_width
        usable_radius = (config.wafer_diameter - 2 * config.wafer_buffer) / 2.0
        flat_exclusion_zone = 2250.0  # 2.25mm exclusion zone from flat
        flat_y = -config.wafer_radius + config.flat_depth
        
        layer_idx = self.layout.layer(config.METAL_LAYER)
        
        # Collect unique x and y coordinates for dicing lanes
        # Dicing lanes are at chip edges
        x_coords = set()
        y_coords = set()
        
        for chip_x, chip_y, _ in chip_positions:
            # Left and right edges of each chip
            x_coords.add(chip_x)
            x_coords.add(chip_x + chip_width)
            # Bottom and top edges of each chip
            y_coords.add(chip_y)
            y_coords.add(chip_y + chip_height)
        
        # Create vertical traces at each unique x coordinate
        for x in sorted(x_coords):
            # Calculate the extent of the trace in y direction
            # It should go from the usable wafer edge to the other edge,
            # but clipped to the wafer circle and excluding flat zone
            
            # Find y range where x is within the usable circle
            if abs(x) < usable_radius:
                y_extent = math.sqrt(usable_radius * usable_radius - x * x)
                
                # Clip bottom extent to respect flat exclusion zone
                y_bottom = max(-y_extent, flat_y + flat_exclusion_zone)
                y_top = y_extent
                
                # Only create trace if there's a valid range
                if y_bottom < y_top:
                    # Create vertical trace
                    trace = pya.Box(
                        self._um_to_dbu(x - tab_width / 2.0),
                        self._um_to_dbu(y_bottom),
                        self._um_to_dbu(x + tab_width / 2.0),
                        self._um_to_dbu(y_top)
                    )
                    wafer_cell.shapes(layer_idx).insert(trace)
        
        # Create horizontal traces at each unique y coordinate
        for y in sorted(y_coords):
            # Only create horizontal traces that are above the flat exclusion zone
            if y >= flat_y + flat_exclusion_zone:
                # Find x range where y is within the usable circle
                if abs(y) < usable_radius:
                    x_extent = math.sqrt(usable_radius * usable_radius - y * y)
                    
                    # Create horizontal trace
                    trace = pya.Box(
                        self._um_to_dbu(-x_extent),
                        self._um_to_dbu(y - tab_width / 2.0),
                        self._um_to_dbu(x_extent),
                        self._um_to_dbu(y + tab_width / 2.0)
                    )
                    wafer_cell.shapes(layer_idx).insert(trace)
    
    def create_right_pad_electroplating_tab(self, cell, chip_config):
        """
        Create electroplating tab on the right side CPW bond pad.
        
        This adds a metal tab extending from the right bond pad to the chip edge
        for electroplating connection. Used only on blank (no-omega) chips.
        
        Args:
            cell: KLayout cell to insert tab into
            chip_config: Chip configuration with pad and dimension parameters
        """
        config = chip_config
        layer_idx = self.layout.layer(config.METAL_LAYER)
        
        # Right bond pad center position
        chip_center_x = config.chip_width / 2.0
        chip_center_y = config.chip_height / 2.0
        
        # Right pad is at the right edge of the chip
        # Pad center x = chip_width - edge_buffer - pad_width/2
        right_pad_center_x = config.chip_width - config.edge_buffer - config.pad_width / 2.0
        right_pad_center_y = chip_center_y
        
        # Electroplating tab extends from right edge of pad to chip edge
        tab_width = config.electroplating_tab_width
        tab_start_x = right_pad_center_x + config.pad_width / 2.0  # Right edge of pad
        tab_end_x = config.chip_width - config.dicing_margin  # To chip edge (with dicing margin)
        
        # Create the tab as a rectangle
        tab_box = pya.Box(
            self._um_to_dbu(tab_start_x),
            self._um_to_dbu(right_pad_center_y - tab_width / 2.0),
            self._um_to_dbu(tab_end_x),
            self._um_to_dbu(right_pad_center_y + tab_width / 2.0)
        )
        cell.shapes(layer_idx).insert(tab_box)
        
        print(f"    → Added electroplating tab on right CPW pad (blank chip)")
    
    def create_unit_cell(self):
        """
        Create a unit cell containing all chip variants in a 2x3 pattern.
        
        The unit cell contains all 6 chip designs (or however many are configured)
        arranged in a chip_count_x by chip_count_y grid. This unit cell is then
        repeated across the wafer.
        
        Returns:
            Tuple of (unit_cell, chip_variant_cells, unit_width, unit_height) 
            where chip_variant_cells is a list of (cell, local_x, local_y) for each variant
            and dimensions are in µm
        """
        config = self.wafer_config
        base_chip_config = self.chip_configs[0]
        
        chip_width = base_chip_config.chip_width
        chip_height = base_chip_config.chip_height
        spacing = config.chip_spacing
        
        # Calculate unit cell dimensions
        unit_width = config.chip_count_x * chip_width + (config.chip_count_x - 1) * spacing
        unit_height = config.chip_count_y * chip_height + (config.chip_count_y - 1) * spacing
        
        # Create the unit cell
        unit_cell = self.layout.create_cell("unit_cell_2x3")
        
        print(f"  Creating unit cell ({config.chip_count_x}x{config.chip_count_y}) with {len(self.chip_configs)} chip variants")
        
        chip_variant_cells = []  # List of (cell, local_x, local_y, chip_config, omega_config)
        chip_index = 0
        for row in range(config.chip_count_y):
            for col in range(config.chip_count_x):
                # Get per-chip config
                chip_config = self.chip_configs[chip_index] if chip_index < len(self.chip_configs) else base_chip_config
                omega_config = self.omega_configs[chip_index] if chip_index < len(self.omega_configs) else None
                
                # Calculate chip position within unit cell (origin at bottom-left)
                chip_x = col * (chip_width + spacing)
                chip_y = row * (chip_height + spacing)
                
                # Determine label for this chip based on omega config
                chip_label = None
                if omega_config is not None:
                    chip_label = f"{omega_config.center_radius * 2:.0f} um"
                
                # Create chip cell with per-chip config and optional label
                chip_name = f"chip_variant_{chip_index}"
                chip_cell = create_chip_cell(
                    self.layout, 
                    config=chip_config, 
                    chip_name=chip_name,
                    label=chip_label
                )
                
                # Add omega design to a wrapper cell that includes chip + omega
                wrapper_name = f"chip_with_omega_{chip_index}"
                wrapper_cell = self.layout.create_cell(wrapper_name)
                
                # Insert chip at origin of wrapper
                wrapper_cell.insert(pya.CellInstArray(chip_cell.cell_index(), pya.Trans()))
                
                # Add omega design if omega_config is provided for this chip
                if omega_config is not None:
                    aperture_x = chip_config.chip_width / 2.0
                    aperture_y = chip_config.chip_height / 2.0
                    self.create_omega(wrapper_cell, aperture_x, aperture_y, omega_config, chip_config)
                else:
                    # For blank chips (no omega), add electroplating tab on right CPW bond pad
                    self.create_right_pad_electroplating_tab(wrapper_cell, chip_config)
                
                # Store wrapper cell info for later placement
                chip_variant_cells.append((wrapper_cell, chip_x, chip_y, chip_config, omega_config))
                
                # Insert wrapper into unit cell
                chip_trans = pya.Trans(
                    self._um_to_dbu(chip_x),
                    self._um_to_dbu(chip_y)
                )
                unit_cell.insert(pya.CellInstArray(wrapper_cell.cell_index(), chip_trans))
                
                print(f"    Chip variant {chip_index} at ({chip_x:.0f}, {chip_y:.0f}) µm", end="")
                if omega_config is not None:
                    print(f" (ω radius: {omega_config.center_radius:.0f} µm)")
                else:
                    print(" (blank - no omega)")
                
                chip_index += 1
        
        return unit_cell, chip_variant_cells, unit_width, unit_height
    
    def calculate_chip_positions_from_unit_grid(self, unit_width, unit_height, chip_variant_cells):
        """
        Calculate all individual chip positions based on unit cell grid pattern.
        
        Chips are placed individually - a chip is included if it fits within
        the usable wafer area, even if other chips in its unit cell don't fit.
        
        Args:
            unit_width: Width of unit cell (µm)
            unit_height: Height of unit cell (µm)
            chip_variant_cells: List of (cell, local_x, local_y, chip_config, omega_config)
        
        Returns:
            List of (wafer_x, wafer_y, variant_index) tuples for all valid chip positions
        """
        config = self.wafer_config
        base_chip_config = self.chip_configs[0]
        
        chip_width = base_chip_config.chip_width
        chip_height = base_chip_config.chip_height
        
        # Usable wafer radius
        usable_radius = (config.wafer_diameter - 2 * config.wafer_buffer) / 2.0
        
        # Calculate how many unit cells could potentially fit
        max_units_x = int(math.ceil(config.wafer_diameter / unit_width)) + 1
        max_units_y = int(math.ceil(config.wafer_diameter / unit_height)) + 1
        
        # Center the grid on the wafer
        grid_start_x = -unit_width / 2.0
        grid_start_y = -unit_height / 2.0
        
        valid_positions = []
        
        # Iterate over all possible unit cell positions
        for unit_row in range(-max_units_y // 2, max_units_y // 2 + 1):
            for unit_col in range(-max_units_x // 2, max_units_x // 2 + 1):
                # Calculate unit cell origin
                unit_x = grid_start_x + unit_col * unit_width
                unit_y = grid_start_y + unit_row * unit_height
                
                # Check each chip variant in this unit cell position individually
                for variant_idx, (cell, local_x, local_y, chip_config, omega_config) in enumerate(chip_variant_cells):
                    chip_x = unit_x + local_x
                    chip_y = unit_y + local_y
                    
                    # Check if THIS individual chip fits
                    if (self.chip_fits_in_wafer(chip_x, chip_y, chip_width, chip_height, usable_radius) and
                        not self.chip_too_close_to_flat(chip_x, chip_y, chip_width, chip_height)):
                        valid_positions.append((chip_x, chip_y, variant_idx))
        
        return valid_positions
    
    def create_full_wafer_layout(self, wafer_cell):
        """
        Create complete chip mask covering the full usable wafer area.
        
        Creates chip variant cells, then places them individually across the wafer
        based on the unit cell grid pattern. Each chip is placed if it individually
        fits within the usable area, even if other chips in its unit cell don't fit.
        
        Args:
            wafer_cell: Parent cell for the wafer
        
        Returns:
            List of (wafer_x, wafer_y, variant_index) tuples for all placed chips
        """
        config = self.wafer_config
        base_chip_config = self.chip_configs[0]
        
        chip_width = base_chip_config.chip_width
        chip_height = base_chip_config.chip_height
        spacing = config.chip_spacing
        
        # Create the unit cell with all chip variants (also returns individual variant cells)
        unit_cell, chip_variant_cells, unit_width, unit_height = self.create_unit_cell()
        
        # Get all valid individual chip positions
        chip_positions = self.calculate_chip_positions_from_unit_grid(unit_width, unit_height, chip_variant_cells)
        
        print(f"  Found {len(chip_positions)} individual chip positions that fit in usable wafer area")
        
        # Place individual chips across the wafer
        for chip_x, chip_y, variant_idx in chip_positions:
            wrapper_cell = chip_variant_cells[variant_idx][0]
            chip_trans = pya.Trans(
                self._um_to_dbu(chip_x),
                self._um_to_dbu(chip_y)
            )
            wafer_cell.insert(pya.CellInstArray(wrapper_cell.cell_index(), chip_trans))
        
        # Add electroplating dicing traces if enabled
        if config.electroplating:
            print("  Adding electroplating dicing traces...")
            self.create_electroplating_dicing_traces(wafer_cell, chip_positions)
        
        return chip_positions
    
    def create_chip_array(self, wafer_cell):
        """
        Create 2x3 array of chips at wafer center.
        
        Args:
            wafer_cell: Parent cell for the wafer
        
        Returns:
            List of (chip_cell, x_offset, y_offset) tuples
        """
        config = self.wafer_config
        
        # Use first chip config for array layout calculations (all chips same size)
        base_chip_config = self.chip_configs[0]
        
        # Calculate chip positions (centered on wafer)
        chip_width = base_chip_config.chip_width
        chip_height = base_chip_config.chip_height
        spacing = config.chip_spacing
        
        # Total array size
        array_width = config.chip_count_x * chip_width + (config.chip_count_x - 1) * spacing
        array_height = config.chip_count_y * chip_height + (config.chip_count_y - 1) * spacing
        
        # Starting position (bottom-left of array)
        start_x = -array_width / 2.0
        start_y = -array_height / 2.0
        
        chips = []
        chip_index = 0
        
        for row in range(config.chip_count_y):
            for col in range(config.chip_count_x):
                # Get per-chip config
                chip_config = self.chip_configs[chip_index] if chip_index < len(self.chip_configs) else base_chip_config
                
                # Calculate chip position
                chip_x = start_x + col * (chip_width + spacing)
                chip_y = start_y + row * (chip_height + spacing)
                
                # Determine label for this chip based on omega config
                chip_label = None
                if chip_index < len(self.omega_configs):
                    omega_config = self.omega_configs[chip_index]
                    if omega_config is not None:
                        chip_label = f"{omega_config.center_radius * 2:.0f} um"
                
                # Create chip cell with per-chip config and optional label
                chip_name = f"chip_{row}_{col}"
                chip_cell = create_chip_cell(
                    self.layout, 
                    config=chip_config, 
                    chip_name=chip_name,
                    label=chip_label
                )
                
                # Insert chip as instance in wafer cell
                # The chip is created at origin, so we translate it
                chip_trans = pya.Trans(
                    self._um_to_dbu(chip_x),
                    self._um_to_dbu(chip_y)
                )
                wafer_cell.insert(pya.CellInstArray(chip_cell.cell_index(), chip_trans))
                
                # Calculate aperture center in wafer coordinates
                aperture_x = chip_x + chip_config.chip_width / 2.0
                aperture_y = chip_y + chip_config.chip_height / 2.0
                
                print(f"  Chip [{row},{col}] at ({chip_x:.0f}, {chip_y:.0f}) µm", end="")
                
                # Add omega design if omega_config is provided for this chip
                if chip_index < len(self.omega_configs):
                    omega_config = self.omega_configs[chip_index]
                    if omega_config is not None:
                        print(f" (ω radius: {omega_config.center_radius:.0f} µm)")
                        # Note: Omega design is added to wafer_cell at absolute coordinates
                        self.create_omega(wafer_cell, aperture_x, aperture_y, omega_config, chip_config)
                    else:
                        print(" (blank - no omega)")
                else:
                    print()
                
                chips.append((chip_cell, chip_x, chip_y))
                chip_index += 1
        
        return chips
    
    def create_wafer(self, wafer_name="wafer_100mm"):
        """
        Create complete wafer layout with chip array.
        
        Args:
            wafer_name: Name for the wafer cell
        
        Returns:
            Tuple of (pya.Cell, list of text clearance regions)
        """
        print("Creating wafer layout...")
        
        # Create top-level wafer cell
        wafer_cell = self.layout.create_cell(wafer_name)
        
        # Create wafer outline guide with flat on GUIDE_LAYER
        self.create_wafer_guide(wafer_cell)
        # Add 100um wide ring at 95mm diameter
        self.create_wafer_ring_guide(wafer_cell)
        # Create wafer edge contacts in buffer zone
        self.create_wafer_edge_contacts(wafer_cell)
        
        # Create full wafer chip layout using unit cell repetition
        print("Creating unit cell and placing across wafer...")
        unit_positions = self.create_full_wafer_layout(wafer_cell)
        
        total_chips = len(unit_positions) * self.wafer_config.chip_count_x * self.wafer_config.chip_count_y
        print(f"  Total unit cells placed: {len(unit_positions)}")
        print(f"  Total chips on wafer: {total_chips}")
        
        return wafer_cell
    
    def generate_design(self, output_dir=None):
        """
        Generate complete wafer design and export to GDS files.
        
        Args:
            output_dir: Directory for output files (default: script_location/output)
        
        Returns:
            Tuple of (inspect_path, prod_path)
        """
        # Create output directory if needed (relative to script location)
        if output_dir is None:
            output_dir = Path(__file__).parent / "output"
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Get the current script filename (without extension)
        script_name = Path(__file__).stem
        
        # Create wafer
        wafer = self.create_wafer()
        
        # Set layer names in the layout
        for (layer_num, datatype), name in self.wafer_config.LAYER_NAMES.items():
            layer_idx = self.layout.layer(layer_num, datatype)
            layer_info = self.layout.get_info(layer_idx)
            layer_info.name = name
            self.layout.set_info(layer_idx, layer_info)
        print("  Layer names set: mw_metal, wafer_outline, dc_pads")
        
        # Export hierarchical version (inspect)
        inspect_path = os.path.join(output_dir, f"{script_name}_inspect.gds")
        self.layout.write(inspect_path)
        print(f"✓ Hierarchical design exported: {inspect_path}")
        
        # Flatten and export production version
        for cell in self.layout.each_cell():
            cell.flatten(True)
        
        # Merge all shapes in each cell
        for cell in self.layout.each_cell():
            for layer_info in self.layout.layer_indices():
                shapes = cell.shapes(layer_info)
                if len(shapes) > 0:
                    region = pya.Region(shapes)
                    region.merge()
                    shapes.clear()
                    shapes.insert(region)
        
        prod_path = os.path.join(output_dir, f"{script_name}_prod.gds")
        self.layout.write(prod_path)
        print(f"✓ Flattened production design exported: {prod_path}")
        
        return inspect_path, prod_path


def main():
    """Entry point: generate wafer design with default configuration."""
    print("=" * 70)
    print("KLayout Wafer Design Generator - 100mm Full Wafer Omega Array")
    print("=" * 70)
    print()
    
    # Print configuration summary
    wafer_config = WaferConfig()
    
    # Enable electroplating for full wafer
    wafer_config.electroplating = True
    
    print("Wafer Configuration:")
    print(f"  Wafer diameter:      {wafer_config.wafer_diameter/1000:.0f} mm")
    print(f"  Wafer buffer:        {wafer_config.wafer_buffer:.0f} µm")
    usable_diameter = wafer_config.wafer_diameter - 2 * wafer_config.wafer_buffer
    print(f"  Usable diameter:     {usable_diameter/1000:.1f} mm")
    print(f"  Unit cell:           {wafer_config.chip_count_x}x{wafer_config.chip_count_y} chips")
    print(f"  Chip spacing:        {wafer_config.chip_spacing:.0f} µm")
    print(f"  Electroplating:      {wafer_config.electroplating}")
    print()
    print("Chip Variants (repeating 2x3 pattern):")
    print("  Chip 0: 60 µm omega, aperture 250, trace 10")
    print("  Chip 1: 100 µm omega, aperture 300, trace 10")
    print("  Chip 2: 150 µm omega, aperture 350, trace 12.5")
    print("  Chip 3: 200 µm omega, aperture 450, trace 15")
    print("  Chip 4: 250 µm omega, aperture 600, trace 20")
    print("  Chip 5: Blank (no omega)")
    print()
    
    # Generate design (uses default per-chip configs)
    designer = WaferDesigner(wafer_config=wafer_config)
    inspect_file, prod_file = designer.generate_design()
    
    print()
    print("Design generation complete!")
    print()


if __name__ == "__main__":
    main()
