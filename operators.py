import bpy, bpy_extras
from . import properties
import logging
import traceback
from cmath import inf
import os

def can_preview(context, rig_object):
    """returns True if we can Preview the rig_object, False if we can Unpreview"""
    # Make surethe rig is selected, and it is not already in preview
    return rig_object is not None \
        and rig_object.sr_rigify_properties.generated_rig is None \
        or rig_object.sr_rigify_properties.generated_rig.name not in context.scene.objects \
        or rig_object.sr_rigify_properties.generated_rig.sr_origin is not rig_object

def is_previewing(context, rig_object):
    """returns True if the rig_object is previewing"""
    return rig_object is not None and rig_object.sr_rigify_properties.generated_rig is not None

def deselect_all(context):
    """deselect all and set to object mode. Returns tuple of current mode, current active object and current selected objects"""
    current_selected = context.selected_objects
    current_active = None
    if current_selected is not None:
        current_active = context.view_layer.objects.active
    current_mode = None
    if current_active:
        current_mode = current_active.mode
    if current_mode and current_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

    bpy.ops.object.select_all(action='DESELECT')
    context.view_layer.objects.active = None

    return current_active, current_selected, current_mode

def restore_selection(context, active, selected, mode):
    deselect_all(context)
    if selected is None or len(selected) < 1:
        return
    try:
        for obj in bpy.data.objects:
            obj.select_set(obj in selected)
        context.view_layer.objects.active = active
        bpy.ops.object.mode_set(mode=mode, toggle=False)
    except Exception as e:
        logging.info(traceback.format_exc())

def add_scene_object_to_collection(context, scene_object, collection_name):
    if not scene_object:
        return
    # create collection if it does not exist
    collection_exist = False
    for child_collection in bpy.data.collections:
        if child_collection.name == collection_name:
            collection_exist = True
            collection = child_collection
            break
    if not collection_exist:
        collection = bpy.data.collections.new(name=collection_name)
        context.scene.collection.children.link(collection)
    # remove the scene_object from all collections
    for child_collection in bpy.data.collections:
        if child_collection.objects.get(scene_object.name):
            child_collection.objects.unlink(scene_object)
    # add the scene_object to the proper collection
    if not collection.objects.get(scene_object.name):
        collection.objects.link(scene_object)

def is_bonename_in_rig_object(rig_object, bonename):
    return any(bonename == bn.name for bn in rig_object.data.edit_bones)

def find_bone_by_name_in_rig_object(rig_object, bonename):
    for bone in rig_object.data.edit_bones:
        if bone.name == bonename:
            return bone
    return None

def search_rigify_deform_bone_true_parent(rig_object, bone):
    """walks up the hierarchy and returns parent"""
    ORG_prefix = properties.AddonPreferences.ORG_prefix
    DEF_prefix = properties.AddonPreferences.DEF_prefix
    # root need no parent
    if bone is rig_object.data.edit_bones[0]:
        return None
    current_bone = bone
    current_parent = current_bone.parent
    while current_parent:
        if current_parent.use_deform:
            return current_parent
        # non-deforming parent.
        if current_parent.name.startswith(ORG_prefix):
            # try checking if DEF- alternate of ORG- bone exists and use that as parent
            bonename_to_check = current_parent.name.replace(ORG_prefix, DEF_prefix)
            # make sure the DEF- alternate is not self (current_bone) and does exist
            if bonename_to_check != current_bone.name and is_bonename_in_rig_object(rig_object, bonename_to_check): 
                bone_to_check = rig_object.data.edit_bones[bonename_to_check]
                if bone_to_check.use_deform:
                    return bone_to_check
        # skip to next parent
        current_bone = current_parent
        current_parent = current_parent.parent
    # return root as parent for parentless bones
    return rig_object.data.edit_bones[0]

