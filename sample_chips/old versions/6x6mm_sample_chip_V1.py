#!/usr/bin/env python3
"""
Parametric KLayout design generator for microwave RF chips with CPW and bond pads.

Design specification:
- 6 mm × 6 mm chip with 200 µm edge buffer (included in 6 mm dimension)
- CPW transmission line: 100 µm center trace, 50 µm gap to ground (50 Ω nominal)
- Bond pads: 400 × 800 µm at left/right edges with parametric tapers
- Ground plane: full coverage except aperture (reserved for interior design) and signal line
- Central circular aperture: configurable radius for interior design integration
- Design approach: Python-first, parametric, hierarchical

Version: V3 (chip-level prototype)
Author: Jayich Lab
"""

import klayout.db as pya
import math
import os
from pathlib import Path


class DesignConfig:
    """Centralized design parameters for reproducibility and single-point modification."""
    
    # Database unit: 0.01 µm = 10 nm
    # This provides nanometer-scale precision while keeping coordinates manageable
    # 6 mm = 600,000 DBU (reasonable range for KLayout)
    dbu = 0.01  # 1 DBU = 10 nm
    
    # Layer definitions
    METAL_LAYER = pya.LayerInfo(1, 0)  # Metal/conductor layer (CPW 1/0)
    DC_PAD_LAYER = pya.LayerInfo(3, 0)  # DC pads and traces layer (dc_contacts 3/0)
    
    # Chip dimensions (includes 200 µm edge buffer)
    chip_width = 6000.0      # 6 mm total width
    chip_height = 6000.0     # 6 mm total height
    edge_buffer = 400.0      # 400 µm edge buffer (moved in 200 µm from original)
    
    # CPW (Coplanar Waveguide) specifications
    cpw_signal_width = 100.0  # Center trace width (µm)
    cpw_gap = 50.0            # Gap from signal to ground plane (µm) → 50 Ω impedance
    cpw_ground_width = (chip_width - cpw_signal_width) / 2.0  # Fill remaining width
    
    # Bond pad specifications
    pad_width = 400.0         # Horizontal dimension (µm)
    pad_height = 800.0        # Vertical dimension (µm)
    
    # Taper specifications
    taper_length = 50.0      # Length of rapid taper from pad to CPW (µm)
    
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
    dc_pad_inner_y_shift = 0.0       # Y shift for inner 4 pads toward center (µm, positive = toward center)
    dc_pad_clearance = 50.0          # Clearance around DC pads (µm)
    dc_cutout_width = dc_pad_clearance*(dc_pad_count+1)+dc_pad_width*dc_pad_count        # Width of rectangular cutout for DC pads (µm)
    dc_cutout_height = dc_pad_clearance*4+dc_pad_height        # Height of rectangular cutout for DC pads (µm)
    dc_pad_entrance_width = 150.0    # Width at narrow end of taper to aperture (µm)
    dc_pad_entrance_height = aperture_radius + 50.0  # Height of tapered entrance section (µm)
    dc_trace_width = 10.0            # Width of DC traces after taper (µm)
    dc_trace_taper_length = 80.0     # Length of taper from pad to trace (µm)
    dc_trace_aperture_penetration = 100.0  # How far DC traces extend into aperture (µm)
    dc_trace_fanout_arc_radius = 200.0  # Radius of arc for trace fanout inside aperture (µm)
    dc_trace_fanout_arc_angle = 30.0   # Total angular spread for trace fanout (degrees)
    dc_aperture_triangle_base = 200.0  # Length along circle edge for triangular cutout (µm)
    dc_aperture_triangle_height = 150.0  # Depth of triangular cutout into aperture (µm)
    
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
    electroplating = False           # Enable electroplating tabs
    electroplating_tab_width = 25.0  # Width of electroplating tabs (µm)
    electroplating_tab_clearance = 50.0  # Clearance around signal tab in ground plane (µm)


