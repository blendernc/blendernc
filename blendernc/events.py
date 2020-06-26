from enum import Enum, auto
from bpy.types import Node, NodeTree
from typing import NamedTuple, Union, List

class BlenderEventsTypes(Enum):
    tree_update = auto()  # this updates is calling last with exception of creating new node
    monad_tree_update = auto()
    node_update = auto()  # it can be called last during creation new node event
    add_node = auto()   # it is called first in update wave
    copy_node = auto()  # it is called first in update wave
    free_node = auto()  # it is called first in update wave
    add_link_to_node = auto()  # it can detects only manually created links
    node_property_update = auto()  # can be in correct in current implementation
    undo = auto()  # changes in tree does not call any other update events
    frame_change = auto()

    def print(self, updated_element=None):
        event_name = f"EVENT: {self.name: <30}"
        if updated_element is not None:
            element_data = f"IN: {updated_element.bl_idname: <25} INSTANCE: {updated_element.name: <25}"
        else:
            element_data = ""
        print(event_name + element_data)

class Event(NamedTuple):
    type: BlenderEventsTypes
    updated_element: Union[Node, NodeTree, None]

    def __eq__(self, other):
        return self.type == other

class CurrentEvents:
    events_wave: List[Event] = []

    @classmethod
    def new_event(cls, event_type: BlenderEventsTypes, updated_element=None):
        if event_type == BlenderEventsTypes.node_update:
            # such updates are not informative
            return


    @classmethod
    def is_wave_end(cls):
        # it is not correct now but should be when this module will get control over the update events
        sign_of_wave_end = [BlenderEventsTypes.tree_update, BlenderEventsTypes.node_property_update,
                            BlenderEventsTypes.monad_tree_update, BlenderEventsTypes.undo,
                            BlenderEventsTypes.frame_change]
        return True if cls.events_wave[-1] in sign_of_wave_end else False
