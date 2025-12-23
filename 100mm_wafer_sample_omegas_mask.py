#!/usr/bin/env python3
"""
5"x5" mask plate layout for 4" (100mm) wafer.

Design specification:
- 5"x5" (127mm x 127mm) mask plate
- 4" (100mm) diameter wafer design
- Metal fill from chip array edge to wafer edge (full wafer exposure)
- 2x3 chip unit cell repeated across wafer
- Each chip contains CPW transmission line with central aperture

The mask includes metal from the wafer edge inward to the design area,
ensuring the entire wafer edge is exposed with metal during lithography.

Version: V1
Author: Jayich Lab
"""

import klayout.db as pya
import math
import os
from pathlib import Path

# Import the chip designer module
import importlib.util

# Load the chip module dynamically (handles filename with numbers)
chip_module_path = Path(__file__).parent / "6x6mm_sample_chip_V1.py"
spec = importlib.util.spec_from_file_location("chip_module", chip_module_path)
chip_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chip_module)

# Import the classes and functions we need
ChipDesigner = chip_module.ChipDesigner
create_chip_cell = chip_module.create_chip_cell


class ChipConfig:
    """
    Chip design parameters - local copy for wafer-level customization.
    
    This class mirrors DesignConfig from 6x6mm_sample_chip_V1.py to allow
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
    dc_pad_clearance = 100.0         # Clearance around DC pads (µm)
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
    cross_clearance = 100.0          # Clearance around alignment cross in ground plane (µm)
    
    # Text label parameters
    text_label_height = 200.0        # Height of text label (µm)
    text_label_y_offset = 2150.0     # Y offset from chip center for text label (µm)
    text_label_clearance = 50.0      # Clearance around text for ground plane (µm)
    
    # Electroplating parameters
    electroplating = True            # Enable electroplating tabs
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
    omega_taper_length = 100.0       # Taper length from CPW width to omega trace width (µm)
    
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


class MaskConfig:
    """Configuration for 5"x5" mask plate with 4" wafer."""
    
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
    
    # Mask plate dimensions (5" x 5")
    mask_width = 127000.0   # 5 inches = 127 mm in µm
    mask_height = 127000.0  # 5 inches = 127 mm in µm
    
    # Wafer dimensions (4" = 100mm)
    wafer_diameter = 100000.0  # 100 mm in µm
    wafer_radius = wafer_diameter / 2.0
    wafer_buffer = 3000.0     # Buffer from wafer edge (µm) - usable area is diameter - 2*buffer
    
    # Chip array configuration (for the 2x3 unit cell)
    chip_count_x = 2  # 2x3 array unit
    chip_count_y = 3
    chip_spacing = 0  # Gap between chips (µm) - dicing lanes
    
    # Electroplating
    electroplating = True     # Enable electroplating traces along dicing lanes
    electroplating_tab_width = 50.0  # Width of electroplating traces (µm)
    
    # Wafer flat (for orientation) - standard 100mm wafer flat
    flat_length = 32500.0  # Standard 100mm wafer flat length (µm)
    flat_depth = 2500.0    # Depth of flat from circle edge (µm)
    
    # Edge fill - metal from chip array to wafer edge
    edge_fill_enabled = True  # Enable metal fill from design to wafer edge