def build_armature_hierarchy_from_rigify(rig_object, disconnect_all = True, additional_bones = []):
    """
    Should be in Edit Mode. Additional bones can be added to the hierarchy
    hierarchy = [[Bonename, Parentname, use_connect, use_local_location, use_inherit_rotation, inherit_scale]]
    inherit_scale is enum while the rests that are not names are bools
    """
    hierarchy = []
    # add all deform bones
    for bone in rig_object.data.edit_bones:
        if bone.use_deform:
            parent = search_rigify_deform_bone_true_parent(rig_object, bone)
            parentname = ""
            if parent:
                parentname = parent.name
            hierarchy.append([bone.name, parentname, (not disconnect_all) * bone.use_connect, bone.use_local_location, bone.use_inherit_rotation, bone.inherit_scale])
    # add additional_bones to hierarchy
    for additional_bone in additional_bones:
        bonename = additional_bone.name
        if not is_bonename_in_rig_object(rig_object, bonename):
            continue
        for bone in rig_object.data.edit_bones:
            if bone.name == bonename:
                actual_bone = bone
                break
        if actual_bone and not any(bonename == sl[0] for sl in hierarchy):
            parent = search_rigify_deform_bone_true_parent(rig_object, actual_bone)
            parentname = ""
            if parent:
                parentname = parent.name
            hierarchy.append([actual_bone.name, parentname, (not disconnect_all) * actual_bone.use_connect, actual_bone.use_local_location, actual_bone.use_inherit_rotation, actual_bone.inherit_scale])
    return hierarchy

def restore_armature_hierarchy(rig_object, hierarchy):
    """
    Should be in Edit Mode
    hierarchy = [[Bonename, Parentname, use_connect, use_local_location, use_inherit_rotation, inherit_scale]]
    inherit_scale is enum while the rests that are not names are bools
    """
    for line in hierarchy:
        current_bone = find_bone_by_name_in_rig_object(rig_object, line[0])
        current_parent = find_bone_by_name_in_rig_object(rig_object, line[1])
        if not (current_bone and current_parent):
            continue
        if current_bone is not current_parent:
            current_bone.parent = current_parent
        current_bone.use_connect = line[2]
        current_bone.use_local_location = line[3]
        current_bone.use_inherit_rotation = line[4]
        current_bone.inherit_scale = line[5]

def put_all_bones_into_layer_index(rig_object, layer_index = 0):
    """put bones into bone layer index"""
    for bone in rig_object.data.edit_bones:
        for i in range(32):
            bone.layers[i] = i == layer_index
    # disable unused armature layers
    for i in range(32):
        rig_object.data.layers[i] = i == layer_index

def constrain_rig_to_rigify(gameready_rig, rigify_rig):
    """assumes the rig bones still has matching names to the rigify bones"""
    for bone in gameready_rig.pose.bones:
        copyloc = bone.constraints.new(type='COPY_LOCATION')
        copyloc.name = properties.AddonPreferences.prefix + 'COPY_LOCATION'
        copyloc.target = rigify_rig
        copyloc.subtarget = bone.name
        copyloc.enabled = True
        copyrot = bone.constraints.new(type='COPY_ROTATION')
        copyrot.name = properties.AddonPreferences.prefix + 'COPY_ROTATION'
        copyrot.target = rigify_rig
        copyrot.subtarget = bone.name
        copyrot.enabled = True

def toggle_gameready_rig_constraints(gameready_rig, enabled = True):
    """enables/disables the gameready rig constraints to origin rigify"""
    constraint_names = [properties.AddonPreferences.prefix + 'COPY_LOCATION', properties.AddonPreferences.prefix + 'COPY_ROTATION']
    for bone in gameready_rig.pose.bones:
        for constraint in bone.constraints:
            if constraint.name in constraint_names:
                constraint.enabled = enabled

def reparent_meshes_to_rig(new_rig, old_rig, meshes):
    """make all armature modifiers point to new_rig"""
    for mesh in meshes:
        # reset modifier
        for modifier in mesh.modifiers:
            if modifier.type == 'ARMATURE' and (modifier.object is new_rig or modifier.object is old_rig):
                mesh.modifiers.remove(modifier)
        # set new parent
        mesh.parent = new_rig
        # reset locrotscale
        mesh.location, mesh.rotation_euler, mesh.scale = (0., 0., 0.), (0., 0., 0.), (1., 1., 1.)
        # create new armature modifier and points to new_rig
        new_modifier = mesh.modifiers.new(name=new_rig.name, type='ARMATURE')
        new_modifier.object = new_rig

def remove_duplicates_vertex_groups_in_objects(objects):
    """prioritise higher indexes as they are likely the most recent ones?"""
    for obj in objects:
        unique_vg = []
        for vg in reversed(obj.vertex_groups):
            if vg not in unique_vg:
                unique_vg.append(vg)
        [obj.vertex_groups.remove(vg) for vg in obj.vertex_groups if vg not in unique_vg]

