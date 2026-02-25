"""
100mm Wafer Mask Design - Version 4

V4 Design Architecture:
-----------------------
Two-layer system for 5"×5" mask plate with 4" wafer.

Layer 1/0 (Gold) - Negative Resist:
  - CPW signal lines and RF bond pads
  - Ground plane (drawn as "keep" regions)
  - DC contact pads (larger, more separated than V3)
  - Alignment marks (kept in dicing lanes)
  - Dicing lanes are EXPOSED (no gold between chips)

Layer 2/0 (Platinum) - Positive Resist:
  - PRT serpentine thermometer
  - PRT bond pads (larger than V3, further from DC contacts)
  - Ground plane separation between PRT and DC regions

Key V4 Changes from V3:
  - Negative resist for gold layer (exposure = no gold)
  - Dicing lanes exposed (alignment marks only)
  - DC pads: 100 × 100 µm, 150 µm center spacing
  - PRT pads: 200 × 200 µm (was 125 µm)
  - Clean modular architecture

Author: Jeff Ahlers
Date: 2026-02-05
"""

import klayout.db as pya
import math
import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict

# Import chip designer from the single-chip module
from importlib.util import spec_from_file_location, module_from_spec
_chip_spec = spec_from_file_location(
    "chip_v4",
    os.path.join(os.path.dirname(__file__), "5x5mm_sample_chip_V4.py")
)
_chip_mod = module_from_spec(_chip_spec)
_chip_spec.loader.exec_module(_chip_mod)
ChipDesigner = _chip_mod.ChipDesigner
GoldLayerConfig = _chip_mod.GoldLayerConfig


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
    
    # Layer names for GDS embedding and properties files
    LAYER_NAMES = {
        (1, 0): "gold",
        (2, 0): "platinum",
    }
    
    # Layer colors for .lyp file (AARRGGBB format)
    LAYER_COLORS = {
        (1, 0): "#80ffd700",   # Gold with transparency
        (2, 0): "#80c0c0c0",   # Platinum/silver with transparency
    }


@dataclass
class WaferConfig:
    """Wafer and mask plate dimensions."""
    # Mask plate (5" × 5")
    mask_width: float = 127000.0    # µm (5 inches)
    mask_height: float = 127000.0   # µm (5 inches)
    
    # Wafer dimensions (4" / 100mm)
    wafer_diameter: float = 100000.0  # µm
    wafer_flat_depth: float = 2500.0  # µm (SEMI standard for 100mm)
    
    # Usable area buffer from wafer edge
    edge_buffer: float = 3000.0     # µm
    
    # Database unit
    dbu: float = 0.001              # µm per database unit


@dataclass
class ChipConfig:
    """Per-chip dimensions used for array tiling."""
    chip_width: float = 5000.0      # µm
    chip_height: float = 5000.0     # µm


@dataclass
class OmegaVariant:
    """Parameters for a single omega resonator variant."""
    name: str
    center_radius: float            # µm
    trace_width: float              # µm
    aperture_radius: float          # µm
    trace_gap: float = 15.0         # µm between omega rings


@dataclass
class ChipVariants:
    """Collection of chip variants for the mask (3×3 unit cell)."""
    # 9 variants for 3×3 grid: no_omega, then increasing diameters
    # Row-major order: bottom-left → bottom-right, middle-left → middle-right, etc.
    variants: List[OmegaVariant] = field(default_factory=lambda: [
        # Bottom row (row 0)
        OmegaVariant("no_omega",    center_radius=0,    trace_width=0,    aperture_radius=200),
        OmegaVariant("omega_30um",  center_radius=15,   trace_width=5.0,  aperture_radius=200, trace_gap=7),
        OmegaVariant("omega_60um",  center_radius=30,   trace_width=7.0,  aperture_radius=250, trace_gap=10),
        # Middle row (row 1)
        OmegaVariant("omega_80um",  center_radius=40,   trace_width=8.0,  aperture_radius=280, trace_gap=12.5),
        OmegaVariant("omega_100um", center_radius=50,   trace_width=8.0, aperture_radius=300, trace_gap=15),
        OmegaVariant("omega_125um", center_radius=62.5,  trace_width=12, aperture_radius=350, trace_gap=25),
        # Top row (row 2)
        OmegaVariant("omega_150um", center_radius=75,   trace_width=12.0, aperture_radius=400, trace_gap=30),
        OmegaVariant("omega_200um", center_radius=100,  trace_width=12.0, aperture_radius=450, trace_gap=40),
        OmegaVariant("omega_250um", center_radius=125,  trace_width=15.0, aperture_radius=500, trace_gap=45),
    ])
    
    # Unit cell arrangement (3 columns × 3 rows)
    unit_cell_cols: int = 3
    unit_cell_rows: int = 3


