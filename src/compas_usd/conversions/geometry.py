"""Conversions between COMPAS geometry and USD geometric prims.

Writers are named ``prim_from_<type>(stage, path, obj, ...)`` and return the typed USD schema object
(e.g. ``UsdGeom.Mesh``). Readers are named ``<type>_from_prim(prim, ...)``.

Readers return geometry in the prim's *object space* (raw ``points``), except for the implicit primitives
(Cube, Sphere, Cylinder), whose size and placement are only defined together with the prim's own xform ops;
those readers include the prim's local transformation, as ``box_from_prim`` always did.
Use :func:`compas_usd.conversions.geometry_from_prim` for consistent ``"object" | "local" | "world"`` placement.

Note: USD stores ``points`` as 32-bit floats (``point3f[]``), about 7 significant digits.
"""

from typing import Optional
from typing import Sequence
from typing import Union

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Cylinder
from compas.geometry import Frame
from compas.geometry import NurbsCurve
from compas.geometry import NurbsSurface
from compas.geometry import Point
from compas.geometry import Pointcloud
from compas.geometry import Polyline
from compas.geometry import Scale
from compas.geometry import Sphere
from compas.geometry import Transformation
from pxr import Gf
from pxr import Usd
from pxr import UsdGeom
from pxr import Vt

from .primvars import set_primvar
from .transformations import apply_transformation_on_prim
from .transformations import frame_and_scale_from_prim

PathLike = Union[str, "Sdf.Path"]  # noqa: F821


def unflatten(array: Sequence, n: int) -> list:
    """Split a flat sequence into consecutive chunks of length ``n``."""
    if len(array) % n:
        raise ValueError("The length of the array must be a multiple of n: %d %% %d != 0" % (len(array), n))
    return [array[i : (i + n)] for i in range(0, len(array), n)]


def _vec3f_array(points) -> Vt.Vec3fArray:
    return Vt.Vec3fArray([Gf.Vec3f(float(x), float(y), float(z)) for x, y, z in points])


def _extent(points) -> Vt.Vec3fArray:
    xs, ys, zs = zip(*points)
    return Vt.Vec3fArray([Gf.Vec3f(min(xs), min(ys), min(zs)), Gf.Vec3f(max(xs), max(ys), max(zs))])


def _points(attr) -> list:
    return [[float(c) for c in p] for p in (attr.Get() or [])]


def _set_widths(gprim, widths, n_points: int, n_curves: Optional[int] = None) -> None:
    if widths is None:
        return
    if isinstance(widths, (int, float)):
        gprim.CreateWidthsAttr([float(widths)])
        gprim.SetWidthsInterpolation(UsdGeom.Tokens.constant)
        return
    widths = [float(w) for w in widths]
    gprim.CreateWidthsAttr(widths)
    if len(widths) == n_points:
        gprim.SetWidthsInterpolation(UsdGeom.Tokens.vertex)
    elif n_curves is not None and len(widths) == n_curves:
        gprim.SetWidthsInterpolation(UsdGeom.Tokens.uniform)
    else:
        raise ValueError("widths must be a number, or have one value per point or per curve.")


# =============================================================================
# Implicit primitives
# =============================================================================


def prim_from_box(stage: Usd.Stage, path: PathLike, box: Box) -> UsdGeom.Cube:
    """Write a box as a ``UsdGeom.Cube`` of size 1, scaled and placed by a single matrix xform op.

    Examples
    --------
    >>> box = Box(1, 2, 3, frame=Frame([1, 2, 3], [0, 1, 0], [-1, 0, 0]))
    >>> cube = prim_from_box(stage, "/box", box)
    >>> b = box_from_prim(cube)
    >>> [round(v, 6) for v in (b.xsize, b.ysize, b.zsize)]
    [1.0, 2.0, 3.0]
    >>> b.frame.point
    Point(x=1.0, y=2.0, z=3.0)

    """
    prim = UsdGeom.Cube.Define(stage, path)
    prim.CreateSizeAttr(1.0)
    prim.CreateExtentAttr([(-0.5, -0.5, -0.5), (0.5, 0.5, 0.5)])
    apply_transformation_on_prim(prim, Transformation.from_frame(box.frame) * Scale.from_factors([box.xsize, box.ysize, box.zsize]))
    return prim


def box_from_prim(prim) -> Box:
    """Read a ``UsdGeom.Cube`` as a box, including the prim's local transformation."""
    size = UsdGeom.Cube(prim).GetSizeAttr().Get()
    frame, (sx, sy, sz) = frame_and_scale_from_prim(prim)
    return Box(sx * size, sy * size, sz * size, frame=frame)


