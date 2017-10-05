# import importlib
# importlib.sys.modules['blender-robot-arm-simulator.DH_helper']

import bpy, math
from mathutils import Vector
from .common import output



def initGP(context):
    S = context.scene
    # Create grease pencil data if none exists
    if not S.grease_pencil:
        a = [a for a in bpy.context.screen.areas if a.type == 'VIEW_3D'][0]
        override = {
            'scene': S,
            'screen': bpy.context.screen,
            'object': bpy.context.object,
            'area': a,
            'region': a.regions[0],
            'window': bpy.context.window,
            'active_object': bpy.context.object
        }

        bpy.ops.gpencil.data_add(override)

    return S.grease_pencil


def gpLayerFrame(context):

    gp = initGP(context)

    # 创建画 H-D 辅助线的图层
    if not gp.layers or not gp.layers["H-D"]:
        gpl = gp.layers.new('H-D', set_active=True)
    else:
        gpl = gp.layers['H-D']

    # Reference active GP frame or create one of none exists
    if gpl.frames:
        fr = gpl.active_frame
    else:
        fr = gpl.frames.new(1)

    return fr


def gpColor(context, name):
    gp = initGP(context)

    if "joint-help-line" in gp.palettes:
        palette = gp.palettes.get("joint-help-line")
    else:
        palette = gp.palettes.new("joint-help-line")

    if name in palette.colors :
        color = palette.colors.get(name)
    else:
        color = palette.colors.new()
        color.color = Vector([0.8815780282020569, 0.20415417850017548, 0.32798585295677185])
        color.name = name

    return color


def line(endpoint1, endpoint2, colorname="default") :

    if endpoint1==None or endpoint2==None:
        return

    fr = gpLayerFrame(bpy.context)

    # Create a new stroke
    str = fr.strokes.new(colorname=colorname)
    str.draw_mode = '3DSPACE'

    # Add points
    str.points.add(count = 2 )
    str.points[0].co = (endpoint1)
    str.points[1].co = (endpoint2)

    return str

print("file:::::::",__name__)


def clearGuide():
    fr = gpLayerFrame(bpy.context)
    if fr==None :
        return
    for str in fr.strokes.values() :
        fr.strokes.remove(str)

# 各个关节的坐标系
# 坐标系 i 对应关节 i+1
# -1 对应世界坐标系
joints_cosys = {
    -1: { "O": Vector((0,0,0)), "z-unit": Vector((0,0,50)), "x-unit": Vector((50,0,0)), "y-unit": None, "H": None } ,
    0: { "O": None, "z-unit": None, "x-unit": None, "y-unit": None, "H": None } ,
    1: { "O": None, "z-unit": None, "x-unit": None, "y-unit": None, "H": None } ,
    2: { "O": None, "z-unit": None, "x-unit": None, "y-unit": None, "H": None } ,
    3: { "O": None, "z-unit": None, "x-unit": None, "y-unit": None, "H": None } ,
    4: { "O": None, "z-unit": None, "x-unit": None, "y-unit": None, "H": None } ,
    5: { "O": None, "z-unit": None, "x-unit": None, "y-unit": None, "H": None } ,
    6: { "O": None, "z-unit": None, "x-unit": None, "y-unit": None, "H": None } ,
}


def normalize(v):
    v.normalize()
    return v

# 计算两直线的公垂线
# 算法参考 《3D数学基础》P268
# r1(t1) 为 zn上的垂足
# r2(t2) 为 zpre 上的垂足
# 如果两条直线相交，r1和r2实际为同一点，公垂线长度为0，v则提供了其方向
def commonPerpendicular(p1, d1, p2, d2) :

    v = d1.cross(d2)

    # d1 x d2 的长度为0(受float精度的影响接近0),表示前后两个关节的 z轴平行 或 重叠
    # 该情况下，不存在公垂线
    if v.magnitude<0.002 :
        return (None, None, None)

    magnitude2 = v.magnitude * v.magnitude

    tn = (p2 - p1).cross(d2).dot(v) / magnitude2
    tpre = (p2 - p1).cross(d1).dot(v) / magnitude2

    # 带入射线函数，求出 r1 和 r2
    r1 = p1 + tn * d1
    r2 = p2 + tpre * d2

    return (r1, r2, v)

