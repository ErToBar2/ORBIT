import numpy as np

class PillarModeler:
    """Generate simple rectangular pillar meshes centred on pillar pairs."""

    def __init__(self, point_cloud, pillars_3d_list, takeoff_altitude=0.0, width=1.0):
        self.point_cloud = np.asarray(point_cloud, dtype=float)
        self.pillars_3d_list = [np.asarray(p, dtype=float) for p in pillars_3d_list]
        self.takeoff_altitude = float(takeoff_altitude)
        self.width = float(width)

    # ------------------------------------------------------------------
    # Height estimator (optional – uses nearest point in bridge cloud)
    # ------------------------------------------------------------------
    def get_pillar_height(self, center, search_radius=20.0):
        if self.point_cloud.size == 0:
            return self.takeoff_altitude + 5.0  # fallback
        dxy = np.linalg.norm(self.point_cloud[:, :2] - center[:2], axis=1)
        idx = np.where(dxy <= search_radius)[0]
        if idx.size:
            return float(self.point_cloud[idx[np.argmin(dxy[idx])], 2])
        return self.takeoff_altitude + 5.0

    # ------------------------------------------------------------------
    def _create_box_mesh(self, p1, p2, height):
        half = self.width / 2.0
        direction = (p2 - p1)
        direction /= np.linalg.norm(direction)
        perp = np.array([-direction[1], direction[0], 0]) * half
        base_xy = np.vstack([
            p1[:2] + perp[:2], p1[:2] - perp[:2],
            p2[:2] + perp[:2], p2[:2] - perp[:2]
        ])
        base = np.hstack([base_xy, np.full((4,1), self.takeoff_altitude)])
        top  = base + [0,0,height-self.takeoff_altitude]
        return np.vstack([base, top])

    def generate_all_pillar_meshes(self):
        verts, faces, centers = [], [], []
        for i in range(0, len(self.pillars_3d_list), 2):
            if i+1 >= len(self.pillars_3d_list):
                break
            p1, p2 = self.pillars_3d_list[i], self.pillars_3d_list[i+1]
            center = (p1 + p2) / 2.0
            centers.append(center)
            height = self.get_pillar_height(center)
            mesh_v = self._create_box_mesh(p1, p2, height)
            base_idx = len(verts)
            verts.extend(mesh_v)
            # six quad faces (4 sides + top + bottom)
            for j in range(4):
                faces.append([base_idx+j, base_idx+(j+1)%4, base_idx+4+(j+1)%4, base_idx+4+j])
            faces.append([base_idx+4, base_idx+5, base_idx+6, base_idx+7])  # top
            faces.append([base_idx, base_idx+3, base_idx+2, base_idx+1])    # bottom
        return verts, faces, centers

    def write_ply_with_vertices_and_faces(self, filepath, vertices, faces):
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('ply\nformat ascii 1.0\n')
            f.write(f'element vertex {len(vertices)}\n')
            f.write('property float x\nproperty float y\nproperty float z\n')
            f.write(f'element face {len(faces)}\n')
            f.write('property list uchar int vertex_indices\nend_header\n')
            for v in vertices:
                f.write(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
            for fc in faces:
                f.write('4 '+ ' '.join(map(str, fc)) +'\n') 