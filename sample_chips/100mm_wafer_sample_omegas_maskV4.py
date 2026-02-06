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
from typing import Optional, Tuple, List, Dict
from datetime import date


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
    """Per-chip design parameters."""
    # Chip dimensions
    chip_width: float = 6000.0      # µm
    chip_height: float = 6000.0     # µm
    
    # Dicing lane (exposed for gold removal)
    dicing_margin: float = 100.0    # µm - no gold in this region
    
    # RF Bond pads
    rf_pad_width: float = 400.0     # µm
    rf_pad_height: float = 800.0    # µm
    rf_pad_clearance: float = 50.0  # µm from ground plane
    edge_buffer: float = 200.0      # µm from chip edge to RF pad
    
    # CPW transmission line
    cpw_signal_width: float = 100.0 # µm
    cpw_gap: float = 50.0           # µm (each side)
    cpw_taper_length: float = 50.0  # µm
    
    # Central aperture (will be overridden per variant)
    aperture_radius: float = 300.0  # µm
    
    # DC contact pads (larger than V3)
    dc_pad_size: float = 100.0      # µm × µm square
    dc_pad_spacing: float = 150.0   # µm center-to-center
    dc_pad_count: int = 8           # number of DC pads per array
    dc_pad_y_offset: float = 1500.0 # µm from chip center
    
    # PRT parameters
    prt_pad_size: float = 200.0     # µm × µm square (was 125 µm)
    prt_trace_width: float = 10.0   # µm
    prt_trace_gap: float = 20.0     # µm centerline-to-centerline
    prt_y_offset: float = 2000.0    # µm from chip center


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
    """Collection of chip variants for the mask."""
    # Default variants: parameter sweep
    variants: List[OmegaVariant] = field(default_factory=lambda: [
        OmegaVariant("omega_60um",  center_radius=30,  trace_width=10.0, aperture_radius=250),
        OmegaVariant("omega_100um", center_radius=50,  trace_width=10.0, aperture_radius=300),
        OmegaVariant("omega_150um", center_radius=75,  trace_width=12.5, aperture_radius=350),
        OmegaVariant("omega_200um", center_radius=100, trace_width=15.0, aperture_radius=450),
        OmegaVariant("omega_250um", center_radius=125, trace_width=20.0, aperture_radius=600),
        OmegaVariant("blank",       center_radius=0,   trace_width=0,    aperture_radius=300),
    ])
    
    # Unit cell arrangement (2 columns × 3 rows)
    unit_cell_cols: int = 2
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
        """Create a single chip cell for a given variant."""
        # TODO: Implement chip cell creation
        pass
    
    def create_unit_cell(self) -> pya.Cell:
        """Create unit cell containing all chip variants."""
        # TODO: Implement unit cell
        pass
    
    def create_chip_array(self, cell: pya.Cell) -> int:
        """
        Place chips across usable wafer area.
        
        Returns:
            Number of chips placed
        """
        # TODO: Implement chip array placement
        pass
    
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
        """Create alignment marks at mask corners and in dicing lanes."""
        # TODO: Implement alignment marks
        pass
    
    def create_mask_labels(self, cell: pya.Cell) -> None:
        """Create text labels for mask identification."""
        # TODO: Implement mask labels
        pass
    
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
        self.create_mask_labels(mask_cell)
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Export files
        output_files = {}
        
        # Hierarchical (inspect) GDS
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
        
        # Flattened (prod) GDS
        prod_path = os.path.join(output_dir, "100mm_wafer_sample_omegas_maskV4_prod.gds")
        mask_cell.flatten(True)
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
