import numpy as np
from scipy.interpolate import CubicSpline

class BridgeModeler:
    def __init__(self, trajectory_3d_list, transformed_points):
        self.trajectory_3d_list = trajectory_3d_list
        self.transformed_points = transformed_points
        #self.takeoff_altitude = takeoff_altitude
        # if the takeoff_altitude = 0, 

    def sample_curve(self, num_samples):
        t = np.linspace(0, 1, len(self.trajectory_3d_list))
        cs = CubicSpline(t, self.trajectory_3d_list, bc_type='natural')
        t_sampled = np.linspace(0, 1, num_samples)
        points_smoothed = cs(t_sampled)
        tangents = cs(t_sampled, 1)
        tangents_normalized = tangents / np.linalg.norm(tangents, axis=1)[:, np.newaxis]
        return points_smoothed, tangents_normalized

    def compute_frames(self, tangents):
        normals = np.zeros_like(tangents)
        binormals = np.zeros_like(tangents)
        for i, T in enumerate(tangents):
            if np.linalg.norm(T) == 0:
                continue
            N = np.cross(T, [0, 0, 1])
            N = N / np.linalg.norm(N) if np.linalg.norm(N) != 0 else np.zeros(3)
            B = np.cross(T, N)
            normals[i] = N
            binormals[i] = B
        return normals, binormals

    def create_bridge_representation(self, num_samples):
        points_smoothed, tangents = self.sample_curve(num_samples)
        normals, binormals = self.compute_frames(tangents)
        point_cloud = []
        for i, point in enumerate(points_smoothed):
            N = normals[i]
            B = binormals[i]
            for shape_point in self.transformed_points:
                transformed_point = point + shape_point[1] * N + shape_point[2] * B
                point_cloud.append(transformed_point)
        return np.array(point_cloud), points_smoothed, normals, binormals
    
    def calculate_faces(self, num_samples):
        num_points_per_section = len(self.transformed_points)
        faces = []
        for i in range(num_samples - 1):
            for j in range(num_points_per_section):
                next_j = (j + 1) % num_points_per_section
                face = [
                    i * num_points_per_section + j,
                    i * num_points_per_section + next_j,
                    (i + 1) * num_points_per_section + next_j,
                    (i + 1) * num_points_per_section + j
                ]
                faces.append(face)
        return faces

    # Function to write vertices and quads (as faces) to a .ply file
    def write_ply_with_vertices_and_faces(self, file_path, vertices, faces):
        """
        Writes vertex and face data to a PLY (Polygon File Format or Stanford Triangle Format) file. 
        This function constructs a quadmesh from the given vertices and faces.

        Args:
        file_path (str): The path to the file where the PLY data will be saved.
        vertices (list of tuples/lists): A list where each element is a tuple or list representing a vertex in 3D space. 
                                        Each vertex is in the format (x, y, z).
        faces (list of tuples/lists): A list where each element is a tuple or list representing a face. 
                                    Each face is defined by the indices of vertices that form the corners of the quad.

        The function first writes the PLY header, specifying the format, the number of vertices, and the number of faces. 
        It then iterates over the vertices and faces lists to write the vertex and face data into the file. 
        Each face is assumed to be a quadrilateral, indicated by the prefix '4' before the list of vertex indices in the face.
        
        """
        with open(file_path, 'w') as ply_file:
            ply_file.write("ply\n")
            ply_file.write("format ascii 1.0\n")
            ply_file.write(f"element vertex {len(vertices)}\n")
            ply_file.write("property float x\n")
            ply_file.write("property float y\n")
            ply_file.write("property float z\n")
            ply_file.write(f"element face {len(faces)}\n")
            ply_file.write("property list uchar int vertex_indices\n")
            ply_file.write("end_header\n")
            
            # Write vertices
            for vertex in vertices:
                x, y, z = vertex
                ply_file.write(f"{x:.6f} {y:.6f} {z:.6f}\n")  # Adjust precision as needed
            
            # Write faces
            for face in faces:
                ply_file.write(f"4 {' '.join(map(str, face))}\n")  # '4' indicates a quad
            