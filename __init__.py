# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name" : "Sanitize Rigify",
    "author" : "Twenty Beer Aces",
    "description" : "Export rigify as fbx suitable for game engines (appropriate scale & hierarchy)",
    "blender" : (3, 2, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "category" : "Pipeline"
}

import bpy
from . import ui, properties, operators

classes = (
    properties.AddonPreferences,
    properties.SanitizeRigifyBoneProperty,
    properties.SanitizeRigifyProperties,
    operators.SANITIZERIGIFY_OT_Preview,
    operators.SANITIZERIGIFY_OT_Unpreview,
    operators.SANITIZERIGIFY_OT_Export,
    operators.SANITIZERIGIFY_OT_ResetArmatureName,
    operators.SANITIZERIGIFY_OT_AddAdditionalBone,
    operators.SANITIZERIGIFY_OT_RemoveAdditionalBone,
    operators.SANITIZERIGIFY_OT_ClearAdditionalBones,
    ui.SANITIZERIGIFY_UL_UIList,
    ui.SANITIZERIGIFY_PT_MainPanel,
    ui.SANITIZERIGIFY_PT_AdvancedPanel,
    ui.SANITIZERIGIFY_PT_AdditionalBonesPanel
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    properties.register()

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    properties.unregister()

if __name__ == "__main__":
    register()
