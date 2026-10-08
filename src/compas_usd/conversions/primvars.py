"""Primvars: per-prim, per-curve/face, or per-point data arrays on geometric prims."""

from typing import Any
from typing import Optional
from typing import Sequence

from pxr import Sdf
from pxr import UsdGeom

_SCALAR_TYPES = (
    (bool, Sdf.ValueTypeNames.BoolArray),
    (int, Sdf.ValueTypeNames.IntArray),
    (float, Sdf.ValueTypeNames.DoubleArray),
    (str, Sdf.ValueTypeNames.StringArray),
)
_TUPLE_TYPES = {
    2: Sdf.ValueTypeNames.Double2Array,
    3: Sdf.ValueTypeNames.Double3Array,
    4: Sdf.ValueTypeNames.Double4Array,
}


def _is_sequence(value: Any) -> bool:
    return isinstance(value, (list, tuple)) or (hasattr(value, "__len__") and hasattr(value, "__getitem__") and not isinstance(value, str))


def _infer_type_name(values: Sequence[Any]) -> Sdf.ValueTypeName:
    first = values[0]
    if _is_sequence(first):
        try:
            return _TUPLE_TYPES[len(first)]
        except KeyError:
            raise TypeError("Cannot infer a primvar type for tuples of length {}".format(len(first)))
    for pytype, type_name in _SCALAR_TYPES:  # bool before int: bool is a subclass of int
        if isinstance(first, pytype):
            return type_name
    if hasattr(first, "item"):  # numpy scalar
        return _infer_type_name([first.item()])
    raise TypeError("Cannot infer a primvar type for values of type {}".format(type(first).__name__))


def element_counts(gprim: UsdGeom.Gprim) -> dict:
    """Return the number of elements per interpolation for a gprim.

    Only the interpolations that are unambiguous for the prim type are included.
    """
    counts = {"constant": 1}
    prim = gprim.GetPrim()
    if prim.IsA(UsdGeom.PointBased):
        points = UsdGeom.PointBased(prim).GetPointsAttr().Get() or []
        counts["vertex"] = len(points)
    if prim.IsA(UsdGeom.Mesh):
        counts["uniform"] = len(UsdGeom.Mesh(prim).GetFaceVertexCountsAttr().Get() or [])
        counts["faceVarying"] = len(UsdGeom.Mesh(prim).GetFaceVertexIndicesAttr().Get() or [])
    elif prim.IsA(UsdGeom.Curves):
        curves = UsdGeom.Curves(prim)
        counts["uniform"] = len(curves.GetCurveVertexCountsAttr().Get() or [])
        if prim.IsA(UsdGeom.BasisCurves) and UsdGeom.BasisCurves(prim).GetTypeAttr().Get() == UsdGeom.Tokens.linear:
            counts["varying"] = counts["vertex"]
    elif prim.IsA(UsdGeom.Points):
        counts["varying"] = counts["vertex"]
    return counts


def _infer_interpolation(gprim: UsdGeom.Gprim, n: int) -> str:
    matches = [k for k, v in element_counts(gprim).items() if v == n and k not in ("varying", "faceVarying")]
    if n == 1 and "constant" in matches:
        return "constant"
    for candidate in ("vertex", "uniform"):
        if candidate in matches:
            return candidate
    raise ValueError("Cannot infer interpolation for {} values on {}; pass interpolation explicitly.".format(n, gprim.GetPath()))


def set_primvar(
    gprim: UsdGeom.Gprim,
    name: str,
    values: Any,
    interpolation: Optional[str] = None,
    type_name: Optional[Sdf.ValueTypeName] = None,
) -> UsdGeom.Primvar:
    """Create or overwrite a primvar.

    Parameters
    ----------
    gprim : :class:`pxr.UsdGeom.Gprim`
        A geometric prim (Mesh, BasisCurves, Points, ...).
    name : str
        Primvar name, without the ``primvars:`` prefix. Namespaces are allowed (``"fab:velocity"``).
    values : scalar or sequence
        A scalar is written as a ``constant`` primvar. A sequence is written as an array;
        elements that are sequences of length 2–4 become ``double2/3/4`` values.
        For a constant vector, pass a one-element list, e.g. ``[(0, 0, 1)]``.
    interpolation : str, optional
        ``"constant"``, ``"uniform"``, ``"varying"``, ``"vertex"`` or ``"faceVarying"``.
        If omitted, inferred from the number of values: one per point → ``vertex``, one per face/curve → ``uniform``.
    type_name : :class:`pxr.Sdf.ValueTypeName`, optional
        Explicit value type, e.g. ``Sdf.ValueTypeNames.FloatArray``.

    Returns
    -------
    :class:`pxr.UsdGeom.Primvar`

    Examples
    --------
    >>> from pxr import Usd
    >>> from compas_usd.conversions import prim_from_polylines
    >>> stage = Usd.Stage.CreateInMemory()
    >>> curves = prim_from_polylines(stage, "/path", [Polyline([[0, 0, 0], [1, 0, 0], [2, 0, 0]])])
    >>> pv = set_primvar(curves, "velocity", [10.0, 12.0, 14.0])
    >>> pv.GetInterpolation()
    'vertex'
    >>> get_primvars(curves)["velocity"]
    ([10.0, 12.0, 14.0], 'vertex')

    """
    if not _is_sequence(values):
        values = [values]
        interpolation = interpolation or "constant"
    values = list(values)
    if not values:
        raise ValueError("Cannot write an empty primvar.")
    if hasattr(values[0], "tolist"):
        values = [v.tolist() for v in values]
    if type_name is None:
        type_name = _infer_type_name(values)
    if interpolation is None:
        interpolation = _infer_interpolation(gprim, len(values))
    api = UsdGeom.PrimvarsAPI(gprim.GetPrim())
    primvar = api.CreatePrimvar(name, type_name, interpolation)
    primvar.Set([tuple(v) if _is_sequence(v) else v for v in values])
    return primvar


def get_primvars(gprim: UsdGeom.Gprim, include_builtin: bool = False) -> dict:
    """Return the authored primvars of a gprim as ``{name: (values, interpolation)}``.

    Values are converted to Python lists; vector elements become tuples.

    Parameters
    ----------
    gprim : :class:`pxr.UsdGeom.Gprim`
    include_builtin : bool, optional
        Include ``displayColor``, ``displayOpacity`` and ``st``.

    """
    builtin = {"displayColor", "displayOpacity", "st"}
    result = {}
    for primvar in UsdGeom.PrimvarsAPI(gprim.GetPrim()).GetAuthoredPrimvars():
        name = primvar.GetPrimvarName()
        if not include_builtin and name in builtin:
            continue
        value = primvar.Get()
        if value is None:
            continue
        if primvar.IsIndexed():
            value = primvar.ComputeFlattened()
        values = [_element(v) for v in value] if hasattr(value, "__len__") and not isinstance(value, str) else [_element(value)]
        result[str(name)] = (values, primvar.GetInterpolation())
    return result


def _element(value: Any) -> Any:
    if isinstance(value, (str, bool, int, float)):
        return value
    if type(value).__module__.startswith("pxr.Gf"):
        return tuple(float(v) for v in value)
    return value
