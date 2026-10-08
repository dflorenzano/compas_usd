"""Stage creation and stage-level conventions (units, up axis, prim paths)."""

from typing import Optional
from typing import Union

from compas.tolerance import TOL
from pxr import Sdf
from pxr import Tf
from pxr import Usd
from pxr import UsdGeom

#: Metres per unit for the length units supported by :class:`compas.tolerance.Tolerance`.
METERS_PER_UNIT = {
    "M": 1.0,
    "MM": 0.001,
}


def meters_per_unit_from_unit(unit: str) -> float:
    """Return the USD ``metersPerUnit`` value for a COMPAS length unit.

    Parameters
    ----------
    unit : str
        A COMPAS length unit, i.e. one of ``"M"`` or ``"MM"`` (case-insensitive).

    Returns
    -------
    float

    Raises
    ------
    ValueError
        If the unit is not supported.

    Examples
    --------
    >>> meters_per_unit_from_unit("mm")
    0.001

    """
    try:
        return METERS_PER_UNIT[unit.upper()]
    except KeyError:
        raise ValueError("Unsupported unit: {!r}. Supported: {}".format(unit, sorted(METERS_PER_UNIT)))


def unit_from_meters_per_unit(meters_per_unit: float, tol: float = 1e-12) -> Optional[str]:
    """Return the COMPAS length unit for a USD ``metersPerUnit`` value, or ``None`` if there is no match.

    Examples
    --------
    >>> unit_from_meters_per_unit(0.001)
    'MM'
    >>> unit_from_meters_per_unit(0.01) is None
    True

    """
    for unit, value in METERS_PER_UNIT.items():
        if abs(value - meters_per_unit) <= tol:
            return unit
    return None


def create_stage(
    filepath: Optional[str] = None,
    unit: Optional[str] = None,
    up_axis: str = "Z",
    default_prim: Optional[str] = None,
) -> Usd.Stage:
    """Create a stage with explicit unit and up-axis metadata.

    Parameters
    ----------
    filepath : str, optional
        File to create. If ``None``, the stage is created in memory.
    unit : str, optional
        COMPAS length unit of the coordinates that will be written (``"M"`` or ``"MM"``).
        Defaults to the unit of the global tolerance, ``compas.tolerance.TOL.unit``.
    up_axis : {"Z", "Y"}, optional
        Stage up axis. COMPAS is Z-up.
    default_prim : str, optional
        Name of a root ``Xform`` to create and set as the stage's default prim.

    Returns
    -------
    :class:`pxr.Usd.Stage`

    Examples
    --------
    >>> stage = create_stage(unit="MM", default_prim="World")
    >>> UsdGeom.GetStageMetersPerUnit(stage)
    0.001
    >>> UsdGeom.GetStageUpAxis(stage)
    'Z'
    >>> str(stage.GetDefaultPrim().GetPath())
    '/World'

    """
    stage = Usd.Stage.CreateNew(filepath) if filepath else Usd.Stage.CreateInMemory()
    axis = up_axis.upper()
    if axis not in ("Y", "Z"):
        raise ValueError("up_axis must be 'Y' or 'Z', got {!r}".format(up_axis))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z if axis == "Z" else UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, meters_per_unit_from_unit(unit or TOL.unit))
    if default_prim:
        prim = UsdGeom.Xform.Define(stage, Sdf.Path.absoluteRootPath.AppendChild(make_valid_identifier(default_prim))).GetPrim()
        stage.SetDefaultPrim(prim)
    return stage


def stage_unit(stage: Usd.Stage) -> Optional[str]:
    """Return the COMPAS length unit of a stage, or ``None`` if its ``metersPerUnit`` has no COMPAS equivalent.

    A stage without authored ``metersPerUnit`` is in centimetres (the USD fallback), which has no COMPAS equivalent.
    """
    return unit_from_meters_per_unit(UsdGeom.GetStageMetersPerUnit(stage))


def unit_scale(stage: Usd.Stage, unit: str) -> float:
    """Return the factor that converts lengths in stage units to lengths in ``unit``.

    Examples
    --------
    >>> stage = create_stage(unit="M")
    >>> unit_scale(stage, "MM")
    1000.0

    """
    return UsdGeom.GetStageMetersPerUnit(stage) / meters_per_unit_from_unit(unit)


def make_valid_identifier(name: str) -> str:
    """Turn an arbitrary name into a valid USD prim name.

    Examples
    --------
    >>> make_valid_identifier("Block 3.1")
    'Block_3_1'
    >>> make_valid_identifier("3DCP")
    '_DCP'

    """
    return Tf.MakeValidIdentifier(name or "_")


def unique_child_path(stage: Usd.Stage, parent: Union[str, Sdf.Path], name: str) -> Sdf.Path:
    """Return ``parent/name`` made valid and unique among existing children of ``parent``.

    Examples
    --------
    >>> stage = Usd.Stage.CreateInMemory()
    >>> _ = stage.DefinePrim("/A/b")
    >>> str(unique_child_path(stage, "/A", "b"))
    '/A/b_1'

    """
    parent = Sdf.Path(parent)
    base = make_valid_identifier(name)
    path = parent.AppendChild(base)
    i = 0
    while stage.GetPrimAtPath(path):
        i += 1
        path = parent.AppendChild("{}_{}".format(base, i))
    return path