def remove_bone_DEF_prefix(rig_object):
    """removes DEF- prefix on deform bones. And mark each bone that has it to restore later"""
    for bone in rig_object.data.bones:
        if bone.use_deform and bone.name.startswith(properties.AddonPreferences.DEF_prefix):
            bone.sr_is_prefixed = True
            bone.name = bone.name.removeprefix(properties.AddonPreferences.DEF_prefix)

def restore_bone_DEF_prefix(rig_object):
    """restores DEF- prefix on deform bones"""
    for bone in rig_object.data.bones:
        if bone.use_deform and bone.sr_is_prefixed:
            bone.name = properties.AddonPreferences.DEF_prefix + bone.name

def delete_rig(rig_object, delete_actions = False):
    """delete the rig and optionally all actions"""
    # save all rig actions
    actions = []
    if delete_actions and rig_object.animation_data:
        actions = [strip.action for track in rig_object.animation_data.nla_tracks for strip in track.strips]
    # remove the rig before removing actions
    bpy.data.armatures.remove(rig_object.data)
    for action in actions:
        action.user_clear()
        bpy.data.actions.remove(action)

def get_tracks_to_bake(source_rig):
    """return all nla tracks that are not muted"""
    if not source_rig.animation_data or not source_rig.animation_data.nla_tracks:
        return []
    if any((solo_track := track).is_solo for track in source_rig.animation_data.nla_tracks):
        return [solo_track]
    return [track for track in source_rig.animation_data.nla_tracks if track.mute == False]

def get_track_name(track, animation_naming):
    """returns track name or first strip name"""
    # track with empty strip uses track name
    if animation_naming == 'STRIP' and track.strips:
        return track.strips[0].name
    return track.name

def get_nla_track_frame_range(nla_track):
    """returns frame start and end of nla_track"""
    frame_start = inf
    frame_end = -inf
    for strip in nla_track.strips:
        if strip.frame_start < frame_start:
            frame_start = strip.frame_start
        if strip.frame_end > frame_end:
            frame_end = strip.frame_end
    return int(frame_start), int(frame_end)

def create_game_ready_rig(context, rigify_rig):
    """generate the game-ready rig"""
    deselect_all(context)
    # get all objects (meshes) parented to rigify that are not hidden
    meshes = [mesh for mesh in rigify_rig.children if (mesh.type == 'MESH' and mesh.hide_viewport == False)]
    # duplicate rigify
    gameready_rig_data = rigify_rig.data.copy()
    gameready_rig_data.name = properties.AddonPreferences.prefix + rigify_rig.data.name
    gameready_rig = bpy.data.objects.new(name = gameready_rig_data.name, object_data = gameready_rig_data)
    with context.temp_override(selected_objects = [gameready_rig], active_object = gameready_rig):
        bpy.ops.object.make_local(type = 'SELECT_OBDATA')
    # set position if not recentering (recenter just stays at 0. 0. 0.)
    if rigify_rig.sr_rigify_properties.recenter:
        gameready_rig.location, gameready_rig.rotation_euler = (0., 0., 0.), (0., 0., 0.)
    else:
        gameready_rig.location, gameready_rig.rotation_euler = rigify_rig.location.copy(), rigify_rig.rotation_euler.copy()
    # add new rig to correct collection
    add_scene_object_to_collection(context, gameready_rig, properties.AddonPreferences.collection_name)
    # remove rigify ID (rig_id)
    del gameready_rig.data[properties.AddonPreferences.rigify_id_prop_name]

    # build hierarchy
    gameready_rig.select_set(True)
    context.view_layer.objects.active = gameready_rig
    bpy.ops.object.mode_set(mode = 'EDIT', toggle = False)
    disconnect_all_bones = (rigify_rig.sr_rigify_properties is None) or rigify_rig.sr_rigify_properties.disconnect_all_bones
    additional_bones = []
    if rigify_rig.sr_rigify_properties.have_additional_bones:
        additional_bones = rigify_rig.sr_rigify_properties.additional_bones
    hierarchy = build_armature_hierarchy_from_rigify(gameready_rig, disconnect_all_bones, additional_bones)
    # remove animation data incl. drivers
    gameready_rig.data.animation_data_clear()
    # remove all bones that are not in hierarchy
    for bone in gameready_rig.data.edit_bones:
        if not any(bone.name in sl for sl in hierarchy):
            gameready_rig.data.edit_bones.remove(bone)
    put_all_bones_into_layer_index(gameready_rig, 0)
    # restore hierarchy (destroyed when removing bones above)
    restore_armature_hierarchy(gameready_rig, hierarchy)

    # unhide bones & reset bbone segments
    bpy.ops.object.mode_set(mode = 'POSE', toggle = False)
    for bone in gameready_rig.data.bones:
        bone.hide = False
        bone.bbone_segments = 1
    # add LocRot constraints
    constrain_rig_to_rigify(gameready_rig, rigify_rig)
    # reparent all meshes to generated gameready_rig, with empty groups
    bpy.ops.object.mode_set(mode = 'OBJECT', toggle = False)
    reparent_meshes_to_rig(gameready_rig, rigify_rig, meshes)
    remove_duplicates_vertex_groups_in_objects(meshes)
    # fix bone names. Some things (e.g. UE Control Rig) are messed up if bones have DEF- prefix (any other prefix??)
    remove_bone_DEF_prefix(gameready_rig)
    # save origin rigify on generated rig and vice versa
    gameready_rig.sr_origin = rigify_rig
    rigify_rig.sr_rigify_properties.generated_rig = gameready_rig
    return gameready_rig

