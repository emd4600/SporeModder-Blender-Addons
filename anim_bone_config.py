import bpy

from bpy.props import (BoolProperty,
                       IntProperty,
                       FloatVectorProperty,
                       PointerProperty,
                       FloatProperty,
                       EnumProperty,
                       StringProperty,
                       CollectionProperty
                       )


ANIMATION_NAMES = {
    'eye': ('ClsdOpen', 'MadSad', 'Scared'),
    'slid': ('TurnOn',),
    'mvcl': ('Idle', 'Move', 'Stun', 'Impact', 'Stop'),
    'liqd': ('TurnOn',),
    'mtcl': ('ClsdOpen', 'Breathe', 'mtcl_Stun', 'mtcl_Impact'),
    'ear': ('DroopRaise',),
    'wpch': ('Stun', 'Impact', 'ChargeUp', 'ChargeHold', 'ChargeRelease'),
    'wpps': ('Stun', 'Impact', 'ChargeUp', 'ChargeHold', 'ChargeRelease'),
    'skrs': ('ClsdOpen', 'TurnOn'),
    'shot': ('TurnOn',),
    'gest': ('ClsdOpen', 'TurnOn'),
    'eycl': ('eycl_ClsdOpen', 'Stun', 'eycl_Impact', 'eycl_MadSad', 'eycl_Scared'),
    'mout': ('mout_ClsdOpen', 'SmileFrown', 'LickAir', 'Unique'),
    'wpcl': ('Idle', 'Stun', 'Impact', 'Attack'),
    'wpel': ('Stun', 'Impact', 'ChargeUp', 'ChargeHold', 'ChargeRelease'),
    'root': ('Scale', 'Data1', 'Data2', 'Data3', 'Data4', 'Data5'),
    'grsp': ('ClsdOpen', 'Point'),
    'slsh': ('TurnOn',),
    'wing': ('Tuck', 'wing_Bend'),
    'foot': ('Bend',)
}


ENUM_LIMB_MODIFIER = (
    ('none', "None", ""),
    ('0x1000', "Closest Spine", "Selects the first spine from the body"),  # 0x1000
    ('0x1400', "0x1400", ""),
    ('0xC00', "0xC00", ""),
    ('0x800', "0x800", ""),
    ('0x400', "0x400", ""),
    ('0x800000', "0x800000", ""),
    ('0x800400', "0x800400", ""),
    ('0x1800', "0x1800", ""),
    ('0x1C00', "0x1C00", ""),
)


ENUM_SELECTX = (
    ('all', "All", ""),
    ('left', "Left", "Selects bodies in the left halfspace of the creature"),
    ('center', "Center", "Selects bodies in the center (in X axis) area of the creature"),
    ('right', "Right", "Selects bodies in the right halfspace of the creature"),
    ('localLeft', "Local Left", "Selects bodies in the left halfspace of the space comprised by all bodies that have the specified capability"),
    ('localCenter', "Local Center", "Selects bodies in the center area (in X axis) of the space comprised by all bodies that have the specified capability"),
    ('localRight', "Local Right", "Selects bodies in the right halfspace of the space comprised by all bodies that have the specified capability"),
)


ENUM_SELECTY = (
    ('all', "All", ""),
    ('front', "Front", "Selects bodies in the front halfspace of te creature"),
    ('center', "Center", "Selects bodies in the center (in Y axis) area of the creature"),
    ('back', "Back", "Selects bodies in the back halfspace of the creature"),
    ('localFront', "Local Front", "Selects bodies in the front halfspace of the space comprised by all bodies that have the specified capability"),
    ('localCenter', "Local Center", "Selects bodies in the center area (in Y axis) of the space comprised by all bodies that have the specified capability"),
    ('localBack', "Local Back", "Selects bodies in the back halfspace of the space comprised by all bodies that have the specified capability"),
)


ENUM_SELECTZ = (
    ('all', "All", ""),
    ('top', "Top", "Selects bodies in the top halfspace of te creature"),
    ('center', "Center", "Selects bodies in the center (in Z axis) area of the creature"),
    ('bottom', "Bottom", "Selects bodies in the bottom halfspace of the creature"),
    ('localTop', "Local Top", "Selects bodies in the top halfspace of the space comprised by all bodies that have the specified capability"),
    ('localCenter', "Local Center", "Selects bodies in the center area (in Z axis) of the space comprised by all bodies that have the specified capability"),
    ('localBottom', "Local Bottom", "Selects bodies in the bottom halfspace of the space comprised by all bodies that have the specified capability"),
)


ENUM_EXTENT = (
    ('none', "None", ""),
    ('LeftMost', "LeftMost", "0x2000"),
    ('RightMost', "RightMost", "0x4000"),
    ('FrontMost', "FrontMost", "0x6000"),
    ('BackMost', "BackMost", "0x8000"),
    ('TopMost', "TopMost", "0xA000"),
    ('BottomMost', "BottomMost", "0xC000"),
)


