"""Conversions between COMPAS transformations/frames and USD transforms.

Convention: COMPAS matrices act on column vectors (``p' = T p``); ``Gf.Matrix4d`` acts on row vectors (``p' = p M``).
Hence ``M = T^T``.
"""

import math
from typing import Optional

from compas.geometry import Frame
from compas.geometry import Rotation
from compas.geometry import Transformation
from compas.geometry import transpose_matrix
from pxr import Gf
from pxr import Usd
from pxr import UsdGeom

_ROTATION_ORDERS = {
    UsdGeom.XformCommonAPI.RotationOrderXYZ: "xyz",
    UsdGeom.XformCommonAPI.RotationOrderXZY: "xzy",
    UsdGeom.XformCommonAPI.RotationOrderYXZ: "yxz",
    UsdGeom.XformCommonAPI.RotationOrderYZX: "yzx",
    UsdGeom.XformCommonAPI.RotationOrderZXY: "zxy",
    UsdGeom.XformCommonAPI.RotationOrderZYX: "zyx",
}


def gfmatrix4d_from_transformation(transformation: Transformation) -> Gf.Matrix4d:
    """Convert a :class:`compas.geometry.Transformation` to a ``Gf.Matrix4d``.

    Examples
    --------
    >>> frame = Frame((0, 3, 4), (0.27, 0.95, 0.13), (-0.95, 0.28, -0.09))
    >>> t1 = Transformation.from_frame(frame)
    >>> gf = gfmatrix4d_from_transformation(t1)
    >>> t2 = transformation_from_gfmatrix4d(gf)
    >>> t1 == t2
    True

    """
    return Gf.Matrix4d(*[v for row in transpose_matrix(transformation.matrix) for v in row])


def transformation_from_gfmatrix4d(gfmatrix4d: Gf.Matrix4d) -> Transformation:
    """Convert a ``Gf.Matrix4d`` to a :class:`compas.geometry.Transformation`."""
    matrix = [[float(v) for v in row] for row in gfmatrix4d]
    return Transformation(transpose_matrix(matrix))


def gfvec3f_and_gfquatd_from_frame(frame: Frame):
    """Return the translation (``Gf.Vec3f``) and orientation (``Gf.Quatd``) of a frame."""
    w, x, y, z = Rotation.from_frame(frame).quaternion.wxyz
    return Gf.Vec3f(*frame.point), Gf.Quatd(w, x, y, z)


translate_and_orient_from_frame = gfvec3f_and_gfquatd_from_frame


def xform_rotate_from_frame(frame: Frame, rotation_order) -> list:
    """Return Euler angles in degrees for ``UsdGeom.XformCommonAPI.SetRotate``.

    USD's ``rotateXYZ`` applies X first, then Y, then Z, about the fixed parent axes, i.e. static (extrinsic) angles.

    Parameters
    ----------
    frame : :class:`compas.geometry.Frame`
    rotation_order : ``UsdGeom.XformCommonAPI.RotationOrder``

    Returns
    -------
    list[float]

    """
    axes = _ROTATION_ORDERS[rotation_order]
    return [math.degrees(a) for a in frame.euler_angles(True, axes)]


def frame_and_scale_from_prim(prim) -> tuple:
    """Return the frame and the scale factors of a prim's local transformation.

    Works for any authored xform op stack (not only ``XformCommonAPI``-compatible ones).

    Returns
    -------
    tuple[:class:`compas.geometry.Frame`, list[float]]

    """
    return frame_and_scale_from_transformation(transformation_from_xformable(prim))


def frame_and_scale_from_transformation(transformation: Transformation) -> tuple:
    """Decompose a transformation into a frame (rotation + translation) and scale factors. Shear and projection are dropped."""
    S, _, R, T, _ = transformation.decomposed()
    frame = Frame.from_rotation(R, point=T.translation_vector)
    return frame, [S[0, 0], S[1, 1], S[2, 2]]


def transformation_from_xformable(prim, world: bool = False, time: Optional[Usd.TimeCode] = None) -> Transformation:
    """Return the local (relative to parent) or world transformation of a prim.

    Parameters
    ----------
    prim : :class:`pxr.Usd.Prim` or :class:`pxr.UsdGeom.Xformable`
    world : bool, optional
        If ``True``, return the local-to-world transformation.
    time : :class:`pxr.Usd.TimeCode`, optional
        Defaults to ``Usd.TimeCode.Default()``.

    """
    time = time or Usd.TimeCode.Default()
    xformable = UsdGeom.Xformable(prim if isinstance(prim, Usd.Prim) else prim.GetPrim())
    if world:
        matrix = xformable.ComputeLocalToWorldTransform(time)
    else:
        matrix = xformable.GetLocalTransformation(time)
    return transformation_from_gfmatrix4d(matrix)


def apply_transformation_on_prim(prim, transformation: Transformation) -> None:
    """Replace the prim's xform op stack with a single ``xformOp:transform`` holding ``transformation``."""
    xformable = UsdGeom.Xformable(prim if isinstance(prim, Usd.Prim) else prim.GetPrim())
    xformable.ClearXformOpOrder()
    op = xformable.MakeMatrixXform()
    op.Set(gfmatrix4d_from_transformation(transformation))


def apply_rotate_and_translate_on_prim(prim, frame: Frame) -> None:
    """Set rotation and translation of a prim from a frame, using ``XformCommonAPI``."""
    api = UsdGeom.XformCommonAPI(prim)
    _, _, _, _, rotation_order = api.GetXformVectors(Usd.TimeCode.Default())
    api.SetRotate(xform_rotate_from_frame(frame, rotation_order), rotation_order)
    api.SetTranslate(tuple(frame.point))
