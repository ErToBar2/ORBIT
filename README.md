# ORBIT

**O**ptimized **R**outing for **B**ridge **I**nspection **T**oolkit is an open-source, research-oriented UAS flight planning tool for bridge inspection missions under realistic geometric and operational constraints.

ORBIT was developed to support inspection planning beyond simple top-down waypoint design: it combines project-coordinate-aware data import, bridge geometry reconstruction, satellite-map safety zoning, and 3D route generation for both overview and under-deck inspection flights.

If your work touches bridge inspection, photogrammetry, digital twins, or damage detection, ORBIT provides a practical planning baseline that can be adapted, benchmarked, and extended in further research.

<p align="center">
  <img src=".github/readme-assets/orbit-hero.png" alt="ORBIT 3D route planning view" width="1000">
</p>

## Why ORBIT

Bridge inspection flight planning is difficult when the scene is cluttered, access is constrained, GNSS quality degrades below the deck, and image quality targets are strict. ORBIT is built for exactly that setting.

Key research-relevant capabilities:

- Plan both overview and detailed inspection routes inside one workflow.
- Support difficult bridge geometries, including curved bridges.
- Generate routes for under-deck inspection in GNSS-loss or GNSS-degraded environments.
- Define and visualize safety zones directly on the satellite map.
- Work with project coordinate systems instead of forcing a purely WGS84-only workflow.
- Build 3D inspection geometry from imported trajectory, pillars, and bridge cross-section information.
- Design missions for high-resolution acquisition; in our demonstrated use case, ORBIT supported planning toward a **1 mm/px GSD**.

## Workflow

### 1. Import bridge data in the project coordinate system

ORBIT starts from bridge-specific inspection inputs such as trajectory points, pillar locations, width, and project metadata. The import workflow is coordinate-system aware and intended for engineering data rather than consumer-map-only planning.

<p align="center">
  <img src=".github/readme-assets/workflow-import.png" alt="ORBIT import and coordinate system selection" width="900">
</p>

### 2. Reconstruct bridge geometry from a cross-section

The tool supports importing a bridge cross-section and using it to build the geometric basis for later route generation. This makes the planning stage more explicit and reproducible for research workflows that need a well-defined inspection model.

<p align="center">
  <img src=".github/readme-assets/workflow-cross-section.png" alt="ORBIT bridge cross-section import and scaling" width="900">
</p>

### 3. Define safety zones on the satellite map

ORBIT lets the user place bridge geometry and operational constraints in map context. Safety zones can be drawn and adjusted directly, which is useful when comparing route strategies, access assumptions, or inspection policies.

<p align="center">
  <img src=".github/readme-assets/workflow-safety-zones.jpg" alt="ORBIT satellite map with safety zones" width="900">
</p>

### 4. Generate and inspect 3D flight routes

The final planning stage brings the model, safety zones, and route definitions together in a 3D view. Overview trajectories and under-deck inspection routes can be inspected visually before export.

<p align="center">
  <img src=".github/readme-assets/workflow-flight-generation.png" alt="ORBIT 3D flight route generation" width="900">
</p>

## Why researchers may want to use ORBIT

ORBIT is useful as a starting point for work on:

- automated or semi-automated bridge inspection planning,
- photogrammetric mission design for condition assessment,
- crack and damage detection data acquisition,
- benchmark generation for route planning in constrained environments,
- GNSS-denied or GNSS-degraded infrastructure inspection,
- bridge digital twins and inspection data integration,
- comparison of inspection strategies across bridge types and access conditions.

In short: ORBIT gives researchers a concrete mission-planning workflow for difficult inspection scenarios rather than only a visualization demo or a generic waypoint editor.

## Publication

The project is described in the following conference paper:

- **Bartczak, E. T., Bassier, M., & Vergauwen, M. (2025).** *ORBIT: Optimized Routing for Bridge Inspection Toolkit. An open-source UAS flight path planning tool for comprehensive bridge inspections under realistic constraints.* ISPRS Archives, UAV-g 2025, Espoo, Finland.  
  Paper: https://isprs-archives.copernicus.org/articles/XLVIII-2-W11-2025/25/2025/

Citation metadata is also provided in [`CITATION.cff`](./CITATION.cff).

## Installation

Create the Conda environment from the repository root:

```bash
conda env create -f Orbit_Environment.yml
conda activate Orbit
python ORBITv01.2.2.py
```

If the 3D view fails because Qt bindings are missing, install the missing runtime packages in the same environment:

```bash
python -m pip install qtpy pyvistaqt
```

## Repository Focus

This repository is intended to support continued research and experimentation around bridge inspection flight planning. Contributions, adaptations to new bridge types, and connections to downstream inspection-analysis tasks are all natural next steps.