ENUM_CAPABILITY = (
    ('all', "All", ""),
    ('frame', "Creature Frame", ""),
    ('root', "Root (root)", ""),
    ('spin', "Spine (spin)", ""),
    ('limb', "Limb (limb)", ""),
    ('foot', "Foot (foot)", ""),
    ('psft', "Pseudo Foot (psft)", ""),
    ('nstr', "No Stretch (nstr)", ""),
    ('weap', "Weapon (weap)", ""),
    ('gest', "Gesture (gest)", ""),
    ('grsp', "Grasper (grsp)", ""),
    ('ear', "Ear (ear)", ""),
    ('eye', "Eye (eye)", ""),
    ('mout', "Mouth (mout)", ""),
    ('wing', "Wing (wing)", ""),
    ('slsh', "Slash (slsh)", ""),
    ('poke', "Poke (poke)", ""),
    ('bash', "Bash (bash)", ""),
    ('liqd', "Liquid (liqd)", ""),
    ('slid', "Solid (slid)", ""),
    ('shot', "Shoot (shot)", ""),
    ('prch', "Perch (prch)", ""),
    ('frut', "Fruit (frut)", ""),
    ('fin', "Fin (fin)", ""),
    ('dvis', "Day Vision (dvis)", ""),
    ('nvis', "Night Vision (nvis)", ""),
    ('carn', "Carnivorous (carn)", ""),
    ('herb', "Herbivorous (herb)", ""),
    ('socl', "Social (socl)", ""),
    ('heal', "Health (heal)", ""),
    ('stel', "Stealth (stel)", ""),
    ('cute', "Cuteness (cute)", ""),
    ('jump', "Jump (jump)", ""),
    ('blck', "Block (blck)", ""),
    ('call', "Call (call)", ""),
    ('cspd', "Creature Speed (cspd)", ""),
    ('spnt', "Sprint (spnt)", ""),
    ('glid', "Glide (glid)", ""),
    ('sens', "Sense (sens)", ""),
    ('mean', "Mean (mean)", ""),
    ('bite', "Bite (bite)", ""),
    ('crge', "Charge (crge)", ""),
    ('spit', "Spit (spit)", ""),
    ('strk', "Strike (strk)", ""),
    ('voca', "Sing (voca)", ""),
    ('danc', "Dance (danc)", ""),
    ('post', "Pose (post)", ""),
    ('chrm', "Charm (chrm)", ""),
    ('skrs', "Strikers (skrs)", ""),
    ('tatk', "Tribe Attack (tatk)", ""),
    ('tsoc', "Tribe Social (tsoc)", ""),
    ('tarm', "Tribe Armor (tarm)", ""),
    ('tgth', "Tribe Gather (tgth)", ""),
    ('tfsh', "Tribe Fishing (tfsh)", ""),
    ('mtcl', "Mouth Cell (mtcl)", ""),
    ('mvcl', "Movement Cell (mvcl)", ""),
    ('eycl', "Eye Cell (eycl)", ""),
    ('wpcl', "Weapon Cell (wpcl)", ""),
    ('wpps', "Weapon Poison (wpps)", ""),
    ('wpel', "Weapon Electro (wpel)", ""),
    ('wpch', "Weapon Charging (wpch)", ""),
    ('stop', "Stop (stop)", ""),
    ('argn', "Adventurer Energy Regen (argn)", ""),
    ('amsl', "Adventurer Missile (amsl)", ""),
    ('abld', "Adventurer Energy Blade (abld)", ""),
    ('asgn', "Adventurer Shield Generator (asgn)", ""),
    ('ahch', "Adventurer Holo Charm (ahch)", ""),
    ('alsw', "Adventurer Lightning Sword (alsw)", ""),
    ('apgn', "Adventurer Pulse Gun (apgn)", ""),
    ('abta', "Adventurer Battle Armor (abta)", ""),
    ('apwa', "Adventurer Powered Armor (apwa)", ""),
    ('aabs', "Adventurer Absorption Shield (aabs)", ""),
    ('ahrg', "Adventurer Health Regen (ahrg)", ""),
    ('ahbn', "Adventurer Health Bonus (ahbn)", ""),
    ('asms', "Adventurer Summon Swarm (asms)", ""),
    ('amml', "Adventurer Mind Meld (amml)", ""),
    ('apbl', "Adventurer Posion Blade (apbl)", ""),
    ('afrz', "Adventurer Freeze (afrz)", ""),
    ('agwz', "Adventurer Graceful Waltz (agwz)", ""),
    ('ahsn', "Adventurer Harmonious Song (ahsn)", ""),
    ('arch', "Adventurer Royal Charm (arch)", ""),
    ('arps', "Adventurer Radiant Pose (arps)", ""),
    ('aspb', "Adventurer Sprint Burst (aspb)", ""),
    ('ahvr', "Adventurer Hover (ahvr)", ""),
    ('asfl', "Adventurer Stealth Field (asfl)", ""),
    ('ajmj', "Adventurer Jumpt Jet (ajmj)", ""),
    ('ains', "Adventurer Inspiring Song (ains)", ""),
    ('asdn', "Adventurer Stunning Dance (asdn)", ""),
    ('acps', "Adventurer Confetti Pose (acps)", ""),
    ('aest', "Adventurer Energy Storage (aest)", ""),
)


ENUM_YES_NO_IGNORE = (
    ('ignore', "Ignore", "Don't use this as a requirement"),
    ('yes', "Yes", "The creature must have this"),
    ('no', "No", "The creature must NOT have this")
)