def prim_from_sphere(stage: Usd.Stage, path: PathLike, sphere: Sphere) -> UsdGeom.Sphere:
    """Write a sphere as a ``UsdGeom.Sphere``.

    Examples
    --------
    >>> s = sphere_from_prim(prim_from_sphere(stage, "/sphere", Sphere(5, point=[1, 2, 3])))
    >>> s.radius, s.frame.point
    (5.0, Point(x=1.0, y=2.0, z=3.0))

    """
    prim = UsdGeom.Sphere.Define(stage, path)
    prim.CreateRadiusAttr(float(sphere.radius))
    r = float(sphere.radius)
    prim.CreateExtentAttr([(-r, -r, -r), (r, r, r)])
    apply_transformation_on_prim(prim, Transformation.from_frame(sphere.frame))
    return prim


def sphere_from_prim(prim) -> Sphere:
    """Read a ``UsdGeom.Sphere``, including the prim's local transformation (uniform scale assumed)."""
    radius = UsdGeom.Sphere(prim).GetRadiusAttr().Get()
    frame, scale = frame_and_scale_from_prim(prim)
    return Sphere(radius * scale[0], frame=frame)


def prim_from_cylinder(stage: Usd.Stage, path: PathLike, cylinder: Cylinder) -> UsdGeom.Cylinder:
    """Write a cylinder as a ``UsdGeom.Cylinder`` with axis along the local Z of the cylinder frame.

    Examples
    --------
    >>> c = cylinder_from_prim(prim_from_cylinder(stage, "/cyl", Cylinder(0.5, 2.0)))
    >>> c.radius, c.height
    (0.5, 2.0)

    """
    prim = UsdGeom.Cylinder.Define(stage, path)
    prim.CreateHeightAttr(float(cylinder.height))
    prim.CreateRadiusAttr(float(cylinder.radius))
    prim.CreateAxisAttr(UsdGeom.Tokens.z)
    r, h = float(cylinder.radius), float(cylinder.height)
    prim.CreateExtentAttr([(-r, -r, -h / 2), (r, r, h / 2)])
    apply_transformation_on_prim(prim, Transformation.from_frame(cylinder.frame))
    return prim


def cylinder_from_prim(prim) -> Cylinder:
    """Read a ``UsdGeom.Cylinder`` (axis ``Z`` only), including the prim's local transformation."""
    cyl = UsdGeom.Cylinder(prim)
    if cyl.GetAxisAttr().Get() != UsdGeom.Tokens.z:
        raise NotImplementedError("Only cylinders with axis 'Z' are supported.")
    frame, (sx, _, sz) = frame_and_scale_from_prim(prim)
    return Cylinder(cyl.GetRadiusAttr().Get() * sx, cyl.GetHeightAttr().Get() * sz, frame=frame)


# =============================================================================
# Transform-only prims
# =============================================================================


def prim_from_transformation(stage: Usd.Stage, path: PathLike, transformation: Optional[Transformation] = None) -> UsdGeom.Xform:
    """Define a ``UsdGeom.Xform`` holding a transformation.

    Examples
    --------
    >>> prim_from_transformation(stage, "/xform", Transformation())
    UsdGeom.Xform(Usd.Prim(</xform>))

    """
    prim = UsdGeom.Xform.Define(stage, path)
    if transformation is not None:
        apply_transformation_on_prim(prim, transformation)
    return prim


def prim_default(stage: Usd.Stage, path: PathLike, transformation: Optional[Transformation] = None) -> UsdGeom.Xform:
    """Deprecated alias of :func:`prim_from_transformation`."""
    return prim_from_transformation(stage, path, transformation)


def prim_from_frame(stage: Usd.Stage, path: PathLike, frame: Frame) -> UsdGeom.Xform:
    """Define a ``UsdGeom.Xform`` whose local coordinate system is ``frame``."""
    return prim_from_transformation(stage, path, Transformation.from_frame(frame))


# =============================================================================
# Mesh
# =============================================================================