class MaskDesigner:
    """Designer class for 5"x5" mask plate with 4" wafer layout."""
    
    def __init__(self, mask_config=None, chip_configs=None, omega_configs=None):
        """
        Initialize mask designer.
        
        Args:
            mask_config: MaskConfig instance or None for defaults
            chip_configs: List of ChipConfig instances (one per chip) or None for defaults
            omega_configs: List of OmegaConfig instances (one per chip) or None for defaults
                          Use None in list position for blank chip (no omega)
        """
        self.mask_config = mask_config if mask_config is not None else MaskConfig()
        
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
            chip_config.dbu = self.mask_config.dbu
        
        self.layout = pya.Layout()
        self.layout.dbu = self.mask_config.dbu
    
    def _um_to_dbu(self, um_value):
        """Convert micrometers to database units."""
        return int(round(um_value / self.mask_config.dbu))
    
    def create_wafer_region(self):
        """
        Create circular wafer region with flat.
        
        Returns:
            pya.Region representing the wafer area (circle with flat cut)
        """
        config = self.mask_config
        
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
        config = self.mask_config
        guide_layer_idx = self.layout.layer(config.GUIDE_LAYER)
        
        wafer_region = self.create_wafer_region()
        cell.shapes(guide_layer_idx).insert(wafer_region)
        
        print(f"  Added wafer guide outline (4\" diameter with flat) on layer {config.GUIDE_LAYER}")
    
    def create_mask_plate_guide(self, cell):
        """
        Create 5"x5" mask plate outline on the GUIDE_LAYER.
        
        Args:
            cell: KLayout cell to insert guide into
        """
        config = self.mask_config
        guide_layer_idx = self.layout.layer(config.GUIDE_LAYER)
        
        # Mask plate centered at origin
        half_width = config.mask_width / 2.0
        half_height = config.mask_height / 2.0
        
        mask_box = pya.Box(
            self._um_to_dbu(-half_width),
            self._um_to_dbu(-half_height),
            self._um_to_dbu(half_width),
            self._um_to_dbu(half_height)
        )
        cell.shapes(guide_layer_idx).insert(mask_box)
        
        print(f"  Added 5\"x5\" mask plate outline on layer {config.GUIDE_LAYER}")
    
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
            chip_config = self.chip_configs[0]
        
        center_radius = omega_config.center_radius
        trace_width = omega_config.trace_width
        spacing = omega_config.omega_spacing
        trace_gap = omega_config.omega_trace_gap
        
        # Calculate inner and outer radii from center_radius and trace_width
        outer_radius = center_radius + trace_width / 2.0
        inner_radius = center_radius - trace_width / 2.0
        
        # Distance from center to each ring center (along diagonal)
        offset = outer_radius + spacing
        
        # Horizontal offset for top/bottom rings
        h_offset = trace_gap / 2.0 + trace_width / 2.0
        
        # Four diagonal positions with horizontal offsets
        positions = [
            (x_center + offset - h_offset, y_center + offset, 'bottom'),
            (x_center - offset - h_offset, y_center + offset, 'bottom'),
            (x_center - offset + h_offset, y_center - offset, 'top'),
            (x_center + offset + h_offset, y_center - offset, 'top'), 
        ]
        
        layer_idx = self.layout.layer(omega_config.METAL_LAYER)
        num_segments = 64
        
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
            if ring_type == 'top':
                gap_box = pya.Box(
                    self._um_to_dbu(cx - trace_gap / 2.0),
                    self._um_to_dbu(cy),
                    self._um_to_dbu(cx + trace_gap / 2.0),
                    self._um_to_dbu(cy + outer_radius + trace_width)
                )
            else:
                gap_box = pya.Box(
                    self._um_to_dbu(cx - trace_gap / 2.0),
                    self._um_to_dbu(cy - outer_radius - trace_width),
                    self._um_to_dbu(cx + trace_gap / 2.0),
                    self._um_to_dbu(cy)
                )
            
            gap_region = pya.Region(gap_box)
            ring_region -= gap_region
            
            cell.shapes(layer_idx).insert(ring_region)
        
        # Create vertical rectangles connecting each top/bottom pair
        right_conn_x = x_center + offset
        right_conn_box = pya.Box(
            self._um_to_dbu(right_conn_x - trace_width / 2.0),
            self._um_to_dbu(y_center - offset + outer_radius - trace_width),
            self._um_to_dbu(right_conn_x + trace_width / 2.0),
            self._um_to_dbu(y_center + offset - outer_radius + trace_width)
        )
        cell.shapes(layer_idx).insert(right_conn_box)
        
        left_conn_x = x_center - offset
        left_conn_box = pya.Box(
            self._um_to_dbu(left_conn_x - trace_width / 2.0),
            self._um_to_dbu(y_center - offset + outer_radius - trace_width),
            self._um_to_dbu(left_conn_x + trace_width / 2.0),
            self._um_to_dbu(y_center + offset - outer_radius + trace_width)
        )
        cell.shapes(layer_idx).insert(left_conn_box)
        
        # Create feed lines from ring ends to center level
        top_right_feed_x = x_center + offset - 2*h_offset
        top_right_feed_box = pya.Box(
            self._um_to_dbu(top_right_feed_x - trace_width / 2.0),
            self._um_to_dbu(y_center),
            self._um_to_dbu(top_right_feed_x + trace_width / 2.0),
            self._um_to_dbu(y_center + offset - outer_radius + trace_width)
        )
        cell.shapes(layer_idx).insert(top_right_feed_box)
        
        top_left_feed_x = x_center - offset - 2*h_offset
        top_left_feed_box = pya.Box(
            self._um_to_dbu(top_left_feed_x - trace_width / 2.0),
            self._um_to_dbu(y_center),
            self._um_to_dbu(top_left_feed_x + trace_width / 2.0),
            self._um_to_dbu(y_center + offset - outer_radius + trace_width)
        )
        cell.shapes(layer_idx).insert(top_left_feed_box)
        
        bottom_right_feed_x = x_center + offset + 2*h_offset
        bottom_right_feed_box = pya.Box(
            self._um_to_dbu(bottom_right_feed_x - trace_width / 2.0),
            self._um_to_dbu(y_center - offset + outer_radius - trace_width),
            self._um_to_dbu(bottom_right_feed_x + trace_width / 2.0),
            self._um_to_dbu(y_center)
        )
        cell.shapes(layer_idx).insert(bottom_right_feed_box)
        
        bottom_left_feed_x = x_center - offset + 2*h_offset
        bottom_left_feed_box = pya.Box(
            self._um_to_dbu(bottom_left_feed_x - trace_width / 2.0),
            self._um_to_dbu(y_center - offset + outer_radius - trace_width),
            self._um_to_dbu(bottom_left_feed_x + trace_width / 2.0),
            self._um_to_dbu(y_center)
        )
        cell.shapes(layer_idx).insert(bottom_left_feed_box)
        
        # Create CPW connection rectangles
        cpw_end_left = x_center - chip_config.aperture_radius
        cpw_end_right = x_center + chip_config.aperture_radius
        
        top_left_cpw_box = pya.Box(
            self._um_to_dbu(cpw_end_left),
            self._um_to_dbu(y_center - trace_width/2),
            self._um_to_dbu(top_left_feed_x + trace_width / 2.0),
            self._um_to_dbu(y_center + trace_width/2)
        )
        cell.shapes(layer_idx).insert(top_left_cpw_box)
        
        top_right_cpw_box = pya.Box(
            self._um_to_dbu(bottom_right_feed_x - trace_width / 2.0),
            self._um_to_dbu(y_center - trace_width/2),
            self._um_to_dbu(cpw_end_right),
            self._um_to_dbu(y_center + trace_width/2)
        )
        cell.shapes(layer_idx).insert(top_right_cpw_box)
        
        middle_connector_box = pya.Box(
            self._um_to_dbu(bottom_left_feed_x - trace_width / 2.0),
            self._um_to_dbu(y_center - trace_width/2),
            self._um_to_dbu(top_right_feed_x + trace_width / 2.0),
            self._um_to_dbu(y_center + trace_width/2)
        )
        cell.shapes(layer_idx).insert(middle_connector_box)
        
        # Create tapers from CPW width to omega trace width
        cpw_signal_width = chip_config.cpw_signal_width
        taper_length = omega_config.omega_taper_length
        
        left_taper_vertices = [
            pya.Point(self._um_to_dbu(cpw_end_left), self._um_to_dbu(y_center - cpw_signal_width / 2.0)),
            pya.Point(self._um_to_dbu(cpw_end_left + taper_length), self._um_to_dbu(y_center - trace_width / 2.0)),
            pya.Point(self._um_to_dbu(cpw_end_left + taper_length), self._um_to_dbu(y_center + trace_width / 2.0)),
            pya.Point(self._um_to_dbu(cpw_end_left), self._um_to_dbu(y_center + cpw_signal_width / 2.0)),
        ]
        left_taper_polygon = pya.Polygon(left_taper_vertices)
        cell.shapes(layer_idx).insert(left_taper_polygon)
        
        right_taper_vertices = [
            pya.Point(self._um_to_dbu(cpw_end_right - taper_length), self._um_to_dbu(y_center - trace_width / 2.0)),
            pya.Point(self._um_to_dbu(cpw_end_right), self._um_to_dbu(y_center - cpw_signal_width / 2.0)),
            pya.Point(self._um_to_dbu(cpw_end_right), self._um_to_dbu(y_center + cpw_signal_width / 2.0)),
            pya.Point(self._um_to_dbu(cpw_end_right - taper_length), self._um_to_dbu(y_center + trace_width / 2.0)),
        ]
        right_taper_polygon = pya.Polygon(right_taper_vertices)
        cell.shapes(layer_idx).insert(right_taper_polygon)
        
        print(f"  → Omega design: 4 rings (r={center_radius:.0f} µm, w={trace_width:.0f} µm, gap={trace_gap:.0f} µm) at ({x_center:.0f}, {y_center:.0f}) µm")
    
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
        corners = [
            (chip_x, chip_y),
            (chip_x + chip_width, chip_y),
            (chip_x, chip_y + chip_height),
            (chip_x + chip_width, chip_y + chip_height)
        ]
        
        for cx, cy in corners:
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
        config = self.mask_config
        flat_y = -config.wafer_radius + config.flat_depth
        flat_exclusion_zone = 2250.0  # 2.25mm exclusion zone
        
        chip_bottom = chip_y
        
        if chip_bottom < flat_y + flat_exclusion_zone:
            return True
        return False
    
    def create_unit_cell(self):
        """
        Create a unit cell containing all chip variants in a 2x3 pattern.
        
        Returns:
            Tuple of (unit_cell, chip_variant_cells, unit_width, unit_height) 
        """
        config = self.mask_config
        base_chip_config = self.chip_configs[0]
        
        chip_width = base_chip_config.chip_width
        chip_height = base_chip_config.chip_height
        spacing = config.chip_spacing
        
        unit_width = config.chip_count_x * chip_width + (config.chip_count_x - 1) * spacing
        unit_height = config.chip_count_y * chip_height + (config.chip_count_y - 1) * spacing
        
        unit_cell = self.layout.create_cell("unit_cell_2x3")
        
        print(f"  Creating unit cell ({config.chip_count_x}x{config.chip_count_y}) with {len(self.chip_configs)} chip variants")
        
        chip_variant_cells = []
        chip_index = 0
        for row in range(config.chip_count_y):
            for col in range(config.chip_count_x):
                chip_config = self.chip_configs[chip_index] if chip_index < len(self.chip_configs) else base_chip_config
                omega_config = self.omega_configs[chip_index] if chip_index < len(self.omega_configs) else None
                
                chip_x = col * (chip_width + spacing)
                chip_y = row * (chip_height + spacing)
                
                chip_label = None
                if omega_config is not None:
                    chip_label = f"{int(omega_config.center_radius * 2)} UM"
                
                # Create chip cell using the imported chip designer
                chip_cell = create_chip_cell(self.layout, chip_config, f"chip_variant_{chip_index}", chip_label)
                
                # Create wrapper cell for this chip variant at its position in unit cell
                wrapper_cell = self.layout.create_cell(f"chip_wrapper_{chip_index}")
                wrapper_cell.insert(pya.CellInstArray(chip_cell.cell_index(), pya.Trans()))
                
                # Add omega if configured
                if omega_config is not None:
                    chip_center_x = chip_config.chip_width / 2.0
                    chip_center_y = chip_config.chip_height / 2.0
                    self.create_omega(wrapper_cell, chip_center_x, chip_center_y, omega_config, chip_config)
                
                chip_variant_cells.append((wrapper_cell, chip_x, chip_y, chip_config, omega_config))
                
                print(f"    Chip variant {chip_index} at ({chip_x:.0f}, {chip_y:.0f}) µm" + 
                      (f" (ω radius: {omega_config.center_radius:.0f} µm)" if omega_config else " (blank - no omega)"))
                
                chip_index += 1
        
        return unit_cell, chip_variant_cells, unit_width, unit_height
    
    def calculate_chip_positions_from_unit_grid(self, unit_width, unit_height, chip_variant_cells):
        """
        Calculate all individual chip positions based on unit cell grid pattern.
        
        Args:
            unit_width: Width of unit cell (µm)
            unit_height: Height of unit cell (µm)
            chip_variant_cells: List of (cell, local_x, local_y, chip_config, omega_config)
        
        Returns:
            List of (wafer_x, wafer_y, variant_index) tuples for all valid chip positions
        """
        config = self.mask_config
        base_chip_config = self.chip_configs[0]
        
        chip_width = base_chip_config.chip_width
        chip_height = base_chip_config.chip_height
        
        usable_radius = (config.wafer_diameter - 2 * config.wafer_buffer) / 2.0
        
        max_units_x = int(math.ceil(config.wafer_diameter / unit_width)) + 1
        max_units_y = int(math.ceil(config.wafer_diameter / unit_height)) + 1
        
        grid_start_x = -unit_width / 2.0
        grid_start_y = -unit_height / 2.0
        
        valid_positions = []
        
        for unit_row in range(-max_units_y // 2, max_units_y // 2 + 1):
            for unit_col in range(-max_units_x // 2, max_units_x // 2 + 1):
                unit_x = grid_start_x + unit_col * unit_width
                unit_y = grid_start_y + unit_row * unit_height
                
                for variant_idx, (cell, local_x, local_y, chip_config, omega_config) in enumerate(chip_variant_cells):
                    chip_x = unit_x + local_x
                    chip_y = unit_y + local_y
                    
                    if (self.chip_fits_in_wafer(chip_x, chip_y, chip_width, chip_height, usable_radius) and
                        not self.chip_too_close_to_flat(chip_x, chip_y, chip_width, chip_height)):
                        valid_positions.append((chip_x, chip_y, variant_idx))
        
        return valid_positions
    
    def create_edge_fill(self, cell, chip_positions):
        """
        Create metal fill from chip array boundary to wafer edge.
        
        This fills the area between the outermost chips and the wafer edge
        with metal, ensuring the entire wafer edge is exposed. The fill
        does NOT extend into the usable chip area.
        
        Args:
            cell: KLayout cell to insert fill into
            chip_positions: List of (chip_x, chip_y, variant_index) tuples
        """
        config = self.mask_config
        base_chip_config = self.chip_configs[0]
        metal_layer_idx = self.layout.layer(config.METAL_LAYER)
        
        chip_width = base_chip_config.chip_width
        chip_height = base_chip_config.chip_height
        
        # Get full wafer region (circle with flat)
        wafer_region = self.create_wafer_region()
        
        # Get usable wafer region (smaller circle where chips go)
        usable_radius = (config.wafer_diameter - 2 * config.wafer_buffer) / 2.0
        num_segments = 360
        usable_points = []
        for i in range(num_segments):
            angle = 2.0 * math.pi * i / num_segments
            x = self._um_to_dbu(usable_radius * math.cos(angle))
            y = self._um_to_dbu(usable_radius * math.sin(angle))
            usable_points.append(pya.Point(x, y))
        usable_polygon = pya.Polygon(usable_points)
        usable_region = pya.Region(usable_polygon)
        
        # Edge fill = full wafer - usable area (ring between usable and wafer edge)
        edge_fill_region = wafer_region - usable_region
        
        # Add edge fill to both CPW (metal) and DC layers
        dc_layer_idx = self.layout.layer(config.DC_PAD_LAYER)
        cell.shapes(metal_layer_idx).insert(edge_fill_region)
        cell.shapes(dc_layer_idx).insert(edge_fill_region)
        
        print(f"  Added edge fill metal ring from usable area to wafer edge (both CPW and DC layers)")
    
    def create_studded_alignment_ring(self, cell, ring_diameter=100.25, stud_width=500.0, stud_spacing=1000.0, ring_width=200.0):
        """
        Create an intermittent (studded/dashed) ring at specified diameter for alignment.
        
        Args:
            cell: KLayout cell to insert ring into
            ring_diameter: Diameter of the ring in mm (default 100.25mm)
            stud_width: Angular width of each stud segment in µm (arc length)
            stud_spacing: Gap between studs in µm (arc length)
            ring_width: Radial width of the ring in µm
        """
        config = self.mask_config
        metal_layer_idx = self.layout.layer(config.METAL_LAYER)
        dc_layer_idx = self.layout.layer(config.DC_PAD_LAYER)
        
        # Convert ring diameter from mm to µm and get radius
        ring_radius = (ring_diameter * 1000.0) / 2.0
        
        # Calculate inner and outer radii for the ring
        inner_radius = ring_radius - ring_width / 2.0
        outer_radius = ring_radius + ring_width / 2.0
        
        # Calculate angular parameters
        # Arc length = radius * angle, so angle = arc_length / radius
        stud_angle = stud_width / ring_radius  # radians
        gap_angle = stud_spacing / ring_radius  # radians
        segment_angle = stud_angle + gap_angle
        
        # Number of segments that fit around the circle
        num_segments = int(2.0 * math.pi / segment_angle)
        
        # Create region for all studs
        studs_region = pya.Region()
        
        for i in range(num_segments):
            # Start angle for this stud
            start_angle = i * segment_angle
            end_angle = start_angle + stud_angle
            
            # Create polygon for this stud (arc segment)
            # Use small angular steps for smooth arcs
            angular_resolution = 0.01  # radians per point
            num_points = max(10, int(stud_angle / angular_resolution))
            
            stud_points = []
            
            # Outer arc (counterclockwise)
            for j in range(num_points + 1):
                angle = start_angle + (j / num_points) * stud_angle
                x = outer_radius * math.cos(angle)
                y = outer_radius * math.sin(angle)
                stud_points.append(pya.Point(self._um_to_dbu(x), self._um_to_dbu(y)))
            
            # Inner arc (clockwise)
            for j in range(num_points + 1):
                angle = end_angle - (j / num_points) * stud_angle
                x = inner_radius * math.cos(angle)
                y = inner_radius * math.sin(angle)
                stud_points.append(pya.Point(self._um_to_dbu(x), self._um_to_dbu(y)))
            
            stud_polygon = pya.Polygon(stud_points)
            studs_region.insert(stud_polygon)
        
        # Add studded ring to both CPW and DC layers
        cell.shapes(metal_layer_idx).insert(studs_region)
        cell.shapes(dc_layer_idx).insert(studs_region)
        
        print(f"  Added studded alignment ring at {ring_diameter} mm diameter with {num_segments} studs")
    
    def create_alignment_cross(self, cell, x_center, y_center, size=500.0, linewidth=50.0):
        """
        Create an alignment cross (+ shape) at specified position on both layers.
        
        Args:
            cell: KLayout cell to insert cross into
            x_center: x-coordinate of cross center (µm)
            y_center: y-coordinate of cross center (µm)
            size: Total size of cross (µm)
            linewidth: Width of cross arms (µm)
        """
        config = self.mask_config
        metal_layer_idx = self.layout.layer(config.METAL_LAYER)
        dc_layer_idx = self.layout.layer(config.DC_PAD_LAYER)
        
        # Horizontal bar
        h_bar = pya.Box(
            self._um_to_dbu(x_center - size / 2.0),
            self._um_to_dbu(y_center - linewidth / 2.0),
            self._um_to_dbu(x_center + size / 2.0),
            self._um_to_dbu(y_center + linewidth / 2.0)
        )
        
        # Vertical bar
        v_bar = pya.Box(
            self._um_to_dbu(x_center - linewidth / 2.0),
            self._um_to_dbu(y_center - size / 2.0),
            self._um_to_dbu(x_center + linewidth / 2.0),
            self._um_to_dbu(y_center + size / 2.0)
        )
        
        # Insert on both layers
        cell.shapes(metal_layer_idx).insert(h_bar)
        cell.shapes(metal_layer_idx).insert(v_bar)
        cell.shapes(dc_layer_idx).insert(h_bar)
        cell.shapes(dc_layer_idx).insert(v_bar)
    
    def create_corner_alignment_marks(self, cell, positions=None):
        """
        Create alignment crosses at specified corner positions.
        
        Args:
            cell: KLayout cell to insert marks into
            positions: List of (x, y) tuples in µm, or None for default ±38000 and ±24000 µm
        """
        if positions is None:
            # Default positions at ±33000 µm (x) and ±30000 µm (y) (4 corners)
            positions = [
                (-33000.0, 30000.0),   # Top-left
                (33000.0, 30000.0),    # Top-right
                (-33000.0, -30000.0),  # Bottom-left
                (33000.0, -30000.0),   # Bottom-right
            ]
        
        for x, y in positions:
            self.create_alignment_cross(cell, x, y, size=500.0, linewidth=50.0)
        
        print(f"  Added {len(positions)} corner alignment marks")
    
    def create_electroplating_contact_bars(self, cell, chip_positions):
        """
        Create rectangular metal bars between the chip array and the edge ring
        for electroplating contact. Bars are placed on top, left, and right sides.
        
        Args:
            cell: KLayout cell to insert bars into
            chip_positions: List of (chip_x, chip_y, variant_index) tuples
        """
        config = self.mask_config
        base_chip_config = self.chip_configs[0]
        metal_layer_idx = self.layout.layer(config.METAL_LAYER)
        
        chip_width = base_chip_config.chip_width
        chip_height = base_chip_config.chip_height
        
        # Get usable wafer radius (where the edge ring starts)
        usable_radius = (config.wafer_diameter - 2 * config.wafer_buffer) / 2.0
        
        # Find chip array bounding box
        min_chip_x = min(pos[0] for pos in chip_positions)
        max_chip_x = max(pos[0] for pos in chip_positions) + chip_width
        min_chip_y = min(pos[1] for pos in chip_positions)
        max_chip_y = max(pos[1] for pos in chip_positions) + chip_height
        
        # Bar dimensions - 2 dies wide for good contact area
        bar_width = 2 * chip_width
        
        # === TOP BAR ===
        # From top of chip array to usable radius, centered horizontally
        top_bar_left = -bar_width / 2.0
        top_bar_right = bar_width / 2.0
        top_bar_bottom = max_chip_y
        top_bar_top = usable_radius
        
        top_bar = pya.Box(
            self._um_to_dbu(top_bar_left),
            self._um_to_dbu(top_bar_bottom),
            self._um_to_dbu(top_bar_right),
            self._um_to_dbu(top_bar_top)
        )
        cell.shapes(metal_layer_idx).insert(top_bar)
        
        # === LEFT BAR ===
        # From left of chip array to -usable_radius, centered vertically
        left_bar_left = -usable_radius
        left_bar_right = min_chip_x
        left_bar_bottom = -bar_width / 2.0
        left_bar_top = bar_width / 2.0
        
        left_bar = pya.Box(
            self._um_to_dbu(left_bar_left),
            self._um_to_dbu(left_bar_bottom),
            self._um_to_dbu(left_bar_right),
            self._um_to_dbu(left_bar_top)
        )
        cell.shapes(metal_layer_idx).insert(left_bar)
        
        # === RIGHT BAR ===
        # From right of chip array to usable_radius, centered vertically
        right_bar_left = max_chip_x
        right_bar_right = usable_radius
        right_bar_bottom = -bar_width / 2.0
        right_bar_top = bar_width / 2.0
        
        right_bar = pya.Box(
            self._um_to_dbu(right_bar_left),
            self._um_to_dbu(right_bar_bottom),
            self._um_to_dbu(right_bar_right),
            self._um_to_dbu(right_bar_top)
        )
        cell.shapes(metal_layer_idx).insert(right_bar)
        
        # === BOTTOM BAR ===
        # From bottom of chip array to above wafer flat, centered horizontally
        # Wafer flat is at y = -wafer_radius + flat_depth
        flat_y = -config.wafer_radius + config.flat_depth
        
        bottom_bar_left = -bar_width / 2.0
        bottom_bar_right = bar_width / 2.0
        bottom_bar_bottom = flat_y
        bottom_bar_top = min_chip_y
        
        bottom_bar = pya.Box(
            self._um_to_dbu(bottom_bar_left),
            self._um_to_dbu(bottom_bar_bottom),
            self._um_to_dbu(bottom_bar_right),
            self._um_to_dbu(bottom_bar_top)
        )
        cell.shapes(metal_layer_idx).insert(bottom_bar)
        
        print(f"  Added electroplating contact bars (top, left, right, bottom) between chip array and edge ring")
    
    def text_to_polygons(self, text_string, x, y, height, layer_idx, cell):
        """
        Convert text string to polygon shapes and insert into cell.
        
        Uses KLayout's built-in text generator to create polygonal text
        that will be rendered as actual metal on the mask.
        
        Args:
            text_string: The text to render
            x: X position in µm
            y: Y position in µm  
            height: Text height in µm
            layer_idx: Layer index to insert polygons
            cell: KLayout cell to insert into
        """
        # Create a text generator
        gen = pya.TextGenerator.default_generator()
        
        # Generate text as region (polygons)
        # The generator creates text at origin, we transform after
        text_region = gen.text(text_string, self.layout.dbu, height)
        
        # Transform to desired position
        transform = pya.Trans(self._um_to_dbu(x), self._um_to_dbu(y))
        text_region.transform(transform)
        
        # Insert polygons into cell
        cell.shapes(layer_idx).insert(text_region)
    
    def create_mask_labels(self, cell, design_name="100mm_wafer_sample_omegas_V1"):
        """
        Create text labels as polygons in the top left corner of the mask plate.
        Adds design name, date, and layer info labels on both the CPW (metal) 
        layer and the DC trace layer for identification. Text is converted
        to polygons so it appears as actual metal on the mask.
        
        Args:
            cell: KLayout cell to insert labels into
            design_name: Name of the design to display
        """
        config = self.mask_config
        metal_layer_idx = self.layout.layer(config.METAL_LAYER)
        dc_layer_idx = self.layout.layer(config.DC_PAD_LAYER)
        
        # Get current date
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        # Mask plate dimensions
        mask_width = config.mask_width
        mask_height = config.mask_height
        
        # Text parameters
        text_height = 1500.0  # 1500 µm tall text
        line_spacing = 150.0  # 100 µm gap between lines
        margin = 5000.0         # 400 µm from mask plate edge
        
        # Label lines
        label_lines = [
            design_name,
            date_str,
            "Layer 1/2 - CPW",
            "Jayich Lab - Jeff Ahlers"
        ]
        N = len(label_lines)
        total_label_height = N * text_height + (N - 1) * line_spacing
        
        # Top-left corner: x = margin, y = mask_height - margin - text_height (first line)
        label_x = -mask_width/2 + margin
        label_y = mask_height/2 - margin - text_height
        
        # CPW Layer labels
        current_y = label_y
        for line in label_lines:
            self.text_to_polygons(line, label_x, current_y, text_height, metal_layer_idx, cell)
            current_y -= (text_height + line_spacing)
        
        # DC Layer labels (same position, but last line is "Layer 2/2 - DC Contacts")
        dc_label_lines = [
            design_name,
            date_str,
            "Layer 2/2 - DC Contacts",
            "Jayich Lab - Jeff Ahlers"
        ]
        current_y = label_y
        for line in dc_label_lines:
            self.text_to_polygons(line, label_x, current_y, text_height, dc_layer_idx, cell)
            current_y -= (text_height + line_spacing)
        
        print(f"  Added mask labels (as polygons): '{design_name}', '{date_str}', layer info on CPW and DC layers")
    
    def create_electroplating_dicing_traces(self, cell, chip_positions):
        """
        Create electroplating traces along dicing lanes between chips.
        
        Args:
            cell: KLayout cell to insert traces into
            chip_positions: List of (chip_x, chip_y, chip_index) tuples
        """
        config = self.mask_config
        base_chip_config = self.chip_configs[0]
        
        chip_width = base_chip_config.chip_width
        chip_height = base_chip_config.chip_height
        tab_width = config.electroplating_tab_width
        usable_radius = (config.wafer_diameter - 2 * config.wafer_buffer) / 2.0
        flat_exclusion_zone = 2250.0
        flat_y = -config.wafer_radius + config.flat_depth
        
        layer_idx = self.layout.layer(config.METAL_LAYER)
        
        # Collect unique x and y coordinates for dicing lanes
        x_coords = set()
        y_coords = set()
        
        for chip_x, chip_y, _ in chip_positions:
            x_coords.add(chip_x)
            x_coords.add(chip_x + chip_width)
            y_coords.add(chip_y)
            y_coords.add(chip_y + chip_height)
        
        # Create vertical traces at each unique x coordinate
        for x in sorted(x_coords):
            if abs(x) < usable_radius:
                y_extent = math.sqrt(usable_radius * usable_radius - x * x)
                y_bottom = max(-y_extent, flat_y + flat_exclusion_zone)
                y_top = y_extent
                
                if y_bottom < y_top:
                    trace_box = pya.Box(
                        self._um_to_dbu(x - tab_width / 2.0),
                        self._um_to_dbu(y_bottom),
                        self._um_to_dbu(x + tab_width / 2.0),
                        self._um_to_dbu(y_top)
                    )
                    cell.shapes(layer_idx).insert(trace_box)
        
        # Create horizontal traces at each unique y coordinate
        for y in sorted(y_coords):
            if y >= flat_y + flat_exclusion_zone:
                if abs(y) < usable_radius:
                    x_extent = math.sqrt(usable_radius * usable_radius - y * y)
                    
                    trace_box = pya.Box(
                        self._um_to_dbu(-x_extent),
                        self._um_to_dbu(y - tab_width / 2.0),
                        self._um_to_dbu(x_extent),
                        self._um_to_dbu(y + tab_width / 2.0)
                    )
                    cell.shapes(layer_idx).insert(trace_box)
        
        print("  Added electroplating dicing traces")
    
    def create_full_wafer_layout(self, wafer_cell):
        """
        Create complete chip mask covering the full usable wafer area.
        
        Args:
            wafer_cell: Parent cell for the wafer
        
        Returns:
            List of (wafer_x, wafer_y, variant_index) tuples for all placed chips
        """
        config = self.mask_config
        base_chip_config = self.chip_configs[0]
        
        chip_width = base_chip_config.chip_width
        chip_height = base_chip_config.chip_height
        
        # Create the unit cell with all chip variants
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
        
        # Add edge fill metal from chip array to wafer edge
        if config.edge_fill_enabled:
            self.create_edge_fill(wafer_cell, chip_positions)
            # Add contact bars between chip array and edge ring for electroplating
            self.create_electroplating_contact_bars(wafer_cell, chip_positions)
            # Add studded alignment ring that overlaps with wafer edge ring
            # Position at wafer edge (100mm diameter) so it connects with the solid edge fill
            self.create_studded_alignment_ring(wafer_cell, ring_diameter=100.0)
        
        # Add electroplating dicing traces if enabled
        if config.electroplating:
            self.create_electroplating_dicing_traces(wafer_cell, chip_positions)
        
        # Add corner alignment marks at ±37.5mm
        self.create_corner_alignment_marks(wafer_cell)
        
        return chip_positions
    
    def create_mask(self, mask_name="mask_5inch"):
        """
        Create complete mask layout with wafer design.
        
        Args:
            mask_name: Name for the mask cell
        
        Returns:
            pya.Cell for the mask
        """
        print("Creating mask layout...")
        
        # Create top-level mask cell
        mask_cell = self.layout.create_cell(mask_name)
        
        # Create mask plate outline on guide layer
        self.create_mask_plate_guide(mask_cell)
        
        # Create wafer outline guide on guide layer
        self.create_wafer_guide(mask_cell)
        
        # Create full wafer chip layout
        print("Creating unit cell and placing across wafer...")
        chip_positions = self.create_full_wafer_layout(mask_cell)
        
        total_chips = len(chip_positions)
        print(f"  Total chips on wafer: {total_chips}")
        
        # Add text labels with design name and date
        self.create_mask_labels(mask_cell)
        
        return mask_cell
    
    def generate_design(self, output_dir="output"):
        """
        Generate complete mask design and export to GDS files.
        
        Args:
            output_dir: Directory for output files
        
        Returns:
            Tuple of (inspect_path, prod_path)
        """
        # Create output directory if needed
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Get the current script filename (without extension)
        script_name = Path(__file__).stem
        
        # Create mask
        mask = self.create_mask()
        
        # Set layer names in the layout
        for (layer_num, datatype), name in self.mask_config.LAYER_NAMES.items():
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
            for layer_idx in self.layout.layer_indices():
                region = pya.Region(cell.shapes(layer_idx))
                region.merge()
                cell.shapes(layer_idx).clear()
                cell.shapes(layer_idx).insert(region)
        
        prod_path = os.path.join(output_dir, f"{script_name}_prod.gds")
        self.layout.write(prod_path)
        print(f"✓ Flattened production design exported: {prod_path}")
        
        return inspect_path, prod_path


def main():
    """Entry point: generate mask design with default configuration."""
    print("=" * 70)
    print("KLayout Mask Design Generator - 5\"x5\" Mask for 4\" Wafer")
    print("=" * 70)
    print()
    
    # Print configuration summary
    mask_config = MaskConfig()
    
    print("Mask Configuration:")
    print(f"  Mask plate size:     {mask_config.mask_width/1000:.0f} mm x {mask_config.mask_height/1000:.0f} mm (5\" x 5\")")
    print(f"  Wafer diameter:      {mask_config.wafer_diameter/1000:.0f} mm (4\")")
    print(f"  Wafer buffer:        {mask_config.wafer_buffer:.0f} µm")
    usable_diameter = mask_config.wafer_diameter - 2 * mask_config.wafer_buffer
    print(f"  Usable diameter:     {usable_diameter/1000:.1f} mm")
    print(f"  Unit cell:           {mask_config.chip_count_x}x{mask_config.chip_count_y} chips")
    print(f"  Chip spacing:        {mask_config.chip_spacing:.0f} µm")
    print(f"  Edge fill:           {mask_config.edge_fill_enabled}")
    print(f"  Electroplating:      {mask_config.electroplating}")
    print()
    print("Chip Variants (repeating 2x3 pattern):")
    print("  Chip 0: 60 µm omega, aperture 250, trace 10")
    print("  Chip 1: 100 µm omega, aperture 300, trace 10")
    print("  Chip 2: 150 µm omega, aperture 350, trace 12.5")
    print("  Chip 3: 200 µm omega, aperture 450, trace 15")
    print("  Chip 4: 250 µm omega, aperture 600, trace 20")
    print("  Chip 5: Blank (no omega)")
    print()
    
    # Generate design
    designer = MaskDesigner(mask_config=mask_config)
    inspect_file, prod_file = designer.generate_design()
    
    print()
    print("Design generation complete!")
    print()


if __name__ == "__main__":
    main()