class ChipDesigner:
    """Main design generator class for chip-level layout."""
    
    def __init__(self, config=None, layout=None):
        """
        Initialize designer with configuration.
        
        Args:
            config: DesignConfig instance or None to use defaults
            layout: External pya.Layout to use, or None to create new one
        """
        self.config = config if config is not None else DesignConfig()
        
        # Use external layout if provided, otherwise create new one
        if layout is not None:
            self.layout = layout
            self._external_layout = True
        else:
            self.layout = pya.Layout()
            self.layout.dbu = self.config.dbu
            self._external_layout = False
    
    def _um_to_dbu(self, um_value):
        """
        Convert micrometers to database units.
        
        With dbu=0.01 µm, 1 µm = 100 DBU.
        
        Args:
            um_value: value in micrometers (float)
        
        Returns:
            value in database units (int)
        """
        # 1 µm = 100 DBU (when dbu=0.01 µm)
        return int(round(um_value / self.config.dbu))
    
    def _get_dc_layer_idx(self, config=None):
        """
        Get the layer index for DC pads/traces.
        
        Uses DC_PAD_LAYER if defined, otherwise falls back to METAL_LAYER.
        
        Args:
            config: design configuration (uses self.config if None)
        
        Returns:
            int: KLayout layer index for DC geometry
        """
        if config is None:
            config = self.config
        dc_layer = getattr(config, 'DC_PAD_LAYER', config.METAL_LAYER)
        return self.layout.layer(dc_layer)
    
    def add_text_label(self, cell, text, x_center, y_center, height=None, clearance=None, config=None, insert_text=True):
        """
        Generate text label polygons and clearance region.
        
        Creates polygon-based text that will appear on the final wafer.
        Optionally inserts the text into the cell and returns a clearance region
        for ground plane subtraction.
        
        Args:
            cell: KLayout cell to insert text into (can be None if insert_text=False)
            text: Text string to display
            x_center: x-coordinate of text center (µm)
            y_center: y-coordinate of text center (µm)
            height: Height of text in µm (default from config)
            clearance: Clearance around text for ground plane (µm, default from config)
            config: design configuration
            insert_text: If True, insert text polygons into cell. If False, only return clearance region.
        
        Returns:
            pya.Region: Region representing text clearance box for ground plane subtraction
        """
        if config is None:
            config = self.config
        
        if height is None:
            height = config.text_label_height
        if clearance is None:
            clearance = config.text_label_clearance
        
        # Create a TextGenerator for polygon-based text
        gen = pya.TextGenerator.default_generator()
        
        # Generate text at unit scale first to measure its native height
        test_region = gen.text(text, config.dbu, 1.0)
        native_height = test_region.bbox().height() * config.dbu  # in µm
        
        # Calculate magnification needed to achieve target height
        if native_height > 0:
            mag = height / native_height
        else:
            mag = 1.0
        
        # Generate text with correct magnification
        text_region = gen.text(text, config.dbu, mag)
        
        # Calculate text bounding box to center it
        text_bbox = text_region.bbox()
        
        # Transform to center at (x_center, y_center)
        offset_x = self._um_to_dbu(x_center) - text_bbox.center().x
        offset_y = self._um_to_dbu(y_center) - text_bbox.center().y
        text_region.transform(pya.Trans(offset_x, offset_y))
        
        # Insert text polygons into cell if requested
        if insert_text and cell is not None:
            layer_idx = self.layout.layer(config.METAL_LAYER)
            cell.shapes(layer_idx).insert(text_region)
        
        # Create clearance region using bounding box + buffer
        text_bbox_transformed = text_region.bbox()
        clearance_dbu = self._um_to_dbu(clearance)
        clearance_box = pya.Box(
            text_bbox_transformed.left - clearance_dbu,
            text_bbox_transformed.bottom - clearance_dbu,
            text_bbox_transformed.right + clearance_dbu,
            text_bbox_transformed.top + clearance_dbu
        )
        
        return pya.Region(clearance_box)
    
    def _create_text_clearance_region(self, text, x_center, y_center, height=None, clearance=None, config=None):
        """
        Create clearance region for text without inserting the text.
        
        This is a convenience wrapper around add_text_label with insert_text=False.
        Used to subtract clearance from ground plane before adding text.
        
        Args:
            text: Text string
            x_center: x-coordinate of text center (µm)
            y_center: y-coordinate of text center (µm)
            height: Height of text in µm
            clearance: Clearance around text (µm)
            config: design configuration
        
        Returns:
            pya.Region: Region representing text clearance box
        """
        return self.add_text_label(
            cell=None, text=text, x_center=x_center, y_center=y_center,
            height=height, clearance=clearance, config=config, insert_text=False
        )
    
    def create_alignment_cross(self, cell, x_center, y_center, config=None):
        """
        Create an alignment cross (+ shape) at specified position.
        
        Also creates DC pad layer extension rectangles at the ends of each arm
        to enable alignment between the two layers.
        
        Args:
            cell: KLayout cell to insert cross into
            x_center: x-coordinate of cross center (µm)
            y_center: y-coordinate of cross center (µm)
            config: design configuration
        """
        if config is None:
            config = self.config
        
        size = config.cross_size
        lw = config.cross_linewidth
        clearance = config.cross_clearance
        extension = clearance / 2.0  # DC layer extension beyond metal layer
        
        # Horizontal bar (metal layer)
        h_bar = pya.Box(
            self._um_to_dbu(x_center - size / 2.0),
            self._um_to_dbu(y_center - lw / 2.0),
            self._um_to_dbu(x_center + size / 2.0),
            self._um_to_dbu(y_center + lw / 2.0)
        )
        cell.shapes(self.layout.layer(config.METAL_LAYER)).insert(h_bar)
        
        # Vertical bar (metal layer)
        v_bar = pya.Box(
            self._um_to_dbu(x_center - lw / 2.0),
            self._um_to_dbu(y_center - size / 2.0),
            self._um_to_dbu(x_center + lw / 2.0),
            self._um_to_dbu(y_center + size / 2.0)
        )
        cell.shapes(self.layout.layer(config.METAL_LAYER)).insert(v_bar)
        
        # DC pad layer extensions at ends of each arm (for layer alignment)
        dc_layer_idx = self.layout.layer(config.DC_PAD_LAYER)
        
        # Left extension (extends left from left end of horizontal bar)
        left_ext = pya.Box(
            self._um_to_dbu(x_center - size / 2.0 - extension),
            self._um_to_dbu(y_center - lw / 2.0),
            self._um_to_dbu(x_center - size / 2.0),
            self._um_to_dbu(y_center + lw / 2.0)
        )
        cell.shapes(dc_layer_idx).insert(left_ext)
        
        # Right extension (extends right from right end of horizontal bar)
        right_ext = pya.Box(
            self._um_to_dbu(x_center + size / 2.0),
            self._um_to_dbu(y_center - lw / 2.0),
            self._um_to_dbu(x_center + size / 2.0 + extension),
            self._um_to_dbu(y_center + lw / 2.0)
        )
        cell.shapes(dc_layer_idx).insert(right_ext)
        
        # Bottom extension (extends down from bottom of vertical bar)
        bottom_ext = pya.Box(
            self._um_to_dbu(x_center - lw / 2.0),
            self._um_to_dbu(y_center - size / 2.0 - extension),
            self._um_to_dbu(x_center + lw / 2.0),
            self._um_to_dbu(y_center - size / 2.0)
        )
        cell.shapes(dc_layer_idx).insert(bottom_ext)
        
        # Top extension (extends up from top of vertical bar)
        top_ext = pya.Box(
            self._um_to_dbu(x_center - lw / 2.0),
            self._um_to_dbu(y_center + size / 2.0),
            self._um_to_dbu(x_center + lw / 2.0),
            self._um_to_dbu(y_center + size / 2.0 + extension)
        )
        cell.shapes(dc_layer_idx).insert(top_ext)
    
    def create_alignment_cross_clearance(self, x_center, y_center, edge_length, config=None):
        """
        Create clearance box for alignment cross.
        
        Args:
            x_center: x-coordinate of cross center (µm)
            y_center: y-coordinate of cross center (µm)
            edge_length: side length of square clearance region (µm)
            config: design configuration
        
        Returns:
            pya.Box for the clearance region
        """
        if config is None:
            config = self.config
        
        clearance_box = pya.Box(
            self._um_to_dbu(x_center - edge_length / 2.0),
            self._um_to_dbu(y_center - edge_length / 2.0),
            self._um_to_dbu(x_center + edge_length / 2.0),
            self._um_to_dbu(y_center + edge_length / 2.0)
        )
        return clearance_box
    
    def create_electroplating_signal_tab(self, cell, left_pad_x, pad_y_center, config=None):
        """
        Create electroplating tab from left signal bond pad to chip edge (x=0).
        
        Args:
            cell: KLayout cell to insert tab into
            left_pad_x: x-position of left pad left edge (µm)
            pad_y_center: y-center of pad (µm)
            config: design configuration
        
        Returns:
            pya.Region: clearance region for ground plane subtraction
        """
        if config is None:
            config = self.config
        
        tab_width = config.electroplating_tab_width
        clearance = config.electroplating_tab_clearance
        
        # Signal tab: from x=0 to left edge of pad
        signal_tab = pya.Box(
            self._um_to_dbu(0),
            self._um_to_dbu(pad_y_center - tab_width / 2.0),
            self._um_to_dbu(left_pad_x),
            self._um_to_dbu(pad_y_center + tab_width / 2.0)
        )
        cell.shapes(self.layout.layer(config.METAL_LAYER)).insert(signal_tab)
        
        # Clearance region around signal tab (for ground plane subtraction)
        # Extends from x=0 to left_pad_x, with clearance on top/bottom
        clearance_box = pya.Box(
            self._um_to_dbu(0),
            self._um_to_dbu(pad_y_center - tab_width / 2.0 - clearance),
            self._um_to_dbu(left_pad_x),
            self._um_to_dbu(pad_y_center + tab_width / 2.0 + clearance)
        )
        
        return pya.Region(clearance_box)
    
    def create_electroplating_ground_tabs(self, cell, config=None):
        """
        Create electroplating tabs from ground plane extending to all 4 chip edges.
        
        Tabs extend from inside the ground plane (past dicing_margin) all the way to chip edge.
        
        Args:
            cell: KLayout cell to insert tabs into
            config: design configuration
        """
        if config is None:
            config = self.config
        
        tab_width = config.electroplating_tab_width
        margin = config.dicing_margin
        chip_w = config.chip_width
        chip_h = config.chip_height
        center_x = chip_w / 2.0
        center_y = chip_h / 2.0
        
        # Tabs need to extend from edge (0) INTO the ground plane area
        # Ground plane starts at margin, so tabs go from 0 to margin + overlap
        # Use a generous overlap to ensure connection
        overlap = 50.0  # 50 µm overlap into ground plane
        
        layer_idx = self.layout.layer(config.METAL_LAYER)
        
        # Left edge tab: from x=0 to past margin into ground plane
        # Position it away from signal tab (offset up or down)
        left_tab_y = center_y + 500.0  # Offset 500 µm above center to avoid signal tab
        left_tab = pya.Box(
            self._um_to_dbu(0),
            self._um_to_dbu(left_tab_y - tab_width / 2.0),
            self._um_to_dbu(margin + overlap),
            self._um_to_dbu(left_tab_y + tab_width / 2.0)
        )
        cell.shapes(layer_idx).insert(left_tab)
        
        # Right edge tab: from inside ground plane to chip edge
        right_tab = pya.Box(
            self._um_to_dbu(chip_w - margin - overlap),
            self._um_to_dbu(center_y - tab_width / 2.0),
            self._um_to_dbu(chip_w),
            self._um_to_dbu(center_y + tab_width / 2.0)
        )
        cell.shapes(layer_idx).insert(right_tab)
        
        # Top edge tab: from inside ground plane to chip edge
        top_tab = pya.Box(
            self._um_to_dbu(center_x - tab_width / 2.0),
            self._um_to_dbu(chip_h - margin - overlap),
            self._um_to_dbu(center_x + tab_width / 2.0),
            self._um_to_dbu(chip_h)
        )
        cell.shapes(layer_idx).insert(top_tab)
        
        # Bottom edge tab: from chip edge to inside ground plane
        bottom_tab = pya.Box(
            self._um_to_dbu(center_x - tab_width / 2.0),
            self._um_to_dbu(0),
            self._um_to_dbu(center_x + tab_width / 2.0),
            self._um_to_dbu(margin + overlap)
        )
        cell.shapes(layer_idx).insert(bottom_tab)
    
    def create_bond_pad(self, cell, x_pos, y_center, width, height, config=None):
        """
        Create a rectangular bond pad at specified position.
        
        Args:
            cell: KLayout cell to insert pad into
            x_pos: x-coordinate of left edge (µm)
            y_center: y-coordinate of center (µm)
            width: pad width (µm)
            height: pad height (µm)
            config: design configuration
        
        Returns:
            Bounding box of created pad (pya.Box in database units)
        """
        if config is None:
            config = self.config
        
        # Calculate pad corners in micrometers, then convert to database units
        y_top = y_center + height / 2.0
        y_bot = y_center - height / 2.0
        x_right = x_pos + width
        
        # Create pad as region (coordinates in database units)
        pad_region = pya.Region()
        pad_box = pya.Box(
            self._um_to_dbu(x_pos),
            self._um_to_dbu(y_bot),
            self._um_to_dbu(x_right),
            self._um_to_dbu(y_top)
        )
        pad_region.insert(pad_box)
        
        # Insert into cell
        cell.shapes(self.layout.layer(config.METAL_LAYER)).insert(pad_region)
        
        return pad_box
    
    def create_tapered_trace(self, cell, x_start, y_center, length, width_start, 
                             width_end, config=None):
        """
        Create a linearly tapered trace (pad → CPW).
        
        Uses polygon approximation for linear width transition.
        
        Args:
            cell: KLayout cell to insert trace into
            x_start: starting x-coordinate (µm)
            y_center: vertical center (µm)
            length: trace length along x (µm)
            width_start: width at start (µm)
            width_end: width at end (µm)
            config: design configuration
        
        Returns:
            List of vertices defining taper polygon
        """
        if config is None:
            config = self.config
        
        x_end = x_start + length
        
        # Create tapered polygon: trapezoid
        # Top edge tapers from width_start to width_end
        # Bottom edge symmetric
        vertices = [
            pya.Point(self._um_to_dbu(x_start), self._um_to_dbu(y_center + width_start/2.0)),
            pya.Point(self._um_to_dbu(x_end), self._um_to_dbu(y_center + width_end/2.0)),
            pya.Point(self._um_to_dbu(x_end), self._um_to_dbu(y_center - width_end/2.0)),
            pya.Point(self._um_to_dbu(x_start), self._um_to_dbu(y_center - width_start/2.0)),
        ]
        
        # Create and insert polygon
        taper_region = pya.Region(pya.Polygon(vertices))
        cell.shapes(self.layout.layer(config.METAL_LAYER)).insert(taper_region)
        
        return vertices
    
    def create_dc_pad_array(self, cell, y_offset, config=None):
        """
        Create DC bond pad array in an arc centered at chip center.
        
        Creates the complete DC signal path for each pad:
        1. Bond pad: Rectangle on arc at dc_pad_arc_radius
        2. Taper: From pad width to dc_trace_width
        3. Angled section: Follows ground plane taper slope toward center
        4. Vertical trace: From angled section to aperture edge
        5. Fan-out (optional): Traces spread inside aperture on arc at dc_trace_fanout_arc_radius
        
        Args:
            cell: KLayout cell to insert pads into
            y_offset: vertical offset from chip center (positive = above, negative = below)
            config: design configuration
        
        Returns:
            List of pad center positions [(x, y), ...] in µm
        """
        if config is None:
            config = self.config
        
        chip_center_x = config.chip_width / 2.0
        chip_center_y = config.chip_height / 2.0
        
        # Arc center is at chip center
        arc_center_x = chip_center_x
        arc_center_y = chip_center_y
        
        pad_positions = []
        
        # Determine if this is top or bottom array
        is_top = y_offset > 0
        
        # Sign multiplier for direction-dependent calculations (+1 for top, -1 for bottom)
        sign = 1 if is_top else -1
        
        # Arc angle range for pad placement (from config, default 30 degrees)
        dc_pad_arc_angle_deg = getattr(config, 'dc_pad_arc_angle', 30.0)
        total_arc_angle = math.radians(dc_pad_arc_angle_deg)
        
        # Center angle: 90 degrees (top) or 270 degrees (bottom)
        center_angle = math.pi / 2 if is_top else 3 * math.pi / 2
        
        # Get DC layer index once (instead of repeated getattr calls)
        dc_layer_idx = self._get_dc_layer_idx(config)
        
        # Place pads along arc
        for i in range(config.dc_pad_count):
            # Distribute pads evenly across the arc
            t = (i - (config.dc_pad_count - 1) / 2.0) / ((config.dc_pad_count - 1) / 2.0) if config.dc_pad_count > 1 else 0
            
            angle = center_angle + t * (total_arc_angle / 2.0)
            
            # Calculate pad center position on arc
            pad_x = arc_center_x + config.dc_pad_arc_radius * math.cos(angle)
            pad_y = arc_center_y + config.dc_pad_arc_radius * math.sin(angle)
            
            # Apply Y shift for inner pads (indices 1, 2, 3, 4 for 6 pads)
            # Shift them toward the chip center
            inner_y_shift = getattr(config, 'dc_pad_inner_y_shift', 0.0)
            if inner_y_shift > 0 and config.dc_pad_count == 6 and i in [1, 2, 3, 4]:
                # Shift toward center: subtract for top array, add for bottom array
                pad_y = pad_y - sign * inner_y_shift
            
            pad_positions.append((pad_x, pad_y))
            
            # Create pad as rectangle centered at (pad_x, pad_y)
            pad_box = pya.Box(
                self._um_to_dbu(pad_x - config.dc_pad_width / 2.0),
                self._um_to_dbu(pad_y - config.dc_pad_height / 2.0),
                self._um_to_dbu(pad_x + config.dc_pad_width / 2.0),
                self._um_to_dbu(pad_y + config.dc_pad_height / 2.0)
            )
            cell.shapes(dc_layer_idx).insert(pad_box)
            
            # Calculate final trace X position - evenly spaced within entrance width
            # For top: reverse index so left pads connect to left side of entrance
            # For bottom: use original index (pads are mirrored)
            entrance_spacing = config.dc_pad_entrance_width / (config.dc_pad_count + 1)
            trace_index = (config.dc_pad_count - 1 - i) if is_top else i
            trace_final_x = chip_center_x - config.dc_pad_entrance_width / 2.0 + entrance_spacing * (trace_index + 1)
            
            # Ground plane taper geometry (for reference):
            # - Wide end at dc_box_inner_y with width computed from dc_pad_arc_angle
            # - Narrow end at taper_end_y with width dc_pad_entrance_width
            # - Height = dc_pad_entrance_height
            dc_cutout_center_y = chip_center_y + y_offset
            
            # Pad inner edge (toward chip center)
            taper_start_y = pad_y - sign * config.dc_pad_height / 2.0
            taper_end_y = taper_start_y - sign * config.dc_trace_taper_length
            
            # Ground plane taper boundaries - computed from arc geometry
            # The taper starts at the innermost pad edge (plus clearance), not the cutout box edge
            dc_pad_arc_angle_deg = getattr(config, 'dc_pad_arc_angle', 30.0)
            half_arc_angle_rad = math.radians(dc_pad_arc_angle_deg / 2.0)
            pad_vertical_extent = config.dc_pad_arc_radius * math.cos(half_arc_angle_rad)
            
            if is_top:
                gp_taper_top_y = chip_center_y + pad_vertical_extent - config.dc_pad_height / 2.0 - config.dc_pad_clearance
            else:
                gp_taper_top_y = chip_center_y - pad_vertical_extent + config.dc_pad_height / 2.0 + config.dc_pad_clearance
            gp_taper_bottom_y = gp_taper_top_y - sign * config.dc_pad_entrance_height
            
            # Trace ends at aperture edge (vertical section)
            trace_end_y = chip_center_y + sign * config.aperture_radius
            
            # Fan-out parameters
            aperture_penetration = getattr(config, 'dc_trace_aperture_penetration', 0)
            fanout_arc_radius = getattr(config, 'dc_trace_fanout_arc_radius', 200.0)
            
            # Angled trace width is 3x the typical trace width
            angled_trace_width = config.dc_trace_width * 3.0
            
            # Create taper polygon (trapezoid) - stays centered on pad_x
            # Tapers from pad width to the angled trace width
            taper_vertices = [
                # Wide end (at pad)
                pya.Point(self._um_to_dbu(pad_x - config.dc_pad_width / 2.0),
                         self._um_to_dbu(taper_start_y)),
                pya.Point(self._um_to_dbu(pad_x + config.dc_pad_width / 2.0),
                         self._um_to_dbu(taper_start_y)),
                # Narrow end (to angled trace width)
                pya.Point(self._um_to_dbu(pad_x + angled_trace_width / 2.0),
                         self._um_to_dbu(taper_end_y)),
                pya.Point(self._um_to_dbu(pad_x - angled_trace_width / 2.0),
                         self._um_to_dbu(taper_end_y)),
            ]
            taper_polygon = pya.Polygon(taper_vertices)
            cell.shapes(dc_layer_idx).insert(taper_polygon)
            
            # Calculate the angle of the ground plane taper
            # Width is computed dynamically based on DC pad arc angle
            pad_horizontal_extent = config.dc_pad_arc_radius * math.sin(half_arc_angle_rad)
            cutout_width = 2.0 * (pad_horizontal_extent + config.dc_pad_width / 2.0 + config.dc_pad_clearance)
            
            gp_width_change = (cutout_width - config.dc_pad_entrance_width) / 2.0
            gp_height = config.dc_pad_entrance_height
            
            # How far does this trace need to move horizontally?
            trace_x_travel = abs(pad_x - trace_final_x)
            
            # Calculate Y distance needed for the angled section (same slope as ground plane)
            angled_section_height = trace_x_travel * (gp_height / gp_width_change) if gp_width_change > 0 else 0
            
            # Calculate angled end position with clamping
            angled_end_y = taper_end_y - sign * angled_section_height
            if is_top:
                angled_end_y = max(angled_end_y, gp_taper_bottom_y)
            else:
                angled_end_y = min(angled_end_y, gp_taper_bottom_y)
            
            # Angled trace width is 3x the typical trace width
            angled_trace_width = config.dc_trace_width * 3.0
            
            # Determine which side is "outer" (away from chip center)
            # Extra width extends only outward to maintain inner edge alignment
            is_left_of_center = trace_final_x < chip_center_x
            
            # At the end, inner edge should be at same position as vertical trace inner edge
            # Vertical trace inner edge: trace_final_x + dc_trace_width/2 (left) or trace_final_x - dc_trace_width/2 (right)
            if is_left_of_center:
                # Inner edge is on right (+x), outer edge on left (-x)
                angled_end_inner_x = trace_final_x + config.dc_trace_width / 2.0
                angled_end_outer_x = angled_end_inner_x - angled_trace_width
            else:
                # Inner edge is on left (-x), outer edge on right (+x)
                angled_end_inner_x = trace_final_x - config.dc_trace_width / 2.0
                angled_end_outer_x = angled_end_inner_x + angled_trace_width
            
            # Create angled trace section (parallelogram)
            angled_vertices = [
                # Start at taper end (centered on pad_x)
                pya.Point(self._um_to_dbu(pad_x - angled_trace_width / 2.0),
                         self._um_to_dbu(taper_end_y)),
                pya.Point(self._um_to_dbu(pad_x + angled_trace_width / 2.0),
                         self._um_to_dbu(taper_end_y)),
                # End at angled_end_y (inner edge aligned with vertical trace)
                pya.Point(self._um_to_dbu(max(angled_end_inner_x, angled_end_outer_x)),
                         self._um_to_dbu(angled_end_y)),
                pya.Point(self._um_to_dbu(min(angled_end_inner_x, angled_end_outer_x)),
                         self._um_to_dbu(angled_end_y)),
            ]
            angled_polygon = pya.Polygon(angled_vertices)
            cell.shapes(dc_layer_idx).insert(angled_polygon)
            
            # Create taper from angled trace width to vertical trace width
            # Taper only on the OUTER edge to maintain gap between traces
            # Taper length is proportional to width change for smooth transition
            width_taper_length = (angled_trace_width - config.dc_trace_width) * 2.0
            
            if is_top:
                width_taper_start_y = angled_end_y
                width_taper_end_y = angled_end_y - width_taper_length
            else:
                width_taper_start_y = angled_end_y
                width_taper_end_y = angled_end_y + width_taper_length
            
            # Use the same edge positions calculated for the angled trace
            # Inner edge stays constant, outer edge tapers in
            if is_left_of_center:
                # Keep right edge (inner) constant, taper left edge (outer)
                inner_edge_x = angled_end_inner_x
                wide_outer_x = angled_end_outer_x
                narrow_outer_x = trace_final_x - config.dc_trace_width / 2.0
                
                width_taper_vertices = [
                    # Wide end (at angled section end)
                    pya.Point(self._um_to_dbu(wide_outer_x), self._um_to_dbu(width_taper_start_y)),
                    pya.Point(self._um_to_dbu(inner_edge_x), self._um_to_dbu(width_taper_start_y)),
                    # Narrow end (inner edge stays same, outer edge tapers in)
                    pya.Point(self._um_to_dbu(inner_edge_x), self._um_to_dbu(width_taper_end_y)),
                    pya.Point(self._um_to_dbu(narrow_outer_x), self._um_to_dbu(width_taper_end_y)),
                ]
            else:
                # Keep left edge (inner) constant, taper right edge (outer)
                inner_edge_x = angled_end_inner_x
                wide_outer_x = angled_end_outer_x
                narrow_outer_x = trace_final_x + config.dc_trace_width / 2.0
                
                width_taper_vertices = [
                    # Wide end (at angled section end)
                    pya.Point(self._um_to_dbu(inner_edge_x), self._um_to_dbu(width_taper_start_y)),
                    pya.Point(self._um_to_dbu(wide_outer_x), self._um_to_dbu(width_taper_start_y)),
                    # Narrow end (inner edge stays same, outer edge tapers in)
                    pya.Point(self._um_to_dbu(narrow_outer_x), self._um_to_dbu(width_taper_end_y)),
                    pya.Point(self._um_to_dbu(inner_edge_x), self._um_to_dbu(width_taper_end_y)),
                ]
            
            width_taper_polygon = pya.Polygon(width_taper_vertices)
            cell.shapes(dc_layer_idx).insert(width_taper_polygon)
            
            # Create vertical trace section from width taper end to aperture radius
            # Box constructor needs (min_x, min_y, max_x, max_y)
            vert_y1, vert_y2 = (trace_end_y, width_taper_end_y) if is_top else (width_taper_end_y, trace_end_y)
            vertical_box = pya.Box(
                self._um_to_dbu(trace_final_x - config.dc_trace_width / 2.0),
                self._um_to_dbu(min(vert_y1, vert_y2)),
                self._um_to_dbu(trace_final_x + config.dc_trace_width / 2.0),
                self._um_to_dbu(max(vert_y1, vert_y2))
            )
            cell.shapes(dc_layer_idx).insert(vertical_box)
            
            # Create fan-out section inside the aperture using arc positioning
            if aperture_penetration > 0:
                # Calculate angular spread for fanout (independent of bond pad arc)
                fanout_arc_angle_deg = getattr(config, 'dc_trace_fanout_arc_angle', 30.0)
                fanout_total_arc_angle = math.radians(fanout_arc_angle_deg)
                
                # Center angle: 90 degrees (top) or 270 degrees (bottom)
                fanout_center_angle = math.pi / 2 if is_top else 3 * math.pi / 2
                
                # Calculate angle for this trace
                fanout_t = (i - (config.dc_pad_count - 1) / 2.0) / ((config.dc_pad_count - 1) / 2.0) if config.dc_pad_count > 1 else 0
                
                fanout_angle = fanout_center_angle + fanout_t * (fanout_total_arc_angle / 2.0)
                
                # Fan-out end position on arc
                fanout_final_x = chip_center_x + fanout_arc_radius * math.cos(fanout_angle)
                fanout_final_y = chip_center_y + fanout_arc_radius * math.sin(fanout_angle)
                
                # Create fan-out polygon (trapezoid from vertical trace to arc position)
                fanout_vertices = [
                    # Start at aperture edge (vertical trace position)
                    pya.Point(self._um_to_dbu(trace_final_x - config.dc_trace_width / 2.0),
                             self._um_to_dbu(trace_end_y)),
                    pya.Point(self._um_to_dbu(trace_final_x + config.dc_trace_width / 2.0),
                             self._um_to_dbu(trace_end_y)),
                    # End at fanned-out position on arc inside aperture
                    pya.Point(self._um_to_dbu(fanout_final_x + config.dc_trace_width / 2.0),
                             self._um_to_dbu(fanout_final_y)),
                    pya.Point(self._um_to_dbu(fanout_final_x - config.dc_trace_width / 2.0),
                             self._um_to_dbu(fanout_final_y)),
                ]
                
                fanout_polygon = pya.Polygon(fanout_vertices)
                cell.shapes(dc_layer_idx).insert(fanout_polygon)
        
        return pad_positions
    
    def create_dc_cutout_region(self, y_offset, config=None):
        """
        Create rectangular cutout region for DC pad array.
        
        The cutout width and inner edge position are computed dynamically based 
        on the DC pad arc angle to ensure all pads are encompassed regardless 
        of their angular spread, and to connect seamlessly with the entrance taper.
        
        Args:
            y_offset: vertical offset from chip center (positive = above, negative = below)
            config: design configuration
        
        Returns:
            pya.Region representing the cutout area
        """
        if config is None:
            config = self.config
        
        chip_center_x = config.chip_width / 2.0
        chip_center_y = config.chip_height / 2.0
        
        is_top = y_offset > 0
        
        # Calculate cutout width based on arc geometry
        # The outermost pads are at angle = center_angle ± (arc_angle/2)
        # Their horizontal extent from center is: arc_radius * sin(arc_angle/2)
        dc_pad_arc_angle_deg = getattr(config, 'dc_pad_arc_angle', 30.0)
        half_arc_angle_rad = math.radians(dc_pad_arc_angle_deg / 2.0)
        
        # Horizontal distance from center to outermost pad center
        pad_horizontal_extent = config.dc_pad_arc_radius * math.sin(half_arc_angle_rad)
        
        # Total cutout width: 2x (pad extent + half pad width + clearance)
        cutout_width = 2.0 * (pad_horizontal_extent + config.dc_pad_width / 2.0 + config.dc_pad_clearance)
        
        # Vertical extent: from chip edge (with clearance) to innermost pad edge
        # The innermost pad edge is determined by the arc geometry
        pad_vertical_extent = config.dc_pad_arc_radius * math.cos(half_arc_angle_rad)
        
        # Inner edge (toward chip center) - must match taper start position
        if is_top:
            inner_edge_y = chip_center_y + pad_vertical_extent - config.dc_pad_height / 2.0 - config.dc_pad_clearance
            # Outer edge extends to chip edge area (use old formula for outer extent)
            outer_edge_y = chip_center_y + y_offset + config.dc_cutout_height / 2.0
        else:
            inner_edge_y = chip_center_y - pad_vertical_extent + config.dc_pad_height / 2.0 + config.dc_pad_clearance
            outer_edge_y = chip_center_y + y_offset - config.dc_cutout_height / 2.0
        
        cutout_box = pya.Box(
            self._um_to_dbu(chip_center_x - cutout_width / 2.0),
            self._um_to_dbu(min(inner_edge_y, outer_edge_y)),
            self._um_to_dbu(chip_center_x + cutout_width / 2.0),
            self._um_to_dbu(max(inner_edge_y, outer_edge_y))
        )
        
        return pya.Region(cutout_box)
    
    def create_dc_entrance_cutout(self, y_offset, config=None):
        """
        Create tapered entrance cutout from DC pad box to aperture.
        
        Consists of two parts:
        1. Tapered section: from dynamically calculated cutout width at the innermost
           pad edge (plus clearance) down to dc_pad_entrance_width
        2. Rectangular channel: from taper end through aperture circle
        
        The wide end width and Y position are computed from the DC pad arc geometry
        to ensure the taper clears all bond pads.
        
        Args:
            y_offset: vertical offset from chip center (positive = above, negative = below)
            config: design configuration
        
        Returns:
            pya.Region representing the combined cutout area
        """
        if config is None:
            config = self.config
        
        chip_center_x = config.chip_width / 2.0
        chip_center_y = config.chip_height / 2.0
        
        is_top = y_offset > 0
        sign = 1 if is_top else -1
        
        # Calculate wide width based on arc geometry (same as create_dc_cutout_region)
        dc_pad_arc_angle_deg = getattr(config, 'dc_pad_arc_angle', 30.0)
        half_arc_angle_rad = math.radians(dc_pad_arc_angle_deg / 2.0)
        pad_horizontal_extent = config.dc_pad_arc_radius * math.sin(half_arc_angle_rad)
        wide_width = 2.0 * (pad_horizontal_extent + config.dc_pad_width / 2.0 + config.dc_pad_clearance)
        
        # Calculate taper start Y position based on innermost pad edge
        # The outermost pads (at half_arc_angle from center) are at:
        # pad_y = chip_center_y + dc_pad_arc_radius * sin(center_angle + half_arc_angle)
        # For top: center_angle = 90°, so the outermost pads are at lower Y
        # For bottom: center_angle = 270°, so the outermost pads are at higher Y
        #
        # The innermost Y position of all pads (closest to chip center) is:
        # min_pad_y (top) = chip_center_y + dc_pad_arc_radius * cos(half_arc_angle) - dc_pad_height/2
        # max_pad_y (bottom) = chip_center_y - dc_pad_arc_radius * cos(half_arc_angle) + dc_pad_height/2
        #
        # Note: For angle from vertical (90°), we use cos for the vertical component
        pad_vertical_extent = config.dc_pad_arc_radius * math.cos(half_arc_angle_rad)
        
        if is_top:
            # Taper starts below the innermost pad edge with clearance
            taper_wide_y = chip_center_y + pad_vertical_extent - config.dc_pad_height / 2.0 - config.dc_pad_clearance
        else:
            # Taper starts above the innermost pad edge with clearance
            taper_wide_y = chip_center_y - pad_vertical_extent + config.dc_pad_height / 2.0 + config.dc_pad_clearance
        
        # Taper dimensions
        taper_height = config.dc_pad_entrance_height  # Height of tapered section
        narrow_width = config.dc_pad_entrance_width
        
        # Taper end position (toward center)
        if is_top:
            taper_end_y = taper_wide_y - taper_height
        else:
            taper_end_y = taper_wide_y + taper_height
        
        # Create tapered polygon (trapezoid)
        if is_top:
            taper_vertices = [
                # Wide end (at innermost pad edge with clearance)
                pya.Point(self._um_to_dbu(chip_center_x - wide_width / 2.0),
                         self._um_to_dbu(taper_wide_y)),
                pya.Point(self._um_to_dbu(chip_center_x + wide_width / 2.0),
                         self._um_to_dbu(taper_wide_y)),
                # Narrow end (toward center)
                pya.Point(self._um_to_dbu(chip_center_x + narrow_width / 2.0),
                         self._um_to_dbu(taper_end_y)),
                pya.Point(self._um_to_dbu(chip_center_x - narrow_width / 2.0),
                         self._um_to_dbu(taper_end_y)),
            ]
        else:
            taper_vertices = [
                # Wide end (at innermost pad edge with clearance)
                pya.Point(self._um_to_dbu(chip_center_x - wide_width / 2.0),
                         self._um_to_dbu(taper_wide_y)),
                pya.Point(self._um_to_dbu(chip_center_x + wide_width / 2.0),
                         self._um_to_dbu(taper_wide_y)),
                # Narrow end (toward center)
                pya.Point(self._um_to_dbu(chip_center_x + narrow_width / 2.0),
                         self._um_to_dbu(taper_end_y)),
                pya.Point(self._um_to_dbu(chip_center_x - narrow_width / 2.0),
                         self._um_to_dbu(taper_end_y)),
            ]
        
        taper_polygon = pya.Polygon(taper_vertices)
        taper_region = pya.Region(taper_polygon)
        
        # Create rectangular channel from taper end through aperture
        # Channel goes from taper_end_y to chip_center_y (through aperture)
        if is_top:
            channel_box = pya.Box(
                self._um_to_dbu(chip_center_x - narrow_width / 2.0),
                self._um_to_dbu(chip_center_y),  # Stop at center (aperture will be cut separately)
                self._um_to_dbu(chip_center_x + narrow_width / 2.0),
                self._um_to_dbu(taper_end_y)
            )
        else:
            channel_box = pya.Box(
                self._um_to_dbu(chip_center_x - narrow_width / 2.0),
                self._um_to_dbu(taper_end_y),
                self._um_to_dbu(chip_center_x + narrow_width / 2.0),
                self._um_to_dbu(chip_center_y)  # Stop at center
            )
        
        channel_region = pya.Region(channel_box)
        
        # Combine taper and channel
        combined_region = taper_region + channel_region
        combined_region.merge()
        
        return combined_region

    def create_dc_aperture_triangle_cutout(self, y_offset, config=None):
        """
        Create triangular cutouts at the aperture edge where DC entrance meets the circle.
        
        Creates two triangles (left and right of the DC entrance channel) to provide
        more clearance for DC trace fan-out.
        
        Triangle vertices:
        1. Corner where DC entrance channel edge intersects aperture circle
        2. Point along circle edge at dc_aperture_triangle_base distance away
        3. Point toward aperture center at dc_aperture_triangle_height depth
        
        Args:
            y_offset: vertical offset from chip center (positive = above, negative = below)
            config: design configuration
        
        Returns:
            pya.Region representing both triangular cutouts
        """
        if config is None:
            config = self.config
        
        chip_center_x = config.chip_width / 2.0
        chip_center_y = config.chip_height / 2.0
        
        is_top = y_offset > 0
        
        # Get parameters
        triangle_base = getattr(config, 'dc_aperture_triangle_base', 200.0)
        triangle_height = getattr(config, 'dc_aperture_triangle_height', 150.0)
        narrow_width = config.dc_pad_entrance_width
        radius = config.aperture_radius
        
        # The DC entrance channel edges are at these x positions
        channel_left_x = chip_center_x - narrow_width / 2.0
        channel_right_x = chip_center_x + narrow_width / 2.0
        
        # Distance from center to channel edge
        half_width = narrow_width / 2.0
        
        # Check if channel is narrower than circle diameter
        if half_width >= radius:
            return pya.Region()  # Channel wider than circle, no triangles needed
        
        # Y position where channel edges intersect the circle
        # Circle equation: (x - cx)^2 + (y - cy)^2 = r^2
        # At x = channel_left_x: (channel_left_x - cx)^2 + (y - cy)^2 = r^2
        # y = cy ± sqrt(r^2 - (half_width)^2)
        y_offset_from_center = math.sqrt(radius**2 - half_width**2)
        
        if is_top:
            # For top: intersection is above center
            corner_y = chip_center_y + y_offset_from_center
        else:
            # For bottom: intersection is below center
            corner_y = chip_center_y - y_offset_from_center
        
        combined_region = pya.Region()
        
        # Calculate angle offset for the base length along the circle
        angle_offset = triangle_base / radius
        
        # For each side (left and right of the DC entrance channel)
        for side in ['left', 'right']:
            apex_y = 0
            apex_x = 0
            far_angle = 0
            
            if side == 'left':
                corner_x = channel_left_x
                # Angle of the corner point on the circle
                # cos(theta) = (corner_x - cx) / r = -half_width / r
                apex_x = channel_left_x
                if is_top:
                    corner_angle = math.acos(-half_width / radius)  # In range [pi/2, pi]
                    # Going further left means increasing angle
                    far_angle = corner_angle + angle_offset
                    apex_y = radius + triangle_height+ chip_center_y
                else:
                    corner_angle = -math.acos(-half_width / radius)  # Negative angle, in range [-pi, -pi/2]
                    # Going further left means decreasing angle (more negative)
                    far_angle = corner_angle - angle_offset
                    apex_y = -radius - triangle_height+ chip_center_y
            else:
                corner_x = channel_right_x
                # cos(theta) = (corner_x - cx) / r = +half_width / r
                apex_x = channel_right_x
                if is_top:
                    corner_angle = math.acos(half_width / radius)  # In range [0, pi/2]
                    # Going further right means decreasing angle
                    far_angle = corner_angle - angle_offset
                    apex_y = radius + triangle_height+ chip_center_y
                else:
                    corner_angle = -math.acos(half_width / radius)  # Negative angle, in range [-pi/2, 0]
                    # Going further right means increasing angle (less negative)
                    far_angle = corner_angle + angle_offset
                    apex_y = -radius - triangle_height+ chip_center_y
            
            # Far point on circle
            far_x = chip_center_x + radius * math.cos(far_angle)
            far_y = chip_center_y + radius * math.sin(far_angle)
            
            
            
            
            # Create triangle polygon
            triangle_vertices = [
                pya.Point(self._um_to_dbu(corner_x), self._um_to_dbu(corner_y)),
                pya.Point(self._um_to_dbu(far_x), self._um_to_dbu(far_y)),
                pya.Point(self._um_to_dbu(apex_x), self._um_to_dbu(apex_y)),
            ]
            
            triangle_polygon = pya.Polygon(triangle_vertices)
            combined_region += pya.Region(triangle_polygon)
        
        combined_region.merge()
        return combined_region

    def create_ground_plane_with_traces(self, cell, left_pad_x, right_pad_x, pad_y_center,
                                       left_cpw_start_x, right_cpw_start_x, config=None):
        """
        Create ground plane filling chip except:
        - Left rapid taper (pad → CPW)
        - Left CPW section (pad→aperture)
        - Right CPW section (aperture→pad)
        - Right rapid taper (CPW → pad)
        - Central circular aperture
        - Bond pad clearance zones
        - DC pad cutout regions (top and bottom)
        
        Uses region Boolean operations for robust subtraction.
        
        Args:
            cell: KLayout cell to insert ground into
            left_pad_x: x-position of left pad (µm)
            right_pad_x: x-position of right pad (µm)
            pad_y_center: y-center of pads (µm)
            left_cpw_start_x: x-position where left CPW begins (µm)
            right_cpw_start_x: x-position where right taper begins (µm)
            config: design configuration
        """
        if config is None:
            config = self.config        # Start with ground plane inset by dicing margin
        ground_region = pya.Region(pya.Box(
            self._um_to_dbu(config.dicing_margin),
            self._um_to_dbu(config.dicing_margin),
            self._um_to_dbu(config.chip_width - config.dicing_margin),
            self._um_to_dbu(config.chip_height - config.dicing_margin)
        ))
        
        # Chip center
        chip_center_x = config.chip_width / 2.0
        chip_center_y = config.chip_height / 2.0
        
        # Subtract left rapid taper with CPW gap margin
        # The gap margin must taper: starts wide (pad + gap), ends narrow (cpw + gap)
        left_taper_start_x = left_pad_x + config.pad_width
        left_taper_end_x = left_cpw_start_x
        
        # Create gap region above signal taper (transitions from pad_to_ground_clearance to cpw_gap)
        left_gap_vertices = [
            # Outer edge at pad side: offset by pad_to_ground_clearance
            pya.Point(self._um_to_dbu(left_taper_start_x + config.cpw_gap), 
                     self._um_to_dbu(pad_y_center + config.pad_height/2.0 + config.pad_to_ground_clearance)),
            # Outer edge at CPW side: offset by cpw_gap (transitions to match CPW)
            pya.Point(self._um_to_dbu(left_taper_end_x + config.cpw_gap), 
                     self._um_to_dbu(pad_y_center + config.cpw_signal_width/2.0 + config.cpw_gap)),
            # Inner edge: signal boundary
            pya.Point(self._um_to_dbu(left_taper_end_x), 
                     self._um_to_dbu(pad_y_center + config.cpw_signal_width/2.0)),
            pya.Point(self._um_to_dbu(left_taper_start_x), 
                     self._um_to_dbu(pad_y_center + config.pad_height/2.0)),
        ]
        left_gap_top_polygon = pya.Polygon(left_gap_vertices)
        ground_region -= pya.Region(left_gap_top_polygon)
        
        # Bottom gap (symmetric)
        left_gap_vertices_bot = [
            pya.Point(self._um_to_dbu(left_taper_start_x + config.cpw_gap), 
                     self._um_to_dbu(pad_y_center - config.pad_height/2.0 - config.pad_to_ground_clearance)),
            pya.Point(self._um_to_dbu(left_taper_end_x + config.cpw_gap), 
                     self._um_to_dbu(pad_y_center - config.cpw_signal_width/2.0 - config.cpw_gap)),
            pya.Point(self._um_to_dbu(left_taper_end_x), 
                     self._um_to_dbu(pad_y_center - config.cpw_signal_width/2.0)),
            pya.Point(self._um_to_dbu(left_taper_start_x), 
                     self._um_to_dbu(pad_y_center - config.pad_height/2.0)),
        ]
        left_gap_bot_polygon = pya.Polygon(left_gap_vertices_bot)
        ground_region -= pya.Region(left_gap_bot_polygon)
        
        # Subtract signal line itself (taper)
        left_taper_vertices = [
            pya.Point(self._um_to_dbu(left_taper_start_x), 
                     self._um_to_dbu(pad_y_center + config.pad_height/2.0)),
            pya.Point(self._um_to_dbu(left_taper_end_x), 
                     self._um_to_dbu(pad_y_center + config.cpw_signal_width/2.0)),
            pya.Point(self._um_to_dbu(left_taper_end_x), 
                     self._um_to_dbu(pad_y_center - config.cpw_signal_width/2.0)),
            pya.Point(self._um_to_dbu(left_taper_start_x), 
                     self._um_to_dbu(pad_y_center - config.pad_height/2.0)),
        ]
        left_taper_polygon = pya.Polygon(left_taper_vertices)
        ground_region -= pya.Region(left_taper_polygon)
        
        # Subtract left CPW section with gap margin
        left_cpw_end_x = chip_center_x - config.aperture_radius
        # Extend gap region slightly past where signal ends to account for circular aperture
        left_cpw_end_extended = chip_center_x - config.aperture_radius * 0.85  # Extend past chord
        left_cpw_box = pya.Box(
            self._um_to_dbu(left_cpw_start_x),
            self._um_to_dbu(pad_y_center - config.cpw_signal_width/2.0 - config.cpw_gap),
            self._um_to_dbu(left_cpw_end_extended),
            self._um_to_dbu(pad_y_center + config.cpw_signal_width/2.0 + config.cpw_gap)
        )
        ground_region -= pya.Region(left_cpw_box)
        
        # Subtract right CPW section with gap margin
        right_cpw_start_x = chip_center_x + config.aperture_radius
        # Extend gap region slightly past where signal ends to account for circular aperture
        right_cpw_start_extended = chip_center_x + config.aperture_radius * 0.85  # Extend past chord
        right_taper_start_x = right_pad_x - config.taper_length
        right_cpw_box = pya.Box(
            self._um_to_dbu(right_cpw_start_extended),
            self._um_to_dbu(pad_y_center - config.cpw_signal_width/2.0 - config.cpw_gap),
            self._um_to_dbu(right_taper_start_x),
            self._um_to_dbu(pad_y_center + config.cpw_signal_width/2.0 + config.cpw_gap)
        )
        ground_region -= pya.Region(right_cpw_box)
        
        # Subtract right rapid taper with CPW gap margin
        # The gap margin must taper: starts narrow (cpw + gap), ends wide (pad + gap)
        right_taper_start_x = right_pad_x - config.taper_length
        right_taper_end_x = right_pad_x
        
        # Create gap region above signal taper (transitions from cpw_gap to pad_to_ground_clearance)
        right_gap_vertices = [
            # Outer edge at CPW side: offset by cpw_gap in X, cpw_gap in Y
            pya.Point(self._um_to_dbu(right_taper_start_x - config.cpw_gap), 
                     self._um_to_dbu(pad_y_center + config.cpw_signal_width/2.0 + config.cpw_gap)),
            # Outer edge at pad side: offset by cpw_gap in X, pad_to_ground_clearance in Y
            pya.Point(self._um_to_dbu(right_taper_end_x - config.cpw_gap), 
                     self._um_to_dbu(pad_y_center + config.pad_height/2.0 + config.pad_to_ground_clearance)),
            # Inner edge: signal boundary
            pya.Point(self._um_to_dbu(right_taper_end_x), 
                     self._um_to_dbu(pad_y_center + config.pad_height/2.0)),
            pya.Point(self._um_to_dbu(right_taper_start_x), 
                     self._um_to_dbu(pad_y_center + config.cpw_signal_width/2.0)),
        ]
        right_gap_top_polygon = pya.Polygon(right_gap_vertices)
        ground_region -= pya.Region(right_gap_top_polygon)
        
        # Bottom gap (symmetric)
        right_gap_vertices_bot = [
            pya.Point(self._um_to_dbu(right_taper_start_x - config.cpw_gap), 
                     self._um_to_dbu(pad_y_center - config.cpw_signal_width/2.0 - config.cpw_gap)),
            pya.Point(self._um_to_dbu(right_taper_end_x - config.cpw_gap), 
                     self._um_to_dbu(pad_y_center - config.pad_height/2.0 - config.pad_to_ground_clearance)),
            pya.Point(self._um_to_dbu(right_taper_end_x), 
                     self._um_to_dbu(pad_y_center - config.pad_height/2.0)),
            pya.Point(self._um_to_dbu(right_taper_start_x), 
                     self._um_to_dbu(pad_y_center - config.cpw_signal_width/2.0)),
        ]
        right_gap_bot_polygon = pya.Polygon(right_gap_vertices_bot)
        ground_region -= pya.Region(right_gap_bot_polygon)
        
        # Subtract signal line itself (taper)
        right_taper_vertices = [
            pya.Point(self._um_to_dbu(right_taper_start_x), 
                     self._um_to_dbu(pad_y_center + config.cpw_signal_width/2.0)),
            pya.Point(self._um_to_dbu(right_taper_end_x), 
                     self._um_to_dbu(pad_y_center + config.pad_height/2.0)),
            pya.Point(self._um_to_dbu(right_taper_end_x), 
                     self._um_to_dbu(pad_y_center - config.pad_height/2.0)),
            pya.Point(self._um_to_dbu(right_taper_start_x), 
                     self._um_to_dbu(pad_y_center - config.cpw_signal_width/2.0)),
        ]
        right_taper_polygon = pya.Polygon(right_taper_vertices)
        ground_region -= pya.Region(right_taper_polygon)
        
        # Subtract central circular aperture
        # Create circle by approximating with high-precision polygon
        aperture_center_x = self._um_to_dbu(chip_center_x)
        aperture_center_y = self._um_to_dbu(chip_center_y)
        aperture_radius_dbu = self._um_to_dbu(config.aperture_radius)
        
        num_segments = 128  # Higher precision circle approximation (128 segments)
        aperture_points = []
        for i in range(num_segments):
            angle = 2.0 * math.pi * i / num_segments
            x = aperture_center_x + int(round(aperture_radius_dbu * math.cos(angle)))
            y = aperture_center_y + int(round(aperture_radius_dbu * math.sin(angle)))
            aperture_points.append(pya.Point(x, y))
        
        aperture_polygon = pya.Polygon(aperture_points)
        aperture_region = pya.Region(aperture_polygon)
        aperture_region.merge()  # Clean up the polygon before subtraction
        ground_region -= aperture_region
        
        # Create tapered ground plane cutouts leading into aperture (left and right)
        # The taper widens the CPW gap as it approaches the aperture
        taper_angle_rad = math.radians(config.aperture_taper_angle)
        taper_length = config.aperture_taper_length
        
        # Calculate the width increase at the aperture end
        # tan(angle) = (width_increase / 2) / length
        width_increase = 2.0 * taper_length * math.tan(taper_angle_rad)
        
        # Calculate where the CPW gap edge intersects the circle
        # Circle: (x - cx)^2 + (y - cy)^2 = r^2
        # At y = pad_y_center + cpw_signal_width/2 + cpw_gap (top edge of gap)
        # Since pad_y_center = chip_center_y, the y offset from center is:
        gap_top_y_offset = config.cpw_signal_width/2.0 + config.cpw_gap + width_increase/2.0
        gap_bot_y_offset = config.cpw_signal_width/2.0 + config.cpw_gap + width_increase/2.0
        
        # x offset from center where circle intersects that y level
        # x = cx - sqrt(r^2 - y_offset^2) for left side
        if config.aperture_radius > gap_top_y_offset:
            left_circle_intersect_x = chip_center_x - math.sqrt(config.aperture_radius**2 - gap_top_y_offset**2)
            right_circle_intersect_x = chip_center_x + math.sqrt(config.aperture_radius**2 - gap_top_y_offset**2)
        else:
            # Fallback if gap is larger than radius (shouldn't happen normally)
            left_circle_intersect_x = chip_center_x - config.aperture_radius
            right_circle_intersect_x = chip_center_x + config.aperture_radius
        
        # Left side aperture taper (CPW gap widens into aperture)
        left_taper_start_x = left_circle_intersect_x - taper_length
        left_taper_end_x = left_circle_intersect_x
        
        # Top taper (above signal line)
        left_aperture_taper_top = [
            # Start: narrow (CPW gap)
            pya.Point(self._um_to_dbu(left_taper_start_x),
                     self._um_to_dbu(pad_y_center + config.cpw_signal_width/2.0)),
            pya.Point(self._um_to_dbu(left_taper_start_x),
                     self._um_to_dbu(pad_y_center + config.cpw_signal_width/2.0 + config.cpw_gap)),
            # End: widened (meets circle)
            pya.Point(self._um_to_dbu(left_taper_end_x),
                     self._um_to_dbu(pad_y_center + gap_top_y_offset)),
            pya.Point(self._um_to_dbu(left_taper_end_x),
                     self._um_to_dbu(pad_y_center + config.cpw_signal_width/2.0)),
        ]
        ground_region -= pya.Region(pya.Polygon(left_aperture_taper_top))
        
        # Bottom taper (below signal line)
        left_aperture_taper_bot = [
            # Start: narrow (CPW gap)
            pya.Point(self._um_to_dbu(left_taper_start_x),
                     self._um_to_dbu(pad_y_center - config.cpw_signal_width/2.0)),
            pya.Point(self._um_to_dbu(left_taper_start_x),
                     self._um_to_dbu(pad_y_center - config.cpw_signal_width/2.0 - config.cpw_gap)),
            # End: widened (meets circle)
            pya.Point(self._um_to_dbu(left_taper_end_x),
                     self._um_to_dbu(pad_y_center - gap_bot_y_offset)),
            pya.Point(self._um_to_dbu(left_taper_end_x),
                     self._um_to_dbu(pad_y_center - config.cpw_signal_width/2.0)),
        ]
        ground_region -= pya.Region(pya.Polygon(left_aperture_taper_bot))
        
        # Right side aperture taper
        right_taper_start_x_ap = right_circle_intersect_x + taper_length
        right_taper_end_x_ap = right_circle_intersect_x
        
        # Top taper (above signal line)
        right_aperture_taper_top = [
            # Start: narrow (CPW gap)
            pya.Point(self._um_to_dbu(right_taper_start_x_ap),
                     self._um_to_dbu(pad_y_center + config.cpw_signal_width/2.0)),
            pya.Point(self._um_to_dbu(right_taper_start_x_ap),
                     self._um_to_dbu(pad_y_center + config.cpw_signal_width/2.0 + config.cpw_gap)),
            # End: widened (meets circle)
            pya.Point(self._um_to_dbu(right_taper_end_x_ap),
                     self._um_to_dbu(pad_y_center + gap_top_y_offset)),
            pya.Point(self._um_to_dbu(right_taper_end_x_ap),
                     self._um_to_dbu(pad_y_center + config.cpw_signal_width/2.0)),
        ]
        ground_region -= pya.Region(pya.Polygon(right_aperture_taper_top))
        
        # Bottom taper (below signal line)
        right_aperture_taper_bot = [
            # Start: narrow (CPW gap)
            pya.Point(self._um_to_dbu(right_taper_start_x_ap),
                     self._um_to_dbu(pad_y_center - config.cpw_signal_width/2.0)),
            pya.Point(self._um_to_dbu(right_taper_start_x_ap),
                     self._um_to_dbu(pad_y_center - config.cpw_signal_width/2.0 - config.cpw_gap)),
            # End: widened (meets circle)
            pya.Point(self._um_to_dbu(right_taper_end_x_ap),
                     self._um_to_dbu(pad_y_center - gap_bot_y_offset)),
            pya.Point(self._um_to_dbu(right_taper_end_x_ap),
                     self._um_to_dbu(pad_y_center - config.cpw_signal_width/2.0)),
        ]
        ground_region -= pya.Region(pya.Polygon(right_aperture_taper_bot))
        
        # Subtract bond pad clearance zones 
        # Extend past pad edge to meet gap taper region
        pad_clearance = config.pad_to_ground_clearance
        
        # Left pad clearance - extend right edge to meet gap taper
        left_pad_exclusion = pya.Box(
            self._um_to_dbu(left_pad_x - pad_clearance),
            self._um_to_dbu(pad_y_center - config.pad_height/2.0 - pad_clearance),
            self._um_to_dbu(left_pad_x + config.pad_width + config.cpw_gap),  # Extend past pad
            self._um_to_dbu(pad_y_center + config.pad_height/2.0 + pad_clearance)
        )
        ground_region -= pya.Region(left_pad_exclusion)
        
        # Right pad clearance - extend left edge to meet gap taper
        right_pad_exclusion = pya.Box(
            self._um_to_dbu(right_pad_x - config.cpw_gap),  # Extend before pad
            self._um_to_dbu(pad_y_center - config.pad_height/2.0 - pad_clearance),
            self._um_to_dbu(right_pad_x + config.pad_width + pad_clearance),
            self._um_to_dbu(pad_y_center + config.pad_height/2.0 + pad_clearance)
        )
        ground_region -= pya.Region(right_pad_exclusion)
        
        # Subtract DC pad array cutout regions (top and bottom)
        top_dc_cutout = self.create_dc_cutout_region(config.dc_pad_y_offset, config)
        ground_region -= top_dc_cutout
        
        bottom_dc_cutout = self.create_dc_cutout_region(-config.dc_pad_y_offset, config)
        ground_region -= bottom_dc_cutout
        
        # Subtract DC entrance tapered cutouts (connect DC pads to aperture area)
        top_dc_entrance = self.create_dc_entrance_cutout(config.dc_pad_y_offset, config)
        ground_region -= top_dc_entrance
        
        bottom_dc_entrance = self.create_dc_entrance_cutout(-config.dc_pad_y_offset, config)
        ground_region -= bottom_dc_entrance
        
        # Subtract triangular cutouts at aperture edge for DC fan-out clearance
        top_dc_triangle = self.create_dc_aperture_triangle_cutout(config.dc_pad_y_offset, config)
        ground_region -= top_dc_triangle
        
        bottom_dc_triangle = self.create_dc_aperture_triangle_cutout(-config.dc_pad_y_offset, config)
        ground_region -= bottom_dc_triangle
        
        # Subtract alignment cross clearance regions
        cross_offset = config.cross_offset
        clearance_size = config.cross_size + config.cross_clearance * 2
        ground_region -= pya.Region(self.create_alignment_cross_clearance(chip_center_x - cross_offset, chip_center_y + cross_offset, clearance_size, config))
        ground_region -= pya.Region(self.create_alignment_cross_clearance(chip_center_x + cross_offset, chip_center_y + cross_offset, clearance_size, config))
        ground_region -= pya.Region(self.create_alignment_cross_clearance(chip_center_x - cross_offset, chip_center_y - cross_offset, clearance_size, config))
        ground_region -= pya.Region(self.create_alignment_cross_clearance(chip_center_x + cross_offset, chip_center_y - cross_offset, clearance_size, config))
        
        # Insert merged ground plane
        ground_region.merge()
        cell.shapes(self.layout.layer(config.METAL_LAYER)).insert(ground_region)
    
    def create_chip(self, chip_name="chip_main", config=None, label=None):
        """
        Create complete chip with CPW signal traces, bond pads, and ground plane.
        
        Signal path: Pad (400×800 µm) → Rapid taper (50 µm) → CPW (100 µm) → Aperture
        
        Hierarchy:
        1. Left bond pad and 50 µm rapid taper
        2. Left CPW section (constant 100 µm width)
        3. Right CPW section (constant 100 µm width)
        4. Right 50 µm rapid taper and pad
        5. Ground plane (fills remaining area with subtractions)
        6. Optional text label at top of chip
        
        Args:
            chip_name: cell name for chip
            config: design configuration
            label: Optional text label to display at top of chip (e.g., "40 um")
        
        Returns:
            pya.Cell object
        """
        if config is None:
            config = self.config
        
        # Store label for use in ground plane creation
        self._current_label = label
        self._label_clearance_region = None
        self._electroplating_signal_clearance = None
        
        # Create cell
        chip_cell = self.layout.create_cell(chip_name)
        
        # Chip center
        chip_center_x = config.chip_width / 2.0
        chip_center_y = config.chip_height / 2.0
        
        # Left and right pad positions
        left_pad_x = config.edge_buffer
        right_pad_x = config.chip_width - config.edge_buffer - config.pad_width
        pad_y_center = chip_center_y
        
        # 1. Create left bond pad
        self.create_bond_pad(chip_cell, left_pad_x, pad_y_center,
                            config.pad_width, config.pad_height, config)
        
        # 2. Create right bond pad
        self.create_bond_pad(chip_cell, right_pad_x, pad_y_center,
                            config.pad_width, config.pad_height, config)
        
        # 3. Create left rapid taper (pad → CPW)
        # Taper from pad width to CPW signal width over 50 µm
        left_taper_start_x = left_pad_x + config.pad_width
        left_taper_end_x = left_taper_start_x + config.taper_length
        
        self.create_tapered_trace(chip_cell, left_taper_start_x, pad_y_center,
                                 config.taper_length, config.pad_height,
                                 config.cpw_signal_width, config)
        
        # 4. Create left CPW section (constant 100 µm width, pad→aperture boundary)
        left_cpw_start_x = left_taper_end_x
        left_cpw_end_x = chip_center_x - config.aperture_radius
        
        if left_cpw_end_x > left_cpw_start_x:
            left_cpw_length = left_cpw_end_x - left_cpw_start_x
            # Create CPW as constant-width rectangle
            left_cpw_box = pya.Box(
                self._um_to_dbu(left_cpw_start_x),
                self._um_to_dbu(pad_y_center - config.cpw_signal_width / 2.0),
                self._um_to_dbu(left_cpw_end_x),
                self._um_to_dbu(pad_y_center + config.cpw_signal_width / 2.0)
            )
            left_cpw_region = pya.Region(left_cpw_box)
            chip_cell.shapes(self.layout.layer(config.METAL_LAYER)).insert(left_cpw_region)
        
        # 5. Create right CPW section (aperture boundary → before right taper)
        right_cpw_start_x = chip_center_x + config.aperture_radius
        right_taper_start_x = right_pad_x - config.taper_length  # Taper starts 50 µm before pad
        right_cpw_end_x = right_taper_start_x
        
        if right_cpw_end_x > right_cpw_start_x:
            # Create CPW as constant-width rectangle
            right_cpw_box = pya.Box(
                self._um_to_dbu(right_cpw_start_x),
                self._um_to_dbu(pad_y_center - config.cpw_signal_width / 2.0),
                self._um_to_dbu(right_cpw_end_x),
                self._um_to_dbu(pad_y_center + config.cpw_signal_width / 2.0)
            )
            right_cpw_region = pya.Region(right_cpw_box)
            chip_cell.shapes(self.layout.layer(config.METAL_LAYER)).insert(right_cpw_region)
        
        # 6. Create right rapid taper (CPW → pad)
        # Taper from CPW signal width to pad width over 50 µm
        self.create_tapered_trace(chip_cell, right_taper_start_x, pad_y_center,
                                 config.taper_length, config.cpw_signal_width,
                                 config.pad_height, config)
        
        # 7. Create DC bond pad arrays (top and bottom)
        self.create_dc_pad_array(chip_cell, config.dc_pad_y_offset, config)   # Top array
        self.create_dc_pad_array(chip_cell, -config.dc_pad_y_offset, config)  # Bottom array
        
        # 8. Create alignment crosses at four diagonal positions
        cross_offset = config.cross_offset
        self.create_alignment_cross(chip_cell, chip_center_x - cross_offset, chip_center_y + cross_offset, config)  # Top-left
        self.create_alignment_cross(chip_cell, chip_center_x + cross_offset, chip_center_y + cross_offset, config)  # Top-right
        self.create_alignment_cross(chip_cell, chip_center_x - cross_offset, chip_center_y - cross_offset, config)  # Bottom-left
        self.create_alignment_cross(chip_cell, chip_center_x + cross_offset, chip_center_y - cross_offset, config)  # Bottom-right
        
        # 8.5. Create electroplating signal tab if enabled (before ground plane)
        if config.electroplating:
            self._electroplating_signal_clearance = self.create_electroplating_signal_tab(
                chip_cell, left_pad_x, pad_y_center, config
            )
        
        # 9. Create ground plane
        # Ground fills entire chip except signal traces and aperture
        self.create_ground_plane_with_traces(chip_cell, left_pad_x, right_pad_x,
                                            pad_y_center, left_taper_end_x,
                                            right_taper_start_x, config)
        
        # 9.5. Handle electroplating: subtract signal tab clearance from ground, add ground tabs
        if config.electroplating and self._electroplating_signal_clearance is not None:
            layer_idx = self.layout.layer(config.METAL_LAYER)
            shapes = chip_cell.shapes(layer_idx)
            
            # Get all shapes as region
            all_shapes_region = pya.Region(shapes)
            
            # Subtract the signal tab clearance (this cuts the gap in ground plane)
            all_shapes_region -= self._electroplating_signal_clearance
            
            # Clear and reinsert modified shapes
            shapes.clear()
            shapes.insert(all_shapes_region)
            
            # Re-add the signal tab (it was removed by the clear)
            tab_width = config.electroplating_tab_width
            signal_tab = pya.Box(
                self._um_to_dbu(0),
                self._um_to_dbu(pad_y_center - tab_width / 2.0),
                self._um_to_dbu(left_pad_x),
                self._um_to_dbu(pad_y_center + tab_width / 2.0)
            )
            shapes.insert(signal_tab)
            
            # Add ground tabs
            self.create_electroplating_ground_tabs(chip_cell, config)
        
        # 10. Create text label if provided (subtract clearance from ground, then add text)
        if self._current_label:
            text_x = chip_center_x
            text_y = chip_center_y + config.text_label_y_offset
            
            # First, create clearance region without inserting text yet
            label_clearance_region = self._create_text_clearance_region(
                self._current_label, text_x, text_y,
                height=config.text_label_height,
                clearance=config.text_label_clearance,
                config=config
            )
            
            # Subtract text clearance from ground plane
            layer_idx = self.layout.layer(config.METAL_LAYER)
            shapes = chip_cell.shapes(layer_idx)
            ground_region = pya.Region(shapes)
            ground_region -= label_clearance_region
            shapes.clear()
            shapes.insert(ground_region)
            
            # Now add the text on top of the cleared area
            self.add_text_label(
                chip_cell, self._current_label, text_x, text_y,
                height=config.text_label_height,
                clearance=config.text_label_clearance,
                config=config
            )
        
        return chip_cell
    
    def generate_design(self, output_dir=None):
        """
        Generate complete design and export to GDS files.
        
        Outputs:
        - _inspect.gds: hierarchical (with cell references)
        - _prod.gds: flattened (all geometry merged, ready for fabrication)
        
        Args:
            output_dir: directory for output files (default: script_location/output)
        """
        # Create output directory if needed (relative to script location)
        if output_dir is None:
            output_dir = Path(__file__).parent / "output"
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Get the current script filename (without extension)
        script_name = Path(__file__).stem
        
        # Create chip
        chip = self.create_chip()
        
        # Export hierarchical version (inspect)
        inspect_path = os.path.join(output_dir, f"{script_name}_inspect.gds")
        self.layout.write(inspect_path)
        print(f"✓ Hierarchical design exported: {inspect_path}")
        
        # Flatten and export production version
        # Flatten: convert all instances to merged polygons
        for cell in self.layout.each_cell():
            cell.flatten(True)  # Recursive, including instances
        
        # Merge all shapes in each cell and resolve arrays
        for cell in self.layout.each_cell():
            # Resolve all instances (convert references to actual geometry)
            for layer_info in self.layout.layer_indices():
                shapes = cell.shapes(layer_info)
                if len(shapes) > 0:
                    # Merge all shapes on this layer
                    region = pya.Region(shapes)
                    region.merge()
                    # Clear and re-insert merged shapes
                    shapes.clear()
                    shapes.insert(region)
        
        prod_path = os.path.join(output_dir, f"{script_name}_prod.gds")
        self.layout.write(prod_path)
        print(f"✓ Flattened production design exported: {prod_path}")
        
        return inspect_path, prod_path


