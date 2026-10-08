"""
# https://github.com/kcoley/gltf2usd/blob/master/Source/_gltf2usd/usd_material.py
# https://github.com/ColinKennedy/USD-Cookbook/blob/master/concepts/mesh_with_materials/python/material.py
"""

import os
from enum import Enum

from pxr import Gf
from pxr import Sdf
from pxr import UsdGeom
from pxr import UsdShade


class AlphaMode(object):  # todo import from somewhere else?
    BLEND = "BLEND"
    MASK = "MASK"
    OPAQUE = "OPAQUE"


class USDMaterial(object):
    """Wrapper about UsdShade.Material"""

    def __init__(self, stage, name=None, path=None, materials_path="/Looks", textures=None, image_uris=None):
        self.stage = stage
        self.textures = textures
        self.image_uris = image_uris

        if not stage.GetPrimAtPath(materials_path):
            UsdGeom.Scope.Define(stage, materials_path)

        if name:
            material_path = Sdf.Path(materials_path).AppendChild(name)
            self.material = UsdShade.Material.Define(stage, material_path)
            self.surface_output = self.material.CreateOutput("surface", Sdf.ValueTypeNames.Token)
            self.displacement_output = self.material.CreateOutput("displacement", Sdf.ValueTypeNames.Token)
        elif path:
            material_path = path
            self.material = stage.GetPrimAtPath(path)
        else:
            raise ValueError("Please pass name or path")

    def GetPath(self):
        return self.material.GetPath()

    @classmethod
    def from_material(cls, stage, material, image_uris=None, textures=None):  # TODO: move to compas_xr?
        """Create a material from a :class:compas_xr.datastructures.material"""
        umat = cls(stage, material.name, image_uris=image_uris, textures=textures)
        umat.shader = USDPreviewSurface.from_material(material, stage, umat)
        return umat

    @classmethod
    def from_mdl(cls, stage, filepath, material_name=None):
        """Create a material from a MDL file"""
        # get the relative path between stage and mdl
        material_name = material_name or os.path.splitext(os.path.basename(filepath))[0]
        stage_path = stage.GetRootLayer().realPath
        mdl_relative_path = os.path.relpath(filepath, stage_path)
        umat = cls(stage, material_name)
        material_path = umat.GetPath()

        mdlShader = UsdShade.Shader.Define(stage, material_path.AppendChild("Shader"))
        mdlShader.CreateIdAttr("mdlMaterial")
        mdlShaderModule = mdl_relative_path.replace("\\", "/")  # TODO ?
        mdlShaderModule = "./" + mdlShaderModule

        mdlShader.SetSourceAsset(mdlShaderModule, "mdl")
        mdlShader.GetPrim().CreateAttribute("info:mdl:sourceAsset:subIdentifier", Sdf.ValueTypeNames.Token, True).Set(material_name)
        umat.material.CreateSurfaceOutput().ConnectToSource(mdlShader.ConnectableAPI(), "out")
        # later: UsdShade.MaterialBindingAPI(prim).Bind(material)
        return umat

    @classmethod
    def from_path(cls, stage, path):
        return cls(stage, path=path)

    def to_compas(self):
        """Create a :class:`compas_xr.datastructures.Material`"""
        from compas_xr.datastructures import Material

        shader_path = self.GetPath().AppendChild("Shader")
        shader = self.stage.GetPrimAtPath(shader_path)

        for name in shader.GetPropertyNames():
            if name in ["info:id", "info:implementationSource", "outputs:displacement", "outputs:surface"]:
                continue  # TODO

            "inputs:clearcoat"
            "inputs:clearcoatRoughness"
            "inputs:diffuseColor"
            "inputs:displacement"
            "inputs:emissiveColor"
            "inputs:ior"
            "inputs:metallic"
            "inputs:normal"
            "inputs:occlusion"
            "inputs:opacity"
            "inputs:roughness"
            "inputs:specularColor"
            "inputs:useSpecularWorkflow"

        return Material(
            name=None,
            pbr_metallic_roughness=None,
            normal_texture=None,
            occlusion_texture=None,
            emissive_texture=None,
            emissive_factor=None,
            alpha_mode=None,
            alpha_cutoff=None,
            double_sided=True,
        )


