# compas_usd

COMPAS wrapper for [OpenUSD](https://openusd.org) (Universal Scene Description).

- Two-way conversions between COMPAS geometry and USD prims: meshes, polylines (linear `BasisCurves`),
  points, boxes, spheres, cylinders, NURBS curves and surfaces, frames and transformations.
- Stage conventions: `upAxis`, `metersPerUnit` from COMPAS units, default prim.
- COMPAS identity (`dtype`, `guid`, `name`, `attributes`) preserved in `customData`.
- Per-point / per-face / per-curve data as primvars.
- Export of `compas.scene.Scene` and `compas_model` models as prim hierarchies.
- USD materials (`UsdPreviewSurface`, MDL).

See [Conventions](conventions.md) for the exact mapping.
