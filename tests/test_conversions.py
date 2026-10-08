import os

import pytest
from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Cylinder
from compas.geometry import Frame
from compas.geometry import Point
from compas.geometry import Pointcloud
from compas.geometry import Polyline
from compas.geometry import Rotation
from compas.geometry import Sphere
from compas.geometry import Transformation
from compas.geometry import Translation
from compas.geometry import allclose
from pxr import Gf
from pxr import Usd
from pxr import UsdGeom

from compas_usd import create_stage
from compas_usd import stage_unit
from compas_usd import unit_scale
from compas_usd.conversions import apply_rotate_and_translate_on_prim
from compas_usd.conversions import box_from_prim
from compas_usd.conversions import geometry_from_prim
from compas_usd.conversions import get_compas_metadata
from compas_usd.conversions import get_primvars
from compas_usd.conversions import gfmatrix4d_from_transformation
from compas_usd.conversions import iter_geometry
from compas_usd.conversions import mesh_from_prim
from compas_usd.conversions import nurbssurface_parameters_from_prim
from compas_usd.conversions import pointcloud_from_prim
from compas_usd.conversions import polylines_from_prim
from compas_usd.conversions import prim_from_box
from compas_usd.conversions import prim_from_geometry
from compas_usd.conversions import prim_from_mesh
from compas_usd.conversions import prim_from_nurbssurface
from compas_usd.conversions import prim_from_polylines
from compas_usd.conversions import prim_from_transformation
from compas_usd.conversions import set_primvar
from compas_usd.conversions import transformation_from_gfmatrix4d
from compas_usd.conversions import transformation_from_xformable

TOL32 = 1e-5  # points are stored as float32

FRAME = Frame([1.0, -2.0, 3.5], [0.27, 0.95, 0.13], [-0.95, 0.28, -0.09])


@pytest.fixture
def stage():
    return create_stage(unit="MM", default_prim="World")


def _world_points(prim, points):
    T = transformation_from_xformable(prim, world=True)
    return [Point(*p).transformed(T) for p in points]


# =============================================================================
# transformations
# =============================================================================


def test_gfmatrix_roundtrip_and_convention():
    T = Transformation.from_frame(FRAME)
    M = gfmatrix4d_from_transformation(T)
    assert transformation_from_gfmatrix4d(M) == T
    # USD transforms row vectors: p' = p * M
    p = Point(1, 2, 3)
    q = M.Transform(Gf.Vec3d(*p))
    assert allclose(list(q), list(p.transformed(T)), tol=1e-9)


def test_rotate_and_translate_matches_frame(stage):
    xform = UsdGeom.Xform.Define(stage, "/World/x")
    apply_rotate_and_translate_on_prim(xform, FRAME)
    expected = Transformation.from_frame(FRAME)
    assert allclose(transformation_from_xformable(xform).matrix, expected.matrix, tol=1e-6)


def test_nested_xforms_compose_like_compas(stage):
    a = Translation.from_vector([10, 0, 0])
    b = Rotation.from_axis_and_angle([0, 0, 1], 0.5)
    prim_from_transformation(stage, "/World/a", a)
    child = prim_from_transformation(stage, "/World/a/b", b)
    assert allclose(transformation_from_xformable(child, world=True).matrix, (a * b).matrix, tol=1e-9)


# =============================================================================
# stage conventions
# =============================================================================


def test_stage_units(stage):
    assert UsdGeom.GetStageMetersPerUnit(stage) == 0.001
    assert stage_unit(stage) == "MM"
    assert unit_scale(stage, "M") == 0.001
    assert UsdGeom.GetStageUpAxis(stage) == "Z"


def test_unsupported_unit():
    with pytest.raises(ValueError):
        create_stage(unit="IN")


# =============================================================================
# primitives
# =============================================================================


