# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8-80 compliant>

# Generic helper functions, to be used by any modules.

import bpy
import bmesh
import math
import mathutils
import itertools
import random
import time
import copy
from mathutils.bvhtree import BVHTree
from mathutils import Matrix,Vector
from collections import Counter
from decimal import *

def bb_size(obj):

   x = obj.dimensions.x
   y = obj.dimensions.y
   z = obj.dimensions.z
   bbox_v = x*y*z
   return bbox_v
   
def makestrut(obj1,obj2):
    interactionlist = bpy.context.scene.molprint_lists.interactionlist
    strut_radius = bpy.context.scene.molprint.strut_radius
    dx = obj2.location.x - obj1.location.x
    dy = obj2.location.y - obj1.location.y
    dz = obj2.location.z - obj1.location.z
    
    dist = get_distance(obj1,obj2)
    bpy.ops.mesh.primitive_cylinder_add(
      vertices = bpy.context.scene.molprint.prim_detail,
      radius = strut_radius, 
      depth = dist,
      location = (dx/2 + obj1.location.x, dy/2 + obj1.location.y, dz/2 + obj1.location.z)   
    )
    phi = math.atan2(dy, dx) 
    theta = math.acos(dz/dist) 
    bpy.context.object.rotation_euler[1] = theta 
    bpy.context.object.rotation_euler[2] = phi
    strut = bpy.context.scene.objects.active
    strut["ptype"] = "Cylinder"
    strut["radius"] = strut_radius
    strut["hbond"] = True
    strut["pinlist"] = ["None"]
    
    if len(interactionlist) > 2:
        interactionlist.append((obj1,strut))
        interactionlist.append((obj2,strut))
 
def scalebonds(scale_val):
    for obj in bpy.context.scene.objects:
        if obj["ptype"] == 'Cylinder' and obj["hbond"] == 0:
            #scale the object
            obj.scale = (scale_val,1,scale_val)
            #reset the radius value
            obj["radius"] = obj["radius"]*scale_val 
    
def cylinder_between(pair):
  x2 = pair[1].location.x
  y2 = pair[1].location.y
  z2 = pair[1].location.z
  x1 = pair[0].location.x
  y1 = pair[0].location.y
  z1 = pair[0].location.z  
  dx = x2 - x1
  dy = y2 - y1
  dz = z2 - z1    
  #dist = math.sqrt(dx**2 + dy**2 + dz**2)
  dist = get_distance(pair[0],pair[1])
  r = pair[1]["radius"]/1.5
  hbond = pair[1]["hbond"]
  
  #Pin with rectangles for easier assembly
  if bpy.context.scene.molprint.cubepin and not hbond:
    bpy.ops.mesh.primitive_cube_add(
      radius = r, 
      location = (dx/2 + x1, dy/2 + y1, dz/2 + z1)   
    )
    pin = bpy.context.scene.objects.active
    phi = math.atan2(dy, dx) 
    theta = math.acos(dz/dist) 
    bpy.ops.transform.resize( value=(pin.dimensions.x*2,pin.dimensions.y*2, dist*4) )
    bpy.ops.object.transform_apply( scale=True )
    bpy.context.object.rotation_euler[1] = theta 
    bpy.context.object.rotation_euler[2] = phi
    #resizes the cube
  
  #Pin with cylinders for rotation about bonds  
  else:
    bpy.ops.mesh.primitive_cylinder_add(
      vertices = bpy.context.scene.molprint.prim_detail,
      radius = r, 
      depth = dist,
      location = (dx/2 + x1, dy/2 + y1, dz/2 + z1)   
    )
    pin = bpy.context.scene.objects.active
    cyldim = pin.dimensions
    phi = math.atan2(dy, dx) 
    theta = math.acos(dz/dist) 
    bpy.context.object.rotation_euler[1] = theta 
    bpy.context.object.rotation_euler[2] = phi
    
    #This will be for woodruff style pinning
  
  if bpy.context.scene.molprint.woodruff:
    #pick a random long face from cylinder that was just made:
    
    bm = bmesh_copy_from_object(pin,transform=True,triangulate=False)
    goodfaces =  []
    for face in bm.faces:
        edgelen = len(face.edges)
        if edgelen < 5:
            #gCenterMedian = pin.matrix_world * face.calc_center_median()
            gCenterMedian = face.calc_center_median()
            #gCenterMedian = face.normal
            goodfaces.append((gCenterMedian,face.normal))
    
    placement = random.choice(goodfaces)
    print(placement)
    #place a cylinder at the center of that face
    
    bpy.ops.mesh.primitive_cube_add(location = placement[0])
    bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS') 
    wood = bpy.context.scene.objects.active
    #bpy.ops.transform.resize( snap_normal=placement[1],value=(r/2,r/2,dist/2) )
    wood.dimensions = cyldim/2
    #bpy.ops.object.transform_apply( scale=True ) 

    bpy.context.object.rotation_euler[1] = theta 
    bpy.context.object.rotation_euler[2] = phi
    
    #Unionize them!
    mymodifier = pin.modifiers.new('woodruff', 'BOOLEAN')
    mymodifier.operation = 'UNION'
    mymodifier.solver = 'CARVE'
    mymodifier.object = wood
    bpy.context.scene.objects.active = pin
    bpy.ops.object.modifier_apply (modifier='woodruff')
    bpy.context.scene.objects.unlink(wood)
    