class SporeAnimBoneProperties(bpy.types.PropertyGroup):
    name: StringProperty(default="Default")

    primary_capability: EnumProperty(
        name="Capability Type",
        items=ENUM_CAPABILITY,
        description="Selects bodies that have the specified capability. Bodies can have more than one capability",
        default='all',
        options=set()
    )
    primary_selectX: EnumProperty(
        name="Left/Right (X)",
        items=ENUM_SELECTX,
        description="Criteria for selecting bodies on the left-to-right axis (X) of the creature",
        default='all',
        options=set()
    )
    primary_selectY: EnumProperty(
        name="Front/Back (Y)",
        items=ENUM_SELECTY,
        description="Criteria for selecting bodies on the front-to-back axis (Y) of the creature",
        default='all',
        options=set()
    )
    primary_selectZ: EnumProperty(
        name="Top/Bottom (Z)",
        items=ENUM_SELECTZ,
        description="Criteria for selecting bodies on the top-to-bottom axis (Z) of the creature",
        default='all',
        options=set()
    )
    primary_extent: EnumProperty(
        name="Extent",
        items=ENUM_EXTENT,
        description="If used, of all the selected body it only uses the most distant in the given direction",
        default='none',
        options=set()
    )
    primary_limb: EnumProperty(
        name="Limb Modifier",
        items=ENUM_LIMB_MODIFIER,
        description="If used, for all the selected bodies it actually selects the spine bodies that match the criteria. This means a spine is animated, and not the body itself (so no rigblock deforms can be used)",
        default='none',
        options=set()
    )

    secondary_type: EnumProperty(
        name="Type",
        items=(
            ('none', "None", "No secondary context is used"),
            ("CapsQuery", "Capability Query", "Selects bodies based on their capabilities and positions"),
            ("ExternalTarget", "External Target", "Uses dynamic data from the game, such as a fruit or a stick in the ground")
        ),
        description="Makes movement relative to a secondary target, which can be other bodies from the creature or external targets in the game (such as sticks, fruit,...)",
        default='none',
        options=set()
    )
    secondary_reference_bone: StringProperty(
        name="Reference Bone",
        description="Used only to correctly export the movement, the channel will be exported as if the secondary was at the given bone position/rotation",
        options=set()
    )
    secondary_target_index: IntProperty(
        name="Target Index",
        options=set()
    )
    secondary_capability: EnumProperty(
        name="Capability Type",
        items=ENUM_CAPABILITY,
        description="Selects bodies that have the specified capability. Bodies can have more than one capability",
        default='all',
        options=set()
    )
    secondary_selectX: EnumProperty(
        name="Left/Right (X)",
        items=ENUM_SELECTX,
        description="Criteria for selecting bodies on the left-to-right axis (X) of the creature",
        default='all',
        options=set()
    )
    secondary_selectY: EnumProperty(
        name="Front/Back (Y)",
        items=ENUM_SELECTY,
        description="Criteria for selecting bodies on the front-to-back axis (Y) of the creature",
        default='all',
        options=set()
    )
    secondary_selectZ: EnumProperty(
        name="Top/Bottom (Z)",
        items=ENUM_SELECTZ,
        description="Criteria for selecting bodies on the top-to-bottom axis (Z) of the creature",
        default='all',
        options=set()
    )
    secondary_extent: EnumProperty(
        name="Extent",
        items=ENUM_EXTENT,
        description="If used, of all the selected body it only uses the most distant in the given direction",
        default='none',
        options=set()
    )
    secondary_limb: EnumProperty(
        name="Limb Modifier",
        items=ENUM_LIMB_MODIFIER,
        description="If used, for all the selected bodies it actually selects the spine bodies that match the criteria. This means a spine is selected, and not the body itself",
        default='none',
        options=set()
    )

    ground_relative: BoolProperty(
        name="Ground Relative",
        description="If checked, rescales the Z axis so that movement is relative to the ground",
        default=False,
        options=set()
    )
    scale_mode: EnumProperty(
        name="Scale Mode",
        description="Affects how animation curves are scaled for different creatures",
        items=(
            ('none', "None", "No scaling"),
            ('CreatureSize', "Creature Scale", "Scale proportional to the bounds of the creature: small creatures get small curves, large creatures get large curves"),
            ('LimbLength', "Limb Length", "Scale based on the limb length (distance from the body to the closest spine) of the body")
        ),
        default='none',
        options=set()
    )

    relative_pos: BoolProperty(
        name="Relative Position",
        description="If checked, movement is relative to the rest position. If not checked, the movement will use absolute coordinates, ignoring the body's rest pose (so all selected bodies end up in the same position)",
        default=True,
        options=set()
    )
    
    flag_700: BoolProperty(
        name="flags 0x700 (for wings)",
        description="If checked, movement is relative to the rest position, without IK, maybe",
        default=False,
        options=set()
    )
    
    relative_rot: BoolProperty(
        name="Relative Rotation",
        description="If checked, movement is relative to the rest rotation. If not checked, the movement will use absolute coordinates, ignoring the body's rest pose (so all selected bodies end up with the same rotation)",
        default=True,
        options=set()
    )

    secondary_directional_only: BoolProperty(
        name="Secondary Directional Only",
        description="Only when secondary context is used: if checked, the direction of the movement changes (to be relative to the secondary bodies), but the scaling of the movement will not",
        default=False,
        options=set()
    )
    secondary_lookat: BoolProperty(
        name="Rotation Relative to Secondary",
        description="Only when secondary context is used: aims the rotation towards the secondary object, so that it looks at it",
        default=False,
        options=set()
    )

    require: BoolProperty(
        name="Require",
        description="If checked, the animation will be discarded unless the creature has bodies in this channel",
        default=False,
        options=set()
    )

    primary_flags: IntProperty(
        name="Primary Flags",
        default=0,
        min=0,
        options=set()
    )

    secondary_flags: IntProperty(
        name="Secondary Flags",
        default=0,
        min=0,
        options=set()
    )

    bind_flags: IntProperty(
        name="Bind Flags",
        default=0,
        min=0,
        options=set()
    )

    movement_flags: IntProperty(
        name="Movement Flags",
        default=0,
        min=0,
        options=set()
    )

    keyframe_info_flags: IntProperty(
        name="Keyframe Info Flags",
        description="Flags specific to each keyframe, applied to the 'info' component of the channel",
        default=0,
        min=0
    )

    position_weight: FloatProperty(
        name="Position Weight",
        default=1.0,
        min=0.0,
        max=1.0
    )
    rotation_weight: FloatProperty(
        name="Rotation Weight",
        default=1.0,
        min=0.0,
        max=1.0
    )

    blend_group: IntProperty(
        name="Blend Group",
        description="The same bodies can be shared by multiple channels if they are in the same group. If that is the case, their movement is blended using the weight",
        default=0,
        options=set()
    )
    variant_group: IntProperty(
        name="Variant Group",
        description="Used to create different variations of an animation. The game chooses the appropiate channel from different variants at runtime",
        default=0,
        options=set()
    )

    # Animations
    ClsdOpen: FloatVectorProperty(name="ClsdOpen", min=0.0, max=1.0, size=2, default=(0.5, 1.0))
    eycl_ClsdOpen: FloatVectorProperty(name="ClsdOpen", min=0.0, max=1.0, size=2, default=(0.15, 1.0))
    mout_ClsdOpen: FloatVectorProperty(name="ClsdOpen", min=0.0, max=1.0, size=2, default=(0.0, 1.0))
    MadSad: FloatVectorProperty(name="MadSad", min=0.0, max=1.0, size=2, default=(0.0, 0.0))
    eycl_MadSad: FloatVectorProperty(name="MadSad", min=0.0, max=1.0, size=2, default=(0.0, 1.0))
    Scared: FloatVectorProperty(name="Scared", min=0.0, max=1.0, size=2, default=(1.0, 0.0))
    eycl_Scared: FloatVectorProperty(name="Scared", min=0.0, max=1.0, size=2, default=(0.0, 1.0))
    TurnOn: FloatVectorProperty(name="TurnOn", min=0.0, max=1.0, size=2, default=(0.0, 0.0))
    Idle: FloatVectorProperty(name="Idle", min=0.0, max=1.0, size=2, default=(0.0, 0.0))
    Move: FloatVectorProperty(name="Move", min=0.0, max=1.0, size=2, default=(0.0, 1.0))
    Stun: FloatVectorProperty(name="Stun", min=0.0, max=1.0, size=2, default=(0.0, 0.0))
    mtcl_Stun: FloatVectorProperty(name="Stun", min=0.0, max=1.0, size=2, default=(1.0, 0.0))
    Impact: FloatVectorProperty(name="Impact", min=0.0, max=1.0, size=2, default=(0.0, 0.0))
    mtcl_Impact: FloatVectorProperty(name="Impact", min=0.0, max=1.0, size=2, default=(0.0, 1.0))
    eycl_Impact: FloatVectorProperty(name="Impact", min=0.0, max=1.0, size=2, default=(1.0, 0.0))
    Stop: FloatVectorProperty(name="Stop", min=0.0, max=1.0, size=2, default=(0.0, 0.0))
    Breathe: FloatVectorProperty(name="Breathe", min=0.0, max=1.0, size=2, default=(0.0, 0.0))
    DroopRaise: FloatVectorProperty(name="DroopRaise", min=0.0, max=1.0, size=2, default=(0.5, 1.0))
    ChargeUp: FloatVectorProperty(name="ChargeUp", min=0.0, max=1.0, size=2, default=(0.0, 0.0))
    ChargeHold: FloatVectorProperty(name="ChargeHold", min=0.0, max=1.0, size=2, default=(0.0, 0.0))
    ChargeRelease: FloatVectorProperty(name="ChargeRelease", min=0.0, max=1.0, size=2, default=(0.0, 0.0))
    SmileFrown: FloatVectorProperty(name="SmileFrown", min=0.0, max=1.0, size=2, default=(0.5, 0.0))
    LickAir: FloatVectorProperty(name="LickAir", min=0.0, max=1.0, size=2, default=(0.0, 0.0))
    Attack: FloatVectorProperty(name="Attack", min=0.0, max=1.0, size=2, default=(0.0, 0.0))
    Scale: FloatVectorProperty(name="Scale", min=0.0, max=1.0, size=2, default=(1.0, 1.0))
    Data1: FloatVectorProperty(name="Data1", min=0.0, max=1.0, size=2, default=(1.0, 1.0))
    Data2: FloatVectorProperty(name="Data2", min=0.0, max=1.0, size=2, default=(1.0, 1.0))
    Data3: FloatVectorProperty(name="Data3", min=0.0, max=1.0, size=2, default=(1.0, 1.0))
    Data4: FloatVectorProperty(name="Data4", min=0.0, max=1.0, size=2, default=(1.0, 1.0))
    Data5: FloatVectorProperty(name="Data5", min=0.0, max=1.0, size=2, default=(1.0, 1.0))
    Unique: FloatVectorProperty(name="Unique", min=0.0, max=1.0, size=2, default=(0.0, 0.0))
    Point: FloatVectorProperty(name="Point", min=0.0, max=1.0, size=2, default=(0.0, 0.0))
    Tuck: FloatVectorProperty(name="Tuck", min=0.0, max=1.0, size=2, default=(0.0, 1.0))
    Bend: FloatVectorProperty(name="Bend", min=0.0, max=1.0, size=2, default=(0.5, 1.0))
    wing_Bend: FloatVectorProperty(name="Bend", min=0.0, max=1.0, size=2, default=(0.5, 0.0))
    
    LeftRight: FloatVectorProperty(name="LeftRight", min=0.0, max=1.0, size=2, default=(0.5, 1.0))
    DownUp: FloatVectorProperty(name="DownUp", min=0.0, max=1.0, size=2, default=(0.5, 1.0))


