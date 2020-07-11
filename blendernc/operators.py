# Imports
import bpy

from os.path import abspath, isfile, join

from . python_functions import (load_frame, update_image, get_node, get_var, update_nodes, 
                    update_proxy_file, BlenderncEngine)

from bpy_extras.io_utils import ImportHelper

bNCEngine = BlenderncEngine()

class BlenderNC_OT_ncload(bpy.types.Operator):
    bl_idname = "blendernc.ncload"
    bl_label = "Load netcdf file"
    bl_description = "Loads netcdf file"
    bl_options = {"REGISTER", "UNDO"}

    file_path: bpy.props.StringProperty(
        name="File path",
        description="Path to the netCDF file that will be loaded.",
        subtype="FILE_PATH",
        # default="",
    )

    node_group: bpy.props.StringProperty(
        name="node",
        description="Node calling operator"
    )

    node: bpy.props.StringProperty(
        name="node",
        description="Node calling operator"
    )

    def execute(self, context):
        if not self.file_path:
            self.report({'INFO'}, "Select a file!")
            return {'FINISHED'}
        file_path = abspath(self.file_path)

        node = get_node(self.node_group,self.node)
        # TODO: allow xarray.open_mfdataset if wildcard "*" use in name. 
        # Useful for large datasets. Implement node with chunks if file is huge.
        
        unique_identifier = node.blendernc_dataset_identifier
        node.blendernc_dict[unique_identifier] = bNCEngine.check_files_netcdf(file_path)
        self.report({'INFO'}, "Lazy load of %s!" % file_path)
        var_names = get_var(node.blendernc_dict[unique_identifier]["Dataset"])
        bpy.types.Scene.blendernc_netcdf_vars = bpy.props.EnumProperty(items=var_names,
                                                                name="",update=update_nodes)
        # Create new node in BlenderNC node
        blendernc_nodes = [keys for keys in bpy.data.node_groups.keys() if ('BlenderNC' in keys or 'NodeTree' in keys)]
        if not blendernc_nodes:
            bpy.data.node_groups.new("BlenderNC","BlenderNC")
            bpy.data.node_groups['BlenderNC'].use_fake_user = True
        
        if not bpy.data.node_groups[-1].nodes:
            bpy.data.node_groups[-1].nodes.new("netCDFNode")

        return {'FINISHED'}

class BlenderNC_OT_ncload_Sui(bpy.types.Operator):
    bl_idname = "blendernc.ncload_sui"
    bl_label = "Load netcdf file"
    bl_description = "Loads netcdf file"
    bl_options = {"REGISTER", "UNDO"}

    file_path: bpy.props.StringProperty(
        name="File path",
        description="Path to the netCDF file that will be loaded.",
        subtype="FILE_PATH",
    )

    def execute(self, context):
        scene = context.scene
        netcdf = bpy.data.node_groups.get("BlenderNC").nodes.get("netCDF input")
        node_group = bpy.data.node_groups.get("BlenderNC")
        if not node_group.nodes.get("Resolution"):
            ####################
            resol = node_group.nodes.new("netCDFResolution")
            resol.location[0]=30
            output = node_group.nodes.new("netCDFOutput")
            output.location[0]=190
        else: 
            resol = node_group.nodes.get("Resolution")
            output = node_group.nodes.get("Output")
        #LINK 
        node_group.links.new(resol.inputs[0], netcdf.outputs[0])

        resol.blendernc_resolution = scene.blendernc_resolution
            
        #LINK
        node_group.links.new(output.inputs[0], resol.outputs[0])
        bpy.ops.image.new(name="BlenderNC_default", width=1024, height=1024, 
                            color=(0.0, 0.0, 0.0, 1.0), alpha=True, 
                            generated_type='BLANK', float=True)
        output.image = bpy.data.images.get('BlenderNC_default')
        output.update_on_frame_change = scene.blendernc_animate
        output.update()
        return {'FINISHED'}