def prim_from_mesh(
    stage: Usd.Stage,
    path: PathLike,
    mesh: Mesh,
    vertex_attributes: Optional[Sequence[str]] = None,
    face_attributes: Optional[Sequence[str]] = None,
    subdivision: str = "none",
) -> UsdGeom.Mesh:
    """Write a mesh as a ``UsdGeom.Mesh``.

    Parameters
    ----------
    stage : :class:`pxr.Usd.Stage`
    path : str
    mesh : :class:`compas.datastructures.Mesh`
    vertex_attributes : list[str], optional
        Vertex attribute names written as ``vertex`` primvars.
    face_attributes : list[str], optional
        Face attribute names written as ``uniform`` primvars.
    subdivision : str, optional
        ``subdivisionScheme``. Defaults to ``"none"`` (polygonal); USD's fallback, ``catmullClark``, would smooth the mesh.

    Examples
    --------
    >>> mesh = Mesh.from_polyhedron(6)
    >>> m = prim_from_mesh(stage, "/mesh", mesh)
    >>> other = mesh_from_prim(m)
    >>> other.number_of_vertices(), other.number_of_faces()
    (8, 6)

    """
    prim = UsdGeom.Mesh.Define(stage, path)
    vertices, faces = mesh.to_vertices_and_faces()
    prim.CreatePointsAttr(_vec3f_array(vertices))
    prim.CreateFaceVertexCountsAttr([len(f) for f in faces])
    prim.CreateFaceVertexIndicesAttr([i for f in faces for i in f])
    prim.CreateExtentAttr(_extent(vertices))
    prim.CreateSubdivisionSchemeAttr(subdivision)
    for name in vertex_attributes or []:
        set_primvar(prim, name, mesh.vertices_attribute(name), interpolation="vertex")
    for name in face_attributes or []:
        set_primvar(prim, name, mesh.faces_attribute(name), interpolation="uniform")
    return prim


def mesh_from_prim(prim, attributes: bool = True) -> Mesh:
    """Read a ``UsdGeom.Mesh`` in object space.

    Parameters
    ----------
    prim : :class:`pxr.Usd.Prim` or :class:`pxr.UsdGeom.Mesh`
    attributes : bool, optional
        Read ``vertex`` primvars into vertex attributes and ``uniform`` primvars into face attributes.

    Notes
    -----
    ``leftHanded`` meshes are converted to COMPAS' counter-clockwise convention by reversing face cycles.
    Holes (``holeIndices``) are ignored.

    """
    from .primvars import get_primvars

    usdmesh = UsdGeom.Mesh(prim)
    vertices = _points(usdmesh.GetPointsAttr())
    counts = list(usdmesh.GetFaceVertexCountsAttr().Get() or [])
    indices = list(usdmesh.GetFaceVertexIndicesAttr().Get() or [])
    faces = []
    i = 0
    for n in counts:
        faces.append(indices[i : i + n])
        i += n
    if usdmesh.GetOrientationAttr().Get() == UsdGeom.Tokens.leftHanded:
        faces = [f[::-1] for f in faces]
    mesh = Mesh.from_vertices_and_faces(vertices, faces)
    if attributes:
        vkeys = list(mesh.vertices())
        fkeys = list(mesh.faces())
        for name, (values, interpolation) in get_primvars(usdmesh).items():
            if interpolation == "vertex" and len(values) == len(vkeys):
                for key, value in zip(vkeys, values):
                    mesh.vertex_attribute(key, name, value)
            elif interpolation == "uniform" and len(values) == len(fkeys):
                for key, value in zip(fkeys, values):
                    mesh.face_attribute(key, name, value)
    return mesh


# =============================================================================
# Curves (polylines) and points
# =============================================================================


def prim_from_polylines(
    stage: Usd.Stage,
    path: PathLike,
    polylines: Sequence[Polyline],
    widths: Optional[Union[float, Sequence[float]]] = None,
) -> UsdGeom.BasisCurves:
    """Write polylines as one ``UsdGeom.BasisCurves`` prim with ``type = linear`` and ``wrap = nonperiodic``.

    Points are written as given: a closed polyline keeps its repeated end point, so order and
    closure survive the round trip exactly.

    Parameters
    ----------
    stage : :class:`pxr.Usd.Stage`
    path : str
    polylines : list[:class:`compas.geometry.Polyline`]
    widths : float or list[float], optional
        One value (constant), one per point (vertex) or one per polyline (uniform).

    Examples
    --------
    >>> a = Polyline([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 0, 0]])
    >>> b = Polyline([[0, 0, 1], [2, 0, 1]])
    >>> curves = prim_from_polylines(stage, "/paths", [a, b], widths=0.025)
    >>> [len(p.points) for p in polylines_from_prim(curves)]
    [4, 2]

    """
    if not polylines:
        raise ValueError("No polylines given.")
    prim = UsdGeom.BasisCurves.Define(stage, path)
    points = [list(p) for polyline in polylines for p in polyline.points]
    prim.CreateTypeAttr(UsdGeom.Tokens.linear)
    prim.CreateWrapAttr(UsdGeom.Tokens.nonperiodic)
    prim.CreateCurveVertexCountsAttr([len(polyline.points) for polyline in polylines])
    prim.CreatePointsAttr(_vec3f_array(points))
    prim.CreateExtentAttr(_extent(points))
    _set_widths(prim, widths, len(points), len(polylines))
    return prim