class USDPreviewSurface(object):
    """Material that models a physically based surface for USD."""

    def __init__(self, stage, material, scale_texture=False):
        self.stage = stage
        self.scale_texture = scale_texture
        self.material = material  # USDMaterial
        self.shader = UsdShade.Shader.Define(stage, material.GetPath().AppendChild("Shader"))  # why not already defined in material.. multiple shader possible?
        self.shader.CreateIdAttr("UsdPreviewSurface")

        # initialize_material
        shader = self.shader
        self._use_specular_workflow = shader.CreateInput("useSpecularWorkflow", Sdf.ValueTypeNames.Int)
        self._use_specular_workflow.Set(False)
        surface_output = shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
        self.material.surface_output.ConnectToSource(surface_output)
        displacement_output = shader.CreateOutput("displacement", Sdf.ValueTypeNames.Token)
        self.material.displacement_output.ConnectToSource(displacement_output)
        self._specular_color = shader.CreateInput("specularColor", Sdf.ValueTypeNames.Color3f)
        self._specular_color.Set((0.0, 0.0, 0.0))
        self._metallic = shader.CreateInput("metallic", Sdf.ValueTypeNames.Float)
        self._roughness = shader.CreateInput("roughness", Sdf.ValueTypeNames.Float)
        self._clearcoat = shader.CreateInput("clearcoat", Sdf.ValueTypeNames.Float)
        self._clearcoat.Set(0.0)
        self._clearcoat_roughness = shader.CreateInput("clearcoatRoughness", Sdf.ValueTypeNames.Float)
        self._clearcoat_roughness.Set(0.01)
        self._opacity = shader.CreateInput("opacity", Sdf.ValueTypeNames.Float)
        self._ior = shader.CreateInput("ior", Sdf.ValueTypeNames.Float)
        self._ior.Set(1.5)
        self._normal = shader.CreateInput("normal", Sdf.ValueTypeNames.Normal3f)
        self._displacement = shader.CreateInput("displacement", Sdf.ValueTypeNames.Float)
        self._displacement.Set(0.0)
        self._occlusion = shader.CreateInput("occlusion", Sdf.ValueTypeNames.Float)
        self._emissive_color = shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f)
        self._diffuse_color = shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f)

        self._st0 = USDPrimvarReaderFloat2(self.stage, self.material.GetPath(), "st0")
        self._st1 = USDPrimvarReaderFloat2(self.stage, self.material.GetPath(), "st1")

    @classmethod
    def from_material(cls, material, stage, usd_material):
        ps = cls(stage, usd_material)
        ps._set_normal_texture(material)
        ps._set_emissive_texture(material)
        ps._set_occlusion_texture(material)
        ps._set_pbr_specular_glossiness(material)
        ps._set_pbr_metallic_roughness(material)
        return ps

    def _texture_info_by_index(self, index):
        texture_info = self.material.textures[index]
        texture_info.file = self.material.image_uris[texture_info.index]  # TODO: not so elegant
        return texture_info

    def _uv_texture(self, name, texture_info, scale_factor, fallback=None):
        return USDUVTexture(name, self.stage, self.material, texture_info, scale_factor, [self._st0, self._st1], fallback=fallback)

    def _apply_on_shader(self, uv_texture, mode, apply_on):
        texture_shader = uv_texture.get_shader()
        if mode == "rgb":
            texture_shader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
        elif mode == "r":
            texture_shader.CreateOutput("r", Sdf.ValueTypeNames.Float)
        elif mode == "a":
            texture_shader.CreateOutput("a", Sdf.ValueTypeNames.Float)
        apply_on.ConnectToSource(texture_shader.ConnectableAPI(), mode)

    def _set_normal_texture(self, material):
        normal_texture = material.normal_texture
        if normal_texture is None:
            self._normal.Set((0, 0, 1))
        else:
            scale_factor = [normal_texture.scale for _ in range(3)] + [1.0]
            texture_info = self._texture_info_by_index(normal_texture.index)
            uv_texture = self._uv_texture("normalTexture", texture_info, scale_factor, fallback=scale_factor)
            self._apply_on_shader(uv_texture, "rgb", self._normal)

    def _set_emissive_texture(self, material):
        emissive_texture = material.emissive_texture
        emissive_factor = material.emissive_factor
        if emissive_texture is None:
            self._emissive_color.Set((0, 0, 0))
        else:
            scale_factor = emissive_factor + [1.0]
            texture_info = self._texture_info_by_index(emissive_texture.index)
            uv_texture = self._uv_texture("normalTexture", texture_info, scale_factor)
            self._apply_on_shader(uv_texture, "rgb", self._emissive_color)

    def _set_occlusion_texture(self, material):
        occlusion_texture = material.occlusion_texture
        if occlusion_texture is None:
            self._occlusion.Set(1.0)
        else:
            strength = occlusion_texture.strength
            scale_factor = [strength, strength, strength, 1.0]
            texture_info = self._texture_info_by_index(occlusion_texture.index)
            uv_texture = self._uv_texture("occlusionTexture", texture_info, scale_factor)
            self._apply_on_shader(uv_texture, "r", self._occlusion)

    def _set_pbr_metallic_roughness(self, material):
        pbr_metallic_roughness = material.pbr_metallic_roughness
        if pbr_metallic_roughness is not None:
            self._set_pbr_base_color(pbr_metallic_roughness, material.alpha_mode)
            self._set_pbr_metallic(pbr_metallic_roughness)
            self._set_pbr_roughness(pbr_metallic_roughness)

    def _set_pbr_specular_glossiness(self, material):
        if material.pbr_specular_glossiness is None:
            self._set_pbr_metallic_roughness(material)
        else:
            self._use_specular_workflow.Set(True)
            self._set_pbr_specular_glossiness_diffuse(material.pbr_specular_glossiness)
            self._set_pbr_specular_glossiness_glossiness(material.pbr_specular_glossiness)
            self._set_pbr_specular_glossiness_specular(material.pbr_specular_glossiness)

    def _set_pbr_specular_glossiness_diffuse(self, pbr_specular_glossiness):
        diffuse_texture = pbr_specular_glossiness.diffuse_texture
        diffuse_factor = pbr_specular_glossiness.diffuse_factor
        if not diffuse_texture:
            self._diffuse_color.Set(Gf.Vec3f(diffuse_factor[0], diffuse_factor[1], diffuse_factor[2]))
        else:
            scale_factor = diffuse_factor  # TODO: this is scale? or set from diffuse_texture_info.scale
            texture_info = self._texture_info_by_index(diffuse_texture.index)
            uv_texture = self._uv_texture("diffuseTexture", texture_info, scale_factor)
            self._apply_on_shader(uv_texture, "rgb", self._diffuse_color)
            self._apply_on_shader(uv_texture, "a", self._opacity)

    def _set_pbr_specular_glossiness_specular(self, pbr_specular_glossiness):
        specular_glossiness_texture = pbr_specular_glossiness.specular_glossiness_texture
        specular_factor = pbr_specular_glossiness.specular_factor or [1.0, 1.0, 1.0]  # TODO: defaults in material
        if not specular_glossiness_texture:
            self._specular_color.Set(tuple(specular_factor))
        else:
            scale_factor = specular_factor + [1]
            texture_info = self._texture_info_by_index(specular_glossiness_texture.index)
            uv_texture = self._uv_texture("specularTexture", texture_info, scale_factor)
            self._apply_on_shader(uv_texture, "rgb", self._specular_color)

    def _set_pbr_specular_glossiness_glossiness(self, pbr_specular_glossiness):
        specular_glossiness_texture = pbr_specular_glossiness.specular_glossiness_texture
        glossiness_factor = 1.0 if pbr_specular_glossiness.glossiness_factor is None else pbr_specular_glossiness.glossiness_factor
        roughness_factor = 1 - glossiness_factor
        if specular_glossiness_texture is None:
            self._roughness.Set(roughness_factor)
        else:
            scale_factor = [-1, -1, -1, -1]
            texture_info = self._texture_info_by_index(specular_glossiness_texture.index)
            uv_texture = self._uv_texture("glossinessTexture", texture_info, scale_factor)
            self._apply_on_shader(uv_texture, "r", self._roughness)

    def _set_pbr_base_color(self, pbr_metallic_roughness, alpha_mode):
        base_color_texture = pbr_metallic_roughness.base_color_texture
        base_color_scale = pbr_metallic_roughness.base_color_factor or [1.0, 1.0, 1.0, 1.0]
        alpha_mode = alpha_mode or AlphaMode.OPAQUE
        if alpha_mode == AlphaMode.MASK:
            alpha_mode = AlphaMode.BLEND  # Alpha Mask not supported in USDPreviewSurface

        if base_color_texture is None:
            self._diffuse_color.Set(tuple(base_color_scale[:3]))
            if alpha_mode != AlphaMode.OPAQUE:
                self._opacity.Set(base_color_scale[3])
        else:
            scale_factor = base_color_scale
            texture_info = self._texture_info_by_index(base_color_texture.index)
            uv_texture = self._uv_texture("baseColorTexture", texture_info, scale_factor)
            self._apply_on_shader(uv_texture, "rgb", self._diffuse_color)
            if alpha_mode != AlphaMode.OPAQUE:
                self._apply_on_shader(uv_texture, "a", self._opacity)

    def _set_pbr_metallic(self, pbr_metallic_roughness):
        metallic_roughness_texture = pbr_metallic_roughness.metallic_roughness_texture
        metallic_factor = 1.0 if pbr_metallic_roughness.metallic_factor is None else pbr_metallic_roughness.metallic_factor
        if not metallic_roughness_texture:
            self._metallic.Set(metallic_factor)
        else:
            scale_factor = [metallic_factor for _ in range(4)]
            texture_info = self._texture_info_by_index(metallic_roughness_texture.index)
            uv_texture = self._uv_texture("metallicTexture", texture_info, scale_factor)
            self._apply_on_shader(uv_texture, "r", self._metallic)

    def _set_pbr_roughness(self, pbr_metallic_roughness):
        metallic_roughness_texture = pbr_metallic_roughness.metallic_roughness_texture
        roughness_factor = 1.0 if pbr_metallic_roughness.roughness_factor is None else pbr_metallic_roughness.roughness_factor
        if not metallic_roughness_texture:
            self._roughness.Set(roughness_factor)
        else:
            scale_factor = [roughness_factor for i in range(4)]
            texture_info = self._texture_info_by_index(metallic_roughness_texture.index)
            uv_texture = self._uv_texture("roughnessTexture", texture_info, scale_factor)
            self._apply_on_shader(uv_texture, "r", self._roughness)