class BlenderNC_OT_var(bpy.types.Operator):
    bl_idname = "blendernc.var"
    bl_label = "Load netcdf vars"
    bl_description = "Loads netcdf vars"
    bl_options = {"REGISTER", "UNDO"}

    file_path: bpy.props.StringProperty()
    
    def execute(self, context):
        if not self.file_path:
            self.report({'INFO'}, "Select a file!")
            return {'FINISHED'}

        blendernc_nodes = [ bpy.data.node_groups[keys] for keys in bpy.data.node_groups.keys() if (bpy.data.node_groups[keys].bl_label == 'BlenderNC' and keys == 'BlenderNC')]
        if not blendernc_nodes:
            bpy.data.node_groups.new("BlenderNC","BlenderNC")
            bpy.data.node_groups["BlenderNC"].use_fake_user = True
        
        node_group = bpy.data.node_groups.get("BlenderNC")
        if not node_group.nodes:
            path = node_group.nodes.new("netCDFPath")
            path.location[0]=-300
            netcdf = node_group.nodes.new("netCDFNode")
            netcdf.location[0]=-130
        else:
            path = node_group.nodes.get('netCDF Path')
            netcdf = node_group.nodes.get("netCDF input")
        path.blendernc_file = self.file_path
        #LINK nodes
        if not node_group.links:
            node_group.links.new(netcdf.inputs[0], path.outputs[0])
        
        netcdf.update()
        return {'FINISHED'}

class BlenderNC_OT_preloader(bpy.types.Operator):
    bl_idname = "blendernc.preloader"
    bl_label = "Preload a range of variable steps into memory"
    bl_description = "Preload a range of variable steps into memory"
    bl_options = {"REGISTER", "UNDO"}
    file_name: bpy.props.StringProperty(
        name="File name",
        description="Path to the netCDF file that will be loaded.",
        subtype="FILE_PATH",
        # default="",
    )
    var_name: bpy.props.StringProperty(
        name="File name",
        description="Path to the netCDF file that will be loaded.",
        subtype="FILE_PATH",
        # default="",
    )
    frame_start: bpy.props.IntProperty(
        default=1,
        name="Start",
    )

    frame_end: bpy.props.IntProperty(
        default=250,
        name="End",
    )

    def execute(self, context):
        if not self.file_name:
            self.report({'INFO'}, "Select a file!")
            return {'FINISHED'}
        file_path = abspath(self.file_name)

        scene = context.scene
        scene.nc_dictionary[file_path] = bNCEngine.check_files_netcdf(file_path)

        var_name = self.var_name
        if not var_name:
            self.report({'INFO'}, "Select a variable!")
            return {'FINISHED'}

        # For each frame check if the frame is already in memory
        frame_start, frame_end = self.frame_start, self.frame_end
        for frame in range(frame_start, frame_end):
            print("Frame %i loaded!" % frame)
            load_frame(context, file_path,var_name,frame)

        self.report({'INFO'}, "Frames %i to %i have been loaded!" % (frame_start, frame_end))
        return {'FINISHED'}


class BlenderNC_OT_netcdf2img(bpy.types.Operator):
    bl_idname = "blendernc.nc2img"
    bl_label = "From netcdf to image"
    bl_description = "Updates an image with netcdf data"
    node: bpy.props.StringProperty()
    node_group: bpy.props.StringProperty()
    step: bpy.props.IntProperty()
    flip: bpy.props.BoolProperty()
    image: bpy.props.StringProperty()

    def execute(self, context):
        update_image(context, self.node, self.node_group, self.step, self.image)
        return {'FINISHED'}