def test_box_world_corners(stage):
    box = Box(1, 2, 3, frame=FRAME)
    cube = prim_from_box(stage, "/World/box", box)
    s = 0.5
    unit_corners = [[x, y, z] for x in (-s, s) for y in (-s, s) for z in (-s, s)]
    world = _world_points(cube, unit_corners)
    expected = box.to_vertices_and_faces()[0]
    for p in world:
        assert min(p.distance_to_point(q) for q in expected) < 1e-9
    other = box_from_prim(cube)
    assert allclose([other.xsize, other.ysize, other.zsize], [1, 2, 3], tol=1e-9)
    assert allclose(list(other.frame.point), list(FRAME.point), tol=1e-9)


def test_sphere_and_cylinder_roundtrip(stage):
    s = geometry_from_prim(prim_from_geometry(stage, "/World/s", Sphere(2.0, frame=FRAME)).GetPrim())
    assert abs(s.radius - 2.0) < 1e-9
    c = geometry_from_prim(prim_from_geometry(stage, "/World/c", Cylinder(0.5, 3.0, frame=FRAME)).GetPrim())
    assert abs(c.radius - 0.5) < 1e-9 and abs(c.height - 3.0) < 1e-9
    assert allclose(list(c.frame.zaxis), list(FRAME.zaxis), tol=1e-9)


# =============================================================================
# mesh
# =============================================================================


def test_mesh_roundtrip_with_attributes(stage):
    mesh = Mesh.from_polyhedron(12)
    for i, v in enumerate(mesh.vertices()):
        mesh.vertex_attribute(v, "stress", float(i))
    for i, f in enumerate(mesh.faces()):
        mesh.face_attribute(f, "zone", i % 3)
    prim = prim_from_mesh(stage, "/World/mesh", mesh, vertex_attributes=["stress"], face_attributes=["zone"])
    assert prim.GetSubdivisionSchemeAttr().Get() == "none"
    other = mesh_from_prim(prim)
    assert other.number_of_vertices() == mesh.number_of_vertices()
    assert other.number_of_faces() == mesh.number_of_faces()
    assert other.vertices_attribute("stress") == mesh.vertices_attribute("stress")
    assert other.faces_attribute("zone") == mesh.faces_attribute("zone")
    for a, b in zip(mesh.vertices_attributes("xyz"), other.vertices_attributes("xyz")):
        assert allclose(a, b, tol=TOL32)


def test_mesh_lefthanded_is_flipped(stage):
    mesh = Mesh.from_polyhedron(6)
    prim = prim_from_mesh(stage, "/World/mesh", mesh)
    prim.CreateOrientationAttr(UsdGeom.Tokens.leftHanded)
    other = mesh_from_prim(prim)
    f0 = list(mesh.faces())[0]
    assert other.face_vertices(f0) == mesh.face_vertices(f0)[::-1]


def test_mesh_with_noncontiguous_keys(stage):
    mesh = Mesh.from_polyhedron(6)
    mesh.delete_face(list(mesh.faces())[0])
    mesh.remove_unused_vertices()
    other = mesh_from_prim(prim_from_mesh(stage, "/World/mesh", mesh))
    assert other.number_of_faces() == 5


# =============================================================================
# curves, points, primvars
# =============================================================================


def test_polylines_roundtrip_preserves_order_and_closure(stage):
    a = Polyline([[0, 0, 0], [100, 0, 0], [100, 100, 0], [0, 0, 0]])
    b = Polyline([[0, 0, 10], [250.5, 0, 10], [250.5, 20, 10]])
    curves = prim_from_polylines(stage, "/World/paths", [a, b], widths=[25.0, 30.0])
    assert curves.GetWidthsInterpolation() == UsdGeom.Tokens.uniform
    out = polylines_from_prim(curves)
    assert [len(p.points) for p in out] == [4, 3]
    assert out[0].is_closed and not out[1].is_closed
    for p, q in zip(a.points + b.points, out[0].points + out[1].points):
        assert allclose(p, q, tol=TOL32)


