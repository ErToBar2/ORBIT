import numpy as np
from scipy.interpolate import CubicSpline

# Debug control functions - use the same pattern as main app
def debug_print(*args, **kwargs) -> None:
    """Print function that only outputs when DEBUG is True."""
    # Import DEBUG from main app context
    try:
        from ..io.data_parser import DEBUG_PRINT
        if DEBUG_PRINT:
            print(*args, **kwargs)
    except ImportError:
        # Fallback: use main app's DEBUG if available
        try:
            import sys
            main_module = sys.modules.get('__main__')
            if hasattr(main_module, 'DEBUG') and main_module.DEBUG:
                print(*args, **kwargs)
        except:
            pass  # Silent fallback

def error_print(*args, **kwargs) -> None:
    """Print function that always outputs (for errors)."""
    print(*args, **kwargs)

class BridgeModeler:
    """Sweep a 2-D cross-section along a 3-D trajectory and generate a quad-mesh."""

    def __init__(self, trajectory_3d_list, transformed_points):
        debug_print(f"BridgeModeler initialized")
        self.trajectory_3d_list = trajectory_3d_list
        self.transformed_points = transformed_points

    # ------------------------------------------------------------------
    # Trajectory sampling helpers
    # ------------------------------------------------------------------
    def sample_curve(self, num_samples):
        t = np.linspace(0, 1, len(self.trajectory_3d_list))
        cs = CubicSpline(t, self.trajectory_3d_list, bc_type="natural")
        t_sampled = np.linspace(0, 1, num_samples)
        pts = cs(t_sampled)
        tangents = cs(t_sampled, 1)
        tangents /= np.linalg.norm(tangents, axis=1)[:, None]
        return pts, tangents

    def compute_frames(self, tangents):
        normals = np.zeros_like(tangents)
        binormals = np.zeros_like(tangents)
        for i, T in enumerate(tangents):
            if np.allclose(T, 0):
                continue
            N = np.cross(T, [0, 0, 1])
            N = N / np.linalg.norm(N) if np.linalg.norm(N) else np.zeros(3)
            B = np.cross(T, N)
            normals[i] = N
            binormals[i] = B
        return normals, binormals

    # ------------------------------------------------------------------
    # Public mesh generator
    # ------------------------------------------------------------------
    def create_bridge_representation(self, num_samples):
        pts, tangents = self.sample_curve(num_samples)
        normals, binormals = self.compute_frames(tangents)
        cloud = []
        for i, p in enumerate(pts):
            N, B = normals[i], binormals[i]
            for sp in self.transformed_points:
                cloud.append(p + sp[1] * N + sp[2] * B)
        return np.array(cloud), pts, normals, binormals

    def calculate_faces(self, num_samples):
        n_per = len(self.transformed_points)
        faces = []
        for i in range(num_samples - 1):
            for j in range(n_per):
                nj = (j + 1) % n_per
                faces.append([
                    i * n_per + j,
                    i * n_per + nj,
                    (i + 1) * n_per + nj,
                    (i + 1) * n_per + j,
                ])
        return faces

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    def write_ply_with_vertices_and_faces(self, file_path, vertices, faces):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("ply\nformat ascii 1.0\n")
            f.write(f"element vertex {len(vertices)}\n")
            f.write("property float x\nproperty float y\nproperty float z\n")
            f.write(f"element face {len(faces)}\n")
            f.write("property list uchar int vertex_indices\nend_header\n")
            for v in vertices:
                f.write(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
            for fc in faces:
                f.write("4 " + " ".join(map(str, fc)) + "\n") 