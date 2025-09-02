# ORBIT — Optimized Routing for Bridge Inspection Toolkit
**An open-source UAS flight path planning tool for comprehensive bridge inspections under realistic constraints.**

ORBIT plans drone flight waypoint files for automated flight routes around bridges and other infrastructure to achieve 
**complete, repeatable coverage** of bridge assets while respecting real-world constraints.
It exports deliverables you can visualize (ply files) and use as the basis for flights (.KML and KMZ).

> This repository is released under the **Apache License 2.0**.

---

## Key features
- **Coverage planning for bridges**: deck undersides, piers, girders, arches, etc.
- **Constraint-aware routing**: specify vertical and horizontal offsets, flight speeds and maintain manual control over gimbal/camera.
- **Safety / no-fly handling**: define safety zones to maintain safe distances from traffic and obstacles (e.g. trees).
- **Photogrammetry alignment robustness**: inserts vertical connections to underdeck flights to link footage with overview flights during processing.
- **GNSS-denied aware planning**: Underdeck flight routes are designed to recapture GNSS signal after each pass through, allowing for temporal GNSS loss and partial IMU only navigation.  
- **Outputs for review & ops**: KMZ export optimized for DJI Mavic 3 E.
- **GUI**: a Windows GUI for interactive planning.

---

### 1) Installation
- environment.yml
- cd to the main folder
conda env create -f environment.yml

Note that the QTWebengine can be problematic. For a windows machine, the yml should work fine. Pip can be problematic. 
