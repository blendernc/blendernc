import math

import bpy

from bpy.props import StringProperty, BoolProperty, FloatVectorProperty, IntProperty, FloatProperty
from bpy.types import NodeTree, NodeSocket

from . socketdata import (
    bNCGetSocketInfo, bNCGetSocket, bNCSetSocket, bNCForgetSocket,
    bNCNoDataError, sentinel)

from collections import defaultdict

socket_colors = {
    "bNCnetcdfSocket": (0.6, 1.0, 0.6, 1.0),
    "bNCpercentSocket": (0.8, 0.8, 0.8, 0.3),
}


# Node Sockets modifyed from: 
# https://github.com/nortikin/sverchok/blob/master/core/sockets.py
class bNCSocketDefault:
    """ Base class for all Sockets """
    use_prop: BoolProperty(default=False)

    use_expander: BoolProperty(default=True)
    use_quicklink: BoolProperty(default=True)
    expanded: BoolProperty(default=False)
    custom_draw: StringProperty(description="For name of method which will draw socket UI (optionally)")
    prop_name: StringProperty(default='', description="For displaying node property in socket UI")

    quicklink_func_name: StringProperty(default="", name="quicklink_func_name")

    def get_prop_name(self):
        if self.node and hasattr(self.node, 'does_support_draft_mode') and self.node.does_support_draft_mode() and hasattr(self.node.id_data, 'bn_draft') and self.node.id_data.bn_draft:
            prop_name_draft = self.node.draft_properties_mapping.get(self.prop_name, None)
            if prop_name_draft:
                return prop_name_draft
            else:
                return self.prop_name
        else:
            return self.prop_name

    @property
    def other(self):
        return get_other_socket(self)

    def set_default(self, value):
        if self.get_prop_name():
            setattr(self.node, self.get_prop_name(), value)

    @property
    def socket_id(self):
        """Id of socket used by data_cache"""
        return str(hash(self.node.node_id + self.identifier))

    @property
    def index(self):
        """Index of socket"""
        node = self.node
        sockets = node.outputs if self.is_output else node.inputs
        for i, s in enumerate(sockets):
            if s == self:
                return i

    @property
    def hide_safe(self):
        return self.hide

    @hide_safe.setter
    def hide_safe(self, value):
        # handles both input and output.
        if self.is_linked and value:
            for link in self.links:
                self.id_data.bn_links.remove(self.id_data, link)
                self.id_data.links.remove(link)

        self.hide = value

    def bnc_set(self, data):
        """Set output data"""
        bNCSetSocket(self, data)

    def bnc_forget(self):
        """Delete socket memory"""
        bNCForgetSocket(self)

    def replace_socket(self, new_type, new_name=None):
        """Replace a socket with a socket of new_type and keep links,
        return the new socket, the old reference might be invalid"""
        return replace_socket(self, new_type, new_name)

    @property
    def extra_info(self):
        # print("getting base extra info")
        return ""

    def get_socket_info(self):
        """ Return Number of encapsulated data lists, or empty str  """
        try:
            return bNCGetSocketInfo(self)
        except:
            return ''

    def draw_expander_template(self, context, layout, prop_origin, prop_name="prop"):

        if self.bl_idname == "bNCStringsSocket":
            layout.prop(prop_origin, prop_name)
        else:
            if self.use_expander:
                split = layout.split(factor=.2, align=True)
                c1 = split.column(align=True)
                c2 = split.column(align=True)

                if self.expanded:
                    c1.prop(self, "expanded", icon='TRIA_UP', text='')
                    c1.label(text=self.name[0])
                    c2.prop(prop_origin, prop_name, text="", expand=True)
                else:
                    c1.prop(self, "expanded", icon='TRIA_DOWN', text="")
                    row = c2.row(align=True)
                    if self.bl_idname == "bNCColorSocket":
                        row.prop(prop_origin, prop_name)
                    else:
                        row.template_component_menu(prop_origin, prop_name, name=self.name)

            else:
                layout.template_component_menu(prop_origin, prop_name, name=self.name)

    def infer_visible_location_of_socket(self, node):
        # currently only handles inputs.
        if self.is_output:
            return 0

        counter = 0
        for socket in node.inputs:
            if not socket.hide:
                if socket == self:
                    break
                counter += 1

        return counter

    def draw_quick_link(self, context, layout, node):

        if self.use_quicklink:
            if self.bl_idname == "bNCMatrixSocket":
                new_node_idname = "bNCMatrixInNodeMK4"
            elif self.bl_idname == "bNCVerticesSocket":
                new_node_idname = "GenVectorsNode"
            else:
                return

            op = layout.operator('node.bnc_quicklink_new_node_input', text="", icon="PLUGIN")
            op.socket_index = self.index
            op.origin = node.name
            op.new_node_idname = new_node_idname
            op.new_node_offsetx = -200 - 40 * self.index  ## this is not so useful, we should infer visible socket location
            op.new_node_offsety = -30 * self.index  ## this is not so useful, we should infer visible socket location

    def draw(self, context, layout, node, text):

        # just handle custom draw..be it input or output.
        # hasattr may be excessive here
        if hasattr(self, 'custom_draw') and self.custom_draw:
            # does the node have the draw function referred to by
            # the string stored in socket's custom_draw attribute
            if hasattr(node, self.custom_draw):
                getattr(node, self.custom_draw)(self, context, layout)
                return

        if self.bl_idname == 'bNCStringsSocket':
            if node.bl_idname in {'bNCScriptNodeLite', 'bNCScriptNode'}:
                if not self.is_output and not self.is_linked and self.prop_type:
                    layout.prop(node, self.prop_type, index=self.prop_index, text=self.name)
                    return
            elif node.bl_idname in {'bNCSNFunctor'} and not self.is_output:
                if not self.is_linked:
                    layout.prop(node, self.get_prop_name(), text=self.name)
                    return

        if self.is_linked:  # linked INPUT or OUTPUT
            t = text
            if not self.is_output:
                if self.get_prop_name():
                    prop = node.rna_type.properties.get(self.get_prop_name(), None)
                    t = prop.name if prop else text
            info_text = t + '. ' + bNCGetSocketInfo(self)
            info_text += self.extra_info
            layout.label(text=info_text)

        elif self.is_output:  # unlinked OUTPUT
            layout.label(text=text)

        else:  # unlinked INPUT
            if self.get_prop_name():  # has property
                self.draw_expander_template(context, layout, prop_origin=node, prop_name=self.get_prop_name())

            elif self.use_prop:  # no property but use default prop
                self.draw_expander_template(context, layout, prop_origin=self)

            elif self.quicklink_func_name:
                try:
                    getattr(node, self.quicklink_func_name)(self, context, layout, node)
                except Exception as e:
                    self.draw_quick_link(context, layout, node)
                layout.label(text=text)

            else:  # no property and not use default prop
                self.draw_quick_link(context, layout, node)
                layout.label(text=text)

    def draw_color(self, context, node):
        return socket_colors[self.bl_idname]

    def needs_data_conversion(self):
        if not self.is_linked:
            return False
        return self.other.bl_idname != self.bl_idname

    def convert_data(self, source_data, implicit_conversions=None):
        if not self.needs_data_conversion():
            return source_data
        else:
            policy = self.node.get_implicit_conversions(self.name, implicit_conversions)
            self.node.debug(f"Trying to convert data for input socket {self.name} by {policy}")
            return policy.convert(self, source_data)
    
    def unlink(self,link):
        return self.id_data.links.remove(link)

    
