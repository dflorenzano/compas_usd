# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

* `compas_usd.create_stage` with `upAxis`, `metersPerUnit` (from COMPAS units) and default prim; `stage_unit`, `unit_scale`, `meters_per_unit_from_unit`, `unit_from_meters_per_unit`, `make_valid_identifier`, `unique_child_path`.
* Readers: `mesh_from_prim`, `sphere_from_prim`, `cylinder_from_prim`, `polylines_from_prim`, `points_from_prim`, `pointcloud_from_prim`, `nurbscurve_from_prim`, `nurbssurface_from_prim`, `nurbscurve_parameters_from_prim`, `nurbssurface_parameters_from_prim`.
* Writers: `prim_from_polyline`, `prim_from_polylines` (linear `BasisCurves`), `prim_from_points`, `prim_from_pointcloud`, `prim_from_frame`, `prim_from_nurbscurve`, `prim_from_nurbssurface`, `prim_from_geometry` (type dispatch).
* Mesh vertex/face attributes as `vertex`/`uniform` primvars, both ways.
* `set_primvar`, `get_primvars` with type and interpolation inference.
* COMPAS identity in `customData`: `set_compas_metadata`, `get_compas_metadata`, `apply_compas_metadata`.
* `geometry_from_prim` and `iter_geometry` with `"object" | "local" | "world"` placement and unit conversion.
* `prim_from_model`, `prim_from_element` for `compas_model` models.
* `transformation_from_xformable`, `frame_and_scale_from_transformation`.
* Tests for all conversions; docs on conventions.

### Changed

* Packaging: `pyproject.toml` (COMPAS cookiecutter), ruff, `compas_invocations2`, mkdocs; Python >= 3.9; `usd-core >= 24.5`, `compas >= 2.4`.
* CI runs on `master` (workflows previously triggered on `main` only) with Python 3.9–3.13.
* Writers author a single `xformOp:transform` matrix op instead of `XformCommonAPI` Euler angles.
* `box_from_prim` and `frame_and_scale_from_prim` decompose the full local transformation, so they read any xform op stack.
* `prim_from_mesh` sets `subdivisionScheme = "none"` (USD's fallback, `catmullClark`, renders the mesh smoothed) and writes `extent`.
* `stage_from_scene(scene, filepath=None, unit=None, save=True)`: writes stage metadata, default prim, unique valid prim names, COMPAS identity; supports all `prim_from_geometry` types.
* Root `conftest.py` rewritten for pytest 8; `test_shading` writes to a temp dir and uses `UsdGeom.PrimvarsAPI`.

### Fixed

* `xform_rotate_from_frame` / `apply_rotate_and_translate_on_prim` used rotating (intrinsic) Euler angles for USD's `rotateXYZ`, which is static (extrinsic); rotated frames were placed wrongly.
* `prim_from_surface` used the COMPAS 1 `NurbsSurface` API (`degree`, `knot_vector`, `count`, `control_points`); now `prim_from_nurbssurface` on the COMPAS 2 API.
* Mutable default arguments in `prim_from_sceneobject` / `prim_from_item`.

### Removed

* `setup.py`, `setup.cfg`, `.bumpversion.cfg`, `MANIFEST.in`, Sphinx docs sources, `src/compas_usd/conftest.py`.
