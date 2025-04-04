import numpy as np
import os

class PillarModeler:
    def __init__(self, point_cloud, pillars_3D_list, takeoff_altitude):
        self.point_cloud = point_cloud
        self.pillars_3D_list = pillars_3D_list
        self.takeoff_altitude = takeoff_altitude

    def calculate_pillar_centers_and_directions(self):
        centers = []
        for i in range(0, len(self.pillars_3D_list), 2):
            if i + 1 < len(self.pillars_3D_list):
                p1 = np.array(self.pillars_3D_list[i])
                p2 = np.array(self.pillars_3D_list[i + 1])
                center = (p1 + p2) / 2
                centers.append(center)
        return centers

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

    def create_pillar_mesh(self, p1, p2, height):
        width = 1.0
        half_width = width / 2

        # Calculate the direction vector and the perpendicular vector in the XY plane
        direction = (p2 - p1) / np.linalg.norm(p2 - p1)
        perp_vector = np.array([-direction[1], direction[0], 0]) * half_width

        # Base corners with mean height
        
        base_corners = np.array([
            p1[:2] + perp_vector[:2], p1[:2] - perp_vector[:2],
            p2[:2] + perp_vector[:2], p2[:2] - perp_vector[:2]
        ])
        base_corners = np.hstack((base_corners, np.full((4, 1), self.takeoff_altitude)))

        # Extrude base corners upwards to the given height
        pillar_mesh = np.vstack([base_corners, base_corners + [0, 0, height-self.takeoff_altitude]])

        return pillar_mesh
    

    

    def generate_ground_plane(self, centers, filepath, radius=10.0, point_density=0.2):
        """
        Generates a ground plane around each pillar center and writes it to a PLY file.
        """
        ground_plane = []
        for center in centers:
            lowest_point = np.array([center[0], center[1], self.takeoff_altitude])
            x_values = np.arange(lowest_point[0] - radius, lowest_point[0] + radius, point_density)
            y_values = np.arange(lowest_point[1] - radius, lowest_point[1] + radius, point_density)
            ground_plane += [[x, y, self.takeoff_altitude] for x in x_values for y in y_values]

        ground_plane = np.array(ground_plane)

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
        centers = []
        for i in range(0, len(self.pillars_3D_list), 2):
            if i + 1 < len(self.pillars_3D_list):
                p1 = np.array(self.pillars_3D_list[i])
                p2 = np.array(self.pillars_3D_list[i + 1])
                center = (p1 + p2) / 2
                centers.append(center)
                height = self.get_pillar_height(center)
                mesh = self.create_pillar_mesh(p1, p2, height)
                base_index = len(vertices)
                vertices.extend(mesh)
                # Each pillar has 8 vertices, create quads for each side and top/bottom
                for j in range(4):  # 4 sides
                    faces.append([base_index + j, base_index + (j + 1) % 4, base_index + 4 + (j + 1) % 4, base_index + 4 + j])
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