def create_chip_cell(layout, config=None, chip_name="chip_6x6mm", label=None):
    """
    Create a chip cell and insert it into an existing layout.
    
    This is the main entry point for using this module from other scripts.
    The chip is created at origin (0, 0) and can be placed/arrayed by the caller.
    
    Args:
        layout: pya.Layout object to insert the chip cell into
        config: DesignConfig instance or None to use defaults
        chip_name: Name for the chip cell
        label: Optional text label to display at top of chip (e.g., "40 um")
    
    Returns:
        pya.Cell: The created chip cell (already added to layout)
    
    Example:
        import klayout.db as pya
        from 6x6mm_sample_chip_V1 import create_chip_cell, DesignConfig
        
        layout = pya.Layout()
        layout.dbu = 0.01
        
        # Use default config
        chip_cell = create_chip_cell(layout)
        
        # Or with custom config and label
        custom_config = DesignConfig()
        custom_config.aperture_radius = 500.0
        chip_cell = create_chip_cell(layout, config=custom_config, label="50 um")
    """
    designer = ChipDesigner(config=config, layout=layout)
    return designer.create_chip(chip_name=chip_name, label=label)


def main():
    """Entry point: generate design with default configuration."""
    print("=" * 70)
    print("KLayout Chip Design Generator - CPW with Bond Pads")
    print("=" * 70)
    print()
    
    # Print configuration summary
    config = DesignConfig()
    print("Design Configuration:")
    print(f"  Chip size:           {config.chip_width:.0f} µm × {config.chip_height:.0f} µm")
    print(f"  Edge buffer:         {config.edge_buffer:.0f} µm")
    print(f"  CPW signal width:    {config.cpw_signal_width:.0f} µm")
    print(f"  CPW gap:             {config.cpw_gap:.0f} µm (→ 50 Ω impedance)")
    print(f"  Bond pad:            {config.pad_width:.0f} µm W × {config.pad_height:.0f} µm H")
    print(f"  Taper length:        {config.taper_length:.0f} µm")
    print(f"  Aperture radius:     {config.aperture_radius:.0f} µm")
    print(f"  Pad-ground clearance: {config.pad_to_ground_clearance:.0f} µm")
    print()
    
    # Generate design
    designer = ChipDesigner(config=config)
    inspect_file, prod_file = designer.generate_design()
    
    print()
    print("Design generation complete!")
    print("Next steps:")
    print("  1. Open inspect file in KLayout: File → Open → " + inspect_file)
    print("  2. Visually verify all geometry (pads, traces, ground plane)")
    print("  3. Measure critical dimensions (Tools → Measure)")
    print("  4. Verify no signal-ground shorts and clearances are correct")
    print("  5. Confirm prod file contains only polygons (no cell references)")
    print()


if __name__ == "__main__":
    main()