def bmesh_copy_from_object(obj, transform=True, triangulate=True, apply_modifiers=False):

    assert(obj.type == 'MESH')

    if apply_modifiers and obj.modifiers:
        me = obj.to_mesh(bpy.context.scene, True, 'PREVIEW', calc_tessface=False)
        bm = bmesh.new()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    else:
        me = obj.data
        if obj.mode == 'EDIT':
            bm_orig = bmesh.from_edit_mesh(me)
            bm = bm_orig.copy()
        else:
            bm = bmesh.new()
            bm.from_mesh(me)

    # Remove custom data layers to save memory
    for elem in (bm.faces, bm.edges, bm.verts, bm.loops):
        for layers_name in dir(elem.layers):
            if not layers_name.startswith("_"):
                layers = getattr(elem.layers, layers_name)
                for layer_name, layer in layers.items():
                    layers.remove(layer)

    if transform:
        bm.transform(obj.matrix_world)

    if triangulate:
        bmesh.ops.triangulate(bm, faces=bm.faces)

    return bm

def bmesh_check_intersect_objects(obj, obj2, selectface=False):

    assert(obj != obj2)
    # Triangulate in most cases, not if using CPK matching
    tris = True
    if selectface:
        tris = False
    bm = bmesh_copy_from_object(obj, transform=True, triangulate=tris)
    bm2 = bmesh_copy_from_object(obj2, transform=True, triangulate=tris)
    intersect = False
    BMT1 = BVHTree.FromBMesh(bm)
    BMT2 = BVHTree.FromBMesh(bm2)   
    overlap_pairs = BMT1.overlap(BMT2)

    if len(overlap_pairs) > 0:
       intersect = True
       
    if selectface:
        #deselect everything for both objects
        bpy.context.scene.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        bpy.context.scene.objects.active = obj2
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        
        for each in overlap_pairs:
            obj.data.polygons[each[0]].select = True
            obj.update_from_editmode()
            obj2.data.polygons[each[1]].select = True
            obj2.update_from_editmode()
            
    bm.free()
    bm2.free()
            
    return intersect

def get_distance(obj1, obj2):
    return  (obj1.location - obj2.location).length

def isinside(obj1,obj2):
    #This is messy, but works reasonably well
    if bb_size(obj1) > bb_size(obj2):
        big = obj1
        small = obj2
    else:
        big = obj2
        small = obj1
    #Easier way to do this with Vectors? Had to do it this way because very small objects
    #could be inside very large objects, so location centers may not be close in some cases
    x1 = big.location.x
    x2 = small.location.x
    y1 = big.location.y
    y2 = small.location.y
    z1 = big.location.z
    z2 = small.location.z
       
    inside = True
    
    xdistance = math.sqrt((x1 - x2)**2)
    ydistance = math.sqrt((y1 - y2)**2)
    zdistance = math.sqrt((z1 - z2)**2)
    
    #This makes sure that the bounding box is fully inside
    #Might be an easier way to do?
    if xdistance+((small.dimensions.x)/2) > (big.dimensions.x)/2:
        inside = False
    if ydistance+((small.dimensions.y)/2) > (big.dimensions.y)/2:
        inside = False
    if zdistance+((small.dimensions.z)/2) > (big.dimensions.z)/2:
        inside = False
    if inside:
        return small
    else:
        return None
    
