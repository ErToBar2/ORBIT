# ORBIT — Optimized Routing for Bridge Inspection Toolkit
**An open-source UAS flight path planning tool for comprehensive bridge inspections under realistic constraints.**
<img width="1172" height="921" alt="image" src="https://github.com/user-attachments/assets/6e75be97-ca90-41f9-9f1d-0e6fc6e89ecb" />
<img width="1409" height="915" alt="image" src="https://github.com/user-attachments/assets/e808e044-1e12-4245-a191-14dc08198fbe" />

ORBIT computes waypoint files to facilitate **drone-based bridge inspections** from minimal input.

The generated waypoint files let a UAS automatically execute flight routes **around** and **under** bridges and roads while **addressing domain-specific challenges under real-world constraints**, facilitating downstream tasks such as processing **photogrammetric 3D bridge models** and automatic **damage detection**.

## Key features
- **Coverage planning for bridges:** Plan flight routes from satellite-map input using the approximate bridge axis and pier positions.
- **Constraint-aware routing:** Specify vertical/horizontal offsets and flight speeds while maintaining manual control of the gimbal/camera.
- **Safety / no-fly handling:** Define safety zones to avoid obstacles (e.g., trees, powerlines).
- **Photogrammetry alignment robustness:** Inserts **vertical connections** between under-deck passes and overview routes to link imagery across routes for sufficient overlap and reliable camera alignment.
- **GNSS-denied–aware planning:** Underdeck inspection flight routes are designed to **reacquire GNSS after each pass**, accommodating temporary GNSS loss with short **IMU-only navigation** segments.
- **Outputs for review & ops:** KMZ export optimized for **DJI Mavic 3E** workflows.
- **GUI:** Windows GUI for interactive planning.

> This repository is released under the **Apache License 2.0**.

## Cite ORBIT
This work is part of an ISPRS archive publication. Please cite as:

Bartczak, E. T.*, Bassier, M., Vergauwen, M. (2025). ORBIT: Optimized Routing for Bridge Inspection Toolkit. An open-source UAS flight path planning tool for comprehensive bridge inspections under realistic constraints. ISPRS Archives (UAV-g 2025, Aalto University, Espoo, Finland). DOI: TBA (forthcoming).


## Installation
Use the environment.yml file:
- cd to the main folder
- **conda env create -n Orbit -f orbit-environment.yml**
- In Anaconda prompt 3, the satellite map on tab 2 might not show just yet.
- In that case, run the .py file in Visual Studio. 
- Now it should run as well from Anaconda. 

Note that the QTWebengine can be problematic. For a windows machine, the yml should work fine. Pip can be problematic.


## Usage Instructions:
- Run the ORBTv.98c.py file
- **python ORBTv.98c.py**

### Project Setup Tab
- First selection of a template cross section might crash the program.
- Since the cross section image is now in the import directory for that bridge name, it should work now.
- You can not switch coordinate systems in one instance: If you chose a coordintae system and confirmed the project, you can not go back and load other data in a different coordinate system. Best is to resstart the app.
- **Cross-section**: You can use any cross section image to extrude it over the bridge trajectory. Simply use e.g. a technical drawing and fill the cross section you want to extract with a blue fill. also, mark one (ideally longest) known distance as a green line. Specify that disntance in **input_scale_meters**. Make sure nothing else in the image has these colors. 
  
### Bridge Gemeometry Tab
- In Anaconda prompt 3, the satellite map on tab 2 might not show just yet.
- In that case, run the .py file in Visual Studio. Afterwards, it also works in Anaconda prompt.
- **Trajectory**: mark the center line of the bridge, typically mark from abutment to abutment. This is the basis for all flight route calculations. If no height information was imported in the load bridge dialog, it will use the **trajectory_heights** (Tab1).
- **Pillars**: mark the approx pillar positions (2 points for each pillar) - they devide the bridge into sections for the underdeck inspection flights. Abutments at the start and end of the trajectory dont need to be marked. 
- **Safety Zones**: use the + button to finalize a safety zone before building the model
  