class bNCnetcdfSocket(NodeSocket, bNCSocketDefault):
    bl_idname = "bNCnetcdfSocket"
    bl_label = "netCDF Socket"

    dataset: defaultdict()
    unique_identifier: StringProperty()

    def draw(self, context, layout, node, text):
        layout.label(text=text)

    def draw_color(self, context, node):
        return (0.68,  0.85,  0.90, 1)

    def bnc_get(self, default=sentinel, deepcopy=True, implicit_conversions=None):
        if self.is_linked and not self.is_output:
            return self.convert_data(bNCGetSocket(self, deepcopy), implicit_conversions)
        elif self.text:
            return [self.text]
        elif default is sentinel:
            raise bNCNoDataError(self)
        else:
            return default

class bNCstringSocket(NodeSocket, bNCSocketDefault):
    bl_idname = "bNCstringSocket"
    bl_label = "String Socket"

    text: StringProperty()

    def draw(self, context, layout, node, text):
        layout.label(text=text)

    def draw_color(self, context, node):
        return (0.68,  0.85,  0.90, 1)

    def bnc_get(self, default=sentinel, deepcopy=True, implicit_conversions=None):
        if self.is_linked and not self.is_output:
            return self.convert_data(bNCGetSocket(self, deepcopy), implicit_conversions)
        elif self.text:
            return [self.text]
        elif default is sentinel:
            raise bNCNoDataError(self)
        else:
            return default


# classes = [
#     bNCnetcdfSocket
# ]

# register, unregister = bpy.utils.register_classes_factory(classes)