def makeMaterial(name, diffuse):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = diffuse
    mat.diffuse_shader = 'LAMBERT' 
    mat.diffuse_intensity = 1.0 
    return mat
       
def updategroups():
    start = time.time()
    #Reset grouplist
    grouplist = []
    bpy.context.scene.molprint_lists.grouplist = []
    interaction_list = bpy.context.scene.molprint_lists.interactionlist
    #Run for each object that is selected in scene
    for each in (bpy.context.selected_objects):
        group = []
        #checks to see if the object is already part of a group
        if each in itertools.chain.from_iterable(grouplist):
            continue
        #determine if our current/next interaction will be cylinder of sphere. Must always alternate in this case, i.e. no sphere-sphere contacts
        if each["ptype"] == 'Sphere':
             i,j = 0,1 
        if each["ptype"] == 'Cylinder':
             i,j = 1,0 
        #This object defines the first member of a new group
        group.append(each)
        #This is a list of all interacters that we need to branch from for defining the group
        nextlist = [value[j] for value in interaction_list if value[i] == each and value[j] not in bpy.context.selected_objects]
        additions = True
        
        while additions:
            additionlist = []
            additions = False
            for nextobj in nextlist:
                group.append(nextobj)
                objinteract = [obj[i] for obj in interaction_list if obj[j] == nextobj]
                #print("Object inteaction list:", objinteract)
                for nexts in objinteract:
                    if nexts in group:
                        continue
                    if nextobj["ptype"] == 'Sphere' and nextobj in bpy.context.selected_objects and nexts in bpy.context.selected_objects:
                        continue
                    if nextobj["ptype"] == 'Cylinder' and nextobj in bpy.context.selected_objects and nexts in bpy.context.selected_objects:
                        continue
                    
                    additionlist.append(nexts)
            #print('Addition list:', additionlist)
            nextlist = []
            #Is a copy necessary here? Is it slower?
            #nextlist = copy.copy(additionlist)
            nextlist = additionlist 
            if len(nextlist) > 0:
                additions = True
            if i == 1:
                i,j = 0,1
            else:
                i,j = 1,0        
        grouplist.append(group)

    bpy.context.scene.molprint_lists.grouplist = grouplist
    #This updates materials - useful for small things, but might slow things down for bigger stuff
    
    #if bpy.context.scene.molprint.autocolor:
        #Generate array of colors based on number of groups
    color_num = 0
    i = 1.0
    colors = []
    toggle_r = itertools.cycle([0,0.25,0.5,0.75,1])
    toggle_g = itertools.cycle([1.0, 0.66, 0.33, 0])
    toggle_b = itertools.cycle([1.0,0.33,0.25,0.66,0.05,0.75,0])
    while color_num <= len(grouplist):
        r = next(toggle_r)
        g = next(toggle_g)
        b = next(toggle_b)
        colors.append((r,g,b))
        color_num+=1
            
    #Is creating materials each time a waste of resources? Probably    
    m = 0
    for each in grouplist:
        mat = makeMaterial('mat'+str(m),colors[m])
        for ob in each:    
            ob.data.materials.clear()
            ob.data.materials.append(mat)
        m += 1
      
    end = time.time()
    print("Update group seconds:", end-start)
            
def getinteractions():
    #Build a complete list of interactions between objects to speed up joining
    objlist = itertools.combinations(bpy.context.scene.objects, 2)
    interactionlist = []
    for each in objlist:
        each[0]["pinlist"] = ['None']
        each[1]["pinlist"] = ['None']
        each[0]["hbond"] = 0
        each[1]["hbond"] = 0
        if (each[0]["ptype"] == 'Cylinder') and (each[1]["ptype"] == 'Cylinder'):
            continue
        distance = get_distance(each[0],each[1])
        intersect = False
        if distance < 2:	
            intersect = bmesh_check_intersect_objects(each[0], each[1])
        if intersect:
            if each[0]["ptype"] == 'Sphere':
                interactionlist.append((each[0],each[1]))
           
            if each[0]["ptype"] == 'Cylinder':
                interactionlist.append((each[1],each[0]))     
                
    return interactionlist