def bake_nla_from_source_to_target_rig(context, source_rig, target_rig):
    """bake all unmuted nla tracks from source rig to target rig"""
    deselect_all(context)
    # get tracks to bake
    tracks_to_bake = get_tracks_to_bake(source_rig)
    # save solo state to restore it later
    prev_solo = None
    if len(tracks_to_bake) == 1 and tracks_to_bake[0].is_solo:
        prev_solo = tracks_to_bake[0]
    # select target object
    target_rig.select_set(True)
    context.view_layer.objects.active = target_rig
    bpy.ops.object.mode_set(mode = 'POSE', toggle = False)
    # create target's animation_data if it does not exist
    if not target_rig.animation_data:
        target_rig.animation_data_create()
    # bake tracks
    for track in tracks_to_bake:
        name = get_track_name(track, source_rig.sr_rigify_properties.animation_naming)
        track.is_solo = True
        frame_start, frame_end = get_nla_track_frame_range(track)
        # add prefix to action to avoid collision
        created_action = bpy.data.actions.new(str(properties.AddonPreferences.prefix + name))
        # set active|current before baking
        target_rig.animation_data.action = created_action
        bpy.ops.nla.bake(
            frame_start=frame_start
            , frame_end=frame_end
            , step=1
            , only_selected=False
            , visual_keying=True
            , clear_constraints=False
            , clear_parents=False
            , use_current_action=True
            , bake_types={'POSE'}
        )
        # Push down (new track then new strip from action)
        new_track = target_rig.animation_data.nla_tracks.new()
        new_strip = new_track.strips.new(created_action.name, int(created_action.frame_range[0]), created_action)
        # use track.name since action.name may have suffixes
        new_track.name = name
        new_strip.name = name
        # Un-solo
        track.is_solo = False
    target_rig.animation_data.action = None
    # restore solo track state
    if prev_solo:
        prev_solo.is_solo = True

class SANITIZERIGIFY_OT_Preview(bpy.types.Operator):
    """Preview what will be exported"""
    bl_idname = "sanitize_rigify.preview"
    bl_label = "Preview"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return can_preview(context, context.scene.sr_current_rigify)
    def execute(self, context):
        rigify_rig = context.scene.sr_current_rigify
        deselect_all(context)
        prev_location, prev_rotation = rigify_rig.location.copy(), rigify_rig.rotation_euler.copy()
        if rigify_rig.sr_rigify_properties.recenter:
            rigify_rig.location = (0., 0., 0.)
            rigify_rig.rotation_euler =  (0., 0., 0.)
        # generate rig
        gameready_rig = create_game_ready_rig(context, rigify_rig)
        # bake animations if mode is NLA or ALL
        if rigify_rig.sr_rigify_properties.export_mode != 'ARMATURE':
            bake_nla_from_source_to_target_rig(context, rigify_rig, gameready_rig)
        # unconstrain generated rig from origin rigify
        toggle_gameready_rig_constraints(gameready_rig, False)
        # select newly generated rig
        gameready_rig.select_set(True)
        context.view_layer.objects.active = gameready_rig
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        # restore location and hide rigify
        rigify_rig.location, rigify_rig.rotation_euler = prev_location, prev_rotation
        rigify_rig.hide_viewport = True
        self.report(type={'INFO'}, message=("Preview done"))
        return {'FINISHED'}

