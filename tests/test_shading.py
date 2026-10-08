import os
from pxr import Kind, Sdf, Usd, UsdGeom, UsdShade


BASE_FOLDER = os.path.dirname(__file__)


def attach_billboard(stage, root, name="card"):
    billboard = UsdGeom.Mesh.Define(stage, str(root.GetPath()) + "/" + name)
    billboard.CreatePointsAttr([(-430, -145, 0), (430, -145, 0), (430, 145, 0), (-430, 145, 0)])
    billboard.CreateFaceVertexCountsAttr([4])
    billboard.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    billboard.CreateExtentAttr([(-430, -145, 0), (430, 145, 0)])
    texCoords = UsdGeom.PrimvarsAPI(billboard).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.varying)
    texCoords.Set([(0, 0), (1, 0), (1, 1), (0, 1)])
    return billboard


def attach_surface_shader(stage, material, path):
    shader = UsdShade.Shader.Define(stage, path)
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.4)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return shader


def attach_texture(stage, shader, material_path, reader_name="stReader", shader_name="diffuseTexture"):
    reader = UsdShade.Shader.Define(stage, material_path + "/" + reader_name)
    reader.CreateIdAttr("UsdPrimvarReader_float2")
    diffuseTextureSampler = UsdShade.Shader.Define(stage, material_path + "/" + shader_name)
    diffuseTextureSampler.CreateIdAttr("UsdUVTexture")
    diffuseTextureSampler.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(os.path.join(BASE_FOLDER, "fixtures", "USDLogoLrg.png"))
    diffuseTextureSampler.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(reader.ConnectableAPI(), "result")
    diffuseTextureSampler.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(diffuseTextureSampler.ConnectableAPI(), "rgb")
    return reader


def test_shading(tmp_path):
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    root = UsdGeom.Xform.Define(stage, "/TexModel")
    Usd.ModelAPI(root).SetKind(Kind.Tokens.component)
    UsdGeom.Scope.Define(stage, "/Looks")
    billboard = attach_billboard(stage, root)
    material = UsdShade.Material.Define(stage, "/Looks/boardMat")
    shader = attach_surface_shader(stage, material, str(material.GetPath()) + "/PBRShader")
    reader = attach_texture(stage, shader, str(material.GetPath()))
    st_input = material.CreateInput("frame:stPrimvarName", Sdf.ValueTypeNames.Token)
    st_input.Set("st")
    reader.CreateInput("varname", Sdf.ValueTypeNames.Token).ConnectToSource(st_input)
    UsdShade.MaterialBindingAPI(billboard).Bind(material)
    filename = os.path.join(str(tmp_path), "test1.usda")
    stage.Export(filename)
