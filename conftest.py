import math

import compas
import pytest
from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Point
from compas.geometry import Polyline
from compas.geometry import Sphere
from compas.geometry import Transformation
from pxr import Usd

import compas_usd


@pytest.fixture(autouse=True)
def add_doctest_namespace(doctest_namespace):
    doctest_namespace["math"] = math
    doctest_namespace["compas"] = compas
    doctest_namespace["compas_usd"] = compas_usd
    doctest_namespace["Mesh"] = Mesh
    doctest_namespace["Box"] = Box
    doctest_namespace["Frame"] = Frame
    doctest_namespace["Point"] = Point
    doctest_namespace["Polyline"] = Polyline
    doctest_namespace["Sphere"] = Sphere
    doctest_namespace["Transformation"] = Transformation
    doctest_namespace["stage"] = Usd.Stage.CreateInMemory()