class SANITIZERIGIFY_OT_Unpreview(bpy.types.Operator):
    """Remove the generated rig"""
    bl_idname = "sanitize_rigify.unpreview"
    bl_label = "Unpreview"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return not can_preview(context, context.scene.sr_current_rigify)
    def execute(self, context):
        rigify_rig = context.scene.sr_current_rigify
        gameready_rig = rigify_rig.sr_rigify_properties.generated_rig
        deselect_all(context)
        # restore bone DEF- prefixes of gameready_rig to match rigify_rig
        restore_bone_DEF_prefix(gameready_rig)
        # get all meshes parented to the game-ready rig. Regardless of whether they're hidden or not
        meshes = [mesh for mesh in gameready_rig.children if mesh.type == 'MESH']
        # reparent meshes to rigify
        reparent_meshes_to_rig(rigify_rig, gameready_rig, meshes)
        # delete rig and all its actions
        delete_rig(gameready_rig, True)
        # select rigify
        rigify_rig.hide_viewport = False
        rigify_rig.select_set(True)
        context.view_layer.objects.active = rigify_rig
        self.report(type={'INFO'}, message=("Unpreview done"))
        return {'FINISHED'}

def get_default_file_path(context, rigify_object):
    """returns the default absolute file path with .fbx extension to export this rig"""
    path = rigify_object.sr_rigify_properties.path
    # set default for the first time
    if not path.endswith(".fbx"):
        return os.path.join(bpy.path.abspath(path) + rigify_object.name + ".fbx")
    return path

def rename_matching(list, name):
    """rename any matching element in list and returns it. Simply add a prefix"""
    if any((matching := elem).name == name for elem in list):
        matching.name = properties.AddonPreferences.prefix + matching.name
        return matching
    return None

def scale_for_export(context, rig_object, meshes, scale_target):
    """Scale to scale_target scene, rig, nla anims, and all meshes parented"""
    deselect_all(context)
    scene = context.scene
    scene_unit_scale = scene.unit_settings.scale_length
    scale_factor = scene_unit_scale / scale_target
    # disable auto-keyframing
    prev_autokey = scene.tool_settings.use_keyframe_insert_auto
    scene.tool_settings.use_keyframe_insert_auto = False
    ### ASSUMES SCENE DEFAULT UNIT IS 1.0 ### ????????
    # scale down scene to scale_target
    scene.unit_settings.scale_length = scale_target
    # scale rig by scale_factor
    rig_object.scale[0] *= scale_factor
    rig_object.scale[1] *= scale_factor
    rig_object.scale[2] *= scale_factor
    # scale rig position by scale_factor
    rig_object.location *= scale_factor
    # apply scales on armature & meshes
    [mesh.select_set(True) for mesh in meshes]
    rig_object.select_set(True)
    context.view_layer.objects.active = rig_object
    bpy.ops.object.transform_apply(location = True, rotation = True, scale = True)
    # scale nla_tracks by scale_factor
    if rig_object.animation_data:
        # assume no active action in animation_data
        # nla_tracks are already all made up of only 1 strip
        for nla_track in rig_object.animation_data.nla_tracks:
            action = nla_track.strips[0].action
            for fcurve in [fcurve for fcurve in action.fcurves if fcurve.data_path.endswith("location")]:
                # [1] is y-axis
                for keyframe in fcurve.keyframe_points:
                    keyframe.co[1] *= scale_factor
                    keyframe.handle_left[1] *= scale_factor
                    keyframe.handle_right[1] *= scale_factor
    # restore auto-keyframing
    scene.tool_settings.use_keyframe_insert_auto = prev_autokey

