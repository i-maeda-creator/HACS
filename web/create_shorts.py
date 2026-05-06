"""
HACS YouTube Shorts v3
- edge-tts（Microsoft Neural音声）
- オリジナルキャラクター（Worker/Guardian/Trader/Observer/Governor）
- 余白をキャラクターで埋める
- 最後は「いいね＆チャンネル登録」CTA
"""
import sys, os, subprocess, tempfile, asyncio
sys.path.insert(0, "..")

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import edge_tts
from moviepy import *
import math

W, H = 1080, 1920
FPS  = 30
OUT  = "hacs_shorts.mp4"
SPEED = 1.85

# 音声選択: "ja-JP-NanamiNeural"（女性）or "ja-JP-KeitaNeural"（男性）
VOICE = "ja-JP-NanamiNeural"

FFMPEG = None
try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except: pass

# ── フォント ───────────────────────────────────────────────────
def font(size):
    for p in ["C:/Windows/Fonts/YuGothB.ttc","C:/Windows/Fonts/meiryob.ttc","C:/Windows/Fonts/msgothic.ttc"]:
        if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def font_r(size):
    for p in ["C:/Windows/Fonts/YuGothR.ttc","C:/Windows/Fonts/meiryo.ttc","C:/Windows/Fonts/msgothic.ttc"]:
        if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default()

# ── カラー ─────────────────────────────────────────────────────
BG1=(8,8,20); BG2=(18,18,45)
BLUE=(100,160,255); GREEN=(80,220,140); YELLOW=(255,200,60)
RED=(255,100,100); PURPLE=(200,100,255); WHITE=(255,255,255); GRAY=(170,170,200)
ORANGE=(255,150,60)

ROLE_COLOR = {
    "Worker":   BLUE,
    "Guardian": RED,
    "Trader":   ORANGE,
    "Observer": PURPLE,
    "Governor": (160,120,80),
}

