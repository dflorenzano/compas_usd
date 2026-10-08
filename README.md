# COMPAS USD

COMPAS wrapper for [OpenUSD](https://openusd.org) (Universal Scene Description).

- Two-way conversions between COMPAS geometry and USD prims (meshes, polylines, points, primitives, NURBS, transformations)
- Stage conventions (up axis, `metersPerUnit`, default prim)
- COMPAS identity and attributes in `customData`; per-element data as primvars
- Export of `compas.scene.Scene` and `compas_model` models
- USD materials (`UsdPreviewSurface`, MDL)

## Installation

```bash
pip install -e .
```

For development:

```bash
pip install -e ".[dev]"
invoke test
```

## Documentation

See `docs/` ([Conventions](docs/conventions.md), [Examples](docs/examples.md)).