def prim_from_polyline(stage: Usd.Stage, path: PathLike, polyline: Polyline, widths=None) -> UsdGeom.BasisCurves:
    """Write a single polyline as a linear ``UsdGeom.BasisCurves``. See :func:`prim_from_polylines`."""
    return prim_from_polylines(stage, path, [polyline], widths=widths)


def polylines_from_prim(prim) -> list:
    """Read a linear ``UsdGeom.BasisCurves`` prim as polylines (object space).

    ``periodic`` curves are closed by repeating their first point.

    Raises
    ------
    ValueError
        If the curves are not linear.

    """
    curves = UsdGeom.BasisCurves(prim)
    if curves.GetTypeAttr().Get() != UsdGeom.Tokens.linear:
        raise ValueError("Only linear BasisCurves can be read as polylines.")
    periodic = curves.GetWrapAttr().Get() == UsdGeom.Tokens.periodic
    points = _points(curves.GetPointsAttr())
    polylines = []
    i = 0
    for n in curves.GetCurveVertexCountsAttr().Get() or []:
        chunk = points[i : i + n]
        if periodic:
            chunk = chunk + [chunk[0]]
        polylines.append(Polyline(chunk))
        i += n
    return polylines


def prim_from_points(stage: Usd.Stage, path: PathLike, points: Sequence, widths=None) -> UsdGeom.Points:
    """Write points as a ``UsdGeom.Points`` prim.

    Examples
    --------
    >>> pts = points_from_prim(prim_from_points(stage, "/pts", [[0, 0, 0], [1, 2, 3]], widths=0.1))
    >>> pts[1]
    Point(x=1.0, y=2.0, z=3.0)

    """
    points = [list(p) for p in points]
    prim = UsdGeom.Points.Define(stage, path)
    prim.CreatePointsAttr(_vec3f_array(points))
    prim.CreateExtentAttr(_extent(points))
    _set_widths(prim, widths, len(points))
    return prim


def points_from_prim(prim) -> list:
    """Read the ``points`` of any point-based prim (object space)."""
    return [Point(*p) for p in _points(UsdGeom.PointBased(prim).GetPointsAttr())]


def prim_from_pointcloud(stage: Usd.Stage, path: PathLike, pointcloud: Pointcloud, widths=None) -> UsdGeom.Points:
    """Write a pointcloud as a ``UsdGeom.Points`` prim."""
    return prim_from_points(stage, path, pointcloud.points, widths=widths)


def pointcloud_from_prim(prim) -> Pointcloud:
    """Read a ``UsdGeom.Points`` prim as a pointcloud (object space)."""
    return Pointcloud(points_from_prim(prim))


# =============================================================================
# NURBS
# =============================================================================


def _knotvector(knots, multiplicities) -> list:
    return [float(k) for k, m in zip(knots, multiplicities) for _ in range(m)]


def _knots_and_multiplicities(knotvector, tol: float = 1e-12) -> tuple:
    knots, mults = [], []
    for k in knotvector:
        if knots and abs(k - knots[-1]) <= tol:
            mults[-1] += 1
        else:
            knots.append(float(k))
            mults.append(1)
    return knots, mults


def prim_from_nurbscurve(stage: Usd.Stage, path: PathLike, curve: NurbsCurve) -> UsdGeom.NurbsCurves:
    """Write a non-periodic NURBS curve as a ``UsdGeom.NurbsCurves`` prim with one curve.

    The knot vector is expanded from ``curve.knots`` and ``curve.multiplicities``; USD requires
    ``len(knots) == len(points) + order``.
    """
    if curve.is_periodic:
        raise NotImplementedError("Periodic NURBS curves are not supported.")
    points = [list(p) for p in curve.points]
    knots = _knotvector(curve.knots, curve.multiplicities)
    if len(knots) != len(points) + curve.degree + 1:
        raise ValueError("Knot vector length {} != number of points + order ({}).".format(len(knots), len(points) + curve.degree + 1))
    prim = UsdGeom.NurbsCurves.Define(stage, path)
    prim.CreateCurveVertexCountsAttr([len(points)])
    prim.CreateOrderAttr([curve.degree + 1])
    prim.CreateKnotsAttr(knots)
    prim.CreatePointsAttr(_vec3f_array(points))
    prim.CreatePointWeightsAttr([float(w) for w in curve.weights])
    prim.CreateRangesAttr([(knots[curve.degree], knots[-curve.degree - 1])])
    prim.CreateExtentAttr(_extent(points))
    return prim


