"""Writing COMPAS objects, scenes and models to USD stages."""

import warnings
from typing import Optional

from compas.data import Data
from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Cylinder
from compas.geometry import Frame
from compas.geometry import NurbsCurve
from compas.geometry import NurbsSurface
from compas.geometry import Pointcloud
from compas.geometry import Polyline
from compas.geometry import Sphere
from compas.geometry import Transformation
from compas.scene import Scene
from compas.scene import SceneObject
from pxr import Sdf
from pxr import Usd

from ..stage import create_stage
from ..stage import make_valid_identifier
from ..stage import unique_child_path
from .geometry import PathLike
from .geometry import prim_from_box
from .geometry import prim_from_cylinder
from .geometry import prim_from_frame
from .geometry import prim_from_mesh
from .geometry import prim_from_nurbscurve
from .geometry import prim_from_nurbssurface
from .geometry import prim_from_pointcloud
from .geometry import prim_from_polyline
from .geometry import prim_from_sphere
from .geometry import prim_from_transformation
from .metadata import set_compas_metadata

_WRITERS = (
    (Box, prim_from_box),
    (Sphere, prim_from_sphere),
    (Cylinder, prim_from_cylinder),
    (Mesh, prim_from_mesh),
    (Polyline, prim_from_polyline),
    (Pointcloud, prim_from_pointcloud),
    (Frame, prim_from_frame),
    (NurbsCurve, prim_from_nurbscurve),
    (NurbsSurface, prim_from_nurbssurface),
)


def prim_from_geometry(stage: Usd.Stage, path: PathLike, item: Data, metadata: bool = True, **kwargs):
    """Write any supported COMPAS object to a prim at ``path``.

    Supported: Box, Sphere, Cylinder, Mesh, Polyline, Pointcloud, Frame, NurbsCurve, NurbsSurface.
    Extra keyword arguments are passed to the type-specific writer.

    Parameters
    ----------
    stage : :class:`pxr.Usd.Stage`
    path : str
    item : :class:`compas.data.Data`
    metadata : bool, optional
        Write COMPAS identity and attributes into ``customData`` (see :func:`set_compas_metadata`).

    Raises
    ------
    TypeError
        If the object type is not supported.

    """
    for cls, writer in _WRITERS:
        if isinstance(item, cls):
            schema = writer(stage, path, item, **kwargs)
            if metadata:
                set_compas_metadata(schema.GetPrim(), item)
            return schema
    raise TypeError("No USD writer for objects of type {}".format(type(item).__name__))


def stage_from_scene(scene: Scene, filepath: Optional[str] = None, unit: Optional[str] = None, save: bool = True) -> Usd.Stage:
    """Convert a :class:`compas.scene.Scene` to a USD stage.

    The scene name becomes the default prim. Each scene object becomes an ``Xform`` carrying its
    transformation; its item (if any) becomes a child prim named after the item.

    Parameters
    ----------
    scene : :class:`compas.scene.Scene`
    filepath : str, optional
        File to write. If ``None``, the stage is created in memory.
    unit : str, optional
        COMPAS unit written as ``metersPerUnit``. Defaults to ``compas.tolerance.TOL.unit``.
    save : bool, optional
        Save the root layer if ``filepath`` is given.

    Returns
    -------
    :class:`pxr.Usd.Stage`

    """
    stage = create_stage(filepath, unit=unit, default_prim=scene.name)
    root = stage.GetDefaultPrim().GetPath()
    for obj in scene.root.children:
        prim_from_sceneobject(stage, obj, parent_path=root)
    if filepath and save:
        stage.Save()
    return stage


def prim_from_sceneobject(stage: Usd.Stage, sceneobject: SceneObject, parent_path: PathLike = Sdf.Path.absoluteRootPath) -> Usd.Prim:
    """Write a scene object (and its children) as an ``Xform`` under ``parent_path``.

    ``parent_path`` may also be a list of prim names (the pre-0.2 signature).
    """
    if isinstance(parent_path, (list, tuple)):
        parent_path = "/" + "/".join(make_valid_identifier(n) for n in parent_path) if parent_path else Sdf.Path.absoluteRootPath
    path = unique_child_path(stage, parent_path, sceneobject.name)
    xform = prim_from_transformation(stage, path, sceneobject.transformation or Transformation())
    item = sceneobject.item
    if item is not None:
        try:
            prim_from_geometry(stage, path.AppendChild(make_valid_identifier(item.name)), item)
        except TypeError as error:
            warnings.warn("Skipped {!r}: {}".format(sceneobject.name, error))
    for child in sceneobject.children:
        prim_from_sceneobject(stage, child, parent_path=path)
    return xform.GetPrim()


def prim_from_item(stage: Usd.Stage, item: Data, parent_path: PathLike = Sdf.Path.absoluteRootPath):
    """Write an item under ``parent_path`` using its name as prim name. Kept for backwards compatibility."""
    if isinstance(parent_path, (list, tuple)):
        parent_path = "/" + "/".join(make_valid_identifier(n) for n in parent_path) if parent_path else Sdf.Path.absoluteRootPath
    return prim_from_geometry(stage, unique_child_path(stage, parent_path, item.name), item).GetPrim()
