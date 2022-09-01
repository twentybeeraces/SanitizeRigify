import bpy
from . import operators, properties

class SANITIZERIGIFY_UL_UIList(bpy.types.UIList):
    """Simple list UI"""
    bl_idname = "SANITIZERIGIFY_UL_UIList"
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align = True)
            row.alignment = 'EXPAND'
            row.label(text = item.name, translate = False, icon = 'BONE_DATA')
            op = row.operator(operators.SANITIZERIGIFY_OT_RemoveAdditionalBone.bl_idname, text = "", icon = 'REMOVE')
            op.index = index

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text = "", icon = 'BONE_DATA')

class SANITIZERIGIFY_PT_MainPanel(bpy.types.Panel):
    """The main panel of the addon"""
    bl_idname = "SANITIZERIGIFY_PT_MainPanel"
    bl_label = 'Sanitize Rigify'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Sanitize Rigify'

    def draw(self, context):
        layout = self.layout
        current_rigify = context.scene.sr_current_rigify
        if current_rigify is not None:
            # mode
            row = layout.row(heading = "Export mode")
            if operators.is_previewing(context, current_rigify):
                row.enabled = False
            row.prop(current_rigify.sr_rigify_properties, "export_mode", text = "")
            # preview
            row = layout.row()
            if operators.can_preview(context, current_rigify):
                row.operator(operators.SANITIZERIGIFY_OT_Preview.bl_idname, text = "Preview", emboss = True)
            else:
                row.operator(operators.SANITIZERIGIFY_OT_Unpreview.bl_idname, text = "Unpreview", emboss = True, depress = True)
            # export
            op = row.operator(operators.SANITIZERIGIFY_OT_Export.bl_idname)
            op.filepath = operators.get_default_file_path(context, current_rigify)
        return

class SANITIZERIGIFY_PT_AdvancedPanel(bpy.types.Panel):
    """Panel for advanced properties like bone connections, additional bones, etc."""
    bl_parent_id = SANITIZERIGIFY_PT_MainPanel.bl_idname
    bl_idname = "SANITIZERIGIFY_PT_AdvancedPanel"
    bl_label = "Advanced"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Sanitize Rigify'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        current_rigify = context.scene.sr_current_rigify
        if current_rigify:
            # armature name
            row = layout.row(heading = "Armature name", align = True)
            row.prop(current_rigify.sr_rigify_properties, "armature_name", text = "")
            row.operator(operators.SANITIZERIGIFY_OT_ResetArmatureName.bl_idname, text = "", icon = 'RECOVER_LAST')
            # options
            col = layout.column()
            if operators.is_previewing(context, current_rigify):
                col.enabled = False
            row = col.row()
            row.prop(current_rigify.sr_rigify_properties, "disconnect_all_bones", toggle = -1)
            row.prop(current_rigify.sr_rigify_properties, "recenter", toggle = -1)
            row = col.row(heading = "Animation naming")
            row.prop(current_rigify.sr_rigify_properties, "animation_naming", text = "")
        return

class SANITIZERIGIFY_PT_AdditionalBonesPanel(bpy.types.Panel):
    """Additional bones panel"""
    bl_parent_id = SANITIZERIGIFY_PT_AdvancedPanel.bl_idname
    bl_label = "Additional bones"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Sanitize Rigify'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.scene.sr_current_rigify
    def draw_header(self, context):
        layout = self.layout
        current_rigify = context.scene.sr_current_rigify
        if operators.is_previewing(context, current_rigify):
            layout.enabled = False
        layout.prop(current_rigify.sr_rigify_properties, "have_additional_bones", text="")
    def draw(self, context):
        layout = self.layout
        current_rigify = context.scene.sr_current_rigify
        if operators.is_previewing(context, current_rigify) or not current_rigify.sr_rigify_properties.have_additional_bones:
            layout.enabled = False
        row = layout.row(align = False)
        col = row.column()
        col.prop_search(current_rigify.sr_rigify_properties, "additional_bones_toadd", current_rigify.data, "bones", text = "")
        col = row.column()
        col.operator(operators.SANITIZERIGIFY_OT_AddAdditionalBone.bl_idname, text = "", icon = 'ADD')
        col = row.column()
        col.operator(operators.SANITIZERIGIFY_OT_ClearAdditionalBones.bl_idname, text = "", icon = 'CANCEL')
        if current_rigify.sr_rigify_properties.additional_bones:
            layout.template_list(SANITIZERIGIFY_UL_UIList.bl_idname, "", current_rigify.sr_rigify_properties, "additional_bones", current_rigify.sr_rigify_properties, "additional_bones_index")
        return
