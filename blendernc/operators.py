import bpy
from bpy_extras.io_utils import ImportHelper

from .decorators import check_if_node_tree_exists, create_Shader_nodes, is_linked
from .messages import report_error, report_errors
from .node_utils import create_links, create_nodes
from .utils import (
    GRID_DIMS_PROPERTY,
    add_attribute,
    assign_modifier_to_object,
    extract_dimensions_of_grid,
    get_2D_coords,
    get_datacube_path,
    get_dataset,
    get_grid_coords,
    grid_dims,
    grid_material,
    look_up_object_and_mesh,
    stack_2D_coords,
)


class Import_OT_mfdataset(bpy.types.Operator, ImportHelper):
    """Import a NetCDF/GRIB/Zarr dataset into BlenderNC."""

    bl_idname = "blendernc.import_mfdataset"

    bl_label = "Load Datacube"
    bl_description = "Import Datacube with xarray"

    node_name: bpy.props.StringProperty(default="")
    node_tree: bpy.props.StringProperty(default="")

    filter_glob: bpy.props.StringProperty(
        default="*.nc;*.grib;*.zarr",
        options={"HIDDEN"},
    )
    """An instance of the original StringProperty."""

    directory: bpy.props.StringProperty(
        subtype="DIR_PATH", options={"SKIP_SAVE", "HIDDEN"}
    )
    files: bpy.props.CollectionProperty(
        type=bpy.types.OperatorFileListElement, options={"SKIP_SAVE", "HIDDEN"}
    )

    @report_errors
    @check_if_node_tree_exists
    def execute(self, context):
        """Store the chosen file path on the import node and load the dataset.

        Multiple selected files are collapsed into a single glob pattern.
        Assigning the path to the node loads the dataset through the
        property's update callback. When invoked from the 3D view, the path
        is mirrored to the UI properties.

        Parameters
        ----------
        context : bpy.types.Context
            Current Blender context.

        Returns
        -------
        set
            ``{"FINISHED"}``, or ``{"CANCELLED"}`` with a report when the
            files share no pattern or the dataset cannot be opened.
        """
        node_tree = bpy.data.node_groups.get(self.node_tree)
        import_node = node_tree.nodes.get(self.node_name)

        datacube_path = get_datacube_path(self.directory, self.files)
        import_node.datacube_file = datacube_path
        if get_dataset(import_node.BNC_datastructs[0]) is None:
            return report_error(self, f"Could not open {datacube_path}.")

        area = context.area
        if not bpy.app.background and area is not None and area.type == "VIEW_3D":
            context.scene.BlenderNC_UI_Properties.datacube_file = datacube_path

        return {"FINISHED"}