def union_carve(obj1,obj2):
    mymod = obj1.modifiers.new('simpmod', 'BOOLEAN')
    mymod.operation = 'UNION'
    mymod.solver = 'CARVE'
    mymod.object = obj2
    bpy.ops.object.modifier_apply (modifier='simpmod')
    
def joinpins(obj):
    #pinlist[:] = (value for value in pinlist if value != 'None')
    if len(obj["pinlist"]) <= 1:
        return
    objlist = itertools.combinations(obj["pinlist"], 2)
    removelist = []
    for each in objlist:
        try:
            pin1 = bpy.context.scene.objects[each[0]]
            pin2 = bpy.context.scene.objects[each[1]]
        except:
            continue
        intersect = bmesh_check_intersect_objects(pin1,pin2)
        if intersect:
            union_carve(pin1,pin2)
            print("Joining pins:",pin1,pin2)
            obj["pinlist"].remove(pin2.name)
            removelist.append(pin2)
    for each in removelist:
        bpy.context.scene.objects.unlink(each)

def joinall():
    updategroups()
    cylinders = []
    spheres = []
    pairs = []
    #Turn these off so it isn't constantly trying to update
    bpy.context.scene.molprint.interact = False
    bpy.context.scene.molprint.autogroup = False
    start = time.time()
    #setup objects and pin pairs
    for ob in bpy.context.selected_objects:
        if ob.type == 'MESH' and ob["ptype"] == 'Cylinder':
            cylinders.append(ob)
            ob["pinlist"] = ['None']
        if ob.type == 'MESH' and ob["ptype"] == 'Sphere':
            spheres.append(ob)
            ob["pinlist"] = ['None']    
    for cyl in cylinders:
        intersect = False
        for sphere in spheres:
            intersect = bmesh_check_intersect_objects(sphere, cyl)
            if intersect:
                pairs.append((sphere,cyl))
    #difference of pin pairs
    for each in pairs:
        mymodifier = each[1].modifiers.new('mymodifier1', 'BOOLEAN')
        mymodifier.operation = 'DIFFERENCE'
        mymodifier.solver = 'CARVE'
        mymodifier.object = each[0]
        bpy.context.scene.objects.active = each[1]
        bpy.ops.object.modifier_apply (modifier='mymodifier1')
    
    pinlist = []
    oblist = []
    for each in pairs:
        #Make pin objects and give them a specific ptype   
        cylinder_between(each)
        #put the sphere and the pin cylinder into a list
        pin = bpy.context.scene.objects.active
        pin["ptype"] = 'pin'
        pinlist.append(pin)
        each[0]["pinlist"] += [pin.name]
        #union cylinder and pin
        mymodifier = each[1].modifiers.new('mymodifier2', 'BOOLEAN')
        mymodifier.operation = 'UNION'
        mymodifier.solver = 'CARVE'
        mymodifier.object = pin
        bpy.context.scene.objects.active = each[1]
        bpy.ops.object.modifier_apply (modifier='mymodifier2')
        #union_carve(each[1],pin)
        bpy.ops.object.select_all(action='DESELECT')
       
    for group in bpy.context.scene.molprint_lists.grouplist:
        bpy.ops.object.select_all(action='DESELECT')
        pins = []
        
        for obj in group:
            obpin = []
            obpin[:] = (value for value in obj["pinlist"] if value != 'None')
            pins = pins+obpin
            obj.select = True
        
        #Make all objects of a group active and join    
        bpy.context.scene.objects.active = group[0]
        #copy material to joined group?
        #mat = group[0].data.materials
        pins = list(set(pins))
        group[0]["pinlist"] = pins
        #print(pins)
        bpy.ops.object.join()
        bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS') 
        oblist.append(group[0])
        
    end = time.time()
    print("Pin generation and joining time:", end-start)
    start = time.time()
    #unionize joined objects using large cube and intersection
    for ob in oblist:
        x = ob.location.x
        y = ob.location.y
        z = ob.location.z
        bpy.ops.mesh.primitive_cube_add(location=(x,y,z))
        bpy.ops.transform.resize(value=(30, 30, 30))
        cube = bpy.context.selected_objects[0]
        cube["ptype"] = 'newcube'
        pinlist[:] = (value for value in ob["pinlist"] if value != 'None')
        cube["pinlist"] = pinlist
        mymodifier = cube.modifiers.new('cubeto', 'BOOLEAN')
        mymodifier.operation = 'INTERSECT'
        mymodifier.solver = 'CARVE'
        mymodifier.object = ob
        bpy.ops.object.modifier_apply (modifier='cubeto')
        bpy.context.scene.objects.unlink(ob)
        
    end = time.time()
    print("Intersect unionization time:",end-start)
    start = time.time()
    #now do difference with pin objects with increased scale
    for each in bpy.context.scene.objects:
        if each["ptype"] == 'newcube' and len(each["pinlist"]) > 0:
            #If pins touch each other, this can cause issues. Older version
            #joined pins prior to doing difference.
            #TODO: re-explore this
            #joinpins(each)
            #sce.update()
            bpy.ops.object.select_all(action='DESELECT')
            for pinname in each["pinlist"]:
                pin = bpy.context.scene.objects[pinname]
                pin.scale=((1.05,1.05,1.05))
                pin.select = True
            firstpin = bpy.context.scene.objects[each["pinlist"][0]]
            bpy.context.scene.objects.active = firstpin
            bpy.ops.object.join()              
            mymodifier = each.modifiers.new('pinmodifier', 'BOOLEAN')
            mymodifier.operation = 'DIFFERENCE'
            mymodifier.solver = 'CARVE'
            mymodifier.object = firstpin
            bpy.context.scene.objects.active = each
            bpy.ops.object.modifier_apply (modifier='pinmodifier')
    #This is an ugly way to check and delete only pins. 
    #Not sure why I did this initially. Must be a simpler way?                
    for each in bpy.context.scene.objects:
        try:
            pinlist = each["pinlist"]
        except:
            bpy.context.scene.objects.unlink(each)
    end = time.time()
    print("Difference pinning time:",end-start)

