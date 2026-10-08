import os
import pytest

from pxr import Usd

from compas_usd.material import USDMaterial

BASE_FOLDER = os.path.dirname(__file__)


@pytest.fixture
def blue_mdl():
    return os.path.join(BASE_FOLDER, "fixtures", "blue.mdl")


@pytest.fixture
def grey_mdl():
    return os.path.join(BASE_FOLDER, "fixtures", "grey.mdl")


def test_blue_mdl(blue_mdl):
    stage = Usd.Stage.CreateInMemory()
    USDMaterial.from_mdl(stage, blue_mdl)
    print(stage.GetRootLayer().ExportToString())


def test_grey_mdl(grey_mdl):
    stage = Usd.Stage.CreateInMemory()
    USDMaterial.from_mdl(stage, grey_mdl)
    print(stage.GetRootLayer().ExportToString())
