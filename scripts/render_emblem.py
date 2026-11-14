"""Render a model as a README emblem, turning once: black studio, glossy floor, blue / cyan / gold rim lights.

    blender -b --disable-autoexec -P scripts/render_emblem.py -- MODEL OUT_FOLDER KIND [frames] [samples] [size]

MODEL is a .blend or an .fbx (an .fbx's textures are looked for in ../textures beside it). KIND says how it lies and
turns:

    hookshot   a tool lying along X: tip up and to the right, turning about its own long axis
    shield     a flat thing: upright, facing the camera, turning about the vertical

Writes OUT_FOLDER/<KIND>_000.png ... The models are not in the repository (assets/brand/README.md names the ones
used). scripts/make_hero.py and scripts/make_hero_anim.py lay the frames out as the banner and its animation.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
model, out, kind = argv[0], argv[1], argv[2]
frames = int(argv[3]) if len(argv) >= 4 else 1
samples = int(argv[4]) if len(argv) >= 5 else 128
res = int(argv[5]) if len(argv) >= 6 else 1024

if model.lower().endswith(".blend"):
    bpy.ops.wm.open_mainfile(filepath=model, use_scripts=False)
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=model)
scene = bpy.context.scene
for o in list(bpy.data.objects):
    if o.type in ("LIGHT", "CAMERA"):
        bpy.data.objects.remove(o, do_unlink=True)
meshes = [o for o in bpy.data.objects if o.type == "MESH" and not o.hide_render]


def texture(material, base, colour, normal=None, rough_from_spec=None):
    """Wire a material's Principled shader to the texture files given (colour, and a normal and a specular map when there)."""
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")

    def image(name, data):
        node = nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(os.path.join(base, name), check_existing=True)
        if data:
            node.image.colorspace_settings.name = "Non-Color"
        return node

    links.new(image(colour, False).outputs["Color"], bsdf.inputs["Base Color"])
    if normal:
        nm = next((n for n in nodes if n.type == "NORMAL_MAP"), None) or nodes.new("ShaderNodeNormalMap")
        links.new(image(normal, True).outputs["Color"], nm.inputs["Color"])
        links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if rough_from_spec:   # (a specular map: bright is shiny, so roughness is its inverse)
        inv = nodes.new("ShaderNodeInvert")
        links.new(image(rough_from_spec, True).outputs["Color"], inv.inputs["Color"])
        links.new(inv.outputs["Color"], bsdf.inputs["Roughness"])


if not model.lower().endswith(".blend"):
    tex = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(model))), "textures")
    files = os.listdir(tex) if os.path.isdir(tex) else []

    def find(part, kind_):
        return next((f for f in files if part.lower() in f.lower() and f.rsplit(".", 1)[0].lower().endswith("_" + kind_)), None)

    for m in bpy.data.materials:
        # (the shield's face is "Main"; its rim, studs, crest, grip and straps share "Parts")
        part = "Main" if any(w in m.name for w in ("Base", "Wood")) else "Parts"
        if find(part, "d"):
            texture(m, tex, find(part, "d"), find(part, "n"), find(part, "s"))
            print("TEXTURED", m.name, part)

# one parent for the whole model, at its centre
lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        lo = Vector(map(min, lo, w))
        hi = Vector(map(max, hi, w))
centre, dims = (lo + hi) / 2, hi - lo
size = max(dims)
print("BOUNDS", [round(v, 2) for v in lo], [round(v, 2) for v in hi])
root = bpy.data.objects.new("root", None)
scene.collection.objects.link(root)
root.location = centre
bpy.context.view_layer.update()
for o in bpy.data.objects:
    if o.parent is None and o is not root:
        m = o.matrix_world.copy()
        o.parent = root
        o.matrix_world = m
root.location = (0, 0, 0)
turner = bpy.data.objects.new("turner", None)   # (the turn is the turner's; the root holds the model's pose)
scene.collection.objects.link(turner)
root.parent = turner

if kind == "hookshot":
    # XYZ Euler: X, the long axis, turns first; then the tilt and the yaw put the tip up and to the right
    TILT, YAW, START = 38.0, 200.0, 20.0
    root.rotation_euler = (0, 0, 0)
    turner.rotation_euler = [math.radians(v) for v in (START, TILT, YAW)]

    def pose(f):
        turner.rotation_euler[0] = math.radians(START + 360.0 * f / frames)