# 计算两向量的夹角
def linesAngle(d1, d2, axes=None) :

    acos_value = d1.dot(d2)/(d1.magnitude*d2.magnitude)
    # 由于精度问题， 容易出现 1.0000000000000003 这样的数值
    if acos_value>1 :
        acos_value = 1.0
    if acos_value<-1 :
        acos_value = -1.0
    degree = math.acos( acos_value ) * 180.0/math.pi

    if degree<0.01 :
        degree = 0

    # 两向量叉乘的结果，和传入的axes方向相同，
    # 则 d1 到 d2 的为顺时针，返回正值
    # 否则为逆时针，返回负值
    if axes!=None :
        if d1.cross(d2).dot(axes)<0 :
            degree = -degree

    return degree

# 计算向量 v 到 n 的投影
def projection(v, n):
    return n * ((v * n) / (n.magnitude * n.magnitude))


# 返回关节 jointN 的z轴射线表达式
# 线段的射线表示法：
# r(t) = p  + td
# t = 0~1
def zAxes(jointN):
    if isinstance(jointN,str) :
        link = bpy.context.scene.objects[jointN]
    # 坐标系n 对应 关节n+1
    else:
        link = bpy.context.scene.objects["link" + str(jointN)]
    p = link.matrix_world * Vector((0, 0, 0))
    d = link.matrix_world * Vector((0, 0, 50)) - p
    return (p, d)

# 测定 DH参数模型中的常量值： a, alpha, d
def measureCoordinateSystem2(cosysIdx):

    # 坐标系n 对应 关节n+1
    cosysN = joints_cosys[cosysIdx]

    # 关节n 和 关节n+1 的z轴射线表达式参数
    if cosysIdx==6 :
        (pN, dN) = zAxes("arm-end")
    else:
        (pN, dN) = zAxes(cosysIdx)
    (pPre, dPre) = zAxes(cosysIdx-1)

    # 计算前后z轴的公垂线
    (hN, hPre, hDirection) = commonPerpendicular(pN,dN, pPre, dPre)

    # 没有共垂线，两轴平行或重叠
    if hN==None and hPre==None :

        # n关节的坐标，可以时 n+1 z轴上的任意位置
        cosysN["O"] = pN

        dNP = pN - pPre

        # 两z轴共线（重叠）
        if abs(dNP.dot(dN)-dNP.magnitude * dN.magnitude) < 0.001:
            cosysN["H"] = cosysN["O"]
            cosysN["x-unit"] = Vector((50,0,0)) + cosysN["O"]  # 和世界坐标系的x轴一致
        # 两z轴平行
        else :
            cosysN["H"] = projection(pN-pPre, dPre) + pPre
            cosysN["x-unit"] = 50 * normalize(cosysN["O"]-cosysN["H"]) + cosysN["O"]

    # 存在公垂线
    else :
        # 按照DH模型的约定，关节n 的原点，在关节n+1的 z轴上
        cosysN["O"] = hN
        cosysN["H"] = hPre
        cosysN["x-unit"] = -50 * normalize(hDirection) + cosysN["O"]

    # z轴
    cosysN["z-unit"] = 50 * normalize(dN) + cosysN["O"]