class SPORE_PT_anim_bone(bpy.types.Panel):
    bl_label = "Spore Animation"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.armature

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        self.layout.prop(context.armature.spore_anim, 'requirements')
        if context.armature.spore_anim.requirements:
            self.layout.prop(context.armature.spore_anim, 'has_upright_spine')
            self.layout.prop(context.armature.spore_anim, 'has_graspers')
            self.layout.prop(context.armature.spore_anim, 'has_feet')

        self.layout.separator()
        box = self.layout.box()
        boxc = box.column()
        boxc.template_list("SPORE_UL_anim_channels", "", context.armature.spore_anim, "channels",
                           context.armature.spore_anim, "channel_index")
        boxr = box.row()
        boxr.operator("armature.spore_anim_channel_add")
        boxr.operator("armature.spore_anim_channel_remove")

        if context.armature.spore_anim.channel_index >= 0:
            item = context.armature.spore_anim.channels[context.armature.spore_anim.channel_index]
            col = self.layout.column()
            col.prop_search(item, "name", context.armature, "bones", icon='BONE_DATA', text="")


class SporeAnimBonePanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return context.armature and context.armature.spore_anim.channels and \
               context.armature.spore_anim.channel_index >= 0

    def get_item(self, context):
        return context.armature.spore_anim.channels[context.armature.spore_anim.channel_index]


class SPORE_PT_anim_bone_primary(SporeAnimBonePanel, bpy.types.Panel):
    bl_label = "Primary"
    bl_parent_id = "SPORE_PT_anim_bone"

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        item = self.get_item(context)

        col = self.layout.column()
        col.prop(item, 'primary_capability')
        if item.primary_capability != 'frame':
            col.prop(item, 'primary_selectX')
            col.prop(item, 'primary_selectY')
            col.prop(item, 'primary_selectZ')
            col.prop(item, 'primary_extent')
            col.prop(item, 'primary_limb')


class SPORE_PT_anim_bone_secondary(SporeAnimBonePanel, bpy.types.Panel):
    bl_label = "Secondary"
    bl_parent_id = "SPORE_PT_anim_bone"

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        item = self.get_item(context)

        col = self.layout.column()
        col.prop(item, 'secondary_type')
        if item.secondary_type != 'none':
            col.prop_search(item, 'secondary_reference_bone', context.armature, 'bones')
            if item.secondary_type == 'ExternalTarget':
                col.prop(item, 'secondary_target_index')
            else:
                col.prop(item, 'secondary_capability')
                col.prop(item, 'secondary_selectX')
                col.prop(item, 'secondary_selectY')
                col.prop(item, 'secondary_selectZ')
                col.prop(item, 'secondary_extent')
                col.prop(item, 'secondary_limb')


class SPORE_PT_anim_bone_remappable(SporeAnimBonePanel, bpy.types.Panel):
    bl_label = "Movement"
    bl_parent_id = "SPORE_PT_anim_bone"

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        item = self.get_item(context)

        col = self.layout.column()
        col.prop(item, 'scale_mode')
        col.prop(item, 'relative_pos')
        col.prop(item, 'flag_700')
        col.prop(item, 'relative_rot')

        col = self.layout.column()
        col.prop(item, 'ground_relative')
        col.active = item.relative_pos

        col = self.layout.column()
        col.prop(item, 'secondary_directional_only')
        col.prop(item, 'secondary_lookat')


class SPORE_PT_anim_bone_extra(SporeAnimBonePanel, bpy.types.Panel):
    bl_label = "Extra"
    bl_parent_id = "SPORE_PT_anim_bone"

    def draw(self, context):
        self.layout.use_property_split = True

        item = self.get_item(context)

        col = self.layout.column(align=True)
        col.use_property_decorate = True
        col.prop(item, 'position_weight')
        col.prop(item, 'rotation_weight')

        col = self.layout.column(align=True)
        col.use_property_decorate = False
        col.prop(item, 'require')
        col.prop(item, 'blend_group')
        col.prop(item, 'variant_group')

        col = self.layout.column()
        col.use_property_decorate = False
        col.prop(item, 'primary_flags')
        col.prop(item, 'secondary_flags')
        col.prop(item, 'bind_flags')
        col.prop(item, 'movement_flags')

        col = self.layout.column()
        col.use_property_decorate = True
        col.prop(item, 'keyframe_info_flags')


class SPORE_PT_anim_bone_deforms(SporeAnimBonePanel, bpy.types.Panel):
    bl_label = "Rigblock Deforms"
    bl_parent_id = "SPORE_PT_anim_bone"

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = True

        item = self.get_item(context)

        if item.primary_capability in ANIMATION_NAMES and item.primary_limb == 'none':
            for anim_name in ANIMATION_NAMES[item.primary_capability]:
                col = self.layout.column()
                row = col.row(align=True)
                row.prop(item, anim_name)

                sub = row.column(align=True)
                sub.label(text="Value")
                sub.label(text="Weight")


class SPORE_OT_anim_channel_add(bpy.types.Operator):
    bl_idname = "armature.spore_anim_channel_add"
    bl_label = "Add Channel"
    bl_description = "Adds a new animation channel linked to a certain bone"

    def execute(self, context):
        max_group = max(channel.blend_group for channel in context.armature.spore_anim.channels) if \
            context.armature.spore_anim.channels else 0
        channel = context.armature.spore_anim.channels.add()
        channel.blend_group = max_group + 1

        context.armature.spore_anim.channel_index = len(context.armature.spore_anim.channels) - 1

        name = None
        if context.bone:
            name = context.bone.name
        elif context.active_bone:
            name = context.active_bone.name
        elif context.edit_bone:
            name = context.edit_bone.name

        if name and name not in [c.name for c in context.armature.spore_anim.channels]:
            channel.name = name

        return {'FINISHED'}