def select_hbonds():
    interaction_list = bpy.context.scene.molprint_lists.interactionlist
    for each in interaction_list:
        #Reset in case radius value has been changed, won't deselect however
        each[1]["hbond"] = 0
        if each[1]["radius"] < bpy.context.scene.molprint.max_hbond:
            each[0].select = True
            each[1].select = True
            each[1]["hbond"] = 1

def select_phosphate(context):
    interaction_list = bpy.context.scene.molprint_lists.interactionlist
    countdictsphere = Counter(elem[0] for elem in interaction_list)
    
    for k, v in countdictsphere.items():
        #is it a phosphorous?
        if v == 4 and abs(k["radius"] - bpy.context.scene.molprint.phosphorous_radius) < 0.0001:
            k.select = True
            fin = False
            cyls = [value[1] for value in interaction_list if value[0] == k and not value[1]["hbond"]]
            for cyl in cyls:
                if fin:
                    break
                second_sphere = [each[0] for each in interaction_list if each[0] != k and each[1] == cyl]
                for ss in second_sphere:
                    second_cyl = [each[1] for each in interaction_list if ss == each[0] and each[1] not in cyls]
                    
                    for sc in second_cyl:
                        third_sphere = [each[0] for each in interaction_list if sc == each[1] and each[0] != ss]
                        
                        for k1, v1 in countdictsphere.items():
                            if k1 == third_sphere[0] and v1 > 2:
                                cyl.select = True
                                fin = True
                                break
                            
