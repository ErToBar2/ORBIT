# ORBIT
**O**ptimized **R**outing for **B**ridge **I**nspection **T**oolkit is an open-source, research-oriented UAS flight planning tool to generate waypoint flight routes optimized for bridge inspections under realistic geometric and operational constraints.

<img width="1921" height="1149" alt="0_Cover image 3Dviewer" src="https://github.com/user-attachments/assets/ef9306f4-4e3f-40af-b33d-a7842cc8470c" />

ORBIT was developed within an ongoing research project to facilitate effective and reliable UAS based bridge inspection missions and was used on over 30 bridges. The concept is to create a save first overview flight and then per bridge section dedicated underdeck inspection flights that visually connect to the overview flight to assure alignment success. Additionally, orbit/tool includes various code to facilitate hihg precision UAS photogrammetry.   


## Why ORBIT

Bridge inspection flight planning is difficult when the scene is cluttered, access is constrained, GNSS quality degrades below the deck, and image quality targets are strict. ORBIT is built for exactly that setting.

Key research-relevant capabilities:

- Plan both overview and detailed inspection routes inside one workflow.
- Support difficult bridge geometries, including curved bridges.
- Generate routes for under-deck inspection in GNSS-loss or GNSS-degraded environments.
- Define and visualize safety zones directly on the satellite map.
- Work with any internal project coordinate systems. 
- Build 3D inspection geometry from imported trajectory, pillars, and bridge cross-section information.
- Design missions for high-resolution acquisition. We achieved **1 mm/px GSD** facade inspection using a DJI Mavic 3 Enterprise. 

## Workflow

### 1. Import bridge data in the project coordinate system

ORBIT starts from bridge-specific inspection inputs such as trajectory points, pillar locations, width, and project metadata. The import workflow is coordinate-system aware and the user may enter any known data, such as 2D or 3D points of the bridge trajectory (centre line), position of pillars and width of the bridge. 

<img width="1928" height="1035" alt="1_start- Data import option chosing EPSG code " src="https://github.com/user-attachments/assets/10e857e2-c005-45b4-8ee8-15f02d015120" />

### 2. Reconstruct bridge geometry from a cross-section

To reconstruct the geometry, ORBIT detects a blue filling of any cross section drawing and therefore is easy to use, flexible and effective. 

<img width="1918" height="1153" alt="2_ start - importing CV crosssection extraction" src="https://github.com/user-attachments/assets/a1d7e6b6-1b95-4bef-b954-a2337353be02" />

### 3. Define safety zones on the satellite map

ORBIT lets the user place bridge geometry and operational constraints on a satellite map. Safety zones can be drawn e.g. to avoid trees and electrical powerlines.

<img width="1920" height="1157" alt="3 Satellite image safety zone mapping" src="https://github.com/user-attachments/assets/d5817d6f-298d-4739-997a-93ea58a22872" />

### 4. Generate and inspect 3D flight routes

The final planning stage brings the model, safety zones, and route definitions together in a 3D view. Overview trajectories and under-deck inspection routes can be inspected visually before export.

<img width="1920" height="1160" alt="4 Flighr route optionsPNG" src="https://github.com/user-attachments/assets/50c59ad9-7da2-4bd2-9c3e-b7f54991adc2" />

## Why researchers may want to use ORBIT

ORBIT is useful as a starting point for work on:

- photogrammetric mission design for condition assessment,
- damage detection data acquisition,
- automated or semi-automated bridge inspection planning,
- GNSS-denied or GNSS-degraded infrastructure inspection,
- bridge digital twinning,

In short: ORBIT gives researchers a concrete mission-planning workflow for difficult inspection scenarios rather than only a visualization demo or a generic waypoint editor. The tool and method has been proven in over 30+ bridge project to be effective and deliver high quality results. 

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
