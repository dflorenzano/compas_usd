# Examples

## Mesh with per-vertex data

```python
from compas.datastructures import Mesh
from compas_usd import create_stage
from compas_usd.conversions import prim_from_geometry, iter_geometry

mesh = Mesh.from_polyhedron(12)
for i, vertex in enumerate(mesh.vertices()):
    mesh.vertex_attribute(vertex, "stress", float(i))

stage = create_stage("mesh.usda", unit="M", default_prim="World")
prim_from_geometry(stage, "/World/mesh", mesh, vertex_attributes=["stress"])
stage.Save()

for path, obj in iter_geometry(stage, space="world", unit="MM"):
    print(path, obj)
```

## Toolpaths as curves with process data

```python
from compas.geometry import Polyline
from compas_usd import create_stage
from compas_usd.conversions import prim_from_polylines, set_primvar

layer0 = Polyline([[0, 0, 0], [1000, 0, 0], [1000, 500, 0], [0, 0, 0]])
layer1 = Polyline([[0, 0, 10], [1000, 0, 10], [1000, 500, 10], [0, 0, 10]])

stage = create_stage("toolpath.usda", unit="MM", default_prim="World")
curves = prim_from_polylines(stage, "/World/toolpath", [layer0, layer1], widths=25.0)
set_primvar(curves, "fab:velocity", [100.0] * 8)  # one per point -> vertex
set_primvar(curves, "fab:layer", [0, 1])  # one per curve -> uniform
stage.Save()
```

## compas_model models

```python
from compas_usd import create_stage
from compas_usd.conversions import prim_from_model

stage = create_stage("model.usda", unit="M", default_prim="World")
prim_from_model(stage, model)  # model: compas_model.models.Model
stage.Save()
```

## Scenes

```python
from compas.scene import Scene
from compas_usd.conversions import stage_from_scene

stage = stage_from_scene(scene, "scene.usda")
```
