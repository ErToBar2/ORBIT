import os
import zipfile
from lxml import etree as ET
from datetime import datetime
from pyproj import CRS, Transformer
from PySide2.QtWidgets import QMessageBox

# For more inforamtion see https://developer.dji.com/doc/cloud-api-tutorial/en/api-reference/dji-wpml/template-kml.html

class KMZExporter:
    def __init__(self, flight_route, flight_name, bridge_name, flightroute_directory, flight_speed_map, z_value, heightMode):
        self.flightroute_directory = flightroute_directory
        self.flight_route = flight_route
        self.flight_name = flight_name      #self.flight_name=="Photogrammetric_Flight":
        self.bridge_name = bridge_name
        self.takeoff_height= z_value
        self.flight_speed_map = flight_speed_map
        self.heightMode = heightMode

    def export_route_as_kmz(self):
        
        """
        Exports a given flight route as a KMZ file, using the tagged coordinates.

        :param tagged_coords: List of coordinates with tags, in Lambert 72 format.
        :param flight_name: Name of the route for file naming.
        """

        # Define the namespaces
        ns_map = {
            None: "http://www.opengis.net/kml/2.2",  # Default namespace (no prefix)
            'wpml': "http://www.dji.com/wpmz/1.0.3"  # Prefix 'wpml'
        }

        # Create the root element with the default namespace
        kml_element = ET.Element("kml", nsmap=ns_map)
        document = ET.SubElement(kml_element, "Document")

        # Adding createTime and updateTime elements with the 'wpml' namespace
        wpml_createTime = ET.SubElement(document, "{http://www.dji.com/wpmz/1.0.3}createTime")
        current_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        wpml_createTime.text = current_time 
        wpml_updateTime = ET.SubElement(document, "{http://www.dji.com/wpmz/1.0.3}updateTime")
        wpml_updateTime.text = current_time 

        # Adding missionConfig element with the 'wpml' namespace
        mission_config = ET.SubElement(document, "{http://www.dji.com/wpmz/1.0.3}missionConfig")

        # Adding child elements to missionConfig
        ET.SubElement(mission_config, "{http://www.dji.com/wpmz/1.0.3}flyToWaylineMode").text = "safely"
        ET.SubElement(mission_config, "{http://www.dji.com/wpmz/1.0.3}finishAction").text = "goHome"
        ET.SubElement(mission_config, "{http://www.dji.com/wpmz/1.0.3}exitOnRCLost").text = "goContinue"


        startingpoint = self.flight_route[0][:3]  
        startingpoint_wgs84 = self.convert_coordinates_to_wgs84([startingpoint])
        startingpoint_str = f"{startingpoint_wgs84[0][0]},{startingpoint_wgs84[0][1]}"
        ET.SubElement(mission_config, "{http://www.dji.com/wpmz/1.0.3}takeOffRefPoint").text = startingpoint_str
        
        ET.SubElement(mission_config, "{http://www.dji.com/wpmz/1.0.3}takeOffRefPointAGLHeight").text = str(self.takeoff_height)          # only when heightMode is EGM96
        ET.SubElement(mission_config, "{http://www.dji.com/wpmz/1.0.3}takeOffSecurityHeight").text = "30"
        ET.SubElement(mission_config, "{http://www.dji.com/wpmz/1.0.3}globalTransitionalSpeed").text = "0.2"