def select_glyco_na(context):

    interaction_list = bpy.context.scene.molprint_lists.interactionlist
    countdict = Counter(elem[0] for elem in interaction_list)
    #rads = (0.51,0.465,0.456)
    molprint = bpy.context.scene.molprint
    rads = (round(molprint.carbon_radius,3),round(molprint.nitrogen_radius,3),round(molprint.oxygen_radius,3))
    for k, v in countdict.items():
        if v == 3 and k["radius"] == round(molprint.carbon_radius,3):
            #print('Sphere:',k)
            #k.select = True
            #first get all cylinders connected, ignoring H-bonds
            cyls = [value[1] for value in interaction_list if value[0] == k and not value[1]["hbond"]]
            #now get sphere,cylinders that are not the original
            #print('Cylinders:',cyls)
            second = [each for each in interaction_list if each[0] != k and each[1] in cyls]
            #iterate this new list, and confirm that
            #print('Second spheres:',second)
            dist1 = get_distance(second[0][0],second[1][0])
            dist2 = get_distance(second[0][0],second[2][0])
            dist3 = get_distance(second[1][0],second[2][0])
            avgdist = dist1+dist2+dist3/3
            #print('Distance:',avgdist)
            secondrads = (round(second[0][0]["radius"],3),round(second[1][0]["radius"],3),round(second[2][0]["radius"],3))
            #print(rads,secondrads)
            #print(avgdist)
            if rads == secondrads and avgdist > 5.56 and countdict.get(second[1][0]) > 1:
                k.select = True
                second[1][1].select = True
           
def select_amides(context):

    interaction_list = bpy.context.scene.molprint_lists.interactionlist
    countdict = Counter(elem[0] for elem in interaction_list)
    #TODO: assign element variable to radius so this doesn't have to be hardcoded
    rads = (0.51,0.465,0.456)
    for k, v in countdict.items():
        if v == 3 and k["radius"] == 0.510:
            print('Sphere:',k)
            #first get all cylinders connected, ignoring H-bonds
            cyls = [value[1] for value in interaction_list if value[0] == k and value[1]["radius"] > bpy.context.scene.molprint.max_hbond]
            #now get sphere,cylinders that are not the original
            print('Cylinders:',cyls)
            second = [each for each in interaction_list if each[0] != k and each[1] in cyls]
            #iterate this new list, and confirm that
            print('Second spheres:',second)
            secondrads = (second[0][0]["radius"],second[1][0]["radius"],second[2][0]["radius"])
            #print(secondrads)
            if rads == secondrads:
                #need to differentiate backbone from Asn/Gln
                if countdict.get(second[1][0]) > 1:                 
                    second[0][0].select = True
                    second[0][1].select = True

def floorall(context):
    vec2 = (0,0,-1)
    for each in bpy.context.scene.objects:
        bpy.ops.object.select_all(action='DESELECT')
        facenormal = getlargestface(each)
        align_vector(each,facenormal,vec2)
        bpy.context.scene.objects.active = each

def floorselected(context):
    obj = bpy.context.scene.objects.active
    assert obj.mode == 'EDIT'
    #Get facenormal for each selected face in our object
    bm1 = bmesh.from_edit_mesh(obj.data)
    #bm1.faces.ensure_lookup_table()
    vec2 = (0,0,-1)
    facelist = []
    for f in bm1.faces:
        if f.select:
            #print(f.normal)
            facelist.append(f.normal)
    totalvec = Vector()
    for each in facelist:
        totalvec = totalvec + each
    finalvec = totalvec/len(facelist)
    align_vector(bpy.context.scene.molprint_lists.floorlist[0],finalvec,vec2)
    
                              
def getlargestface(obj):

    bm1 = bmesh_copy_from_object(obj)
    bmesh.ops.convex_hull(bm1,input=(bm1.verts),use_existing_faces=False)
    bmesh.ops.dissolve_limit(bm1,angle_limit=0.09,verts=bm1.verts,edges=bm1.edges)
    bm1.faces.ensure_lookup_table()
  
    largestface = 0
    largestidx = None
    faceidx = 0 
    for face in bm1.faces:
        facearea = face.calc_area()
        if facearea > largestface:
            largestidx = faceidx
            largestface = facearea
        faceidx += 1
    
    bm1.faces[largestidx].select = True
    facenorm = bm1.faces[largestidx].normal
    return facenorm

def align_vector(obj,vec1,vec2):
    matrix_orig = obj.matrix_world.copy()
    axis_src = matrix_orig.to_3x3() * vec1
    axis_dst = vec2
    #axis_dst = Vector((0, 0, -1))
    matrix_rotate = matrix_orig.to_3x3()
    matrix_rotate = matrix_rotate * axis_src.rotation_difference(axis_dst).to_matrix()
    matrix_translation = Matrix.Translation(matrix_orig.to_translation())
    obj.matrix_world = matrix_translation * matrix_rotate.to_4x4()

