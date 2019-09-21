import bpy

from bpy.props import (BoolProperty,
                       IntProperty,
                       FloatVectorProperty,
                       PointerProperty,
                       FloatProperty
                       )


class RW4AnimProperties(bpy.types.PropertyGroup):
    @classmethod
    def register(cls):
        bpy.types.Action.rw4 = PointerProperty(type=RW4AnimProperties)

        cls.is_morph_handle = BoolProperty(
            name="Morph Handle",
            description="Check if you want this action to be a morph handle and not a movement animation",
            default=False
        )
        cls.initial_pos = FloatVectorProperty(
            name="Start Position",
            subtype='XYZ',
            precision=3,
            description="Handle start position"
        )
        cls.final_pos = FloatVectorProperty(
            name="Final Position",
            subtype='XYZ',
            precision=3,
            description="Handle final position"
        )
        cls.default_progress = FloatProperty(
            name="Default Progress",
            default=0,
            min=0.0,
            max=100.0,
            subtype='PERCENTAGE'
        )

    @classmethod
    def unregister(cls):
        del bpy.types.Action.rw4


class SPORE_UL_rw_anims(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index, flt_flag):
        # We could write some code to decide which icon to use here...
        custom_icon = 'OBJECT_DATAMODE'

        # Make sure your code supports all 3 layout types
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=item.name, icon=custom_icon)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=item.name, icon=custom_icon)


class SPORE_PT_rw_anims(bpy.types.Panel):
    bl_label = "RenderWare4 Animations"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'scene'

    def draw(self, context):
        self.layout.use_property_split = True

        self.layout.template_list("SPORE_UL_rw_anims", "The_List", bpy.data, "actions", context.scene, "rw4_list_index")

        if len(bpy.data.actions) > 0:
            item = bpy.data.actions[context.scene.rw4_list_index].rw4
            self.layout.prop(item, 'is_morph_handle')

            if item.is_morph_handle:
                self.layout.prop(item, 'initial_pos')
                self.layout.prop(item, 'final_pos')
                self.layout.prop(item, 'default_progress')
        

def register():
    bpy.utils.register_class(SPORE_UL_rw_anims)
    bpy.utils.register_class(RW4AnimProperties)
    bpy.utils.register_class(SPORE_PT_rw_anims)
    bpy.types.Scene.rw4_list_index = IntProperty(name="Index for rw4_list", default=0)  # , update=update_action_list)


def unregister():
    bpy.utils.unregister_class(SPORE_PT_rw_anims)
    bpy.utils.unregister_class(RW4AnimProperties)
    bpy.utils.unregister_class(SPORE_UL_rw_anims)

    del bpy.types.Scene.rw4_list_index