#Note: The speed at which the aircraft flies to the first waypoint of each route. 
        # !!! When the route mission is interrupted, the speed of the aircraft recovering from the current position to the interruption point.

        # Adding droneInfo and its child elements
        drone_info = ET.SubElement(mission_config, "{http://www.dji.com/wpmz/1.0.3}droneInfo")
        ET.SubElement(drone_info, "{http://www.dji.com/wpmz/1.0.3}droneEnumValue").text = "77"
        ET.SubElement(drone_info, "{http://www.dji.com/wpmz/1.0.3}droneSubEnumValue").text = "0"

        # Adding payloadInfo and its child elements
        payload_info = ET.SubElement(mission_config, "{http://www.dji.com/wpmz/1.0.3}payloadInfo")
        ET.SubElement(payload_info, "{http://www.dji.com/wpmz/1.0.3}payloadEnumValue").text = "66"
        ET.SubElement(payload_info, "{http://www.dji.com/wpmz/1.0.3}payloadSubEnumValue").text = "0"
        ET.SubElement(payload_info, "{http://www.dji.com/wpmz/1.0.3}payloadPositionIndex").text = "0"

        # Adding Folder element
        folder = ET.SubElement(document, "Folder")


        # Adding child elements to Folder
        ET.SubElement(folder, "{http://www.dji.com/wpmz/1.0.3}templateType").text = "waypoint"
        ET.SubElement(folder, "{http://www.dji.com/wpmz/1.0.3}templateId").text = "0"

        # Adding waylineCoordinateSysParam and its child elements
        wayline_coord_sys_param = ET.SubElement(folder, "{http://www.dji.com/wpmz/1.0.3}waylineCoordinateSysParam")
        ET.SubElement(wayline_coord_sys_param, "{http://www.dji.com/wpmz/1.0.3}coordinateMode").text = "WGS84"
        ET.SubElement(wayline_coord_sys_param, "{http://www.dji.com/wpmz/1.0.3}heightMode").text = str(self.heightMode)   #Try EGM96 as well! 

        ET.SubElement(wayline_coord_sys_param, "{http://www.dji.com/wpmz/1.0.3}positioningType").text = "GPS"

        ET.SubElement(folder, "{http://www.dji.com/wpmz/1.0.3}autoFlightSpeed").text = "2"
        ET.SubElement(folder, "{http://www.dji.com/wpmz/1.0.3}globalHeight").text = "100"
        ET.SubElement(folder, "{http://www.dji.com/wpmz/1.0.3}caliFlightEnable").text = "0"
        ET.SubElement(folder, "{http://www.dji.com/wpmz/1.0.3}gimbalPitchMode").text = "manual"

        # Adding globalWaypointHeadingParam and its child elements
        global_waypoint_heading_param = ET.SubElement(folder, "{http://www.dji.com/wpmz/1.0.3}globalWaypointHeadingParam")
        ET.SubElement(global_waypoint_heading_param, "{http://www.dji.com/wpmz/1.0.3}waypointHeadingMode").text = "manually"
        ET.SubElement(global_waypoint_heading_param, "{http://www.dji.com/wpmz/1.0.3}waypointHeadingAngle").text = "0"
        ET.SubElement(global_waypoint_heading_param, "{http://www.dji.com/wpmz/1.0.3}waypointPoiPoint").text = "0.000000,0.000000,0.000000"
        ET.SubElement(global_waypoint_heading_param, "{http://www.dji.com/wpmz/1.0.3}waypointHeadingPoiIndex").text = "0"

        if self.flight_name=="Photogrammetric_Flight_Route":
            ET.SubElement(folder, "{http://www.dji.com/wpmz/1.0.3}globalWaypointTurnMode").text = "coordinateTurn"  
        else:
            ET.SubElement(folder, "{http://www.dji.com/wpmz/1.0.3}globalWaypointTurnMode").text = "toPointAndStopWithDiscontinuityCurvature"  
        
        ET.SubElement(folder, "{http://www.dji.com/wpmz/1.0.3}globalUseStraightLine").text = "1" # 0: The trajectory of the flight segment is a curve in the whole process 1: The trajectory of the flight segment should be as close as possible to the line connecting the two points


########################################## adding the waypoints ##############################################################################

        ### ALL PLACEMARKS ###
        print(self.flight_route)
        indices_to_adjust = []
        for index, item in enumerate(self.flight_route):
            if len(item) != 4:
                print(f"Error: Item at index {index} does not contain four elements: {item}")
            else:
                x, y, z, tag = item
                if self.heightMode == "relativeToStartPoint":
                    z -= self.takeoff_height
                coord = (x, y, z)
                if z < 2:
                    indices_to_adjust.append(index)
                self.add_placemark(folder, coord, index, tag)
        
        if indices_to_adjust:
            self.prompt_and_adjust_z_values(indices_to_adjust)