class SPORE_OT_anim_channel_remove(bpy.types.Operator):
    bl_idname = "armature.spore_anim_channel_remove"
    bl_label = "Remove Channel"
    bl_description = "Removes this animation channel"

    @classmethod
    def poll(cls, context):
        return context.armature and context.armature.spore_anim.channels and \
               context.armature.spore_anim.channel_index >= 0

    def execute(self, context):
        index = context.armature.spore_anim.channel_index
        anim_list = context.armature.spore_anim.channels
        anim_list.remove(index)
        context.armature.spore_anim.channel_index = min(max(0, index), len(anim_list)-1)
        return {'FINISHED'}


class SPORE_UL_anim_channels(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index, flt_flag):
        custom_icon = 'BONE_DATA'

        # Make sure your code supports all 3 layout types
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=item.name, icon=custom_icon)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=item.name, icon=custom_icon)


ENUM_EVENT_TYPE = (
    ('sound', "Sound", ""),
    ('effect', "Effect", ""),
    ('eventControl', "Event Control", ""),
    ('stop', "Stop", "Stops effects or sounds already playing. If an effect index is specified, only stops those with the same index"),
    ('footstep', "Footstep", ""),
    ('message', "Game Message", "Sends a game message"),
    ('unk3', "unk3", ""),
    ('unk5', "unk5", ""),
    ('sound2', "sound2", ""),
    ('unk20000', "unk20000", ""),
)


ENUM_EVENT_SOURCE_TYPE = (
    ('default', "Default", "Uses the bodies of the channel where this event was played"),
    ('standardBodies', "Bodies Select", "Uses a body select query to choose the bodies to be used as sources"),
    ('otherCreature', "Target Creature", "When there's a target creature (like when there is a fight), the source will be the other creature"),
    ('otherStandardBodies', "Target Creature Bodies Select", "Like bodies select, but done to the target creature (like when there is a fight)"),
    ('unk1', "unk1", ""),
    ('unk3', "unk3", ""),
    ('unk7', "unk7", ""),
    ('unk8', "unk8", ""),
    ('unk9', "unk9", ""),
)

ENUM_EVENT_SOURCE_FILTER = (
    ('any', "Any", "Uses all the bodies selected"),
    ('firstOnly', "First Only", "Only uses the first body selected, discards the rest"),
    ('allExceptFirst', "All Except First", "Discards the first body and uses the rest"),
    ('unk1', "unk1", ""),
    ('unk2', "unk2", ""),
    ('unk3', "unk3", ""),
    ('unk4', "unk4", ""),
)


ENUM_EVENT_SOURCE_PREFILTER = (
    ('none', "None", ""),
    ('true', "Require True", ""),
    ('false', "Require False", ""),
)


ENUM_EVENT_SOURCE_SCALE = (
    ('noScale', "None", "Uses a default scaling of 1.0 (so no scaling)"),
    ('currentCreatureScale', "Current Creature Scale", "Uses the scaling applied to the current creature"),
    ('parameter', "Parameter", "Specify the scaling manually"),
    ('creatureScale', "Creature Scale", "Uses the scaling applied to the creature where this event is being played (which might be the target creature)"),
    ('realCurrentCreatureScale', "Current Creature Dimensions", "Uses the dimensions of the current creature (big creatures get big effects, small creatures get small effects)"),
)


ENUM_EVENT_SOURCE_POSITION = (
    ('default', "Default", "Uses the body position"),
    ('groundHeight', "Ground Height", "Uses the body position, but the Z coordinate is changed to be on the ground"),
    ('groundHeight2', "Ground Height 2", "Similar to Ground Height"),
    ('unk', "unk", ""),
)


ENUM_EVENT_SOURCE_ADDPOSITION = (
    ('none', "None", "No additional position is added"),
    ('random', "Random", "Adds a small random offset"),
    ('restPosition', "Rest Position", "Adds the rest position of the body"),
    ('restEffectsOrigin', "Rest Effects Origin", "Adds the rest effects origin of the body"),
)


ENUM_EVENT_SOURCE_ROTATION = (
    ('default', "Default", "Uses the body rotation"),
    ('creatureRotation', "Creature Rotation", "Uses rotation applied to the creature"),
    ('groundNormal', "Ground Normal", "Makes the effect face the normal (perpendicular) direction of the ground"),
    ('noRotation', "No Rotation", "No rotation is applied, leaving the original orientation of the effect"),
    ('unk1', "unk1", ""),
    ('unk2', "unk2", ""),
)


ENUM_EVENT_SOURCE_HANDEDNESS = (
    ('none', "None", "No handedness orientation is applied"),
    ('unk1', "unk1", ""),
    ('unk2', "unk2", ""),
    ('unk3', "unk3", ""),
)


ENUM_EVENT_ARCHETYPE = (
    ('none', "None", ""),
    ('default', "default", ""),
    ('BARD', "BARD", ""),
    ('DIPL', "DIPL", ""),
    ('ECOL', "ECOL", ""),
    ('ECON', "ECON", ""),
    ('GROB', "GROB", ""),
    ('MILI', "MILI", ""),
    ('PLYE', "PLYE", ""),
    ('PLYM', "PLYM", ""),
    ('PLYR', "PLYR", ""),
    ('RELI', "RELI", ""),
    ('SCIE', "SCIE", ""),
    ('SHAM', "SHAM", ""),
    ('TRAD', "TRAD", ""),
    ('WARR', "WARR", ""),
    ('ZEAL', "ZEAL", ""),
    ('bone', "bone", ""),
    ('cil', "cil", ""),
    ('cilv', "cilv", ""),
    ('elec', "elec", ""),
    ('filt', "filt", ""),
    ('flag', "flag", ""),
    ('flwr', "flwr", ""),
    ('frui', "frui", ""),
    ('hit', "hit", ""),
    ('hith', "hith", ""),
    ('hitl', "hitl", ""),
    ('hitm', "hitm", ""),
    ('jaw', "jaw", ""),
    ('jet', "jet", ""),
    ('lowh', "lowh", ""),
    ('lvl0', "lvl0", ""),
    ('lvl9', "lvl9", ""),
    ('miss', "miss", ""),
    ('pois', "pois", ""),
    ('prob', "prob", ""),
    ('raze', "raze", ""),
    ('rock', "rock", ""),
    ('scr0', "scr0", ""),
    ('scr1', "scr1", ""),
    ('scr2', "scr2", ""),
    ('scr3', "scr3", ""),
    ('scr4', "scr4", ""),
    ('scr5', "scr5", ""),
    ('scr6', "scr6", ""),
    ('scr7', "scr7", ""),
    ('scr8', "scr8", ""),
    ('scr9', "scr9", ""),
    ('spik', "spik", ""),
    ('stik', "stik", ""),
)