# 测定 固连到各个关节的相对坐标系
def measureCoordinateSystem(jointIdx):

    # 坐标系n 对应 关节n+1
    cosysN = joints_cosys[jointIdx]

    # 关节n 和 关节n+1 的z轴射线表达式参数
    (pN, dN) = zAxes(jointIdx)
    (pNext, dNext) = zAxes(jointIdx+1)

    # 计算前后z轴的公垂线
    (hN, hNext, hDirection) = commonPerpendicular(pN,dN, pNext, dNext)


    # 没有共垂线，两轴平行或重叠
    if hN==None and hNext==None :

        # n关节的坐标，可以时 n+1 z轴上的任意位置
        cosysN["O"] = pN

        dNP = pNext - pN

        # 两z轴共线（重叠）
        if abs(dNP.dot(dN)-dNP.magnitude * dN.magnitude) < 0.001:
            cosysN["H"] = cosysN["O"]
            cosysN["x-unit"] = bpy.context.scene.objects["link" + str(jointIdx)].matrix_world *  Vector((50,0,0))  # 取世界坐标系的x轴方向
        # 两z轴平行
        else :
            cosysN["H"] = projection(pN-pNext, dNext) + pNext
            cosysN["x-unit"] = 50 * normalize(cosysN["H"]-cosysN["O"]) + cosysN["O"]

    # 存在公垂线
    else :
        # 按照DH模型的约定，关节n 的原点，在关节n+1的 z轴上
        cosysN["O"] = hN
        cosysN["H"] = hNext
        cosysN["x-unit"] = 50 * normalize(hDirection) + cosysN["O"]

    # z轴
    cosysN["z-unit"] = 50 * normalize(dN) + cosysN["O"]

def measureDHConstValue(jointIdx):

    jointDHParam = getattr(bpy.context.scene, "joint"+str(jointIdx)+"_DH")
    cosysN = joints_cosys[jointIdx]
    cosysPre = joints_cosys[jointIdx - 1]

    # 参数a
    jointDHParam[0] = (cosysN["O"] - cosysN["H"]).magnitude

    # 参数alpha
    if (jointIdx+1) in joints_cosys :
        cosysNext = joints_cosys[jointIdx+1]
        jointDHParam[1] = linesAngle(cosysN["z-unit"]-cosysN["O"], cosysNext["z-unit"]-cosysNext["O"], cosysN["x-unit"]-cosysN["O"])
    else :
        # 按习惯 α6 = 0
        jointDHParam[1] = 0

    # 参数d
    jointDHParam[2] = (cosysN["O"]-cosysPre["H"]).magnitude
    # 根据和z轴的方向，确定正负
    if abs(jointDHParam[2])>0.001 :
        if (cosysN["O"] - cosysPre["H"]).dot( cosysN["z-unit"]-cosysN["O"] ) < 0 :
            jointDHParam[2] = -jointDHParam[2]

    # 参数theta
    jointDHParam[3] = linesAngle(cosysPre["x-unit"]-cosysPre["O"], cosysN["x-unit"]-cosysN["O"], cosysN["z-unit"]-cosysN["O"])

    return

def drawJointDHGuide(jointIdx):

    o = joints_cosys[jointIdx]["O"]

    # 画两根线，o-p1 和 o-p2 共线，先画长的那一根，以免短的被盖住
    def drawTwoLine (p1, color1, p2, color2) :
        if (p1-o).magnitude > (p2-o).magnitude :
            line(o, p1, color1)
            line(o, p2, color2)
        else:
            line(o, p2, color2)
            line(o, p1, color1)

    # line a 和 x axes
    drawTwoLine(joints_cosys[jointIdx]["H"],"DH-a", joints_cosys[jointIdx]["x-unit"],"x-axes")

    # line d 和 z axes
    drawTwoLine(joints_cosys[jointIdx - 1]["H"], "DH-d", joints_cosys[jointIdx]["z-unit"], "z-axes")


