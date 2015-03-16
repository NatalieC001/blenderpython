# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ***** END GPL LICENCE BLOCK *****

#
# add_mesh_round_cube.py Copyright (c) 2014, Alain Ducharme
#

bl_info = {
    'name': 'Round Cube',
    'author': 'Alain Ducharme (Phymec)',
    'version': (0, 1),
    'blender': (2, 65, 0),
    'location': 'View3D > Add > Mesh > Round Cube',
    'description': 'Add mesh primitives: Quadsphere, Capsule, Rounded Cuboid, 3D Grid',
    'warning': '',
    'wiki_url': '',
    'category': 'Add Mesh',
}

import bpy
from bpy_extras import object_utils
from itertools import permutations
from math import copysign, pi, sqrt

def round_cube(radius=1.0, arcdiv=4, lindiv=0., size=(0. ,0. ,0.), div_type='CORNERS', odd_axis_align=False, info_only=False):
    # subdiv bitmasks
    CORNERS, EDGES, ALL = 0, 1, 2
    try:
        subdiv = ('CORNERS', 'EDGES', 'ALL').index(div_type)
    except ValueError:
        subdiv = CORNERS # fallback

    radius = max(radius, 0.)
    if not radius:
        arcdiv = 1

    if arcdiv <= 0:
        arcdiv = max(round(pi * radius * lindiv * 0.5), 1)
    arcdiv = max(round(arcdiv), 1)
    if lindiv <= 0.:
        if radius:
            lindiv = 1. / (pi / (arcdiv * 2.) * radius)
    lindiv = max(lindiv, 0.)
    if not lindiv:
        subdiv = CORNERS

    odd = arcdiv % 2 # even = arcdiv % 2 ^ 1
    step_size = 2. / arcdiv

    odd_aligned = 0
    vi = -1.
    steps = arcdiv + 1
    if odd_axis_align and odd:
        odd_aligned = 1
        vi += 0.5 * step_size
        steps = arcdiv
    axis_aligned = not odd or odd_aligned

    if arcdiv == 1 and not odd_aligned and subdiv == EDGES:
        subdiv = CORNERS

    half_chord = 0. # ~ spherical cap base radius
    sagitta = 0. # ~ spherical cap height
    if not axis_aligned:
        half_chord = sqrt(3.) * radius / (3. * arcdiv)
        id2 = 1. / (arcdiv * arcdiv)
        sagitta = radius - radius * sqrt(id2 * id2 / 3. - id2 + 1.)

    # Extrusion per axis
    exyz = [0. if s < 2. * (radius - sagitta) else (s - 2. * (radius - sagitta)) * 0.5 for s in size]
    ex, ey, ez = exyz

    dxyz = [0, 0, 0]      # extrusion divisions per axis
    dssxyz = [0., 0., 0.] # extrusion division step sizes per axis

    for i in range(3):
        sc = 2. * (exyz[i] + half_chord)
        dxyz[i] = round(sc * lindiv) if subdiv else 0
        if dxyz[i]:
            dssxyz[i] = sc / dxyz[i]
            dxyz[i] -= 1
        else:
            dssxyz[i] = sc

    if info_only:
        ec = sum(1 for n in exyz if n)
        if subdiv:
            fxyz = [d + (e and axis_aligned) for d, e in zip(dxyz, exyz)]
            dvc = arcdiv * 4 * sum(fxyz)
            if subdiv == ALL:
                dvc += sum(p1 * p2 for p1, p2 in permutations(fxyz, 2))
            elif subdiv == EDGES:
                #      (0, 0, 2, 4) * sum(dxyz) + (0, 0, 2, 6)
                dvc += ec * ec // 2 * sum(dxyz) + ec * (ec - 1) if axis_aligned else 0
        else:
            dvc = (arcdiv * 4) * ec + ec * (ec - 1) if axis_aligned else 0
        vert_count = int(6 * arcdiv*arcdiv + (0 if odd_aligned else 2) + dvc)
        if not radius and not max(size) > 0:
            vert_count = 1
        return arcdiv, lindiv, vert_count

    if not radius and not max(size) > 0:
        return [(0,0,0)], []

    # uv lookup table
    uvlt = []
    v = vi
    for j in range(1, steps + 1):
        v2 = v*v
        uvlt.append((v, v2, radius * sqrt(18. - 6. * v2) / 6.))
        v = vi + j * step_size # v += step_size # instead of accumulating errors
        # clear precision errors / signs at axis
        if abs(v) < 1e-10:
            v = 0.0

    # Round cube sides built left to right bottom up
    #         xp yp zp  xd  yd  zd
    sides = ((0, 2, 1, (-1,  1,  1)),   # Y+ Front
             (1, 2, 0, (-1, -1,  1)),   # X- Left
             (0, 2, 1, ( 1, -1,  1)),   # Y- Back
             (1, 2, 0, ( 1,  1,  1)),   # X+ Right
             (0, 1, 2, (-1,  1, -1)),   # Z- Bottom
             (0, 1, 2, (-1, -1,  1)))   # Z+ Top

    # side vertex index table
    svit = [[[] for i in range(steps)] for i in range(6)]
    # Extend rows for extrusion
    if ey:
        yer = axis_aligned + (dxyz[1] if subdiv else 0)
        svit[4].extend([[] for i in range(yer)])
        svit[5].extend([[] for i in range(yer)])
    if ez:
        zer = axis_aligned + (dxyz[2] if subdiv else 0)
        for side in range(4):
            svit[side].extend([[] for i in range(zer)])
    ryi = rzi = 0 # row vertex indices
    # Extend rows for odd_aligned
    if odd_aligned:
        for side in range(4):
            svit[side].append([])

    hemi = steps // 2

    # Create vertices and svit without dups
    vert = [0., 0., 0.]
    verts = []

    if arcdiv == 1 and not odd_aligned and subdiv == ALL:
        # Special case: 3D Grid Cuboid
        for side, (xp, yp, zp, dir) in enumerate(sides):
            svitc = svit[side]
            rows = len(svitc)
            if rows < dxyz[yp] + 2:
                svitc.extend([[] for i in range(dxyz[yp] + 2 - rows)])
            vert[zp] = (half_chord + exyz[zp]) * dir[zp]
            print(dssxyz, half_chord, exyz, dir)
            for j in range(dxyz[yp] + 2):
                vert[yp] = (j * dssxyz[yp] - half_chord - exyz[yp]) * dir[yp]
                for i in range(dxyz[xp] + 2):
                    vert[xp] = (i * dssxyz[xp] - half_chord - exyz[xp]) * dir[xp]
                    if (side == 5) or ((i < dxyz[xp] + 1 and j < dxyz[yp] + 1) and (side < 4 or (i and j))):
                        print(side, vert)
                        svitc[j].append(len(verts))
                        verts.append(tuple(vert))
    else:
        for j in range(steps):
            v, v2, mv2 = uvlt[j]
            tv2mh = 1./3. * v2 - 0.5
            hv2 = 0.5 * v2

            if j == hemi:
                # Jump over non-edge row vertex indices
                if ey:
                    ryi += yer
                if ez:
                    rzi += zer

            for i in range(steps):
                u, u2, mu2 = uvlt[i]
                x = u * mv2
                y = v * mu2
                z = radius * sqrt(u2 * tv2mh - hv2 + 1.)

                for side, (xp, yp, zp, dir) in enumerate(sides):
                    svitc = svit[side]
                    ri = rzi if side < 4 else ryi

                    vert[xp] = x
                    vert[yp] = y
                    vert[zp] = z
                    exr = exyz[xp]
                    eyr = exyz[yp]

                    if (side == 5) or (i < arcdiv and j < arcdiv and (side < 4 or (i and j or odd_aligned))):
                        vert[0] = (vert[0] + copysign(ex, vert[0])) * dir[0]
                        vert[1] = (vert[1] + copysign(ey, vert[1])) * dir[1]
                        vert[2] = (vert[2] + copysign(ez, vert[2])) * dir[2]
                        rv = tuple(vert)

                        if exr and i == hemi:
                            rx = vert[xp] # save xp
                            vert[xp] = rxi = (-exr - half_chord) * dir[xp]
                            if axis_aligned:
                                svitc[ri].append(len(verts))
                                verts.append(tuple(vert))
                            if subdiv:
                                offsetx = dssxyz[xp] * dir[xp]
                                for k in range(dxyz[xp]):
                                    vert[xp] += offsetx
                                    svitc[ri].append(len(verts))
                                    verts.append(tuple(vert))
                            if eyr and j == hemi and axis_aligned:
                                vert[xp] = rxi
                                vert[yp] = -eyr * dir[yp]
                                svitc[hemi].append(len(verts))
                                verts.append(tuple(vert))
                                if subdiv:
                                    offsety = dssxyz[yp] * dir[yp]
                                    ry = vert[yp]
                                    for k in range(dxyz[yp]):
                                        vert[yp] += offsety
                                        svitc[hemi + axis_aligned + k].append(len(verts))
                                        verts.append(tuple(vert))
                                    vert[yp] = ry
                                    for k in range(dxyz[xp]):
                                        vert[xp] += offsetx
                                        svitc[hemi].append(len(verts))
                                        verts.append(tuple(vert))
                                        if subdiv & ALL:
                                            for l in range(dxyz[yp]):
                                                vert[yp] += offsety
                                                svitc[hemi + axis_aligned + l].append(len(verts))
                                                verts.append(tuple(vert))
                                            vert[yp] = ry
                            vert[xp] = rx # restore

                        if eyr and j == hemi:
                            vert[yp] = (-eyr - half_chord) * dir[yp]
                            if axis_aligned:
                                svitc[hemi].append(len(verts))
                                verts.append(tuple(vert))
                            if subdiv:
                                offsety = dssxyz[yp] * dir[yp]
                                for k in range(dxyz[yp]):
                                    vert[yp] += offsety
                                    if exr and i == hemi and not axis_aligned and subdiv & ALL:
                                        vert[xp] = rxi
                                        for l in range(dxyz[xp]):
                                            vert[xp] += offsetx
                                            svitc[hemi + k].append(len(verts))
                                            verts.append(tuple(vert))
                                        vert[xp] = rx
                                    svitc[hemi + axis_aligned + k].append(len(verts))
                                    verts.append(tuple(vert))

                        svitc[ri].append(len(verts))
                        verts.append(rv)
            ryi += 1
            rzi += 1

    # Complete svit edges (shared vertices)
    # Sides' right edge
    for side, rows in enumerate(svit[:4]):
        for j, row in enumerate(rows[:-1]):
            svit[3 if not side else side - 1][j].append(row[0])
    # Sides' top edge
    for j, row in enumerate(svit[5]):
        if not j:
            for col in row:
                svit[0][-1].append(col)
        if j == len(svit[5]) - 1:
            for col in reversed(row):
                svit[2][-1].append(col)
        svit[3][-1].insert(0, row[0])
        svit[1][-1].append(row[-1])
    if odd_aligned:
        for side in svit[:4]:
            side[-1].append(-1)
    # Bottom edges
    if odd_aligned:
        svit[4].insert(0, [-1] + svit[2][0][-2::-1] + [-1])
        for i, col in enumerate(svit[3][0][:-1]):
            svit[4][i + 1].insert(0, col)
            svit[4][i + 1].append(svit[1][0][-i - 2])
        svit[4].append([-1] + svit[0][0][:-1] + [-1])
    else:
        svit[4][0].extend(svit[2][0][::-1])
        for i, col in enumerate(svit[3][0][1:-1]):
            svit[4][i + 1].insert(0, col)
            svit[4][i + 1].append(svit[1][0][-i - 2])
        svit[4][-1].extend(svit[0][0])

    # Build faces
    faces = []
    if not axis_aligned:
        hemi -= 1
    for side, rows in enumerate(svit):
        xp, yp = sides[side][:2]
        oa4 = odd_aligned and side == 4
        if oa4: # special case
            hemi += 1
        for j, row in enumerate(rows[:-1]):
            tri = odd_aligned and (oa4 and not j or rows[j+1][-1] < 0)
            for i, vi in enumerate(row[:-1]):
                # odd_aligned triangle corners
                if vi < 0:
                    if not j and not i:
                        faces.append((row[i+1], rows[j+1][i+1], rows[j+1][i]))
                elif oa4 and not i and j == len(rows) - 2:
                    faces.append((vi, row[i+1], rows[j+1][i+1]))
                elif tri and i == len(row) - 2:
                    if j:
                        faces.append((vi, row[i+1], rows[j+1][i]))
                    else:
                        if oa4 or arcdiv > 1:
                            faces.append((vi, rows[j+1][i+1], rows[j+1][i]))
                        else:
                            faces.append((vi, row[i+1], rows[j+1][i]))
                # subdiv = EDGES (not ALL)
                elif subdiv and len(rows[j + 1]) < len(row) and (i >= hemi):
                    if (i == hemi):
                        faces.append((vi, row[i+1+dxyz[xp]], rows[j+1+dxyz[yp]][i+1+dxyz[xp]], rows[j+1+dxyz[yp]][i]))
                    elif i > hemi + dxyz[xp]:
                        faces.append((vi, row[i+1], rows[j+1][i+1-dxyz[xp]], rows[j+1][i-dxyz[xp]]))
                elif subdiv and len(rows[j + 1]) > len(row) and (i >= hemi):
                    if (i > hemi):
                        faces.append((vi, row[i+1], rows[j+1][i+1+dxyz[xp]], rows[j+1][i+dxyz[xp]]))
                elif subdiv and len(row) < len(rows[0]) and i == hemi:
                    pass
                else:
                    # Most faces...
                    faces.append((vi, row[i+1], rows[j+1][i+1], rows[j+1][i]))
        if oa4:
            hemi -= 1

    return verts, faces