class USDPrimvarReaderFloat2(object):
    def __init__(self, stage, material_path, var_name):
        primvar = UsdShade.Shader.Define(stage, material_path.AppendChild("primvar_{}".format(var_name)))
        primvar.CreateIdAttr("UsdPrimvarReader_float2")
        primvar.CreateInput("fallback", Sdf.ValueTypeNames.Float2).Set((0, 0))
        primvar.CreateInput("varname", Sdf.ValueTypeNames.Token).Set(var_name)
        self.output = primvar.CreateOutput("result", Sdf.ValueTypeNames.Float2)


class USDUVTextureWrapMode(Enum):  # NEEDED?
    BLACK = "black"
    CLAMP = "clamp"
    REPEAT = "repeat"
    MIRROR = "mirror"


class TextureWrap(Enum):  # NEEDED?
    CLAMP_TO_EDGE = 33071
    MIRRORED_REPEAT = 33648
    REPEAT = 10497


class USDUVTexture(object):
    TEXTURE_SAMPLER_WRAP = {
        TextureWrap.CLAMP_TO_EDGE.name: "clamp",
        TextureWrap.MIRRORED_REPEAT.name: "mirror",
        TextureWrap.REPEAT.name: "repeat",
    }

    def __init__(self, name, stage, usd_material, texture, scale_factor, usd_primvar_st_arr, fallback=None):

        material_path = usd_material.GetPath()
        self._texture_shader = UsdShade.Shader.Define(stage, material_path.AppendChild(name))
        self._texture_shader.CreateIdAttr(texture.name)
        # self._wrap_s = self._texture_shader.CreateInput("wrapS", Sdf.ValueTypeNames.Token)
        # self._wrap_s.Set(USDUVTexture.TEXTURE_SAMPLER_WRAP[texture.get_wrap_s().name])
        # self._wrap_t = self._texture_shader.CreateInput("wrapT", Sdf.ValueTypeNames.Token)
        # self._wrap_t.Set(USDUVTexture.TEXTURE_SAMPLER_WRAP[texture.get_wrap_t().name])
        self._bias = self._texture_shader.CreateInput("bias", Sdf.ValueTypeNames.Float4)
        self._bias.Set((0, 0, 0, 0))
        if scale_factor is None:
            scale_factor = (1, 1, 1, 1)
            fallback = (0, 0, 0, 1)
        else:
            scale_factor = tuple(scale_factor)
        if not fallback:
            fallback = (0, 0, 0, 1)
        else:
            fallback = tuple(fallback)
        self._scale = self._texture_shader.CreateInput("scale", Sdf.ValueTypeNames.Float4)
        self._scale.Set(scale_factor)
        self._file_asset = self._texture_shader.CreateInput("file", Sdf.ValueTypeNames.Asset)
        self._file_asset.Set(texture.file)
        self._fallback = self._texture_shader.CreateInput("fallback", Sdf.ValueTypeNames.Float4)
        self._fallback.Set(fallback)
        self._st = self._texture_shader.CreateInput("st", Sdf.ValueTypeNames.Float2)
        # self._st.ConnectToSource(usd_primvar_st_arr[texture.get_texcoord_index()].get_output())

    def get_shader(self):
        return self._texture_shader
