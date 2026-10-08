"""Generic reading of USD prims and stages into COMPAS objects."""

from typing import Iterator
from typing import Optional

from compas.data import Data
from compas.geometry import Box
from compas.geometry import Cylinder
from compas.geometry import Scale
from compas.geometry import Sphere
from compas.geometry import Transformation
from pxr import Usd
from pxr import UsdGeom

from ..stage import unit_scale
from .geometry import mesh_from_prim
from .geometry import nurbscurve_from_prim
from .geometry import nurbssurface_from_prim
from .geometry import pointcloud_from_prim
from .geometry import polylines_from_prim
from .metadata import apply_compas_metadata
from .transformations import frame_and_scale_from_transformation
from .transformations import transformation_from_xformable

SPACES = ("object", "local", "world")


def _placement(prim: Usd.Prim, space: str) -> Transformation:
    if space == "object":
        return Transformation()
    if space == "local":
        return transformation_from_xformable(prim)
    if space == "world":
        return transformation_from_xformable(prim, world=True)
    raise ValueError("space must be one of {}, got {!r}".format(SPACES, space))


def geometry_from_prim(prim: Usd.Prim, space: str = "local", scale: float = 1.0) -> Optional[Data]:
    """Convert a geometric prim to a COMPAS object.

    Supported prim types: ``Mesh``, linear ``BasisCurves`` (→ list of polylines), ``Points``, ``Cube``,
    ``Sphere``, ``Cylinder`` (axis Z), ``NurbsCurves`` and ``NurbsPatch`` (the last two need a COMPAS NURBS plugin).

    Parameters
    ----------
    prim : :class:`pxr.Usd.Prim`
    space : {"object", "local", "world"}, optional
        ``"object"``: as authored, without any transform; ``"local"``: with the prim's own xform ops
        (relative to its parent); ``"world"``: with the full local-to-world transform.
    scale : float, optional
        Uniform scale applied after placement, e.g. :func:`compas_usd.unit_scale` to change units.

    Returns
    -------
    :class:`compas.data.Data` | list[:class:`compas.geometry.Polyline`] | None
        ``None`` for unsupported prim types. COMPAS name, GUID and attributes are restored from ``customData``.

    """
    T = Scale.from_factors([scale] * 3) * _placement(prim, space) if scale != 1.0 else _placement(prim, space)

    if prim.IsA(UsdGeom.Cube):
        size = UsdGeom.Cube(prim).GetSizeAttr().Get()
        frame, (sx, sy, sz) = frame_and_scale_from_transformation(T)
        obj = Box(sx * size, sy * size, sz * size, frame=frame)
    elif prim.IsA(UsdGeom.Sphere):
        frame, s = frame_and_scale_from_transformation(T)
        obj = Sphere(UsdGeom.Sphere(prim).GetRadiusAttr().Get() * s[0], frame=frame)
    elif prim.IsA(UsdGeom.Cylinder):
        cyl = UsdGeom.Cylinder(prim)
        if cyl.GetAxisAttr().Get() != UsdGeom.Tokens.z:
            raise NotImplementedError("Only cylinders with axis 'Z' are supported.")
        frame, (sx, _, sz) = frame_and_scale_from_transformation(T)
        obj = Cylinder(cyl.GetRadiusAttr().Get() * sx, cyl.GetHeightAttr().Get() * sz, frame=frame)
    elif prim.IsA(UsdGeom.Mesh):
        obj = mesh_from_prim(prim).transformed(T)
    elif prim.IsA(UsdGeom.BasisCurves):
        polylines = [p.transformed(T) for p in polylines_from_prim(prim)]
        for p in polylines:
            apply_compas_metadata(p, prim, guid=False)
        return polylines
    elif prim.IsA(UsdGeom.Points):
        obj = pointcloud_from_prim(prim).transformed(T)
    elif prim.IsA(UsdGeom.NurbsCurves):
        obj = nurbscurve_from_prim(prim).transformed(T)
    elif prim.IsA(UsdGeom.NurbsPatch):
        obj = nurbssurface_from_prim(prim).transformed(T)
    else:
        return None
    return apply_compas_metadata(obj, prim)


def iter_geometry(stage: Usd.Stage, space: str = "world", unit: Optional[str] = None, root: str = "/") -> Iterator[tuple]:
    """Iterate over the geometric prims of a stage and yield ``(prim_path, geometry)``.

    Parameters
    ----------
    stage : :class:`pxr.Usd.Stage`
    space : {"object", "local", "world"}, optional
    unit : str, optional
        Convert to this COMPAS unit (``"M"`` or ``"MM"``) using the stage's ``metersPerUnit``.
    root : str, optional
        Only traverse below this prim path.

    Examples
    --------
    >>> from compas_usd import create_stage
    >>> from compas_usd.conversions import prim_from_mesh
    >>> stage = create_stage(unit="M")
    >>> _ = prim_from_mesh(stage, "/World/mesh", Mesh.from_polyhedron(6))
    >>> [(path, type(obj).__name__) for path, obj in iter_geometry(stage, unit="MM")]
    [('/World/mesh', 'Mesh')]

    """
    scale = unit_scale(stage, unit) if unit else 1.0
    start = stage.GetPrimAtPath(root)
    for prim in Usd.PrimRange(start):
        if not prim.IsA(UsdGeom.Gprim):
            continue
        obj = geometry_from_prim(prim, space=space, scale=scale)
        if obj is not None:
            yield str(prim.GetPath()), obj
