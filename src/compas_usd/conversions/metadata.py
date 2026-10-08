"""COMPAS identity on USD prims.

COMPAS identity (``dtype``, ``guid``, ``name``) and user attributes are stored in the prim's ``customData``
under the ``compas`` key::

    customData = {
        dictionary compas = {
            string dtype = "compas.datastructures/Mesh"
            string guid = "4e5f..."
            string name = "Mesh"
            string attributes = "{...}"      # JSON, written with compas.json_dumps
        }
    }

Attributes are stored as a JSON string so that arbitrary (nested, mixed-type) values survive the round trip;
``VtDictionary`` cannot hold every JSON value.
"""

from typing import Any
from typing import Optional
from uuid import UUID

import compas
from compas.data import Data
from pxr import Usd

COMPAS_KEY = "compas"


def set_compas_metadata(
    prim: Usd.Prim,
    obj: Optional[Data] = None,
    *,
    attributes: Optional[dict] = None,
    **extra: Any,
) -> None:
    """Write COMPAS identity and attributes into ``prim.customData["compas"]``.

    Parameters
    ----------
    prim : :class:`pxr.Usd.Prim`
    obj : :class:`compas.data.Data`, optional
        Object whose ``__dtype__``, ``guid`` and ``name`` are written.
        If it has a non-empty ``attributes`` dict, that is written too (unless ``attributes`` is given).
    attributes : dict, optional
        Attributes to write instead of ``obj.attributes``.
    **extra
        Additional scalar values (str, int, float, bool) stored under the same key.

    Examples
    --------
    >>> from pxr import Usd
    >>> stage = Usd.Stage.CreateInMemory()
    >>> prim = stage.DefinePrim("/mesh")
    >>> mesh = Mesh.from_polyhedron(4)
    >>> mesh.attributes["load_case"] = "LC1"
    >>> set_compas_metadata(prim, mesh)
    >>> get_compas_metadata(prim)["attributes"]
    {'load_case': 'LC1'}

    """
    if obj is not None:
        prim.SetCustomDataByKey(COMPAS_KEY + ":dtype", obj.__dtype__)
        prim.SetCustomDataByKey(COMPAS_KEY + ":guid", str(obj.guid))
        if obj.name:
            prim.SetCustomDataByKey(COMPAS_KEY + ":name", obj.name)
        if attributes is None:
            attributes = getattr(obj, "attributes", None)
    if attributes:
        prim.SetCustomDataByKey(COMPAS_KEY + ":attributes", compas.json_dumps(attributes))
    for key, value in extra.items():
        prim.SetCustomDataByKey(COMPAS_KEY + ":" + key, value)


def get_compas_metadata(prim: Usd.Prim) -> dict:
    """Read the ``compas`` entry of a prim's ``customData``.

    Returns
    -------
    dict
        Empty if the prim carries no COMPAS metadata. ``attributes`` is decoded from JSON.

    """
    data = dict(prim.GetCustomDataByKey(COMPAS_KEY) or {})
    if "attributes" in data:
        data["attributes"] = compas.json_loads(data["attributes"])
    return data


def apply_compas_metadata(obj: Data, prim: Usd.Prim, guid: bool = True) -> Data:
    """Restore name, attributes and (optionally) GUID from a prim onto a COMPAS object.

    Parameters
    ----------
    obj : :class:`compas.data.Data`
    prim : :class:`pxr.Usd.Prim`
    guid : bool, optional
        Restore the stored GUID. Note that this sets the private ``_guid`` slot, as compas' own JSON decoder does.

    Returns
    -------
    :class:`compas.data.Data`
        The same object.

    """
    data = get_compas_metadata(prim)
    if "name" in data:
        obj.name = data["name"]
    if guid and "guid" in data:
        obj._guid = UUID(data["guid"])
    if "attributes" in data and isinstance(getattr(obj, "attributes", None), dict):
        obj.attributes.update(data["attributes"])
    return obj