class SANITIZERIGIFY_OT_Export(bpy.types.Operator, bpy_extras.io_utils.ExportHelper):
    """Export rig"""
    bl_idname = "sanitize_rigify.export"
    bl_label = "Export"
    bl_options = {'REGISTER'}

    filter_glob : bpy.props.StringProperty(default = "*.fbx", options = {'HIDDEN'})
    filename_ext = ".fbx"
    check_extension = True

    save_path : bpy.props.BoolProperty(name = "Save path", default = True, description = "Save this rig's export path")

    @classmethod
    def poll(cls, context):
        return context.preferences.addons[__package__].preferences.allow_export_without_preview or is_previewing(context, context.scene.sr_current_rigify)
    @classmethod
    def description(cls, context, properties):
        if cls.poll(context):
            return "Export"
        return "Preview first before exporting. Change the addon preferences to allow directly exporting without previewing"
    def execute(self, context):
        file_path = self.filepath
        rigify_rig = context.scene.sr_current_rigify
        prev_active, prev_selected, prev_mode = deselect_all(context)
        # update default export folder
        if self.save_path:
            rigify_rig.sr_rigify_properties.path = file_path
        # generate rig & bake anims if not already previewing. (Save bool so that we can revert automatically after exporting)
        no_preview = False
        if not rigify_rig.sr_rigify_properties.generated_rig:
            bpy.ops.sanitize_rigify.preview()
            no_preview = True
        gameready_rig = rigify_rig.sr_rigify_properties.generated_rig
        # export all meshes parented to the gameready-rig
        meshes = [mesh for mesh in gameready_rig.children if mesh.type == 'MESH']
        # unhide all of them
        for mesh in meshes:
            mesh.hide_viewport = False
        # name of the exported armature
        armature_name = rigify_rig.sr_rigify_properties.armature_name
        # temporary rename objects & armatures of the same name
        renamed_object = rename_matching(bpy.data.objects, armature_name)
        renamed_armature = rename_matching(bpy.data.armatures, armature_name)
        gameready_rig_name = gameready_rig.name
        gameready_rig_data_name = gameready_rig.data.name
        # rename gameready_rig & its data to armature_name
        gameready_rig.name = armature_name
        gameready_rig.data.name = armature_name
        # unsolo and unmute all tracks on the gameready rig
        if gameready_rig.animation_data:
            for track in gameready_rig.animation_data.nla_tracks:
                track.is_solo = False
                track.mute = False
        # scale rig, meshes & nla tracks
        prev_scene_scale = context.scene.unit_settings.scale_length
        scale_for_export(context, gameready_rig, meshes, properties.AddonPreferences.export_scale)
        deselect_all(context)
        if rigify_rig.sr_rigify_properties.export_mode == 'ARMATURE':
            [mesh.select_set(True) for mesh in meshes]
            bake_anim=False
            bake_anim_use_all_bones=False
            bake_anim_force_startend_keying=False
        elif rigify_rig.sr_rigify_properties.export_mode == 'NLA':
            bake_anim=True
            bake_anim_use_all_bones=True
            bake_anim_force_startend_keying=True
        else: # ALL
            [mesh.select_set(True) for mesh in meshes]
            bake_anim=True
            bake_anim_use_all_bones=True
            bake_anim_force_startend_keying=True
        gameready_rig.select_set(True)
        context.view_layer.objects.active = gameready_rig
        bpy.ops.export_scene.fbx(
            filepath=file_path,
            use_selection=True,
            bake_anim_use_nla_strips=True,
            bake_anim_use_all_actions=False,
            object_types={'ARMATURE', 'MESH'},
            use_custom_props=False,
            global_scale=1.0,
            apply_scale_options='FBX_SCALE_NONE',
            axis_forward='-Z',
            axis_up='Y',
            apply_unit_scale=True,
            bake_space_transform=False,
            mesh_smooth_type='FACE',
            use_subsurf=False,
            use_mesh_modifiers=True,
            use_mesh_edges=False,
            use_tspace=False,
            primary_bone_axis='Y',
            secondary_bone_axis='X',
            armature_nodetype='NULL',
            use_armature_deform_only=False,
            add_leaf_bones=False,
            bake_anim = bake_anim,
            bake_anim_use_all_bones = bake_anim_use_all_bones,
            bake_anim_force_startend_keying = bake_anim_force_startend_keying,
            bake_anim_step=1.0,
            bake_anim_simplify_factor=0.0,
            use_metadata=True
        )
        # restore names
        gameready_rig.name = gameready_rig_name
        gameready_rig.data.name = gameready_rig_data_name
        if renamed_object:
            renamed_object = armature_name
        if renamed_armature:
            renamed_armature = armature_name
        # revert scaling
        scale_for_export(context, gameready_rig, meshes, prev_scene_scale)
        # unpreview if we directly exported
        if no_preview:
            bpy.ops.sanitize_rigify.unpreview()
        restore_selection(context, prev_active, prev_selected, prev_mode)
        self.report(type={'INFO'}, message=("Export done"))
        return {'FINISHED'}

