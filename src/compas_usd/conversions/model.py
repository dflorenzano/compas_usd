"""Writing :class:`compas_model.models.Model` instances to USD.

``compas_model`` is not a dependency of compas_usd; the model is accessed through its public API only.

Mapping::

    /<Model>                 Xform   model.transformation           customData: compas model identity
      /<element>             Xform   element.transformation         customData: compas element identity
        /geometry            Mesh    element geometry, in the element's local coordinates
        /<child element>     Xform   ...

USD composes nested Xforms exactly as ``Element.compute_modeltransformation`` composes
``element.transformation`` up the element tree, so world placement is preserved.
"""

import warnings
from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Transformation
from pxr import Sdf
from pxr import Usd

from ..stage import unique_child_path
from .geometry import PathLike
from .geometry import prim_from_mesh
from .geometry import prim_from_transformation
from .metadata import set_compas_metadata

GEOMETRY_PRIM_NAME = "geometry"


def _as_mesh(geometry) -> Optional[Mesh]:
    if isinstance(geometry, Mesh):
        return geometry
    if hasattr(geometry, "to_meshes"):  # Brep
        meshes = geometry.to_meshes()
        if not meshes:
            return None
        mesh = meshes[0].copy()
        for other in meshes[1:]:
            mesh.join(other)
        return mesh
    if hasattr(geometry, "to_mesh"):
        return geometry.to_mesh()
    return None


def _element_geometry(element, geometry: str) -> Optional[Mesh]:
    if geometry == "element":
        return _as_mesh(element.elementgeometry)
    if geometry == "model":
        # modelgeometry includes modifiers (interactions); bring it back to element-local coordinates
        mesh = _as_mesh(element.modelgeometry)
        if mesh is None:
            return None
        return mesh.transformed(element.modeltransformation.inverse())
    raise ValueError("geometry must be 'element' or 'model', got {!r}".format(geometry))


def prim_from_element(stage: Usd.Stage, element, parent_path: PathLike, geometry: str = "model", **mesh_kwargs) -> Usd.Prim:
    """Write an element, and recursively its child elements, under ``parent_path``.

    Parameters
    ----------
    stage : :class:`pxr.Usd.Stage`
    element : :class:`compas_model.elements.Element`
    parent_path : str
    geometry : {"model", "element"}, optional
        ``"model"`` writes ``element.modelgeometry`` (with modifiers applied), ``"element"`` writes ``element.elementgeometry``.
    **mesh_kwargs
        Passed to :func:`prim_from_mesh` (e.g. ``vertex_attributes``).

    """
    path = unique_child_path(stage, parent_path, element.name or type(element).__name__)
    xform = prim_from_transformation(stage, path, element.transformation or Transformation())
    set_compas_metadata(xform.GetPrim(), element, attributes={})
    try:
        mesh = _element_geometry(element, geometry)
    except NotImplementedError:  # e.g. Group: no geometry
        mesh = None
    except Exception as error:  # geometry computation is element-specific
        warnings.warn("No geometry written for element {}: {!r}".format(element.name, error))
        mesh = None
    if mesh is not None and mesh.number_of_faces():
        prim_from_mesh(stage, path.AppendChild(GEOMETRY_PRIM_NAME), mesh, **mesh_kwargs)
    for child in element.children:
        prim_from_element(stage, child, path, geometry=geometry, **mesh_kwargs)
    return xform.GetPrim()


def prim_from_model(stage: Usd.Stage, model, path: Optional[PathLike] = None, geometry: str = "model", **mesh_kwargs) -> Usd.Prim:
    """Write a :class:`compas_model.models.Model` as a prim hierarchy.

    Parameters
    ----------
    stage : :class:`pxr.Usd.Stage`
    model : :class:`compas_model.models.Model`
    path : str, optional
        Prim path of the model root. Defaults to ``/<model.name>`` (or below the default prim, if the stage has one).
    geometry : {"model", "element"}, optional
        See :func:`prim_from_element`.

    Returns
    -------
    :class:`pxr.Usd.Prim`
        The model root prim.

    """
    if path is None:
        default = stage.GetDefaultPrim()
        parent = default.GetPath() if default else Sdf.Path.absoluteRootPath
        path = unique_child_path(stage, parent, model.name or "Model")
    root = prim_from_transformation(stage, path, model.transformation or Transformation())
    set_compas_metadata(root.GetPrim(), model, attributes={})
    for node in model.tree.root.children:
        element = getattr(node, "element", None)
        if element is not None:
            prim_from_element(stage, element, root.GetPath(), geometry=geometry, **mesh_kwargs)
    return root.GetPrim()