class SporeAnimEventSourceProperties(bpy.types.PropertyGroup):
    # Only used in the unknown source
    enabled: BoolProperty(
        name="Enabled",
        description="Whether this source is used or not",
        default=False,
        options=set()
    )
    not_copy_from_position: BoolProperty(
        name="Not Copy From Position Source",
        description="By default it uses the same source specified in the 'Position Source', check this to change this source",
        default=False,
        options=set()
    )

    type: EnumProperty(
        name="Type",
        description="Name of the sound, effect, event control,... to be played",
        items=ENUM_EVENT_SOURCE_TYPE,
        default="default",
        options=set()
    )

    prefilter_2D4: EnumProperty(
        name="Prefilter field_2D4",
        items=ENUM_EVENT_SOURCE_PREFILTER,
        default="none",
        options=set()
    )
    prefilter_2D5: EnumProperty(
        name="Prefilter field_2D5",
        items=ENUM_EVENT_SOURCE_PREFILTER,
        default="none",
        options=set()
    )
    prefilter_2D6: EnumProperty(
        name="Prefilter field_2D6",
        items=ENUM_EVENT_SOURCE_PREFILTER,
        default="none",
        options=set()
    )

    filter: EnumProperty(
        name="Filter",
        description="Of all the bodies selected for the source, chooses which are used and which discarded",
        items=ENUM_EVENT_SOURCE_FILTER,
        default="any",
        options=set()
    )

    scale: EnumProperty(
        name="Scale",
        description="Defines the type of scaling that is applied to the event (not all events use it)",
        items=ENUM_EVENT_SOURCE_SCALE,
        default="noScale",
        options=set()
    )
    position: EnumProperty(
        name="Position",
        description="Defines the type of position that is used by the event (not all events use it)",
        items=ENUM_EVENT_SOURCE_POSITION,
        default="default",
        options=set()
    )
    addposition: EnumProperty(
        name="Additional Position",
        description="An additional position that is added to the current position",
        items=ENUM_EVENT_SOURCE_ADDPOSITION,
        default="none",
        options=set()
    )
    rotation: EnumProperty(
        name="Rotation",
        description="Defines the type of rotation that is used by the event (not all events use it)",
        items=ENUM_EVENT_SOURCE_ROTATION,
        default="default",
        options=set()
    )
    handedness: EnumProperty(
        name="Handedness",
        description="Changes to the orientation of the event only for those bodies in the right side of the creature",
        items=ENUM_EVENT_SOURCE_HANDEDNESS,
        default="none",
        options=set()
    )

    query_capability: EnumProperty(
        name="Capability Type",
        items=ENUM_CAPABILITY,
        description="Selects bodies that have the specified capability. Bodies can have more than one capability",
        default='all',
        options=set()
    )
    query_selectX: EnumProperty(
        name="Left/Right (X)",
        items=ENUM_SELECTX,
        description="Criteria for selecting bodies on the left-to-right axis (X) of the creature",
        default='all',
        options=set()
    )
    query_selectY: EnumProperty(
        name="Front/Back (Y)",
        items=ENUM_SELECTY,
        description="Criteria for selecting bodies on the front-to-back axis (Y) of the creature",
        default='all',
        options=set()
    )
    query_selectZ: EnumProperty(
        name="Top/Bottom (Z)",
        items=ENUM_SELECTZ,
        description="Criteria for selecting bodies on the top-to-bottom axis (Z) of the creature",
        default='all',
        options=set()
    )
    query_extent: EnumProperty(
        name="Extent",
        items=ENUM_EXTENT,
        description="If used, of all the selected body it only uses the most distant in the given direction",
        default='none',
        options=set()
    )
    query_limb: EnumProperty(
        name="Limb Modifier",
        items=ENUM_LIMB_MODIFIER,
        description="If used, for all the selected bodies it actually selects the spine bodies that match the criteria. This means a spine is chosen, and not the body itself",
        default='none',
        options=set()
    )


class SporeAnimEventProperties(bpy.types.PropertyGroup):
    name: StringProperty(
        name="Name",
        description="Name of the sound, effect, event control,... to be played",
        default="default",
        options=set()
    )

    channel_name: StringProperty(
        name="Channel",
        description="The channel that will play this event",
        default="None",
        options=set()
    )

    play_frame: IntProperty(
        name="Play Frame",
        description="Frame in which this effect will be played",
        default=0,
        min=0,
        options=set()
    )

    type: EnumProperty(
        name="Type",
        items=ENUM_EVENT_TYPE,
        description="The type of event (sound, effect,...) that is played",
        default='sound',
        options=set()
    )

    disabled: BoolProperty(
        name="Disabled",
        description="If checked, the event won't be played",
        default=False,
        options=set()
    )

    flags: IntProperty(
        name="Flags",
        default=0,
        min=0,
        options=set()
    )

    archetype: EnumProperty(
        name="Archetype",
        items=ENUM_EVENT_ARCHETYPE,
        description="If used, the event will only be used if the creature has the specified archetype.",
        default='none',
        options=set()
    )

    chance: FloatProperty(
        name="Probability",
        description="Probability (from 0.0 to 1.0) that this event is used. 1.0 means it is always used, 0.5 only used 50% of the times,...",
        default=1.0,
        min=0.0,
        max=1.0,
        options=set()
    )

    event_group: IntProperty(
        name="Event Group",
        default=0,
        min=0,
        options=set()
    )

    max_dist: FloatProperty(
        name="Max Camera Distance",
        description="If the camera is more distant from the creature than this, the event won't be used",
        default=0.0,
        min=0.0,
        options=set()
    )

    requirements: BoolProperty(
        name="Enable Requirements",
        description="If checked, there are some conditions that will be required for the event to be used.",
        default=False,
        options=set()
    )
    has_upright_spine: EnumProperty(
        name="Has Upright Spine",
        description="Requires the creature to have (or not have) an upright spine, otherwise the event is not used",
        items=ENUM_YES_NO_IGNORE,
        default='ignore',
        options=set()
    )
    has_graspers: EnumProperty(
        name="Has Graspers",
        description="Requires the creature to have (or not have) graspers, otherwise the event is not used",
        items=ENUM_YES_NO_IGNORE,
        default='ignore',
        options=set()
    )
    has_feet: EnumProperty(
        name="Has Feet",
        description="Requires the creature to have (or not have) feet, otherwise the event is not used",
        items=ENUM_YES_NO_IGNORE,
        default='ignore',
        options=set()
    )

    position_source: PointerProperty(
        name="Position Source",
        description="What position will be used by the events",
        type=SporeAnimEventSourceProperties
    )
    rotation_source: PointerProperty(
        name="Rotation Source",
        description="What rotation will be used by the events",
        type=SporeAnimEventSourceProperties
    )
    scale_source: PointerProperty(
        name="Scale Source",
        description="What scaling will be used by the events",
        type=SporeAnimEventSourceProperties
    )
    unk_source: PointerProperty(
        name="Unknown Source",
        description="Unknown source, used by some events",
        type=SporeAnimEventSourceProperties
    )

    effect_use_local_reference: BoolProperty(
        name="Use Local Reference Frame",
        description="If selected, the effect rotates and scales with the source",
        default=True,
        options=set()
    )
    effect_update_position: BoolProperty(
        name="Update Position",
        description="Whether the effect position is constantly updated when the source position changes",
        default=True,
        options=set()
    )
    effect_update_rotation: BoolProperty(
        name="Update Rotation",
        description="Whether the effect rotation is constantly updated when the source rotation changes",
        default=True,
        options=set()
    )
    effect_update_scale: BoolProperty(
        name="Update Scale",
        description="Whether the effect scale is constantly updated when the source scale changes",
        default=True,
        options=set()
    )
    effect_update_particle_size: BoolProperty(
        name="Update Particle Size",
        description="Whether the effect particle size is constantly updated when the source scale changes",
        default=False,
        options=set()
    )
    effect_update_attractor: BoolProperty(
        name="Update Attractor",
        description="Whether the effect attractor location is constantly updated when the source4 position changes",
        default=False,
        options=set()
    )
    effect_apply_scale: BoolProperty(
        name="Apply Scale",
        description="By default, the scale is only applied to the particle size. If checked, it will also scale the whole effect",
        default=False,
        options=set()
    )
    effect_identity_color: BoolProperty(
        name="Use Identity Color",
        description="If checked, the effect particles will use the creature identity color",
        default=False,
        options=set()
    )

    stopeffect_hardstop: BoolProperty(
        name="Hard Stop",
        default=False,
        options=set()
    )

    unk3_parameter: FloatProperty(
        name="Parameter",
        default=200.0,
        options=set()
    )
    sound2_parameter: FloatProperty(
        name="Parameter",
        default=0.0,
        options=set()
    )
    footstep_parameter: FloatProperty(
        name="Parameter",
        default=12.0,
        options=set()
    )
    effect_parameter: FloatProperty(
        name="Scale Parameter",
        description="The scale applied to the effect, it's only used if the scaling source is set to 'Parameter'",
        default=1.0,
        options=set()
    )
    unk20000_parameter0: IntProperty(
        name="Parameter 0",
        default=0,
        options=set()
    )
    unk20000_parameter1: FloatProperty(
        name="Parameter 1",
        default=0.0,
        options=set()
    )
    message_parameter0: IntProperty(
        name="Parameter 0",
        default=0,
        options=set()
    )
    message_parameter1: FloatProperty(
        name="Parameter 1",
        default=0.0,
        options=set()
    )


