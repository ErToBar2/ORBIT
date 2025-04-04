import numpy as np

class PillarModeler:
    def __init__(self, point_cloud, pillars_3D_list, takeoff_altitude):
        self.point_cloud = point_cloud
        self.pillars_3D_list = pillars_3D_list
        self.takeoff_altitude = takeoff_altitude

    def calculate_pillar_centers_and_dimensions(self):
        centers = []
        dimensions = []
        default_z = 0.0  # Default z-coordinate if not provided
        for i in range(0, len(self.pillars_3D_list), 2):
            if i + 1 < len(self.pillars_3D_list):
                p1 = np.array(self.pillars_3D_list[i])
                p2 = np.array(self.pillars_3D_list[i + 1])
                # Ensure both p1 and p2 have at least three coordinates
                if p1.shape[0] == 2:
                    p1 = np.append(p1, default_z)
                if p2.shape[0] == 2:
                    p2 = np.append(p2, default_z)
                center = (p1 + p2) / 2
                width = np.abs(p1[0] - p2[0])  # Width along x-axis
                depth = np.abs(p1[1] - p2[1])  # Depth along y-axis
                centers.append(center)
                dimensions.append((width, depth))
        return centers, dimensions
        
    def get_pillar_height(self, center):
        search_radius = 20.0  # Define the search radius in meters
        pillar_center_xy = np.array(center)[:2]  # Pillar center coordinates in XY plane
        distances = np.linalg.norm(self.point_cloud[:, :2] - pillar_center_xy, axis=1)  # Compute distances in XY plane
        points_within_radius_indices = np.where(distances <= search_radius)[0]  # Find points within the search radius
        if len(points_within_radius_indices) > 0:
            closest_point_idx = points_within_radius_indices[np.argmin(distances[points_within_radius_indices])]
            max_height = self.point_cloud[closest_point_idx][2]  # Height of the closest point within the search radius
            return max_height
        else:
            return 0.0  # Return 0 if no points are found within the search radius

    def create_pillar_mesh(self, center, width, depth, height):
        half_width = width / 2
        half_depth = depth / 2
        base_corners = np.array([
            [center[0] + half_width, center[1] - half_depth, center[2] - self.takeoff_altitude],
            [center[0] + half_width, center[1] + half_depth, center[2] - self.takeoff_altitude],
            [center[0] - half_width, center[1] + half_depth, center[2] - self.takeoff_altitude],
            [center[0] - half_width, center[1] - half_depth, center[2] - self.takeoff_altitude]
        ])
        
        # Extrude base corners upwards to the given height
        pillar_mesh = np.vstack([base_corners, base_corners + [0, 0, height]])
        return pillar_mesh
    
    def generate_ground_plane(self, extent_x, extent_y, point_density, filepath):
        """
        Generates a ground plane and writes it to a PLY file.
        """
        x_values = np.arange(-extent_x / 2, extent_x / 2, point_density)
        y_values = np.arange(-extent_y / 2, extent_y / 2, point_density)
        ground_plane = np.array([[x, y, 0] for x in x_values for y in y_values])

        with open(filepath, 'w') as file:
            file.write("ply\n")
            file.write("format ascii 1.0\n")
            file.write(f"element vertex {len(ground_plane)}\n")
            file.write("property float x\n")
            file.write("property float y\n")
            file.write("property float z\n")
            file.write("end_header\n")
            
            for vertex in ground_plane:
                file.write(f"{vertex[0]:.6f} {vertex[1]:.6f} {vertex[2]:.6f}\n")

        return ground_plane

    def generate_all_pillar_meshes(self):
        vertices = []
        faces = []
        centers, dimensions = self.calculate_pillar_centers_and_dimensions()
        
        for idx, center in enumerate(centers):
            width, depth = dimensions[idx]
            height = self.get_pillar_height(center)
            mesh = self.create_pillar_mesh(center, width, depth, height)
            base_index = len(vertices)
            vertices.extend(mesh)
            # Each pillar has 8 vertices, create quads for each side and top/bottom
            for i in range(4):  # 4 sides
                faces.append([base_index + i, base_index + (i + 1) % 4, base_index + 4 + (i + 1) % 4, base_index + 4 + i])
            faces.append([base_index + 4, base_index + 5, base_index + 6, base_index + 7])  # Top
            faces.append([base_index, base_index + 3, base_index + 2, base_index + 1])  # Bottom

        return vertices, faces, centers

    def write_ply_with_vertices_and_faces(self, filepath, vertices, faces):
        with open(filepath, 'w') as file:
            file.write("ply\n")
            file.write("format ascii 1.0\n")
            file.write(f"element vertex {len(vertices)}\n")
            file.write("property float x\n")
            file.write("property float y\n")
            file.write("property float z\n")
            file.write(f"element face {len(faces)}\n")
            file.write("property list uchar int vertex_indices\n")
            file.write("end_header\n")
            
            for vertex in vertices:
                file.write(f"{vertex[0]:.6f} {vertex[1]:.6f} {vertex[2]:.6f}\n")
            
            for face in faces:
                file.write(f"4 {' '.join(map(str, face))}\n")