class Import_OT_CreateGrid(bpy.types.Operator):
    """Create mesh from datacube coordinates."""

    bl_idname = "blendernc.create_grid_from_coords"

    bl_label = "Create Grid"
    bl_description = "Create mesh from datacube coordinates"

    node_name: bpy.props.StringProperty(default="")
    node_tree: bpy.props.StringProperty(default="")

    @report_errors
    @is_linked
    def execute(self, context):
        """Bake a mesh grid from the coordinates linked to a grid node.

        A Mesh Grid geometry node sized from the coordinate dimensions is applied
        to the target object, the 2-D coordinate arrays are written to a
        ``Coordinates`` vector attribute, and a second geometry node modifier
        moves the vertices to those positions before removing the attribute.
        Finally the grid node is updated so its ``Object`` output exists and
        downstream texture nodes are rewritten for the new mesh.

        Parameters
        ----------
        context : bpy.types.Context
            Current Blender context.

        Returns
        -------
        set
            ``{"FINISHED"}``, or ``{"CANCELLED"}`` with a report if no input
            is linked or the coordinates cannot form a grid.
        """

        node_tree = bpy.data.node_groups.get(self.node_tree)
        grid_node = node_tree.nodes.get(self.node_name)

        # Work out the vertex layout before touching Blender data, so a
        # dataset that cannot form a grid is reported without side effects.
        grid_coords = get_grid_coords(grid_node)
        dims = grid_dims(grid_coords)
        grid_coords = get_2D_coords(grid_coords)
        vertices_x, vertices_y = extract_dimensions_of_grid(grid_coords)
        flattened_coords = stack_2D_coords(grid_coords)

        obj, mesh = look_up_object_and_mesh(grid_node.grid_obj_name)

        modifier, grid_nodetree = assign_modifier_to_object(obj, obj.name)
        nodes = {
            "GeometryNodeMeshGrid": {"links": {"Mesh": {"NodeGroupOutput": "Geometry"}}}
        }
        create_nodes(grid_nodetree, nodes)
        create_links(grid_nodetree, nodes)
        mesh_grid_node = nodes["GeometryNodeMeshGrid"]["node"]
        mesh_grid_node.inputs["Vertices X"].default_value = vertices_x
        mesh_grid_node.inputs["Vertices Y"].default_value = vertices_y
        _apply_modifier(context, obj, modifier)

        attr = add_attribute(
            mesh, "Coordinates", attr_type="FLOAT_VECTOR", domain="POINT"
        )
        attr.data.foreach_set("vector", flattened_coords)

        modifier, grid_nodetree = assign_modifier_to_object(obj, "apply_grid_coords")
        nodes = {
            "NodeGroupInput": {
                "links": {"Geometry": {"GeometryNodeSetPosition": "Geometry"}}
            },
            "GeometryNodeInputNamedAttribute": {
                "links": {"Attribute": {"GeometryNodeSetPosition": "Position"}}
            },
            "GeometryNodeSetPosition": {
                "links": {"Geometry": {"GeometryNodeRemoveAttribute": "Geometry"}}
            },
            "GeometryNodeRemoveAttribute": {
                "links": {"Geometry": {"GeometryNodeSetMaterial": "Geometry"}}
            },
            "GeometryNodeSetMaterial": {
                "links": {"Geometry": {"NodeGroupOutput": "Geometry"}}
            },
        }
        create_nodes(grid_nodetree, nodes)
        create_links(grid_nodetree, nodes)
        named_attribute = nodes["GeometryNodeInputNamedAttribute"]["node"]
        named_attribute.data_type = "FLOAT_VECTOR"
        named_attribute.inputs["Name"].default_value = "Coordinates"
        remove_attribute = nodes["GeometryNodeRemoveAttribute"]["node"]
        remove_attribute.inputs["Name"].default_value = "Coordinates"
        set_material = nodes["GeometryNodeSetMaterial"]["node"]
        set_material.inputs["Material"].default_value = grid_material(grid_node)
        _apply_modifier(context, obj, modifier)

        # Texture nodes read the dims to orient fields the same way.
        if dims:
            mesh[GRID_DIMS_PROPERTY] = ",".join(dims)
        else:
            mesh.pop(GRID_DIMS_PROPERTY, None)

        # Remember what was baked so the node can tell when it is stale, then
        # let it expose the object and refresh the nodes reading from it.
        grid_node.baked_object = obj.name
        grid_node.baked_slicing = grid_node.BNC_datastructs[0].slicing
        grid_node.update()

        return {"FINISHED"}


def _apply_modifier(context, obj, modifier):
    """Apply ``modifier`` on ``obj`` without changing the active object."""
    with context.temp_override(object=obj, active_object=obj):
        bpy.ops.object.modifier_apply(modifier=modifier.name)


class BlenderNCBakeFromAttribute(bpy.types.Operator):
    bl_idname = "blendernc.bake_from_attribute"
    bl_label = "Bake From Attribute"
    bl_description = "Create texture from 2D variable of datacube"

    node_name: bpy.props.StringProperty(default="")
    node_tree: bpy.props.StringProperty(default="")

    @report_errors
    @check_if_node_tree_exists
    def execute(self, context):
        """Bake a texture from a 2D variable of a datacube.

        A Material is created and applied to the target object,
        the 2-D variable are written to a float attribute.
        This attribute is then used in the material to create a color.

        Parameters
        ----------
        context : bpy.types.Context
            Current Blender context.

        Returns
        -------
        set
            ``{"FINISHED"}``
        """

        node_tree = bpy.data.node_groups.get(self.node_tree)
        texture_node = node_tree.nodes.get("Datacube Texture")
        obj = texture_node.inputs["Object"].default_value
        var = texture_node.inputs["Variable"].default_value
        if var in bpy.data.materials:
            self.material = bpy.data.materials.get(var)
        else:
            self.material = bpy.data.materials.new(name=var)
        obj.data.materials.append(self.material)
        obj.active_material = self.material
        create_Shader_nodes(self, context)
        shader_node_tree = self.material.node_tree
        attr_node = shader_node_tree.nodes.get("Attribute")
        attr_node.attribute_name = var
        attr_node = shader_node_tree.nodes.get("Attribute.001")
        attr_node.attribute_type = "OBJECT"
        attr_node.attribute_name = "Max value"
        attr_node = shader_node_tree.nodes.get("Attribute.002")
        attr_node.attribute_type = "OBJECT"
        attr_node.attribute_name = "Min value"

        return {"FINISHED"}