def check_split_cyls(obj1,obj2,splitcyllist):
    bpy.ops.object.select_all(action='DESELECT') 
    bm1 = bmesh_copy_from_object(obj1, transform=True, triangulate=False)
    bm2 = bmesh_copy_from_object(obj2, transform=True, triangulate=False)
    matched = False
    #Must also check face normals
    for f1 in bm1.faces:
        if matched:
            break
        if len(f1.edges) > 4:
            f1.normal_flip()
            for f2 in bm2.faces:
                if len(f2.edges) > 4:
                    fnorm1 = (f1.normal * obj1.matrix_world).to_tuple(3)
                    fnorm2 = (f2.normal * obj2.matrix_world).to_tuple(3)
                    #convert these to a tuple to allow comparision without rounding issues of vectors
                    #only need one check. For chimera, needed to drop precision down to 3
                    if tol(f1.calc_center_median(),f2.calc_center_median()) and fnorm1[1] == fnorm2[1]:
                        matched = True
                        splitcyllist.append((obj1,obj2))
                        break
    return splitcyllist

def merge_split_cyls(splitcyllist):
    #looked into doing this with bmesh, but wasn't as straightforward :(
    for a,b in splitcyllist:
        #Some models can have odd organization that leads to failures. Try to fix with a quick check:
        try:
            a.data.materials.clear()
            b.data.materials.clear()
        except:
            continue
        bpy.ops.object.select_all(action='DESELECT') 
        bpy.context.scene.objects.active = a
        a.select = True
        b.select = True
        bpy.ops.object.join()
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.remove_doubles()
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_interior_faces()
        bpy.ops.mesh.delete(type='FACE')
        bpy.ops.mesh.dissolve_limited()
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS') 
        bpy.ops.object.select_all(action='DESELECT')
       
def tol(v1, v2):
    return (v1 - v2).length < 0.01

def AlignX(v1,v2):
    dvec=v2-v1
    rotation_quat = dvec.to_track_quat('Z', 'X')
    return rotation_quat

def median_intersect(ob):
    '''Returns the median point of all selected verts'''
    bpy.context.scene.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    ob.update_from_editmode()
    me = ob.data
    verts_sel = [v.co for v in me.vertices if v.select]
    pivot = sum(verts_sel, Vector()) / len(verts_sel)
    return ob.matrix_world * pivot

def cpkcyl(obj1,obj2, dummy1, dummy2):
    spot1 = median_intersect(obj1)
    #spot2 = median_intersect(obj2)
    #Dummy atom two will be along vector between centers
    #med = (spot1+spot2)/2
    dummy1.location = spot1
    #Here is the vector for positioning second point
    dx,dy,dz = obj2.location.x - obj1.location.x, obj2.location.y - obj1.location.y, obj2.location.z - obj1.location.z
    dist = (obj2.location - obj1.location).length
    diam = obj1.dimensions.x
    #make sure it is sufficient large to extend past
    scale = diam/dist
    dummy2.location = (dx*scale+obj1.location.x, dy*scale+obj1.location.y, dz*scale+obj1.location.z)
    
    #Now make cyl between dummy1 and dummy2 positions
    dx,dy,dz = dummy2.location.x - dummy1.location.x, dummy2.location.y - dummy1.location.y, dummy2.location.z - dummy1.location.z
    
    bpy.ops.mesh.primitive_cylinder_add(
        vertices = 16,
        radius = 2, 
        depth = (dummy2.location - dummy1.location).length,
        location = (dx/2 + dummy1.location.x, dy/2 + dummy1.location.y, dz/2 + dummy1.location.z)
    )
   
    cylinder=bpy.context.scene.objects.active
    cylinder["ptype"] = "CPKcyl"
    cylinder.rotation_mode='QUATERNION'
    #Set rotation
    cylinder.rotation_quaternion=AlignX(obj1.location,obj2.location)
    #Now do difference bool
    
    mymodifier = obj1.modifiers.new('cpkmod', 'BOOLEAN')
    mymodifier.operation = 'DIFFERENCE'
    mymodifier.solver = 'CARVE'
    mymodifier.object = cylinder