def test_periodic_curves_are_closed_on_read(stage):
    curves = prim_from_polylines(stage, "/World/loop", [Polyline([[0, 0, 0], [1, 0, 0], [1, 1, 0]])])
    curves.GetWrapAttr().Set(UsdGeom.Tokens.periodic)
    (loop,) = polylines_from_prim(curves)
    assert len(loop.points) == 4 and loop.is_closed


def test_toolpath_primvars(stage):
    polylines = [Polyline([[0, 0, 0], [1, 0, 0], [2, 0, 0]]), Polyline([[0, 0, 1], [2, 0, 1]])]
    curves = prim_from_polylines(stage, "/World/toolpath", polylines)
    set_primvar(curves, "fab:velocity", [10.0, 10.0, 12.0, 20.0, 20.0])
    set_primvar(curves, "fab:extrude", [True, True, True, False, False])
    set_primvar(curves, "fab:layer", [0, 1])
    set_primvar(curves, "fab:up_vector", [(0, 0, 1)] * 5)
    set_primvar(curves, "fab:nozzle", 25.0)
    pv = get_primvars(curves)
    assert pv["fab:velocity"] == ([10.0, 10.0, 12.0, 20.0, 20.0], "vertex")
    assert pv["fab:extrude"] == ([True, True, True, False, False], "vertex")
    assert pv["fab:layer"] == ([0, 1], "uniform")
    assert pv["fab:up_vector"][0][0] == (0.0, 0.0, 1.0)
    assert pv["fab:nozzle"] == ([25.0], "constant")


def test_primvar_interpolation_must_be_inferable(stage):
    curves = prim_from_polylines(stage, "/World/p", [Polyline([[0, 0, 0], [1, 0, 0], [2, 0, 0]])])
    with pytest.raises(ValueError):
        set_primvar(curves, "bad", [1.0, 2.0])


def test_pointcloud_roundtrip(stage):
    cloud = Pointcloud([[0, 0, 0], [1, 2, 3], [4, 5, 6]])
    prim = prim_from_geometry(stage, "/World/cloud", cloud, widths=0.5)
    other = pointcloud_from_prim(prim)
    assert len(other.points) == 3
    assert allclose(other.points[2], [4, 5, 6], tol=TOL32)


# =============================================================================
# identity metadata
# =============================================================================


def test_metadata_roundtrip(stage):
    mesh = Mesh.from_polyhedron(4)
    mesh.name = "Block_07"
    mesh.attributes["element_guid"] = "abc"
    mesh.attributes["nested"] = {"a": [1, 2.5, None]}
    prim = prim_from_geometry(stage, "/World/b", mesh).GetPrim()
    meta = get_compas_metadata(prim)
    assert meta["dtype"] == "compas.datastructures/Mesh"
    assert meta["guid"] == str(mesh.guid)
    other = geometry_from_prim(prim)
    assert other.guid == mesh.guid
    assert other.name == "Block_07"
    assert other.attributes["nested"] == {"a": [1, 2.5, None]}


# =============================================================================
# reader
# =============================================================================


def test_iter_geometry_world_and_units(stage):
    prim_from_transformation(stage, "/World/group", Translation.from_vector([1000, 0, 0]))
    prim_from_polylines(stage, "/World/group/path", [Polyline([[0, 0, 0], [500, 0, 0]])])
    items = dict(iter_geometry(stage, space="world", unit="M"))
    (path,) = items["/World/group/path"]
    assert allclose(path.points[0], [1.0, 0, 0], tol=1e-6)
    assert allclose(path.points[1], [1.5, 0, 0], tol=1e-6)
    local = dict(iter_geometry(stage, space="local"))["/World/group/path"][0]
    assert allclose(local.points[1], [500, 0, 0], tol=TOL32)


# =============================================================================
# NURBS (no COMPAS NURBS plugin needed for writing / parameter reading)
# =============================================================================