class SANITIZERIGIFY_OT_ResetArmatureName(bpy.types.Operator):
    """Reset armature name"""
    bl_idname = "sanitize_rigify.reset_armature_name"
    bl_label = "Reset"
    bl_options = {'REGISTER'}
    @classmethod
    def poll(cls, context):
        return context.scene.sr_current_rigify
    def execute(self, context):
        current_rigify = context.scene.sr_current_rigify
        current_rigify.sr_rigify_properties.armature_name = context.preferences.addons[__package__].preferences.default_armature_name
        return {'FINISHED'}

class SANITIZERIGIFY_OT_AddAdditionalBone(bpy.types.Operator):
    """Add additional bone"""
    bl_idname = "sanitize_rigify.add_additional_bone"
    bl_label = "Add"
    bl_options = {'REGISTER'}
    @classmethod
    def poll(cls, context):
        current_rigify = context.scene.sr_current_rigify
        bonename_to_add = current_rigify.sr_rigify_properties.additional_bones_toadd
        return current_rigify and bonename_to_add
    def execute(self, context):
        current_rigify = context.scene.sr_current_rigify
        bonename_to_add = current_rigify.sr_rigify_properties.additional_bones_toadd
        if not any(bonename_to_add == bn.name for bn in current_rigify.data.bones):
            self.report(type={'WARNING'}, message=("Idem (" + bonename_to_add + ") is not a bone of " + current_rigify.name))
            return {'CANCELLED'}
        if any(bonename_to_add == bn.name for bn in current_rigify.sr_rigify_properties.additional_bones):
            self.report(type={'WARNING'}, message=("Bone (" + bonename_to_add + ") already added"))
            return {'CANCELLED'}
        added = current_rigify.sr_rigify_properties.additional_bones.add()
        added.name = bonename_to_add
        self.report(type={'INFO'}, message=("Bone (" + bonename_to_add + ") added"))
        return {'FINISHED'}

class SANITIZERIGIFY_OT_RemoveAdditionalBone(bpy.types.Operator):
    """Remove additional bone"""
    bl_idname = "sanitize_rigify.remove_additional_bone"
    bl_label = "Remove"
    bl_options = {'REGISTER'}
    index : bpy.props.IntProperty(default=0)
    @classmethod
    def poll(cls, context):
        current_rigify = context.scene.sr_current_rigify
        return current_rigify.sr_rigify_properties.additional_bones
    def execute(self, context):
        current_rigify = context.scene.sr_current_rigify
        additional_bones = current_rigify.sr_rigify_properties.additional_bones
        additional_bones.remove(self.index)
        current_index = current_rigify.sr_rigify_properties.additional_bones_index
        current_rigify.sr_rigify_properties.additional_bones_index = max(0, min(len(additional_bones.items()) - 1, current_index))
        self.report(type={'INFO'}, message=("Additional bone removed"))
        return {'FINISHED'}
    
class SANITIZERIGIFY_OT_ClearAdditionalBones(bpy.types.Operator):
    """Clear additional bones"""
    bl_idname = "sanitize_rigify.clear_additional_bones"
    bl_label = "Clear"
    bl_options = {'REGISTER'}
    @classmethod
    def poll(cls, context):
        return context.scene.sr_current_rigify
    def execute(self, context):
        current_rigify = context.scene.sr_current_rigify
        additional_bones = current_rigify.sr_rigify_properties.additional_bones
        if not additional_bones:
            self.report(type={'WARNING'}, message="Already empty")
            return {'CANCELLED'}
        additional_bones.clear()
        current_rigify.sr_rigify_properties.additional_bones_toadd = ""
        self.report(type={'INFO'}, message=("Additional bones cleared"))
        return {'FINISHED'}