##########################################################################################################################################

        ### Last part ###
        # Adding the payloadParam section after the last Placemark
        payload_param = ET.SubElement(folder, "{http://www.dji.com/wpmz/1.0.3}payloadParam")
        ET.SubElement(payload_param, "{http://www.dji.com/wpmz/1.0.3}payloadPositionIndex").text = "0"
        ET.SubElement(payload_param, "{http://www.dji.com/wpmz/1.0.3}meteringMode").text = "average"
        ET.SubElement(payload_param, "{http://www.dji.com/wpmz/1.0.3}dewarpingEnable").text = "0"
        ET.SubElement(payload_param, "{http://www.dji.com/wpmz/1.0.3}returnMode").text = "singleReturnStrongest"
        ET.SubElement(payload_param, "{http://www.dji.com/wpmz/1.0.3}samplingRate").text = "240000"
        ET.SubElement(payload_param, "{http://www.dji.com/wpmz/1.0.3}scanningMode").text = "nonRepetitive"
        ET.SubElement(payload_param, "{http://www.dji.com/wpmz/1.0.3}modelColoringEnable").text = "0"

        # Write to file
        tree = ET.ElementTree(kml_element)

        ### Export KMZ ###

        # Create a 'wmpz' folder inside the directory
        wmpz_folder_path = os.path.join(self.flightroute_directory, "wmpz")
        os.makedirs(wmpz_folder_path, exist_ok=True)

        # Save the KML file inside the 'wmpz' folder
        kml_file_path = os.path.join(wmpz_folder_path, "template.kml")
        tree.write(kml_file_path, encoding='utf-8', pretty_print=True, xml_declaration=True)

        # Create a zip file from the 'wmpz' folder
        zip_file_path = os.path.join(self.flightroute_directory, "wmpz.zip")
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(wmpz_folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.relpath(file_path, os.path.join(wmpz_folder_path, '..')))

        # Rename the zip file to '{bridge_name}_Complete_Flightroute.kmz'
        kmz_file_path = os.path.join(self.flightroute_directory, f"{self.bridge_name}_{self.flight_name}.kmz")

        #Check if the .kmz file exists and delete if it does
        if os.path.exists(kmz_file_path):
            os.remove(kmz_file_path)

        os.rename(zip_file_path, kmz_file_path)

######### done ######


    def add_placemark(self, folder, coord, index, tag):
    
        speed = self.flight_speed_map.get(tag, {}).get("speed")
    
        # Convert the Lambert 72 coordinates to WGS84
        wgs84_coord = self.convert_coordinates_to_wgs84([coord])[0]  # Assuming convert_coordinates returns a list
        
        placemark = ET.SubElement(folder, "Placemark")
        # Adding Point and coordinates
        point = ET.SubElement(placemark, "Point")
        coordinates = ET.SubElement(point, "coordinates")
        coordinates.text = f"{wgs84_coord[0]},{wgs84_coord[1]}"
        print(wgs84_coord[2])

        # Adding other elements inside Placemark
        ET.SubElement(placemark, "{http://www.dji.com/wpmz/1.0.3}index").text = str(index)
        
        # The elipsoid height is the wgs84_coord[2] + 44.8 (?), but only if heightMode is set to 'EGM96', else it is wgs84_coord[2]
        if self.heightMode == "EGM96":
            ET.SubElement(placemark, "{http://www.dji.com/wpmz/1.0.3}ellipsoidHeight").text = str(wgs84_coord[2] + 44.8)
        else:
            ET.SubElement(placemark, "{http://www.dji.com/wpmz/1.0.3}ellipsoidHeight").text = str(wgs84_coord[2])
        ET.SubElement(placemark, "{http://www.dji.com/wpmz/1.0.3}height").text = str(wgs84_coord[2])
        ET.SubElement(placemark, "{http://www.dji.com/wpmz/1.0.3}useGlobalHeight").text = "0"
        
        # Setting custom speed
        ET.SubElement(placemark, "{http://www.dji.com/wpmz/1.0.3}useGlobalSpeed").text = "0"  # Use individual speed
        ET.SubElement(placemark, "{http://www.dji.com/wpmz/1.0.3}waypointSpeed").text = str(speed)
        ET.SubElement(placemark, "{http://www.dji.com/wpmz/1.0.3}useGlobalHeadingParam").text = "1"
        ET.SubElement(placemark, "{http://www.dji.com/wpmz/1.0.3}useGlobalTurnParam").text = "1"
        ET.SubElement(placemark, "{http://www.dji.com/wpmz/1.0.3}useStraightLine").text = "1"
        ET.SubElement(placemark, "{http://www.dji.com/wpmz/1.0.3}isRisky").text = "0"
        

    def convert_coordinates_to_wgs84(self, coords):
        in_proj = CRS("EPSG:31370")  # Belgian Lambert 72
        out_proj = CRS("EPSG:4326")  # WGS84
        transformer = Transformer.from_crs(in_proj, out_proj)
        # Include the Z coordinate in the return value
        return [(transformer.transform(x, y)[1], transformer.transform(x, y)[0], z) for x, y, z in coords]
    
    def prompt_and_adjust_z_values(self, indices):
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setText("There are z values less than 2m. Do you want to adjust them to 2.0 m?")
        msg_box.setWindowTitle("Warning")
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        ret_val = msg_box.exec_()

        if ret_val == QMessageBox.Yes:
            for index in indices:
                x, y, z, tag = self.flight_route[index]
                if self.heightMode == "relativeToStartPoint":
                    z -= self.takeoff_height
                self.flight_route[index] = (x, y, 2.0, tag)

    def check_and_adjust_z_values(self, coord):
        x, y, z = coord
        if z < 2:
            return (x, y, 2.0)
        return coord