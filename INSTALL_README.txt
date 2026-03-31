cd main folder
conda env create -f Orbit_Environment.yml


The QTWebengine can be problematic. For a windows machine, the yml should work fine. 

If the 3D view fails with an error like:
RuntimeError: No Qt binding was found, got: No module named 'qtpy'

then the application is running in a Python environment that misses `qtpy`.
Install the missing runtime packages in the same interpreter that launches ORBIT:

python -m pip install qtpy pyvistaqt

Then restart ORBIT.