class BlenderNC_OT_apply_material(bpy.types.Operator):
    bl_label = 'Load netCDF'
    bl_idname = 'blendernc.apply_material'
    bl_description = 'Apply texture to material for simple cases'
    bl_context = 'objectmode'
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        act_obj = context.active_object
        sel_obj = context.scene.blendernc_meshes 
        if not sel_obj:
            sel_obj = act_obj

        blendernc_materials = [material for material in bpy.data.materials if 'BlenderNC_default' in material.name]
        if len(blendernc_materials)!=0:    
            blendernc_material = blendernc_materials[-1]
        else:
            bpy.ops.material.new()
            blendernc_material = bpy.data.materials[-1]
            blendernc_material.name = "BlenderNC_default"

        if len(blendernc_material.node_tree.nodes.keys())==2:
            texcoord = blendernc_material.node_tree.nodes.new('ShaderNodeTexCoord')
            texcoord.location = (-760,250)
            imagetex = blendernc_material.node_tree.nodes.new('ShaderNodeTexImage')
            imagetex.location = (-580,250)
            imagetex.interpolation = 'Smart'
            cmap = blendernc_material.node_tree.nodes.new('cmapsNode')
            cmap.location = (-290,250)
            bump = blendernc_material.node_tree.nodes.new('ShaderNodeBump')
            bump.location = (-290,-50)
            
        else:
            texcoord =  blendernc_material.node_tree.nodes.get('Texture Coordinate')
            imagetex = blendernc_material.node_tree.nodes.get('Image Texture')
            cmap = blendernc_material.node_tree.nodes.get('Colormap')
            bump = blendernc_material.node_tree.nodes.get('Bump')

        P_BSDF = blendernc_material.node_tree.nodes.get('Principled BSDF')
        output = blendernc_material.node_tree.nodes.get('Image Texture')
        
        if act_obj.name == "Icosphere" or sel_obj.name == "Icosphere":
            texcoord_link = texcoord.outputs.get('Generated')
            imagetex.projection = 'SPHERE'
        else:
            texcoord_link = texcoord.outputs.get('UV')
            imagetex.projection = 'FLAT'

        blendernc_material.node_tree.links.new(imagetex.inputs[0],texcoord_link)
        blendernc_material.node_tree.links.new(cmap.inputs[0],imagetex.outputs[0])
        blendernc_material.node_tree.links.new(bump.inputs[2],imagetex.outputs[0])
        blendernc_material.node_tree.links.new(P_BSDF.inputs[0],cmap.outputs[0])
        blendernc_material.node_tree.links.new(P_BSDF.inputs[19],bump.outputs[0])

        imagetex.image = bpy.data.images.get('BlenderNC_default')

        if sel_obj or act_obj.type == 'MESH':
            sel_obj.active_material = bpy.data.materials.get('BlenderNC_default')

        return {'FINISHED'}

import os

class ImportnetCDFCollection(bpy.types.PropertyGroup):
    name : bpy.props.StringProperty(
            name="File Path",
            description="Filepath used for importing the file",
            maxlen=1024,
            subtype='FILE_PATH',
            )


class Import_OT_mfnetCDF(bpy.types.Operator, ImportHelper):
    """
    
    """
    bl_idname = "blendernc.import_mfnetcdf"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Load Netcdf"

    # ImportHelper mixin class uses this
    filename_ext : ".nc"

    filter_glob : bpy.props.StringProperty(
            default="*.nc",
            options={'HIDDEN'},
            )
            
    files : bpy.props.CollectionProperty(type=ImportnetCDFCollection)

    node_group: bpy.props.StringProperty(
        name="node_group",
        description="Node calling operator"
    )

    node: bpy.props.StringProperty(
        name="node",
        description="Node calling operator"
    )

    def execute(self, context):
        split_path = self.properties.filepath.split('/')[0:-1]
        fdir = ('/'.join(str(dir) for dir in split_path))

        if len(self.files) == 1:
            path = join(fdir,self.files[0].name)
        else:
            list_files = [join(fdir,f.name) for f in self.files]
            common_name = findCommonName([f.name for f in self.files])
            path = join(fdir,common_name)
        
        if self.node_group != '' and self.node != '':
            bpy.data.node_groups.get(self.node_group).nodes.get(self.node).blendernc_file=path
        else:
            context.scene.blendernc_file = path
        
        return {'FINISHED'}

def findCommonName(filenames):
    import difflib
    cfname = ''
    fcounter=0
    while (not cfname or len(filenames) == fcounter):
        S = difflib.SequenceMatcher(None,filenames[fcounter], filenames[fcounter+1])

        for block in S.get_matching_blocks():
            if block.a == block.b and block.size!=0:
                if len(cfname)!=0 and len(cfname)!= block.a:
                    cfname = cfname+'*'
                cfname = cfname+filenames[fcounter][block.a:block.a+block.size]
            elif block.size==0:
                pass
            else:
                raise ValueError("Filenames don't match")
        fcounter+=1
    return cfname