def nurbscurve_parameters_from_prim(prim) -> dict:
    """Read the parameters of the first curve of a ``UsdGeom.NurbsCurves`` prim, in the form of ``NurbsCurve.from_parameters``."""
    nc = UsdGeom.NurbsCurves(prim)
    counts = nc.GetCurveVertexCountsAttr().Get()
    if len(counts) != 1:
        raise NotImplementedError("Only NurbsCurves prims with a single curve are supported.")
    order = nc.GetOrderAttr().Get()[0]
    points = [Point(*p) for p in _points(nc.GetPointsAttr())]
    weights = list(nc.GetPointWeightsAttr().Get() or [1.0] * len(points))
    knots, mults = _knots_and_multiplicities(list(nc.GetKnotsAttr().Get()))
    return {"points": points, "weights": weights, "knots": knots, "multiplicities": mults, "degree": order - 1}


def nurbscurve_from_prim(prim) -> NurbsCurve:
    """Read a single-curve ``UsdGeom.NurbsCurves`` prim. Requires a COMPAS NURBS plugin (e.g. compas_occ or Rhino)."""
    return NurbsCurve.from_parameters(**nurbscurve_parameters_from_prim(prim))


def prim_from_nurbssurface(stage: Usd.Stage, path: PathLike, surface: NurbsSurface) -> UsdGeom.NurbsPatch:
    """Write a non-periodic NURBS surface as a ``UsdGeom.NurbsPatch``.

    ``surface.points[i][j]`` is the control point ``i`` along U and ``j`` along V.
    USD stores control points with U varying fastest, so point ``(i, j)`` goes to index ``i + j * nu``.
    """
    if getattr(surface, "is_periodic_u", False) or getattr(surface, "is_periodic_v", False):
        raise NotImplementedError("Periodic NURBS surfaces are not supported.")
    grid = [[list(p) for p in row] for row in surface.points]
    weights = [list(row) for row in surface.weights]
    nu, nv = len(grid), len(grid[0])
    points = [grid[i][j] for j in range(nv) for i in range(nu)]
    flat_weights = [float(weights[i][j]) for j in range(nv) for i in range(nu)]
    knots_u = _knotvector(surface.knots_u, surface.mults_u)
    knots_v = _knotvector(surface.knots_v, surface.mults_v)
    prim = UsdGeom.NurbsPatch.Define(stage, path)
    prim.CreateUVertexCountAttr(nu)
    prim.CreateVVertexCountAttr(nv)
    prim.CreateUOrderAttr(surface.degree_u + 1)
    prim.CreateVOrderAttr(surface.degree_v + 1)
    prim.CreateUKnotsAttr(knots_u)
    prim.CreateVKnotsAttr(knots_v)
    prim.CreatePointsAttr(_vec3f_array(points))
    prim.CreatePointWeightsAttr(flat_weights)
    prim.CreateExtentAttr(_extent(points))
    return prim


prim_from_surface = prim_from_nurbssurface


def nurbssurface_parameters_from_prim(prim) -> dict:
    """Read a ``UsdGeom.NurbsPatch`` into the keyword arguments of ``NurbsSurface.from_parameters``."""
    patch = UsdGeom.NurbsPatch(prim)
    nu = patch.GetUVertexCountAttr().Get()
    nv = patch.GetVVertexCountAttr().Get()
    flat = _points(patch.GetPointsAttr())
    flat_w = list(patch.GetPointWeightsAttr().Get() or [1.0] * len(flat))
    points = [[Point(*flat[i + j * nu]) for j in range(nv)] for i in range(nu)]
    weights = [[flat_w[i + j * nu] for j in range(nv)] for i in range(nu)]
    knots_u, mults_u = _knots_and_multiplicities(list(patch.GetUKnotsAttr().Get()))
    knots_v, mults_v = _knots_and_multiplicities(list(patch.GetVKnotsAttr().Get()))
    return {
        "points": points,
        "weights": weights,
        "knots_u": knots_u,
        "knots_v": knots_v,
        "mults_u": mults_u,
        "mults_v": mults_v,
        "degree_u": patch.GetUOrderAttr().Get() - 1,
        "degree_v": patch.GetVOrderAttr().Get() - 1,
    }


def nurbssurface_from_prim(prim) -> NurbsSurface:
    """Read a ``UsdGeom.NurbsPatch``. Requires a COMPAS NURBS plugin (e.g. compas_occ or Rhino)."""
    return NurbsSurface.from_parameters(**nurbssurface_parameters_from_prim(prim))
