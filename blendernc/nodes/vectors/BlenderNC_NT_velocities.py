import bpy
from mathutils import Matrix

context = bpy.context

## Only works with particle instances.
dg = context.evaluated_depsgraph_get()
ob = context.object.evaluated_get(dg)

ps = ob.particle_systems.active
po = ps.settings.instance_object

for p in ps.particles:
    p.location = (1, 1, 1)
