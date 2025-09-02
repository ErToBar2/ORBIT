# ORBIT — Optimized Routing for Bridge Inspection Toolkit
**An open-source UAS flight path planning tool for comprehensive bridge inspections under realistic constraints.**

ORBIT computes waypoint files to facilitate **drone-based bridge inspections** from minimal input.

The generated waypoint files let a UAS automatically execute flight routes **around** and **under** bridges (and related infrastructure such as roads/overpasses) while **addressing domain-specific challenges under real-world constraints**, facilitating downstream tasks such as processing **photogrammetric 3D bridge models** and automatic **damage detection**.

## Key features
- **Coverage planning for bridges:** Plan flight routes from satellite-map input using the approximate bridge axis and pier positions.
- **Constraint-aware routing:** Specify vertical/horizontal offsets and flight speeds while maintaining manual control of the gimbal/camera.
- **Safety / no-fly handling:** Define safety zones to maintain standoff from obstacles (e.g., trees, powerlines).
- **Photogrammetry alignment robustness:** Inserts **vertical connections** between under-deck passes and overview routes to link imagery across routes for reliable bundle adjustment.
- **GNSS-denied–aware planning:** Under-deck routes are designed to **reacquire GNSS after each pass**, accommodating temporary GNSS loss with short **IMU-only** segments.
- **Outputs for review & ops:** KMZ export optimized for **DJI Mavic 3E** workflows.
- **GUI:** Windows GUI for interactive planning.

> This repository is released under the **Apache License 2.0**.

### Cite ORBIT
This work is part of an ISPRS archive publication. Please cite as:

Bartczak, E. T.*, Bassier, M., Vergauwen, M. (2025). ORBIT: Optimized Routing for Bridge Inspection Toolkit. An open-source UAS flight path planning tool for comprehensive bridge inspections under realistic constraints. ISPRS Archives (UAV-g 2025, Aalto University, Espoo, Finland). DOI: TBA (forthcoming).


#### Installation
use the environment.yml file:
cd to the main folder

**conda env create -f environment.yml**

Note that the QTWebengine can be problematic. For a windows machine, the yml should work fine. Pip can be problematic.