from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty

class AddRoundCube(bpy.types.Operator):
    """Add Round Cube Primitive"""
    bl_idname = 'mesh.primitive_round_cube_add'
    bl_label = 'Add Round Cube'
    bl_description = 'Add mesh primitives: Quadsphere, Capsule, Rounded Cuboid, 3D Grid'
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    sanity_check_verts = 200000

    radius = FloatProperty(
            name = 'Radius',
            description = 'Radius of vertices for sphere, capsule or cuboid bevel',
            default = 1.0, min = 0.0, soft_min=0.01, step=10
            )

    size = FloatVectorProperty(
            name = 'Size',
            description = 'Size',
            subtype = 'XYZ',
            )

    arc_div = IntProperty(
            name = 'Arc Divisions',
            description = 'Arc curve divisions, per quadrant; 0 = derive from Linear',
            default = 4, min = 0
            )

    lin_div = FloatProperty(
            name = 'Linear Divisions',
            description = 'Linear unit divisions (Edges/Faces); 0 = derive from Arc',
            default = 0.0, min = 0.0, step=100, precision=1
            )

    div_type = EnumProperty(
            name = 'Type',
            description = 'Division type',
            items = (
                ('CORNERS', 'Corners', 'Sphere / Corners'),
                ('EDGES', 'Edges', 'Sphere / Corners and extruded edges (size)'),
                ('ALL', 'All', 'Sphere / Corners, extruded edges and faces (size)')),
            default = 'CORNERS',
            )

    odd_axis_align = BoolProperty(
            name='Odd Axis Align',
            description = 'Align odd arc divisions with axes (Note: triangle corners!)',
            )

    no_limit = BoolProperty(
            name='No Limit',
            description = 'Do not limit to '+str(sanity_check_verts)+' vertices (sanity check)',
            )

    preset = EnumProperty(
            name = 'Presets',
            items = (
                ('CUSTOM', 'Custom', 'Round Cube'),
                ('SPHERE', 'Sphere', 'Quadsphere'),
                ('CAPSULE', 'Capsule', 'Capsule'),
                ('CUBOID', 'Cube', 'Rounded Cuboid'),
                ('3DGRID', 'Grid', '3D Grid Cube')),
            default = 'CUSTOM', options={'HIDDEN'}
            )

    def execute(self, context):
        if self.preset == 'SPHERE':
            self.radius = 1.0
            self.size = (0.,0.,0.)
            self.arc_div = max(self.arc_div, 4)
            self.lin_div = 0.
            self.div_type = 'CORNERS'
        elif self.preset == 'CAPSULE':
            self.radius = 0.5
            self.size = (0.,0.,3.)
            self.arc_div = max(self.arc_div, 4)
            self.lin_div = 0.
            self.div_type = 'CORNERS'
        elif self.preset == 'CUBOID':
            self.radius = 0.25
            self.size = (2.,2.,2.)
            self.arc_div = max(self.arc_div, 4)
            self.lin_div = 0.
            self.div_type = 'CORNERS'
        elif self.preset == '3DGRID':
            self.radius = 1.0
            self.arc_div = 1
            self.lin_div = max(self.lin_div, 5.)
            self.div_type = 'ALL'
            self.size = (2.,2.,2.)
            self.odd_axis_align = False
        self.preset = 'CUSTOM'

        if self.arc_div <=0 and self.lin_div <= 0:
            self.report({'ERROR'}, 'Either Arc Divisions or Linear Divisions must be greater than zero!')
            return {'CANCELLED'}

        if not self.no_limit:
            arcdiv, lindiv, vert_count = round_cube(self.radius, self.arc_div, self.lin_div, self.size, self.div_type, self.odd_axis_align, True)
            if vert_count > self.sanity_check_verts:
                self.report({'ERROR'}, 'More than '+str(self.sanity_check_verts)+' vertices!  Check "No Limit" to proceed')
                return {'CANCELLED'}

        verts, faces = round_cube(self.radius, self.arc_div, self.lin_div, self.size, self.div_type, self.odd_axis_align)

        mesh = bpy.data.meshes.new('Roundcube')
        mesh.from_pydata(verts,[],faces)
        object_utils.object_data_add(context, mesh, operator=None)

        return {'FINISHED'}

    def draw(self, context):

        arcdiv, lindiv, vert_count = round_cube(self.radius, self.arc_div, self.lin_div, self.size, self.div_type, self.odd_axis_align, True)

        layout = self.layout

        layout.prop(self, 'radius')
        row = layout.row()
        row.column().prop(self, 'size', expand=True)

        box = layout.box()
        row = box.row()
        row.alignment = 'CENTER'
        row.scale_y = 0.1
        row.label('Divisions')
        row = box.row()# align=True)
        col = row.column()
        col.alignment = 'RIGHT'
        col.label('Arc:')
        col.prop(self, 'arc_div', text="")
        col.label('[ {} ]'.format(arcdiv))
        col = row.column()
        col.alignment = 'RIGHT'
        col.label('Linear:')
        col.prop(self, 'lin_div', text="")
        col.label('[ {:.3g} ]'.format(lindiv))
        box.row().prop(self, 'div_type')
        row = box.row()
        row.active = arcdiv % 2
        row.prop(self, 'odd_axis_align')

        row = layout.row()
        row.alert = vert_count > self.sanity_check_verts
        row.prop(self, 'no_limit', text='No limit ({})'.format(vert_count))

class INFO_MT_mesh_round_cube_add(bpy.types.Menu):
    bl_idname = 'INFO_MT_mesh_round_cube_add'
    bl_label = 'Round Cube'
    def draw(self, context):
        layout = self.layout
        layout.operator_context = 'INVOKE_REGION_WIN'
        layout.operator(AddRoundCube.bl_idname, text = 'Custom', icon='MOD_SUBSURF')
        layout.operator(AddRoundCube.bl_idname, text = 'Sphere', icon='META_BALL').preset = 'SPHERE'
        layout.operator(AddRoundCube.bl_idname, text = 'Capsule', icon='META_ELLIPSOID').preset = 'CAPSULE'
        layout.operator(AddRoundCube.bl_idname, text = 'Cube', icon='META_CUBE').preset = 'CUBOID'
        layout.operator(AddRoundCube.bl_idname, text = 'Grid', icon='META_CUBE').preset = '3DGRID'

def menu_func(self, context):
    self.layout.menu('INFO_MT_mesh_round_cube_add', icon='MOD_SUBSURF')

def register():
    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_mesh_add.append(menu_func)

def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.INFO_MT_mesh_add.remove(menu_func)
