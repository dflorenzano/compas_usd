import compas
from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Sphere
from compas.geometry import Translation
from compas.scene import Scene

from compas_usd.conversions import stage_from_scene

scene = Scene()
group1 = scene.add_group(name="Boxes")
group2 = scene.add_group(name="Spheres", transformation=Translation.from_vector([0, 5, 0]))

mesh = Mesh.from_obj(compas.get("tubemesh.obj"))
mesh.flip_cycles()
scene.add(mesh, name="MeshObj", transformation=Translation.from_vector([-5, 0, 0]))

for i in range(5):
    group1.add(Box(0.5), name=f"Box{i}", transformation=Translation.from_vector([i, 0, 0]))
    group2.add(Sphere(0.5), name=f"Sphere{i}", transformation=Translation.from_vector([i, 0, 0]))

print(scene)

stage = stage_from_scene(scene, "temp/scene.usda")
print(stage)
