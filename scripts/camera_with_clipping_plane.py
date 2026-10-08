from pxr import Gf
from pxr import Usd
from pxr import UsdGeom
from pxr import Vt

stage = Usd.Stage.CreateInMemory()
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
camera = UsdGeom.Camera.Define(stage, "/Camera")

camera_prim = camera.GetPrim()
camera_prim.GetAttribute("focalLength").Set(11)
UsdGeom.XformCommonAPI(camera_prim).SetRotate((90, 0, 180))
UsdGeom.XformCommonAPI(camera_prim).SetTranslate((0, 500, 100))

cmin, cmax = camera_prim.GetAttribute("clippingRange").Get()
clipping_plane = camera_prim.GetAttribute("clippingPlanes")
vec = Gf.Vec4f([1, 0, 0, 1])
pln = Vt.Vec4fArray((0, 1, 0, 0))
clipping_plane.Set(pln)
print(stage.GetRootLayer().ExportToString())