def redrawGuide():

    clearGuide()

    objects = bpy.context.scene.objects

    # 标定关节 1-6 的坐标系
    for idx in range(7) :
        measureCoordinateSystem(idx)
    # 关节6的坐标系的 H 值，用于计算关节6的 DH 参数a
    joints_cosys[6]["H"] = bpy.context.scene.objects["link7"].matrix_world.translation

    # 标定关节 1-6 的DH参数
    for idx in range(1,7) :
        measureDHConstValue(idx)

        # 绘制辅助线
        if getattr(bpy.context.scene, "joint"+str(idx)+"_drawDHGuide") == True :
            drawJointDHGuide(idx)

    # 最后一个关节的参数d 为到末端的距离
    # getattr(bpy.context.scene, "joint6_DH")[2] = (bpy.context.scene.objects["arm-end"].location - joints_cosys[6]["O"]).magnitude

def formatMatrix(m) :
    txt = "Matrix([\n"
    for row in range(0, len(m)):
        txt += "    ["
        for clm in range(0, len(m[row])):
            try:
                if abs(float(m[row][clm]))<0.001 :
                    txt += "0, "
                elif abs(1-float(m[row][clm]))<0.001 :
                    txt += "1, "
                else :
                    txt += str(m[row][clm]) + ", "
            except :
                txt += str(m[row][clm]) + ", "
        txt += "], \n"
    txt += "])"
    return txt

def outputDHEquation():

    codetpl = """
from sympy import *

θ1 = Symbol("θ1")
θ2 = Symbol("θ2")
θ3 = Symbol("θ3")
θ4 = Symbol("θ4")
θ5 = Symbol("θ5")
θ6 = Symbol("θ6")

simplify( """
    exp = [
        [ "cos(θ)", "-sin(θ) * cos(α)", "sin(θ) * sin(α)", "a * cos(θ)"] ,
        [ "sin(θ)", "cos(θ) * cos(α)", "-cos(θ) * sin(α)", "a * sin(θ)"] ,
        [ "0", "sin(α)", "cos(α)", "d"] ,
        [ "0", "0", "0", "1"]
    ]

    # 简化代数式
    def simplify(e, dh) :
        e = e.replace("θ", "θ" + str(joint))
        # 参数 a=0 or d=0
        if dh[0] < 0.001 or dh[2] < 0.001:
            if e.find("d")>=0 or e.find("a")>=0 :
                return "0"
        # 参数 α=90
        if 90 - dh[1] < 0.01:
            if e.find("cos(α)") > -1:
                return "0"
            e = e.replace(" * sin(α)", "")
            e = e.replace("sin(α)", "1")

        # 参数 α=0
        if dh[1] < 0.01:
            if e.find("sin(α)") > -1:
                return "0"
            e = e.replace(" * cos(α)", "")
            e = e.replace("cos(α)", "1")

        e = e.replace("a", str(dh[0]))
        e = e.replace("d", str(dh[2]))

        return e


    for joint in range(1,7) :
        jointDHParam = getattr(bpy.context.scene, "joint" + str(joint) + "_DH")
        m = [["","","",""],["","","",""],["","","",""],["","","",""]]
        for row in range(len(exp)) :
            for clm in range(len(exp[row])) :
                m[row][clm] = simplify( exp[row][clm], jointDHParam )

        if joint>1 :
            codetpl+= " * "
        codetpl+= formatMatrix(m)

    codetpl+=" ) \n"
    output(codetpl)

    #
    # for idx in range(1,7) :
    #     jointDHParam = getattr(bpy.context.scene, "joint" + str(idx) + "_DH")
    #     codetpl = codetpl.replace("a"+str(idx), str(jointDHParam[0]))
    #     codetpl = codetpl.replace("α"+str(idx), str(jointDHParam[1]))
    #     codetpl = codetpl.replace("d"+str(idx), str(jointDHParam[2]))
    #
    # output(codetpl)


def outputDHConst():
    txt = ""
    for i in range(1,7) :
        jointDHParam = getattr(bpy.context.scene, "joint" + str(i) + "_DH")
        txt+= "a"+str(i) + "=" + str(jointDHParam[0]) + "\n"
        txt+= "α"+str(i) + "=" + str(jointDHParam[1]) + "\n"
        txt+= "d"+str(i) + "=" + str(jointDHParam[2]) + "\n"
    output(txt)