### Flightroute Generation Tab
#### Overview Flights
- **order**: specify which "standard flight routes" are connected in which order. The first number is the side (1 = right, 2=left) and use the offsets from the trajectory as specified in **"standard_flight_routes"** and the corresponding flight speed of **"flight_speed_map"**. Use "r" to reverse a flight, e.g. "101", "r101" is going to go down the trajectory and coming back up to the starting point. 
- **transition_mode**: Its recommended to use =2 so the transition from the right to the left side happens on the side where the pilot is standing (start of bridge trajectory on the right) Other options are 0 = separate right and left side and 1=pass middle which can be used to pass underneath the bridge.   transition_mode uses the transition_vertical_offset and transition_horizontal_offsets.

#### Underdeck Flights
- **num_points**: base points per section of the bridge. E.g. if you declare only one pillar (code assums abutments at start and end of trajectory) the bridge will be devided into two sections. For num_points = [3, 7, 3] the first section will have 3 base points and the second 7 base points. Add more points if you add more sections (pillars). The base points are corresponding to the number of passes under the bridge. Also update **flight_speed_map** accrdingly.
- **horizontal_offsets_underdeck**: Horizontal distance from bridge (trajectory + bridge width/2). Corresponds to **num_points**, uses previous distance if not matching number of sections.
- **height_offsets_underdeck**: corresponds to **num_points**. Vertical offset from the trajectory. Mind the thickness of the superstructure. Uses previous value if not matching number of sections.
- **general_height_offset**: additional safety offset
- **thresholds_zones**: safety offset from the pillar positions to avoid e.g. vegetatin around the pillars. 
- **custom_zone_angles**: will be updated automatically (if empty) according to the angle between trajectory and pillars (in degrees).
-  **connection_height**: vertical flight segments at start and end of each section. This should correspond to the height used in the overview flight to guarantee image overlap between flight routes for better photogrammetric alingment. These flight segements use the flight speed as specifiend in **flight_speed_map** under **connection**
-  **num_passes**: defines how often the drone crosses though per base point. =2 is recommended so the UAS comes back and continues on the pilots side of the bridge with the next base point pair. 

#### Export Modus
- **heightMode**: EGM96 is recommended, because then the UAS will update its height when recapturing RTK signal. Needs **heightStartingPoint_Ellipsoid** otherwise defaults to **relativeToStartPoint**. Note that "EGM96" (named by DJi) actually refers to the ellipsoidal height. Check https://geographiclib.sourceforge.io/cgi-bin/GeoidEval and google maps for approximations.
- **heightStartingPoint_Ellipsoid**: Can be read from the UAS controller in RTK settings or from EXIF data in image taken from the UAS sitting on the ground.
- **heightStartingPoint_Reference**: If a geolocated point cloud is available for better flight planning. Typically, 3D flight routes are specified using 3D coordinates and loaded during Project Setup Tab from txt file. In that case, the bridge trajectory is not refering to the height above ground, e.g. in Abose sea level. Therefore, the altitude of the starting point in that system must be entered (will be substracted from the waypoints).

#### Additional Features
- **safety_check_photo** = 1 = perform safety check -> adjusts flight routes according to safety zones. Note that with multiple safety zones in an area, the flight route adjusts sequentially, allowing for the final flight route to contain unsafe points. Always check visually. 
- **safety_check_underdeck** = [[0],[0],[0]] # 1 = execute safety check. 
- **safety_check_underdeck_axial** = [[0],[0],[0]] # 1 = execute safety check.
- **n_girders** = 3 determins the number of flight routes for axial underdeck flight passes. 
- **underdeck_split** = 1 execute each underdeck section separately. 
- **underdeck_axial** = 0  Does not create any axial flight routes. Beacuse of the extensive GNSS loss, this is not considered safe, unless specialized UASs are used. 
- **droneEnumValue** = 77 # M3E = 77 
- **payloadEnumValue** = 66 # M3E = 66 
- **globalWaypointTurnMode** = toPointAndStopWithDiscontinuityCurvature is recommended. Drone stops at waypoint and updates position after pass through and stays close to the intended flight path around safety zones. For overview flights with a lot of waypoints, e.g. following a curved bridge, try # coordinateTurn or toPointAndPassWithContinuityCurvature to not stop at each point.