class SPORE_PT_anim_event(bpy.types.Panel):
    bl_label = "Spore Animation Events"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.armature

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        box = self.layout.box()
        boxc = box.column()
        boxc.template_list("SPORE_UL_anim_events", "", context.armature.spore_anim, "events",
                          context.armature.spore_anim, "event_index")
        boxr = box.row()
        boxr.operator("armature.spore_anim_event_add")
        boxr.operator("armature.spore_anim_event_duplicate")
        boxr.operator("armature.spore_anim_event_remove")

        if context.armature.spore_anim.event_index >= 0:
            item = context.armature.spore_anim.events[context.armature.spore_anim.event_index]
            col = self.layout.column()
            col.prop(item, "name")
            col.prop_search(item, "channel_name", context.armature.spore_anim, "channels", icon='BONE_DATA')
            col.prop(item, "play_frame")

            col.separator()
            col.prop(item, "type")
            col = self.layout.column()
            col.prop(item, "chance")
            col.active = item.type != 'unk20000'

            col = self.layout.column()
            col.prop(item, "disabled")
            col.prop(item, "event_group")
            col.prop(item, "max_dist")
            col.prop(item, "archetype")
            col.prop(item, "requirements")
            if item.requirements:
                col.prop(item, "has_upright_spine")
                col.prop(item, "has_graspers")
                col.prop(item, "has_feet")
            col.prop(item, "flags")
            col.separator()

            if item.type == 'effect':
                col.prop(item, "effect_use_local_reference")
                col.prop(item, "effect_update_position")
                col.prop(item, "effect_update_rotation")
                col.prop(item, "effect_update_scale")
                col.prop(item, "effect_update_particle_size")
                col.prop(item, "effect_update_attractor")
                col.prop(item, "effect_apply_scale")
                col.prop(item, "effect_identity_color")
                col.prop(item, "effect_parameter")
            elif item.type == 'stop':
                col.prop(item, "stopeffect_hardstop")
            elif item.type == 'unk3':
                col.prop(item, "unk3_parameter")
            elif item.type == 'sound2':
                col.prop(item, "sound2_parameter")
            elif item.type == 'footstep':
                col.prop(item, "footstep_parameter")
            elif item.type == 'unk20000':
                col.prop(item, "unk20000_parameter0")
                col.prop(item, "unk20000_parameter1")
            elif item.type == 'message':
                col.prop(item, "message_parameter0")
                col.prop(item, "message_parameter1")


class SporeAnimEventPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return context.armature and context.armature.spore_anim.events and \
               context.armature.spore_anim.event_index >= 0

    def get_item(self, context):
        return context.armature.spore_anim.events[context.armature.spore_anim.event_index]


def layout_event_source(source_index, item, layout):
    if (source_index == 3 and item.enabled) or (source_index == 0 or (source_index < 3 and item.not_copy_from_position)):
        col = layout.column()
        col.prop(item, "type")
        layout.separator()

        if item.type == 'standardBodies' or item.type == 'otherStandardBodies':
            col.prop(item, 'query_capability')
            col.prop(item, 'query_selectX')
            col.prop(item, 'query_selectY')
            col.prop(item, 'query_selectZ')
            col.prop(item, 'query_extent')
            col.prop(item, 'query_limb')

        col = layout.column()
        col.prop(item, "scale")
        col.prop(item, "position")
        col.prop(item, "addposition")
        col.prop(item, "rotation")
        col.prop(item, "handedness")
        col.prop(item, "filter")
        col.prop(item, "prefilter_2D4")
        col.prop(item, "prefilter_2D5")
        col.prop(item, "prefilter_2D6")


class SPORE_PT_anim_event_position(SporeAnimEventPanel, bpy.types.Panel):
    bl_label = "Position Source"
    bl_parent_id = "SPORE_PT_anim_event"

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = True

        item = self.get_item(context)
        layout_event_source(0, item.position_source, self.layout.column())


class SPORE_PT_anim_event_rotation(SporeAnimEventPanel, bpy.types.Panel):
    bl_label = "Rotation Source"
    bl_parent_id = "SPORE_PT_anim_event"

    def draw_header(self, context):
        self.layout.prop(self.get_item(context).rotation_source, "not_copy_from_position", text="")

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = True

        item = self.get_item(context)
        layout_event_source(1, item.rotation_source, self.layout.column())


class SPORE_PT_anim_event_scaling(SporeAnimEventPanel, bpy.types.Panel):
    bl_label = "Scaling Source"
    bl_parent_id = "SPORE_PT_anim_event"

    def draw_header(self, context):
        self.layout.prop(self.get_item(context).scale_source, "not_copy_from_position", text="")

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = True

        item = self.get_item(context)
        layout_event_source(2, item.scale_source, self.layout.column())


class SPORE_PT_anim_event_unksource(SporeAnimEventPanel, bpy.types.Panel):
    bl_label = "Unknown Source"
    bl_parent_id = "SPORE_PT_anim_event"

    def draw_header(self, context):
        self.layout.prop(self.get_item(context).unk_source, "enabled", text="")

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = True

        item = self.get_item(context)
        layout_event_source(3, item.unk_source, self.layout.column())


