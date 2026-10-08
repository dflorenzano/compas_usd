# Conventions

## Stage

| Item | Convention |
|---|---|
| Up axis | `Z` (COMPAS) unless `create_stage(up_axis="Y")` |
| Units | `metersPerUnit` = 1.0 for `"M"`, 0.001 for `"MM"`; default `compas.tolerance.TOL.unit` |
| Default prim | optional root `Xform`, `create_stage(default_prim=...)` |
| Prim names | `Tf.MakeValidIdentifier`, de-duplicated among siblings (`name`, `name_1`, …) |

A stage without authored `metersPerUnit` is in centimetres (USD fallback); `stage_unit()` then returns `None`.

## Transformations

COMPAS matrices act on column vectors, `Gf.Matrix4d` on row vectors: `M = T^T`.
Writers author a single `xformOp:transform` (matrix) op. Readers evaluate any op stack
(`GetLocalTransformation` / `ComputeLocalToWorldTransform`).

## Geometry

| COMPAS | USD | Notes |
|---|---|---|
| `Mesh` | `Mesh` | `subdivisionScheme = "none"`; vertex attributes → `vertex` primvars, face attributes → `uniform` primvars; `leftHanded` read as reversed cycles |
| `Polyline` / list of `Polyline` | `BasisCurves` | `type = linear`, `wrap = nonperiodic`; points written as given (closed polylines keep the repeated end point); `periodic` curves read back closed |
| `Pointcloud`, list of points | `Points` | optional `widths` |
| `Box` | `Cube` | `size = 1`, placement × scale in the matrix op |
| `Sphere` | `Sphere` | |
| `Cylinder` | `Cylinder` | `axis = Z` of the cylinder frame |
| `Frame` | `Xform` | |
| `NurbsCurve` | `NurbsCurves` | one curve; knot vector expanded from knots × multiplicities; non-periodic only |
| `NurbsSurface` | `NurbsPatch` | control point `(i, j)` (i along U) at index `i + j * nu` (U varies fastest); non-periodic only |

Reading NURBS objects requires a COMPAS NURBS plugin (compas_occ, Rhino); `*_parameters_from_prim` works without.

USD `points` are 32-bit floats (≈7 significant digits). At millimetre scale this resolves 0.001 mm up to 10 m.

### Placement when reading

`geometry_from_prim(prim, space=...)` and `iter_geometry(stage, space=...)`:

- `"object"`: authored coordinates, no transform.
- `"local"`: including the prim's own xform ops (relative to its parent). This is what `box_from_prim` etc. return.
- `"world"`: full local-to-world transform.

`iter_geometry(stage, unit="MM")` additionally rescales from the stage unit.

## Identity

```
customData = {
    dictionary compas = {
        string dtype = "compas.datastructures/Mesh"
        string guid = "…"
        string name = "…"
        string attributes = "{…}"   # JSON via compas.json_dumps
    }
}
```

`geometry_from_prim` restores `name`, `guid` and `attributes`.

## Primvars

`set_primvar(gprim, name, values, interpolation=None)`:

| Python value | USD type |
|---|---|
| `bool` | `bool[]` |
| `int` | `int[]` |
| `float` | `double[]` |
| `str` | `string[]` |
| 2/3/4-tuples | `double2[]` / `double3[]` / `double4[]` |

Interpolation is inferred when omitted: one value → `constant`, one per point → `vertex`, one per face/curve → `uniform`.
Namespaced names (`"fab:velocity"`) are allowed.

## compas_model

```
/<Model>             Xform   model.transformation
  /<element>         Xform   element.transformation
    /geometry        Mesh    element geometry in element-local coordinates
    /<child>         Xform   …
```

Nested Xforms compose like `Element.compute_modeltransformation`. With `geometry="model"` (default) the
geometry includes modifiers (`modelgeometry`), mapped back to element-local coordinates.