class _FakeSurface:
    degree_u, degree_v = 2, 1
    knots_u, mults_u = [0.0, 1.0], [3, 3]
    knots_v, mults_v = [0.0, 1.0], [2, 2]
    is_periodic_u = is_periodic_v = False

    def __init__(self):
        self.points = [[Point(i, j, i * j) for j in range(2)] for i in range(3)]
        self.weights = [[1.0, 0.5], [1.0, 1.0], [2.0, 1.0]]


def test_nurbspatch_layout_u_fastest(stage):
    surface = _FakeSurface()
    patch = prim_from_nurbssurface(stage, "/World/srf", surface)
    flat = patch.GetPointsAttr().Get()
    assert tuple(flat[1]) == (1.0, 0.0, 0.0)  # index i + j * nu with i=1, j=0
    assert tuple(flat[3]) == (0.0, 1.0, 0.0)  # i=0, j=1
    assert len(patch.GetUKnotsAttr().Get()) == 3 + 3
    params = nurbssurface_parameters_from_prim(patch)
    assert params["mults_u"] == [3, 3] and params["degree_v"] == 1
    assert params["weights"] == surface.weights
    assert [[list(p) for p in row] for row in params["points"]] == [[list(p) for p in row] for row in surface.points]


# =============================================================================
# files, scenes, models
# =============================================================================


def test_file_roundtrip(tmp_path):
    filepath = os.path.join(str(tmp_path), "out.usda")
    stage = create_stage(filepath, unit="M", default_prim="World")
    prim_from_geometry(stage, "/World/mesh", Mesh.from_polyhedron(6))
    stage.Save()
    reopened = Usd.Stage.Open(filepath)
    assert stage_unit(reopened) == "M"
    assert str(reopened.GetDefaultPrim().GetPath()) == "/World"
    assert geometry_from_prim(reopened.GetPrimAtPath("/World/mesh")).number_of_faces() == 6


def test_stage_from_scene():
    from compas.scene import Scene

    from compas_usd.conversions import stage_from_scene

    scene = Scene()
    group = scene.add_group(name="Boxes", transformation=Translation.from_vector([0, 5, 0]))
    for i in range(3):
        group.add(Box(0.5), name="Box{}".format(i), transformation=Translation.from_vector([i, 0, 0]))
    stage = stage_from_scene(scene, unit="M")
    paths = [str(p.GetPath()) for p in Usd.PrimRange(stage.GetPseudoRoot()) if p.IsA(UsdGeom.Cube)]
    assert len(paths) == 3
    boxes = [obj for _, obj in iter_geometry(stage)]
    assert sorted(round(b.frame.point.x, 6) for b in boxes) == [0.0, 1.0, 2.0]
    assert all(abs(b.frame.point.y - 5.0) < 1e-9 for b in boxes)


def test_prim_from_model_preserves_world_geometry(stage):
    compas_model = pytest.importorskip("compas_model")
    from compas_model.elements import Element
    from compas_model.elements import Group
    from compas_model.models import Model

    from compas_usd.conversions import prim_from_model

    class MeshElement(Element):
        def compute_elementgeometry(self, include_features=False):
            return Mesh.from_polyhedron(6)

    model = Model(name="Floor")
    group = model.add_element(Group(name="row", transformation=Translation.from_vector([0, 0, 100])))
    for i in range(2):
        element = MeshElement(transformation=Translation.from_vector([10 * i, 0, 0]) * Rotation.from_axis_and_angle([0, 0, 1], 0.3), name="block{}".format(i))
        model.add_element(element, parent=group)
    root = prim_from_model(stage, model)
    assert str(root.GetPath()) == "/World/Floor"
    assert get_compas_metadata(root)["guid"] == str(model.guid)
    world = dict(iter_geometry(stage, space="world"))
    for element in model.elements():
        if isinstance(element, Group):
            continue
        mesh = world["/World/Floor/row/{}/geometry".format(element.name)]
        expected = element.modelgeometry.vertices_attributes("xyz")
        for a, b in zip(expected, mesh.vertices_attributes("xyz")):
            assert allclose(a, b, tol=1e-4)
    assert compas_model.__version__