# ── キャラクター描画 ────────────────────────────────────────────
def draw_character(d, cx, cy, role, size=110, mood="normal"):
    """各エージェントのオリジナルキャラクターを描く"""
    c = ROLE_COLOR.get(role, WHITE)
    dark = tuple(max(0, v-60) for v in c)
    light = tuple(min(255, v+60) for v in c)
    s = size

    # 胴体
    d.rounded_rectangle([cx-s//2, cy-s//4, cx+s//2, cy+s//2],
                         radius=s//5, fill=c, outline=WHITE, width=2)

    # 頭
    d.ellipse([cx-s//2+4, cy-s-s//4, cx+s//2-4, cy-s//4+4],
              fill=c, outline=WHITE, width=2)

    # 顔（目）
    ey = cy - s*3//4
    eye_size = s//8
    if mood == "happy":
        # 笑顔の目（アーチ）
        d.arc([cx-s//4-eye_size, ey-eye_size, cx-s//4+eye_size, ey+eye_size],
              200, 340, fill=dark, width=3)
        d.arc([cx+s//4-eye_size, ey-eye_size, cx+s//4+eye_size, ey+eye_size],
              200, 340, fill=dark, width=3)
    elif mood == "cool":
        # サングラス
        d.rectangle([cx-s//3, ey-eye_size//2, cx-s//8, ey+eye_size//2], fill=dark)
        d.rectangle([cx+s//8, ey-eye_size//2, cx+s//3, ey+eye_size//2], fill=dark)
        d.line([cx-s//8, ey, cx+s//8, ey], fill=dark, width=2)
    else:
        d.ellipse([cx-s//4-eye_size, ey-eye_size, cx-s//4+eye_size, ey+eye_size], fill=dark)
        d.ellipse([cx+s//4-eye_size, ey-eye_size, cx+s//4+eye_size, ey+eye_size], fill=dark)
        # 口
        d.arc([cx-s//6, ey+eye_size, cx+s//6, ey+eye_size*3],
              0, 180, fill=dark, width=3)

    # 役割別アクセサリー
    if role == "Worker":
        # レンチ
        rx, ry = cx+s//2+6, cy-s//4
        d.ellipse([rx-10, ry-20, rx+10, ry], fill=GRAY, outline=WHITE, width=1)
        d.rectangle([rx-4, ry, rx+4, ry+30], fill=GRAY)
    elif role == "Guardian":
        # シールド
        sx, sy = cx+s//2+4, cy-s//8
        pts = [(sx,sy-28),(sx+20,sy-10),(sx+20,sy+16),(sx,sy+28),(sx-20,sy+16),(sx-20,sy-10)]
        d.polygon(pts, fill=RED, outline=WHITE, width=2)
        d.line([(sx,sy-20),(sx,sy+16)], fill=WHITE, width=2)
    elif role == "Trader":
        # コイン
        for i in range(3):
            ox = cx+s//2+6+i*6
            oy = cy-s//6+i*8
            d.ellipse([ox-10,oy-10,ox+10,oy+10], fill=YELLOW, outline=WHITE, width=1)
            d.text((ox-6,oy-10), "EC", font=font_r(14), fill=(10,10,30))
    elif role == "Observer":
        # 望遠鏡
        ox, oy = cx+s//2+4, cy-s//4
        d.rectangle([ox, oy, ox+30, oy+12], fill=PURPLE, outline=WHITE, width=1)
        d.ellipse([ox+22, oy-4, ox+36, oy+16], fill=light, outline=WHITE, width=1)
    elif role == "Governor":
        # 王冠
        gx, gy = cx, cy-s-s//4-20
        pts = [(gx-30,gy+20),(gx-30,gy),(gx-15,gy+12),(gx,gy-8),
               (gx+15,gy+12),(gx+30,gy),(gx+30,gy+20)]
        d.polygon(pts, fill=YELLOW, outline=WHITE, width=2)

    # 足
    d.rounded_rectangle([cx-s//3, cy+s//2, cx-s//10, cy+s//2+s//3],
                         radius=6, fill=dark, outline=WHITE, width=1)
    d.rounded_rectangle([cx+s//10, cy+s//2, cx+s//3, cy+s//2+s//3],
                         radius=6, fill=dark, outline=WHITE, width=1)


def draw_character_group(img, positions_roles, size=90):
    """複数キャラクターをまとめて描画"""
    d = ImageDraw.Draw(img)
    for (cx, cy), role, mood in positions_roles:
        draw_character(d, cx, cy, role, size=size, mood=mood)


# ── 共通ユーティリティ ─────────────────────────────────────────
def grad_bg(c1=BG1, c2=BG2):
    img = Image.new("RGB",(W,H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t=y/H; r=int(c1[0]+(c2[0]-c1[0])*t); g=int(c1[1]+(c2[1]-c1[1])*t); b=int(c1[2]+(c2[2]-c1[2])*t)
        d.line([(0,y),(W,y)],fill=(r,g,b))
    return img

def grid_overlay(img):
    ov = Image.new("RGBA",(W,H),(0,0,0,0))
    d  = ImageDraw.Draw(ov)
    for x in range(0,W,60): d.line([(x,0),(x,H)],fill=(80,100,255,15))
    for y in range(0,H,60): d.line([(0,y),(W,y)],fill=(80,100,255,15))
    return Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")

def cx_text(draw, text, y, fnt, color=WHITE, shadow=True):
    bb = draw.textbbox((0,0),text,font=fnt); tw=bb[2]-bb[0]
    x  = (W-tw)//2
    if shadow: draw.text((x+3,y+3),text,font=fnt,fill=(0,0,0,160))
    draw.text((x,y),text,font=fnt,fill=color)

def tag_box(draw, text, y, fnt, bg, fg=(10,10,30)):
    bb = draw.textbbox((0,0),text,font=fnt); tw=bb[2]-bb[0]; th=bb[3]-bb[1]
    x=(W-tw)//2; pad=18
    draw.rounded_rectangle([x-pad,y-pad,x+tw+pad,y+th+pad],radius=14,fill=bg)
    draw.text((x,y),text,font=fnt,fill=fg)

def progress_bar(draw, pct, color=BLUE):
    y=H-50; draw.rectangle([0,y,W,y+10],fill=(30,30,60))
    draw.rectangle([0,y,int(W*pct),y+10],fill=color)

def speech_bubble(draw, x, y, text, fnt, color):
    bb = draw.textbbox((0,0),text,font=fnt); tw=bb[2]-bb[0]; th=bb[3]-bb[1]
    pad=14; r=10
    bx1,by1=x-tw//2-pad, y-th-pad*2
    bx2,by2=x+tw//2+pad, y-pad//2
    draw.rounded_rectangle([bx1,by1,bx2,by2],radius=r,fill=color)
    draw.polygon([(x-10,by2),(x+10,by2),(x,by2+18)],fill=color)
    draw.text((bx1+pad,by1+pad),text,font=fnt,fill=(10,10,30))

def arrow(draw, x1,y1,x2,y2,color,width=6):
    draw.line([(x1,y1),(x2,y2)],fill=color,width=width)
    angle=math.atan2(y2-y1,x2-x1); size=22
    draw.polygon([(x2,y2),
        (int(x2-size*math.cos(angle-0.5)),int(y2-size*math.sin(angle-0.5))),
        (int(x2-size*math.cos(angle+0.5)),int(y2-size*math.sin(angle+0.5)))],fill=color)

# ── 音声生成（edge-tts + 2倍速）─────────────────────────────────
async def _tts(text, voice, path):
    c = edge_tts.Communicate(text, voice)
    await c.save(path)

def make_audio_fast(text, speed=SPEED, voice=VOICE):
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        orig = f.name
    asyncio.run(_tts(text, voice, orig))
    if FFMPEG is None or speed == 1.0:
        return orig
    out = orig.replace(".mp3","_fast.mp3")
    af = f"atempo={speed}" if speed <= 2.0 else f"atempo=2.0,atempo={speed/2.0}"
    subprocess.run([FFMPEG,"-y","-i",orig,"-filter:a",af,"-vn",out],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.unlink(orig)
    return out

# ── シーン ──────────────────────────────────────────────────────

def scene_hook():
    img=grad_bg(); img=grid_overlay(img); d=ImageDraw.Draw(img)
    tag_box(d,"AI x ロボット x 文明",110,font(40),BLUE)
    cx_text(d,"自律文明を",270,font(96))
    cx_text(d,"Pythonで",380,font(96))
    cx_text(d,"作ってみた",490,font(96))
    # キャラクター5体を下に並べる
    chars = [
        ((130,1550),"Worker","happy"),
        ((330,1580),"Guardian","normal"),
        ((540,1540),"Trader","happy"),
        ((750,1580),"Observer","cool"),
        ((950,1550),"Governor","normal"),
    ]
    draw_character_group(img, chars, size=115)
    # ラベル
    labels=[("Worker",130),("Guardian",330),("Trader",540),("Observer",750),("Governor",950)]
    for name,lx in labels:
        bb=d.textbbox((0,0),name,font=font_r(28)); tw=bb[2]-bb[0]
        d.text((lx-tw//2,1680),name,font=font_r(28),fill=GRAY)
    progress_bar(d,0.0,BLUE)
    return img


def scene_what_is():
    img=grad_bg(); img=grid_overlay(img); d=ImageDraw.Draw(img)
    tag_box(d,"概要",110,font(42),GREEN)
    cx_text(d,"HACS とは？",240,font(90))
    cx_text(d,"Home Autonomous",380,font_r(52),GRAY)
    cx_text(d,"Civilization System",450,font_r(52),GRAY)
    # 説明テキスト
    lines=["17体のロボットが","自律的に仕事をして","生活するシミュレーター"]
    y=580
    for line in lines:
        cx_text(d,line,y,font(62)); y+=84
    # キャラクター左右に配置
    draw_character_group(img,[
        ((130,1100),"Worker","happy"),((950,1100),"Guardian","normal"),
        ((130,1380),"Trader","happy"),((950,1380),"Observer","cool"),
        ((540,1480),"Governor","normal"),
    ], size=110)
    progress_bar(d,0.12,GREEN)
    return img


def scene_auction1():
    img=grad_bg(); img=grid_overlay(img); d=ImageDraw.Draw(img)
    tag_box(d,"仕事の仕組み 1/3",110,font(40),YELLOW,fg=(10,10,30))
    cx_text(d,"タスクが発生！",240,font(88))
    cx_text(d,"誰が仕事をする？",360,font(58),GRAY)

    # グリッド
    GX,GY=140,480; CS=88; COLS=9; ROWS=6
    for gy in range(ROWS):
        for gx in range(COLS):
            x1=GX+gx*CS; y1=GY+gy*CS
            d.rectangle([x1,y1,x1+CS-2,y1+CS-2],outline=(50,50,100),width=1,fill=(15,15,35))
    # タスク（星）
    tx,ty=GX+4*CS+CS//2,GY+2*CS+CS//2
    pts=[]
    for i in range(10):
        angle=math.pi/5*i-math.pi/2
        r=38 if i%2==0 else 16
        pts.append((tx+r*math.cos(angle),ty+r*math.sin(angle)))
    d.polygon(pts,fill=YELLOW)
    cx_text(d,"タスク発生！",GY+ROWS*CS+40,font(52),YELLOW)

    # キャラクターをグリッドの角に配置
    draw_character_group(img,[
        ((GX+CS//2,     GY+CS//2),     "Worker",  "normal"),
        ((GX+8*CS+CS//2,GY+CS//2),     "Guardian","normal"),
        ((GX+CS//2,     GY+5*CS+CS//2),"Trader",  "normal"),
        ((GX+8*CS+CS//2,GY+5*CS+CS//2),"Observer","normal"),
    ], size=72)

    cx_text(d,"みんなが仕事に注目！",GY+ROWS*CS+130,font_r(46),GRAY)
    progress_bar(d,0.30,YELLOW)
    return img


def scene_auction2():
    img=grad_bg(); img=grid_overlay(img); d=ImageDraw.Draw(img)
    tag_box(d,"仕事の仕組み 2/3",110,font(40),GREEN,fg=(10,10,30))
    cx_text(d,"一斉に入札！",240,font(88))
    cx_text(d,"最安値が落札",360,font(60),GREEN)

    GX,GY=140,480; CS=88; COLS=9; ROWS=6
    for gy in range(ROWS):
        for gx in range(COLS):
            x1=GX+gx*CS; y1=GY+gy*CS
            d.rectangle([x1,y1,x1+CS-2,y1+CS-2],outline=(50,50,100),width=1,fill=(15,15,35))
    tx,ty=GX+4*CS+CS//2,GY+2*CS+CS//2
    pts=[]
    for i in range(10):
        ang=math.pi/5*i-math.pi/2; r=38 if i%2==0 else 16
        pts.append((tx+r*math.cos(ang),ty+r*math.sin(ang)))
    d.polygon(pts,fill=YELLOW)

    # エージェント + 吹き出し
    agents_info=[
        (GX+CS//2,     GY+CS//2,     "Worker",  "5.2 EC"),
        (GX+8*CS+CS//2,GY+CS//2,     "Worker",  "4.8 EC"),
        (GX+CS//2,     GY+5*CS+CS//2,"Trader",  "6.1 EC"),
        (GX+8*CS+CS//2,GY+5*CS+CS//2,"Guardian","5.9 EC"),
    ]
    winner_idx = 1  # 4.8 ECが最安
    for i,(ax,ay,role,bid) in enumerate(agents_info):
        is_w = (i==winner_idx)
        draw_character(d, ax, ay, role, size=72, mood="happy" if is_w else "normal")
        bc = GREEN if is_w else (60,60,100)
        label = bid + (" WIN!" if is_w else "")
        speech_bubble(d, ax, ay-50, label, font_r(30), bc)
        if is_w:
            arrow(d, ax, ay+50, tx, ty, GREEN, width=5)

    cx_text(d,"最安値落札 → 報酬支払い",GY+ROWS*CS+60,font_r(46),GRAY)
    progress_bar(d,0.46,GREEN)
    return img


def scene_auction3():
    img=grad_bg(); img=grid_overlay(img); d=ImageDraw.Draw(img)
    tag_box(d,"仕事の仕組み 3/3",110,font(40),PURPLE,fg=(10,10,30))
    cx_text(d,"全取引を台帳に記録",240,font(76))

    headers=["tx_id","from","to","EC","理由"]
    rows=[["a3f2","city","W2","9.5","task_reward"],
          ["a3f3","W2","city","0.5","tax(5%)"],
          ["a3f4","city","W1","8.1","task_reward"]]
    col_widths=[130,130,100,110,220]
    tx0,ty0,row_h=55,390,68
    # ヘッダ
    x=tx0
    for h,cw in zip(headers,col_widths):
        d.rectangle([x,ty0,x+cw,ty0+row_h],fill=(40,40,90),outline=(80,80,140))
        bb=d.textbbox((0,0),h,font=font(30)); tw=bb[2]-bb[0]
        d.text((x+(cw-tw)//2,ty0+18),h,font=font(30),fill=BLUE); x+=cw
    # 行
    for ri,row in enumerate(rows):
        x=tx0; y=ty0+(ri+1)*row_h
        rc = GREEN if ri!=1 else RED
        for ci,(cell,cw) in enumerate(zip(row,col_widths)):
            d.rectangle([x,y,x+cw,y+row_h],fill=(20,20,40),outline=(60,60,100))
            bb=d.textbbox((0,0),cell,font=font_r(26)); tw=bb[2]-bb[0]
            col = rc if ci in (3,4) else WHITE
            d.text((x+(cw-tw)//2,y+18),cell,font=font_r(26),fill=col); x+=cw

    y_after=ty0+4*row_h+50
    for pt,col in [("全取引が永続記録される",WHITE),
                   ("5% が税として都市に還元",YELLOW),
                   ("seed固定で完全再現可能",GREEN)]:
        cx_text(d,"* "+pt,y_after,font_r(42),col); y_after+=66

    # 残った余白にキャラクター
    draw_character_group(img,[
        ((160,1550),"Observer","cool"),
        ((920,1550),"Governor","normal"),
    ], size=110)
    progress_bar(d,0.60,PURPLE)
    return img


def scene_energy():
    img=grad_bg(); img=grid_overlay(img); d=ImageDraw.Draw(img)
    tag_box(d,"経済システム",110,font(42),YELLOW,fg=(10,10,30))
    cx_text(d,"Energy Coin",250,font(88),YELLOW)
    cx_text(d,"エネルギー = 通貨",380,font(64))

    # 大きなコインイラスト
    cx2,cy2=W//2,680; r=140
    d.ellipse([cx2-r,cy2-r,cx2+r,cy2+r],fill=YELLOW,outline=WHITE,width=4)
    d.ellipse([cx2-r+16,cy2-r+16,cx2+r-16,cy2+r-16],outline=(200,150,0),width=3,fill=YELLOW)
    cx_text(d,"EC",cy2-50,font(110),(10,10,30))

    cx_text(d,"1 EC = 1 Wh",870,font(58),WHITE)
    cx_text(d,"エネルギーそのものがお金",960,font_r(44),GRAY)

    # キャラクターをコインの周りに
    draw_character_group(img,[
        ((160, 580),"Worker","happy"),
        ((920, 580),"Trader","happy"),
        ((160, 900),"Guardian","normal"),
        ((920, 900),"Observer","cool"),
        ((540,1150),"Governor","normal"),
    ], size=100)
    progress_bar(d,0.72,YELLOW)
    return img


def scene_kpi():
    img=grad_bg(); img=grid_overlay(img); d=ImageDraw.Draw(img)
    tag_box(d,"シミュレーション結果",110,font(40),GREEN)
    cx_text(d,"100tick の成果",240,font(84))
    items=[
        ("タスク効率",  "95%",  GREEN,  "ほぼ全てのタスクを完了"),
        ("平等性",      "90%",  BLUE,   "格差(Gini)が非常に小さい"),
        ("取引数",      "200+", YELLOW, "全て台帳に自動記録"),
        ("違反対処",    "20件", RED,    "Policy Engineが自動処理"),
    ]
    y=380
    for label,val,col,desc in items:
        d.rounded_rectangle([80,y,W-80,y+128],radius=16,fill=(20,20,50),outline=col,width=2)
        cx_text(d,val,y+10,font(72),col)
        cx_text(d,f"{label} — {desc}",y+88,font_r(34),GRAY)
        y+=148
    # 下にキャラ
    draw_character_group(img,[
        ((200,1720),"Worker","happy"),
        ((540,1750),"Trader","happy"),
        ((880,1720),"Guardian","normal"),
    ], size=95)
    progress_bar(d,0.88,GREEN)
    return img


def scene_cta():
    img=grad_bg((10,5,30),(25,10,60)); img=grid_overlay(img); d=ImageDraw.Draw(img)
    tag_box(d,"お願いがあります！",110,font(42),YELLOW,fg=(10,10,30))
    cx_text(d,"もし面白かったら",260,font(72))

    # 大きなハートボタン
    bx,by=W//2,550; bw,bh=400,120
    d.rounded_rectangle([bx-bw//2,by-bh//2,bx+bw//2,by+bh//2],radius=30,fill=RED,outline=WHITE,width=3)
    cx_text(d,"いいね！",by-30,font(72),(255,255,255))

    # チャンネル登録ボタン
    d.rounded_rectangle([bx-bw//2,700-bh//2,bx+bw//2,700+bh//2],radius=30,fill=(50,50,200),outline=WHITE,width=3)
    cx_text(d,"チャンネル登録！",700-30,font(60),WHITE)

    cx_text(d,"してね！",820,font(72))

    d.line([(120,920),(W-120,920)],fill=(60,60,100),width=2)
    cx_text(d,"次のステップ",980,font(58),BLUE)
    nexts=["Layer1：実機ロボット接続","AWS クラウド移行","Digital Twin 3D化"]
    y=1060
    for n in nexts: cx_text(d,f"-> {n}",y,font_r(44),GRAY); y+=64

    # 全キャラ集合
    draw_character_group(img,[
        ((130,1520),"Worker","happy"),
        ((310,1560),"Guardian","happy"),
        ((540,1520),"Trader","happy"),
        ((770,1560),"Observer","happy"),
        ((950,1520),"Governor","happy"),
    ], size=110)
    # セリフ
    d.text((60,1430),"また",font=font_r(32),fill=GRAY)
    d.text((260,1460),"ね！",font=font_r(32),fill=GRAY)
    d.text((480,1430),"ありがとう！",font=font_r(32),fill=GRAY)
    progress_bar(d,1.0,YELLOW)
    return img


# ── シーン定義 ─────────────────────────────────────────────────
SCENES = [
    {"narration":"自律文明をPythonだけで作ってみた。","fn":scene_hook,        "min_dur":2.5},
    {"narration":"これはHACS。17体のロボットが自律的に仕事をして生活するシミュレーターです。","fn":scene_what_is,"min_dur":4.0},
    {"narration":"タスクが発生すると、ロボットたちが一斉に注目します。","fn":scene_auction1,"min_dur":3.5},
    {"narration":"ロボットが一斉に入札して、最安値を提示したロボットが落札します。","fn":scene_auction2,"min_dur":4.0},
    {"narration":"全ての取引は台帳に自動記録。報酬から5パーセントが税として都市に還元されます。","fn":scene_auction3,"min_dur":4.0},
    {"narration":"通貨はエネルギーコイン。1コインは1ワットアワー。エネルギーそのものがお金です。","fn":scene_energy, "min_dur":3.5},
    {"narration":"100ティック動かした結果、タスク効率95パーセント、平等性90パーセントを達成しました。","fn":scene_kpi,"min_dur":4.5},
    {"narration":"面白かったらいいねとチャンネル登録してね！また次の動画でお会いしましょう！","fn":scene_cta,"min_dur":4.0},
]


def build_video():
    clips = []
    tmp_files = []
    print(f"Voice: {VOICE}")
    print(f"Scenes: {len(SCENES)}")
    for i, sc in enumerate(SCENES):
        print(f"  [{i+1}/{len(SCENES)}] {sc['narration'][:28]}...")
        img = sc["fn"]()
        audio_path = make_audio_fast(sc["narration"])
        tmp_files.append(audio_path)
        audio_clip = AudioFileClip(audio_path)
        duration = max(sc["min_dur"], audio_clip.duration + 0.2)
        video_clip = ImageClip(np.array(img)).with_duration(duration).with_audio(audio_clip)
        clips.append(video_clip)

    print("\nMerging...")
    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(OUT, fps=FPS, codec="libx264", audio_codec="aac", logger=None)
    print(f"Done! --> {OUT}  ({final.duration:.1f}sec)")
    for f in tmp_files:
        try: os.unlink(f)
        except: pass


if __name__ == "__main__":
    build_video()
