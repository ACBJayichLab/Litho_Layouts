# Copilot Instructions for KLayout Lithographic Design

## Project Overview
This is a **professional KLayout-based lithographic design repository** for creating high-accuracy photoresist mask patterns and integrated circuit layouts. The workspace is a **generalized KLayout design environment** supporting various RF/microwave circuit topologies (primarily microwave omega circuits, but extensible to arbitrary component designs). All designs prioritize **geometric precision, consistency, and reusability**. The GDS II files are production-ready outputs for photolithography fabrication on sapphire, silicon, and other substrates.

## KLayout Workflow & Setup

### Essential Context
- **Design Tool:** KLayout (https://www.klayout.de/) - open-source layout viewer/editor with robust Python API
- **Format:** GDS II (Graphic Database System) - industry-standard binary layout format
- **Python Scripting:** Designs are generated via Python scripts using KLayout's `klayout.db` module for full parametric control
- **Substrates:** Sapphire, silicon, diamond, quartz (100 mm wafers primary; scalable to other formats)
- **Key Principle:** All designs are **parametric, documented, and geometrically validated** before export

### File Naming & Version Control
All designs follow strict naming conventions:
- `V#` suffix (e.g., `V3`) indicates design iteration; increment when geometry changes
- `_inspect.gds` = hierarchical design (with cell references) for review and verification
- `_prod.gds` = flattened production version (all geometry merged) ready for fabrication tool
- `_dose.gds` = small single-unit test variant for lithography/parameter exploration
- Always maintain inspect/prod pairs; never modify GDS directly—regenerate from Python source

**Version control:** Use descriptive commit messages for Python script changes; GDS files are auto-generated.

## Design Generation: Python-First Approach

### Core Principle: Parametric Generation
**Never manually edit GDS files.** All designs are generated from Python scripts using KLayout's `klayout.db` API:
```python
import klayout.db as pya
import math

class DesignConfig:
    """Centralized parameters for reproducibility and reusability."""
    dbu = 0.001  # database unit in microns
    METAL_LAYER = pya.LayerInfo(1, 0)
    # All critical dimensions here for single-point modification

def create_component(layout, name, param1, param2, config=DesignConfig):
    """Reusable component generator with geometric documentation."""
    cell = layout.create_cell(name)
    layer_idx = layout.layer(config.METAL_LAYER)
    # Geometry created from parameters; all dimensions computed
    return cell

layout = pya.Layout()
layout.dbu = DesignConfig.dbu
cell = create_component(layout, "my_component", p1=100, p2=50)
layout.write("output_inspect.gds")
```

### Geometry Accuracy & Verification
**Critical Requirement:** All geometric calculations must be validated:
1. **Document assumptions:** Comment all non-obvious dimension calculations
2. **Validate overlaps:** Confirm intentional overlaps; ensure accidental overlaps are prevented via clearance subtractions
3. **Check layer assignments:** Verify all shapes are on intended layers
4. **Test parametrically:** Run with multiple parameter sets; observe expected geometry changes
5. **Visual review:** Always inspect `_inspect.gds` in KLayout before finalizing `_prod.gds`

### Best Practices
1. **Reusable functions:** Extract common patterns (tapers, fan routes, pads) into dedicated functions
2. **Centralized config:** All dimensions live in `DesignConfig` class for single-point edits
3. **Type clarity:** Use region operations (`Region.insert()`, `Region.sized()`, `Region.merge()`) for robust Boolean geometry
4. **Clearance management:** Always subtract buffered regions to prevent unintended overlaps
5. **Layer consistency:** Use enum-like layer definitions; never hardcode layer numbers

## Design Development Workflow

### 1. Create Parametric Python Script
- Define all geometry in a class-based design (DesignConfig) for reusability
- Use helper functions for repeated patterns (e.g., `create_pad()`, `create_taper()`, `create_fanout()`)
- Document each parameter's purpose and fabrication constraints
- Include comments for non-obvious geometric calculations

### 2. Generate & Inspect
```bash
python omegas_100mm_V3.py  # Outputs _inspect.gds and _prod.gds to output/ folder
```
- Open `_inspect.gds` in KLayout GUI
- Visually verify: pad sizes, clearances, layer assignments, alignment
- Check cell hierarchy and instance placement
- Zoom in on critical features (tapers, overlaps, gaps)

### 3. Validate Geometry
- **Measure key dimensions** in KLayout (Tools → Measure)
- **Verify overlaps:** Signal lines overlap pads/tapers; no accidental ground-signal shorts
- **Confirm clearances:** Ground plane clears signal lines by specified gap (50 µm minimum typical)
- **Check symmetry:** Left/right mirrored designs should be identical

### 4. Production Export
- Once validated, use `_prod.gds` for fabrication tools
- `_prod.gds` is fully flattened (no cell references) for tool compatibility
- Commit Python script to version control; GDS files are auto-generated

## Code Organization & Reusability

### Python Script Structure
```
omegas_100mm_V3.py
├─ DesignConfig       # All parameters (dimensions, layers, DBU)
├─ Primitives         # Basic shapes (pad, taper, trace)
│  ├─ create_bond_pad()
│  ├─ create_taper()
│  └─ create_trace_fan()
├─ Components         # RF/DC building blocks
│  ├─ create_chip()  # Complete chip with ground, signal, pads
│  ├─ create_quad_array()  # 2x2 chip arrangement
│  └─ create_wafer_layout()
├─ Utility Functions  # Flattening, merging, validation
│  ├─ flatten_and_merge()
│  └─ validate_geometry()
└─ generate_design()  # Entry point
```

### Reusable Component Library
Extract commonly used patterns into functions:
- **Pads:** Rectangular or rounded-corner contact pads (parametrized width/height)
- **Tapers:** Smooth transitions from wide to narrow traces (parametrized lengths)
- **Fan routes:** Multi-trace convergence (e.g., DC connections with clearance)
- **Ground planes:** Full coverage with apertures (parametrized via region subtraction)

Documentation must include:
- Parameter meanings and units (micrometers, radians, etc.)
- Layer assignments
- Example usage with typical parameter ranges
- Known constraints (e.g., minimum taper length)

## Geometry Accuracy Checklist

Before finalizing any design, verify:

### Dimensional Correctness
- [ ] All pad sizes match specification (RF pads, DC pads, alignment marks)
- [ ] Trace widths are correct for impedance matching (e.g., CPW 100 µm signal, 50 µm gaps)
- [ ] Taper lengths are sufficient for smooth transitions without sharp corners
- [ ] Bond pad placement leaves adequate clearance for connections (min 50 µm typical)

### Electrical Integrity
- [ ] Signal lines never overlap ground planes (except at intentional pads)
- [ ] Ground planes have continuous paths (no isolated islands)
- [ ] Clearances around DC/RF connections are uniform and deliberate
- [ ] No unintended short circuits between layers (same-layer design only)

### Consistency
- [ ] All instances of the same component are identical (check via cell comparison)
- [ ] Symmetry is exact (measure left vs. right halves)
- [ ] Layer assignments are consistent across all cells
- [ ] Cell naming follows a predictable convention (e.g., `chip_omega_A`, `pad_rf_left`)

### Fabrication Readiness
- [ ] Minimum feature size respects process limits (typically >5 µm)
- [ ] Acute angles are avoided (prefer 90° or smooth arcs)
- [ ] All shapes are closed polygons (no open paths)
- [ ] Flattened output (`_prod.gds`) contains only polygons (no cell references)

## Specialized Patterns: Microwave Circuits

### Omega Resonators
- Parametrize outer radius, wire width, gap angle, and lead positions
- Document frequency vs. geometry relationship if known
- Generate variants for parameter sweeps (e.g., different resonator spacings)

### Coplanar Waveguide (CPW)
- Signal width, gap, and ground width are critical for impedance (typically 50 Ω)
- Ensure smooth transitions at junctions (use tapers, not sharp bends)
- Ground planes must surround signal line (top, bottom, left/right)

### Bond Pad Layout
- RF pads: Larger (250 µm typical) for robust wirebond contact
- DC pads: Smaller (50 µm typical) for biasing; array format for fanout
- Always include taper from large pad to narrow signal trace
- Clearance from ground ≥ 50 µm to avoid solder bridge risk

## External Resources & References
- **KLayout Documentation:** https://www.klayout.de/doc/
- **KLayout Python API:** https://www.klayout.de/doc/programming/python_api.html
- **GDS II Specification:** IEEE 1481-1998 (binary layout format standard)
- **CPW Design Guide:** Recommended impedance calculations for 50 Ω lines
- **Photolithography Basics:** Contact your foundry for process minimum feature sizes and design rules

## Common Pitfalls to Avoid
1. **Hardcoded dimensions:** All parameters must be in `DesignConfig`; never use magic numbers in geometry functions
2. **Overlapping traces:** Use region subtraction with clearance buffers to prevent shorts
3. **Missing cell documentation:** Every function must include docstring with parameter meanings
4. **Unchecked flattening:** Always inspect `_inspect.gds` hierarchy before trusting `_prod.gds` flattened output
5. **Version confusion:** Keep clear naming (`V2`, `V3`) and always document what changed from prior version