# =============================================================================
# MASK DESIGNER CLASS
# =============================================================================

class MaskDesigner:
    """
    V4 Mask Designer for 100mm wafer on 5"×5" mask plate.
    
    Generates two-layer mask design:
      - Gold (1/0): CPW, ground plane, DC contacts (negative resist)
      - Platinum (2/0): PRT thermometer (positive resist)
      
    Key features:
      - Dicing lanes exposed (no gold except alignment marks)
      - Chip array within usable wafer area
      - Parameter sweep via chip variants
    """
    
    def __init__(self,
                 wafer_config: Optional[WaferConfig] = None,
                 chip_config: Optional[ChipConfig] = None,
                 chip_variants: Optional[ChipVariants] = None,
                 layer_config: Optional[LayerConfig] = None):
        """Initialize mask designer with configuration."""
        self.wafer = wafer_config or WaferConfig()
        self.chip = chip_config or ChipConfig()
        self.variants = chip_variants or ChipVariants()
        self.layers = layer_config or LayerConfig()
        
        # Layout will be created in generate()
        self.layout: Optional[pya.Layout] = None
        self.gold_layer_idx: Optional[int] = None
        self.platinum_layer_idx: Optional[int] = None
    
    def _um_to_dbu(self, um: float) -> int:
        """Convert micrometers to database units."""
        return int(round(um / self.wafer.dbu))
    
    # -------------------------------------------------------------------------
    # WAFER & MASK GEOMETRY
    # -------------------------------------------------------------------------
    
    def create_wafer_outline(self, cell: pya.Cell) -> None:
        """Create wafer outline with flat for alignment reference."""
        # TODO: Implement wafer outline
        pass
    
    def create_mask_plate_outline(self, cell: pya.Cell) -> None:
        """Create 5"×5" mask plate border."""
        # TODO: Implement mask plate outline
        pass
    
    # -------------------------------------------------------------------------
    # CHIP ARRAY
    # -------------------------------------------------------------------------
    
    def create_chip_cell(self, variant: OmegaVariant) -> pya.Cell:
        """
        Create a single chip cell for a given omega variant.
        
        Uses ChipDesigner from 6x6mm_sample_chip_V4 with overridden omega
        and aperture parameters. The chip origin is at (0, 0).
        
        Args:
            variant: OmegaVariant with omega radius, trace width, aperture radius
            
        Returns:
            pya.Cell containing the complete chip design
        """
        # Build gold config with variant-specific overrides
        gold_cfg = GoldLayerConfig(
            omega_center_radius=variant.center_radius,
            omega_trace_width=variant.trace_width,
            aperture_radius=variant.aperture_radius,
            omega_trace_gap=variant.trace_gap,
        )
        
        # For no-omega variant, set omega count to 0
        if variant.center_radius == 0:
            gold_cfg.omega_count = 0
        
        # Create chip designer sharing this layout's layout object
        designer = ChipDesigner(
            gold_config=gold_cfg,
        )
        designer.layout = self.layout
        designer.gold_layer_idx = self.gold_layer_idx
        designer.platinum_layer_idx = self.platinum_layer_idx
        
        # Generate chip cell
        chip_cell = designer.create_chip(name=variant.name)
        return chip_cell
    
    def create_unit_cell(self) -> pya.Cell:
        """
        Create 3×3 unit cell containing all 9 chip variants.
        
        Chips are arranged in a grid centered at (0, 0).
        Row-major order: variants[0..2] = bottom row, [3..5] = middle, [6..8] = top.
        
        Returns:
            pya.Cell containing 3×3 arrangement of chip variants
        """
        unit_cell = self.layout.create_cell("unit_cell_3x3")
        
        cw = self.chip.chip_width
        ch = self.chip.chip_height
        cols = self.variants.unit_cell_cols
        rows = self.variants.unit_cell_rows
        
        # Total unit cell extent
        total_w = cols * cw
        total_h = rows * ch
        
        for idx, variant in enumerate(self.variants.variants):
            col = idx % cols
            row = idx // cols
            
            # Chip lower-left corner (centered about 0,0)
            x = -total_w / 2.0 + col * cw
            y = -total_h / 2.0 + row * ch
            
            chip_cell = self.create_chip_cell(variant)
            
            # Place as cell instance with translation
            trans = pya.CellInstArray(
                chip_cell.cell_index(),
                pya.Trans(pya.Point(self._um_to_dbu(x), self._um_to_dbu(y)))
            )
            unit_cell.insert(trans)
            print(f"    [{col},{row}] {variant.name} (d={2*variant.center_radius:.0f} µm)")
        
        return unit_cell
    
    def create_chip_array(self, cell: pya.Cell) -> int:
        """
        Tile the 3×3 unit cell across a 100 mm × 100 mm area centered at (0, 0).
        
        The unit cell is repeated in a regular grid. Only complete unit cells
        that fit within the 100 mm square are placed.
        
        Args:
            cell: Top-level mask cell to insert instances into
            
        Returns:
            Total number of individual chips placed
        """
        unit_cell = self.create_unit_cell()
        
        cw = self.chip.chip_width
        ch = self.chip.chip_height
        cols = self.variants.unit_cell_cols
        rows = self.variants.unit_cell_rows
        
        # Unit cell pitch
        uc_w = cols * cw  # 3 × 5000 = 15000 µm
        uc_h = rows * ch  # 3 × 5000 = 15000 µm
        
        # Array area (100 mm × 100 mm)
        array_size = 100000.0  # µm
        
        # Number of unit cell repetitions in each direction
        n_x = int(array_size // uc_w)
        n_y = int(array_size // uc_h)
        
        # Centering offset so the array is centered at (0, 0)
        # Unit cell positions: origin, origin+uc_w, ... origin+(n-1)*uc_w
        # For symmetry about 0: origin = -(n-1)*uc_w/2
        origin_x = -((n_x - 1) * uc_w) / 2.0
        origin_y = -((n_y - 1) * uc_h) / 2.0
        
        chip_count = 0
        for ix in range(n_x):
            for iy in range(n_y):
                x = origin_x + ix * uc_w
                y = origin_y + iy * uc_h
                
                trans = pya.CellInstArray(
                    unit_cell.cell_index(),
                    pya.Trans(pya.Point(self._um_to_dbu(x), self._um_to_dbu(y)))
                )
                cell.insert(trans)
                chip_count += cols * rows
        
        print(f"  Unit cell: {uc_w/1000:.0f} × {uc_h/1000:.0f} mm ({cols}×{rows} chips)")
        print(f"  Array: {n_x} × {n_y} unit cells = {n_x * n_y} unit cells")
        
        return chip_count
    
    # -------------------------------------------------------------------------
    # DICING LANES & ALIGNMENT
    # -------------------------------------------------------------------------
    
    def create_dicing_lanes(self, cell: pya.Cell) -> None:
        """
        Create dicing lanes between chips.
        
        For V4 (negative resist gold layer):
          - Dicing lanes are EXPOSED (no gold)
          - Only alignment marks are kept in dicing lanes
        """
        # TODO: Implement dicing lanes
        pass
    
    def create_alignment_marks(self, cell: pya.Cell) -> None:
        """Create alignment marks at every chip junction in the tiled array.
        
        Marks are placed at every intersection of the chip grid lines,
        including the outermost edges.  This means for an array of
        n_x × n_y chips there are (n_x+1) × (n_y+1) junction points.
        
        Each mark is a simple cross: two perpendicular bars.
        """
        cw = self.chip.chip_width
        ch = self.chip.chip_height
        cols = self.variants.unit_cell_cols
        rows = self.variants.unit_cell_rows
        uc_w = cols * cw
        uc_h = rows * ch

        array_size = 100000.0
        n_uc_x = int(array_size // uc_w)
        n_uc_y = int(array_size // uc_h)

        # Total chips in each direction
        total_cols = n_uc_x * cols  # 5 × 3 = 15
        total_rows = n_uc_y * rows  # 5 × 3 = 15

        # Array origin (lower-left chip corner, matching create_chip_array)
        uc_origin_x = -((n_uc_x - 1) * uc_w) / 2.0
        uc_origin_y = -((n_uc_y - 1) * uc_h) / 2.0
        # Unit cell is internally centered, so chips start at -total_uc/2
        array_left = uc_origin_x - uc_w / 2.0
        array_bottom = uc_origin_y - uc_h / 2.0

        # Cross dimensions
        arm_length = 200.0   # µm half-length of each arm
        arm_width = 20.0     # µm width of each arm

        # Create a reusable cross cell
        cross_cell = self.layout.create_cell("align_cross")
        h_bar = pya.Box(
            self._um_to_dbu(-arm_length), self._um_to_dbu(-arm_width / 2.0),
            self._um_to_dbu(arm_length),  self._um_to_dbu(arm_width / 2.0),
        )
        v_bar = pya.Box(
            self._um_to_dbu(-arm_width / 2.0), self._um_to_dbu(-arm_length),
            self._um_to_dbu(arm_width / 2.0),  self._um_to_dbu(arm_length),
        )
        cross_cell.shapes(self.gold_layer_idx).insert(h_bar)
        cross_cell.shapes(self.gold_layer_idx).insert(v_bar)

        mark_count = 0
        # Junction points: (total_cols + 1) × (total_rows + 1)
        for ix in range(total_cols + 1):
            for iy in range(total_rows + 1):
                x = array_left + ix * cw
                y = array_bottom + iy * ch
                trans = pya.CellInstArray(
                    cross_cell.cell_index(),
                    pya.Trans(pya.Point(self._um_to_dbu(x), self._um_to_dbu(y)))
                )
                cell.insert(trans)
                mark_count += 1

        print(f"  Placed {mark_count} alignment crosses at chip junctions")

    def _make_wafer_region(self, radius_um: float, flat_depth_um: float,
                           num_segments: int = 256) -> pya.Region:
        """Create a circle region with a wafer flat at the bottom.
        
        The flat is a horizontal chord at y = -(radius - flat_depth).
        Built by intersecting a full circle with a clipping box whose
        bottom edge sits at the flat line.
        
        Args:
            radius_um: Circle radius in µm
            flat_depth_um: Depth of the flat from the circle edge in µm
            num_segments: Number of polygon segments for the circle
            
        Returns:
            pya.Region of the circle with flat
        """
        # Full circle
        pts = []
        for i in range(num_segments):
            angle = 2.0 * math.pi * i / num_segments
            pts.append(pya.Point(
                self._um_to_dbu(radius_um * math.cos(angle)),
                self._um_to_dbu(radius_um * math.sin(angle)),
            ))
        circle_region = pya.Region(pya.Polygon(pts))
        
        # Clip box: everything above the flat line
        flat_y = -(radius_um - flat_depth_um)
        margin = radius_um + 1000.0  # generous overshoot
        clip_box = pya.Box(
            self._um_to_dbu(-margin),
            self._um_to_dbu(flat_y),
            self._um_to_dbu(margin),
            self._um_to_dbu(margin),
        )
        return circle_region & pya.Region(clip_box)

    def clip_to_radius(self, cell: pya.Cell, radius_um: float) -> None:
        """Clip all gold and platinum features to a wafer-shaped region.
        
        Uses a circle of the given radius with a standard wafer flat at
        the bottom.  Iterates through the cell hierarchy using
        RecursiveShapeIterator, boolean-ANDs each layer with the clip
        shape, clears the cell, and re-inserts the clipped geometry.
        
        Args:
            cell: Top-level cell to clip
            radius_um: Clip circle radius in µm
        """
        clip_region = self._make_wafer_region(
            radius_um, self.wafer.wafer_flat_depth)
        
        # Clip each active layer by gathering all shapes recursively
        layers_to_clip = [self.gold_layer_idx, self.platinum_layer_idx]
        clipped_regions = {}
        for layer_idx in layers_to_clip:
            layer_region = pya.Region(cell.begin_shapes_rec(layer_idx))
            clipped_regions[layer_idx] = layer_region & clip_region
        
        # Clear all instances and shapes, then re-insert clipped geometry
        cell.clear()
        for layer_idx, region in clipped_regions.items():
            cell.shapes(layer_idx).insert(region)

    def create_gold_ring(self, cell: pya.Cell) -> None:
        """Create a gold annular ring with wafer flat (96–101 mm diameter).
        
        Both the inner and outer boundaries include a standard wafer flat
        at the bottom, matching the clip shape.  The flat depth is taken
        from WaferConfig so all wafer-shaped features are consistent.
        """
        inner_r = 96000.0 / 2   # µm  (48 mm radius)
        outer_r = 101000.0 / 2  # µm  (50.5 mm radius)
        flat_depth = self.wafer.wafer_flat_depth  # 2500 µm
        
        outer_shape = self._make_wafer_region(outer_r, flat_depth)
        inner_shape = self._make_wafer_region(inner_r, flat_depth)
        
        ring_region = outer_shape - inner_shape
        cell.shapes(self.gold_layer_idx).insert(ring_region)

    def create_mask_labels(self, cell: pya.Cell) -> None:
        """Create text labels for mask identification on both layers.
        
        Labels are placed outside the wafer clip area on the mask plate
        so they don't merge with chip geometry.
        
        Gold layer text (bottom-left):
            5x5 Sample Chips V4
            Gold Electroplating Mask
            Negative PR
            Layer 1 of 2
            
        Platinum layer text (bottom-right):
            5x5 Sample Chips V4
            Pt Thermometer
            Positive PR
            Layer 2 of 2
        
        Gold labels placed bottom-left, platinum labels bottom-right,
        both outside the wafer clip area but on the mask plate.
        """
        gen = pya.TextGenerator.default_generator()
        target_height = 1100.0   # µm character height
        line_spacing = 1000.0    # µm between baselines
        bold_size = 8.0         # µm sizing for bold
        dbu = self.layout.dbu

        def _place_text_block(lines: list[str], layer_idx: int,
                              anchor_x: float, anchor_y: float) -> None:
            """Render multi-line text block as bold polygons."""
            for i, line in enumerate(lines):
                y_offset = anchor_y - i * line_spacing
                text_region = gen.text(line, dbu, target_height)
                text_region = text_region.sized(int(bold_size / dbu))
                text_region.move(int(anchor_x / dbu), int(y_offset / dbu))
                cell.shapes(layer_idx).insert(text_region)

        # Gold layer labels (bottom-left, outside wafer area)
        gold_lines = [
            "5x5 Sample Chips V4",
            "Gold Electroplating Mask",
            "Negative PR",
            "Layer 1 of 2",
        ]
        _place_text_block(gold_lines, self.gold_layer_idx,
                          anchor_x=-23000, anchor_y=52000.0)

        # Platinum layer labels (bottom-right, outside wafer area)
        pt_lines = [
            "5x5 Sample Chips V4",
            "Pt Thermometer",
            "Positive PR",
            "Layer 2 of 2",
        ]
        _place_text_block(pt_lines, self.platinum_layer_idx,
                          anchor_x=22000.0, anchor_y=52000.0)
    
    # -------------------------------------------------------------------------
    # OUTPUT GENERATION
    # -------------------------------------------------------------------------
    
    def export_layer_properties(self, output_dir: str) -> str:
        """Export .lyp layer properties file for KLayout."""
        # TODO: Implement layer properties export
        pass
    
    def export_layer_map(self, output_dir: str) -> str:
        """Export .map layer mapping file."""
        # TODO: Implement layer map export
        pass
    
    # -------------------------------------------------------------------------
    # MAIN GENERATION
    # -------------------------------------------------------------------------
    
    def generate(self, output_dir: str = "output") -> Dict[str, str]:
        """
        Generate complete mask design and export all files.
        
        Args:
            output_dir: Directory for output files
            
        Returns:
            Dictionary of output file paths
        """
        print("=" * 70)
        print("100mm Wafer Mask V4 - Two-Layer Design")
        print("=" * 70)
        print()
        print("Configuration:")
        print(f"  Mask plate:     {self.wafer.mask_width/1000:.0f} mm × {self.wafer.mask_height/1000:.0f} mm")
        print(f"  Wafer diameter: {self.wafer.wafer_diameter/1000:.0f} mm")
        print(f"  Chip size:      {self.chip.chip_width:.0f} × {self.chip.chip_height:.0f} µm")
        print(f"  Variants:       {len(self.variants.variants)}")
        print()
        
        # Create layout
        self.layout = pya.Layout()
        self.layout.dbu = self.wafer.dbu
        
        # Register layers
        self.gold_layer_idx = self.layout.layer(self.layers.GOLD)
        self.platinum_layer_idx = self.layout.layer(self.layers.PLATINUM)
        
        # Create top-level cell
        mask_cell = self.layout.create_cell("mask_V4")
        
        # Build mask components
        print("Creating mask layout...")
        self.create_mask_plate_outline(mask_cell)
        self.create_wafer_outline(mask_cell)
        
        print("Creating chip array...")
        chip_count = self.create_chip_array(mask_cell)
        print(f"  Placed {chip_count} chips")
        
        print("Creating dicing lanes and alignment marks...")
        self.create_dicing_lanes(mask_cell)
        self.create_alignment_marks(mask_cell)
        
        # Clip all features to 96 mm radius (flattens the cell)
        print("Clipping features to 96 mm radius...")
        self.clip_to_radius(mask_cell, 96000.0/2)
        
        # Add gold ring AFTER clipping so it is not clipped
        print("Creating gold ring (96–101 mm)...")
        self.create_gold_ring(mask_cell)
        
        # Add labels AFTER clipping so they aren't merged into chip geometry
        print("Creating mask labels...")
        self.create_mask_labels(mask_cell)
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Export files
        output_files = {}
        
        # Inspect GDS (already flattened by clip_to_radius)
        inspect_path = os.path.join(output_dir, "100mm_wafer_sample_omegas_maskV4_inspect.gds")
        self.layout.write(inspect_path)
        output_files["inspect"] = inspect_path
        print(f"✓ Hierarchical design: {inspect_path}")
        
        # Layer properties file
        lyp_path = self.export_layer_properties(output_dir)
        if lyp_path:
            output_files["lyp"] = lyp_path
            print(f"✓ Layer properties: {lyp_path}")
        
        # Layer map file
        map_path = self.export_layer_map(output_dir)
        if map_path:
            output_files["map"] = map_path
            print(f"✓ Layer map: {map_path}")
        
        # Production GDS (cell is already flat from clip step)
        prod_path = os.path.join(output_dir, "100mm_wafer_sample_omegas_maskV4_prod.gds")
        self.layout.write(prod_path)
        output_files["prod"] = prod_path
        print(f"✓ Production design: {prod_path}")
        
        print()
        print("Mask generation complete!")
        print()
        print("V4 Design Notes:")
        print("  - Gold layer uses NEGATIVE resist (exposure = no gold)")
        print("  - Dicing lanes are exposed (no gold between chips)")
        print("  - Alignment marks are kept in dicing lanes")
        print("  - DC pads are larger and more separated")
        print("  - PRT pads are larger and further from DC contacts")
        
        return output_files


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Generate V4 mask design."""
    # Create designer with default configuration
    designer = MaskDesigner()
    
    # Generate design
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    designer.generate(output_dir)


if __name__ == "__main__":
    main()