else:
    # stand it up when it lies flat, its face to the camera (-Y), leaning back a little
    thin = min(range(3), key=lambda i: dims[i])
    root.rotation_euler = (math.radians(90), 0, 0) if thin == 2 else (0, 0, math.radians(90)) if thin == 0 else (0, 0, 0)
    bpy.context.view_layer.update()
    # The project's own letter in the crest's place: the crest (and the three triangles in it) is Nintendo's mark, so
    # its mesh is left out of the render and a gold H stands on the face instead.
    for o in meshes:
        if any("Triforce" in (s.material.name if s.material else "") for s in o.material_slots):
            o.hide_render = True
    # (the crest's bird is painted on the face's colour texture too: its red is painted over with the face's own blue,
    #  in memory only, and the face's normal map, which embosses the same bird, is left out)
    import numpy as np
    for img in bpy.data.images:
        if "main_d" in img.name.lower():
            px = np.array(img.pixels[:], dtype=np.float32).reshape(-1, 4)
            red = (px[:, 0] > px[:, 2] * 1.15) & (px[:, 0] > 0.2)
            blue = (px[:, 2] > px[:, 0] * 1.6) & (px[:, 2] > 0.3)
            if red.any() and blue.any():
                px[red, :3] = np.median(px[blue, :3], axis=0)
                img.pixels.foreach_set(px.reshape(-1))
                img.update()
                img.pack()   # (so the render takes these pixels, not the file's)
                print("PAINTED OVER", int(red.sum()), "pixels of", img.name)
    for mat in bpy.data.materials:
        if "Base" in mat.name and mat.use_nodes:
            for link in list(mat.node_tree.links):
                if link.to_socket.name == "Normal" and link.to_node.type == "BSDF_PRINCIPLED":
                    mat.node_tree.links.remove(link)
    shown = [o for o in meshes if not o.hide_render]
    front = min((o.matrix_world @ Vector(c)).y for o in shown for c in o.bound_box)
    gold = bpy.data.materials.new("letter")
    gold.use_nodes = True
    gb = next(n for n in gold.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    gb.inputs["Base Color"].default_value = (0.95, 0.66, 0.16, 1)
    gb.inputs["Metallic"].default_value = 0.55   # (all metal, it mirrored the black studio and went dark)
    gb.inputs["Roughness"].default_value = 0.32
    gb.inputs["Emission Color"].default_value = (0.95, 0.6, 0.12, 1)
    gb.inputs["Emission Strength"].default_value = 0.25
    # the H: two posts and a bar, as boxes (a font's extruded outline came out with torn faces)
    high, wide, stroke, deep = size * 0.44, size * 0.36, size * 0.105, size * 0.035
    for x, w, h in ((-(wide - stroke) / 2, stroke, high), ((wide - stroke) / 2, stroke, high), (0, wide, stroke)):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, front - deep / 2, -size * 0.03))
        part = bpy.context.object
        part.scale = (w, deep, h)
        bevel = part.modifiers.new("bevel", "BEVEL")
        bevel.width, bevel.segments = size * 0.006, 3
        part.data.materials.append(gold)
        bpy.context.view_layer.update()
        m = part.matrix_world.copy()
        part.parent = root
        part.matrix_world = m
    START = float(os.environ.get("EMBLEM_START", "-25"))
    turner.rotation_euler = (math.radians(-8), 0, math.radians(START))

    def pose(f):
        turner.rotation_euler[2] = math.radians(START + 360.0 * f / frames)
bpy.context.view_layer.update()

# the floor: glossy black, under the model wherever its turn takes it
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -size * 0.62))
fm = bpy.data.materials.new("floor")
fm.use_nodes = True
bsdf = next(n for n in fm.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
bsdf.inputs["Base Color"].default_value = (0.004, 0.004, 0.006, 1)
bsdf.inputs["Roughness"].default_value = 0.22
bpy.context.object.data.materials.append(fm)

world = scene.world or bpy.data.worlds.new("w")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.0, 0.0, 0.0, 1)


def light(name, loc, colour, power, sz):
    d = bpy.data.lights.new(name, "AREA")
    d.energy, d.color, d.size = power, colour, sz
    o = bpy.data.objects.new(name, d)
    scene.collection.objects.link(o)
    o.location = Vector(loc) * size
    o.rotation_euler = (Vector((0, 0, 0)) - o.location).to_track_quat("-Z", "Y").to_euler()


p = size * size * 55
light("key", (-1.2, -2.2, 2.4), (1.0, 0.97, 0.94), p * 2.4, size * 1.6)
light("rim_blue", (2.4, 1.8, 1.2), (0.15, 0.4, 1.0), p * 2.2, size * 1.0)
light("rim_cyan", (-2.6, 1.6, 0.6), (0.1, 0.85, 1.0), p * 1.4, size * 1.0)
light("gold", (0.4, -2.0, -0.2), (1.0, 0.7, 0.2), p * 0.35, size * 1.2)

cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
scene.collection.objects.link(cam)
scene.camera = cam
cam.data.lens = 85
cam.location = Vector((0.0, -2.9, 0.55)) * size
cam.rotation_euler = (Vector((0, 0, 0)) - cam.location).to_track_quat("-Z", "Y").to_euler()

scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
try:
    prefs.compute_device_type = "OPTIX"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == "OPTIX"
    scene.cycles.device = "GPU"
except Exception as e:   # (the CPU then)
    print("no OptiX:", e)
scene.cycles.samples = samples
scene.cycles.use_denoising = True
scene.render.resolution_x = scene.render.resolution_y = res
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
for f in range(frames):
    pose(f)
    scene.render.filepath = os.path.join(out, "%s_%03d.png" % (kind, f))
    bpy.ops.render.render(write_still=True)
print("WROTE", frames, "frames to", out)