class SPORE_OT_anim_event_add(bpy.types.Operator):
    bl_idname = "armature.spore_anim_event_add"
    bl_label = "Add Event"
    bl_description = "Adds a new animation event to be played at a certain frame"

    def execute(self, context):
        event = context.armature.spore_anim.events.add()
        context.armature.spore_anim.event_index = len(context.armature.spore_anim.events) - 1

        name = None
        if context.bone:
            name = context.bone.name
        elif context.active_bone:
            name = context.active_bone.name
        elif context.edit_bone:
            name = context.edit_bone.name

        if name and name in [c.name for c in context.armature.spore_anim.channels]:
            event.channel_name = name

        event.play_frame = context.scene.frame_current

        return {'FINISHED'}


class SPORE_OT_anim_event_remove(bpy.types.Operator):
    bl_idname = "armature.spore_anim_event_remove"
    bl_label = "Remove"
    bl_description = "Removes this animation event"

    @classmethod
    def poll(cls, context):
        return context.armature and context.armature.spore_anim.events and \
               context.armature.spore_anim.event_index >= 0

    def execute(self, context):
        index = context.armature.spore_anim.event_index
        event_list = context.armature.spore_anim.events
        event_list.remove(index)
        context.armature.spore_anim.event_index = min(max(0, index), len(event_list)-1)
        return {'FINISHED'}


class SPORE_OT_anim_event_duplicate(bpy.types.Operator):
    bl_idname = "armature.spore_anim_event_duplicate"
    bl_label = "Duplicate"
    bl_description = "Creates a copy this animation event"

    @classmethod
    def poll(cls, context):
        return context.armature and context.armature.spore_anim.events and \
               context.armature.spore_anim.event_index >= 0

    def execute(self, context):
        index = context.armature.spore_anim.event_index
        event_list = context.armature.spore_anim.events
        old_event = event_list[index]
        event = context.armature.spore_anim.events.add()

        for key in old_event.__annotations__.keys():
            setattr(event, key, getattr(old_event, key))

        context.armature.spore_anim.event_index = len(event_list) - 1

        return {'FINISHED'}


class SPORE_UL_anim_events(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index, flt_flag):
        custom_icon = 'MOD_PARTICLES'

        # Make sure your code supports all 3 layout types
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=item.name, icon=custom_icon)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=item.name, icon=custom_icon)


class SporeAnimProperties(bpy.types.PropertyGroup):
    channels: CollectionProperty(type=SporeAnimBoneProperties)
    channel_index: IntProperty(default=-1)

    events: CollectionProperty(type=SporeAnimEventProperties)
    event_index: IntProperty(default=-1)

    requirements: BoolProperty(
        name="Enable Requirements",
        description="If checked, there are some conditions that will be required for the animation to be used. This can be used to provide different versions of an animation (one for creatures with graspers and another for those without,...)",
        default=False,
        options=set()
    )
    has_upright_spine: EnumProperty(
        name="Has Upright Spine",
        description="Requires the creature to have (or not have) an upright spine, otherwise the animation is not used",
        items=ENUM_YES_NO_IGNORE,
        default='ignore',
        options=set()
    )
    has_graspers: EnumProperty(
        name="Has Graspers",
        description="Requires the creature to have (or not have) graspers, otherwise the animation is not used",
        items=ENUM_YES_NO_IGNORE,
        default='ignore',
        options=set()
    )
    has_feet: EnumProperty(
        name="Has Feet",
        description="Requires the creature to have (or not have) feet, otherwise the animation is not used",
        items=ENUM_YES_NO_IGNORE,
        default='ignore',
        options=set()
    )


def register():
    bpy.utils.register_class(SporeAnimBoneProperties)
    bpy.utils.register_class(SPORE_UL_anim_channels)
    bpy.utils.register_class(SPORE_OT_anim_channel_add)
    bpy.utils.register_class(SPORE_OT_anim_channel_remove)
    bpy.utils.register_class(SPORE_PT_anim_bone)
    bpy.utils.register_class(SPORE_PT_anim_bone_primary)
    bpy.utils.register_class(SPORE_PT_anim_bone_secondary)
    bpy.utils.register_class(SPORE_PT_anim_bone_remappable)
    bpy.utils.register_class(SPORE_PT_anim_bone_extra)
    bpy.utils.register_class(SPORE_PT_anim_bone_deforms)
    bpy.utils.register_class(SporeAnimEventSourceProperties)
    bpy.utils.register_class(SporeAnimEventProperties)
    bpy.utils.register_class(SPORE_PT_anim_event)
    bpy.utils.register_class(SPORE_PT_anim_event_position)
    bpy.utils.register_class(SPORE_PT_anim_event_rotation)
    bpy.utils.register_class(SPORE_PT_anim_event_scaling)
    bpy.utils.register_class(SPORE_PT_anim_event_unksource)
    bpy.utils.register_class(SPORE_OT_anim_event_add)
    bpy.utils.register_class(SPORE_OT_anim_event_remove)
    bpy.utils.register_class(SPORE_OT_anim_event_duplicate)
    bpy.utils.register_class(SPORE_UL_anim_events)
    bpy.utils.register_class(SporeAnimProperties)

    bpy.types.Armature.spore_anim = PointerProperty(type=SporeAnimProperties)


def unregister():
    del bpy.types.Armature.spore_anim

    bpy.utils.unregister_class(SporeAnimProperties)
    bpy.utils.unregister_class(SPORE_UL_anim_events)
    bpy.utils.unregister_class(SPORE_OT_anim_event_remove)
    bpy.utils.unregister_class(SPORE_OT_anim_event_add)
    bpy.utils.unregister_class(SPORE_PT_anim_event_unksource)
    bpy.utils.unregister_class(SPORE_PT_anim_event_scaling)
    bpy.utils.unregister_class(SPORE_PT_anim_event_rotation)
    bpy.utils.unregister_class(SPORE_PT_anim_event_position)
    bpy.utils.unregister_class(SPORE_PT_anim_event)
    bpy.utils.unregister_class(SporeAnimEventProperties)
    bpy.utils.unregister_class(SporeAnimEventSourceProperties)
    bpy.utils.unregister_class(SPORE_PT_anim_bone_deforms)
    bpy.utils.unregister_class(SPORE_PT_anim_bone_extra)
    bpy.utils.unregister_class(SPORE_PT_anim_bone_remappable)
    bpy.utils.unregister_class(SPORE_PT_anim_bone_secondary)
    bpy.utils.unregister_class(SPORE_PT_anim_bone_primary)
    bpy.utils.unregister_class(SPORE_PT_anim_bone)
    bpy.utils.unregister_class(SPORE_OT_anim_event_duplicate)
    bpy.utils.unregister_class(SPORE_OT_anim_channel_remove)
    bpy.utils.unregister_class(SPORE_OT_anim_channel_add)
    bpy.utils.unregister_class(SPORE_UL_anim_channels)
    bpy.utils.unregister_class(SporeAnimBoneProperties)
