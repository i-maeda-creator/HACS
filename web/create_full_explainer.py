"""
HACS Full Explainer — Layer 0〜3 完全解説動画
新UIデザイン: 図解ファースト / 章立て / レイヤーカラーコード
"""
import sys, os, subprocess, tempfile, asyncio, math
sys.path.insert(0, "..")

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import edge_tts
from moviepy import *

W, H  = 1080, 1920
FPS   = 30
OUT   = "hacs_full_explainer.mp4"
SPEED = 1.75   # やや遅め：内容が多いので聞き取りやすく
VOICE = "ja-JP-NanamiNeural"

FFMPEG = None
try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except: pass

# ═══════════════════════════════════════════════════════════════
# 新カラーパレット
# ═══════════════════════════════════════════════════════════════
BG      = (4,  8, 24)       # 深い青黒
BG2     = (8, 14, 38)
L0_C    = ( 0, 230, 118)    # Layer0 = エメラルドグリーン
L1_C    = (255, 109,   0)   # Layer1 = バーントオレンジ
L2_C    = (  0, 176, 255)   # Layer2 = エレクトリックシアン
L3_C    = (170,   0, 255)   # Layer3 = ビビッドパープル
GOLD    = (255, 214,   0)   # アクセントゴールド
WHITE   = (232, 234, 246)   # ソフトホワイト
GRAY    = (120, 130, 160)
DARK    = ( 18,  22,  50)   # パネル背景
PANEL   = ( 14,  18,  42)

LAYER_META = {
    0: {"color": L0_C, "label": "Layer 0", "name": "Simulation"},
    1: {"color": L1_C, "label": "Layer 1", "name": "Physical"},
    2: {"color": L2_C, "label": "Layer 2", "name": "Communication"},
    3: {"color": L3_C, "label": "Layer 3", "name": "City OS"},
}

# ═══════════════════════════════════════════════════════════════
# フォント
# ═══════════════════════════════════════════════════════════════
def F(sz):
    for p in ["C:/Windows/Fonts/YuGothB.ttc","C:/Windows/Fonts/meiryob.ttc","C:/Windows/Fonts/msgothic.ttc"]:
        if os.path.exists(p): return ImageFont.truetype(p, sz)
    return ImageFont.load_default()

def Fr(sz):
    for p in ["C:/Windows/Fonts/YuGothR.ttc","C:/Windows/Fonts/meiryo.ttc","C:/Windows/Fonts/msgothic.ttc"]:
        if os.path.exists(p): return ImageFont.truetype(p, sz)
    return ImageFont.load_default()

# ═══════════════════════════════════════════════════════════════
# 描画ユーティリティ
# ═══════════════════════════════════════════════════════════════
def base_img(layer_n=None):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # 細かいドットグリッド
    for x in range(0, W, 48):
        for y in range(0, H, 48):
            d.ellipse([x-1,y-1,x+1,y+1], fill=(20,28,60))
    return img

def draw_hex_accent(d, x, y, r, color, alpha=60):
    pts = [(x + r*math.cos(math.pi/3*i - math.pi/6),
            y + r*math.sin(math.pi/3*i - math.pi/6)) for i in range(6)]
    # 薄い六角形の枠
    c = tuple(int(v * alpha/255) for v in color)
    d.polygon(pts, outline=c, fill=None)

def cx(d, text, y, fnt, color=WHITE, shadow=True):
    bb = d.textbbox((0,0), text, font=fnt)
    tw = bb[2]-bb[0]; x = (W-tw)//2
    if shadow:
        d.text((x+2,y+2), text, font=fnt, fill=(0,0,0))
    d.text((x,y), text, font=fnt, fill=color)

def lx(d, text, x, y, fnt, color=WHITE):
    d.text((x, y), text, font=fnt, fill=color)

def badge(d, text, x, y, color, size=32):
    fnt = F(size)
    bb = d.textbbox((0,0), text, font=fnt)
    tw,th = bb[2]-bb[0], bb[3]-bb[1]
    pad = 12
    d.rounded_rectangle([x, y, x+tw+pad*2, y+th+pad*2], radius=8,
                         fill=tuple(int(v*0.25) for v in color), outline=color, width=2)
    d.text((x+pad, y+pad), text, font=fnt, fill=color)
    return tw + pad*2, th + pad*2

def panel(d, x1, y1, x2, y2, color=None, title=None):
    d.rounded_rectangle([x1,y1,x2,y2], radius=12, fill=PANEL,
                         outline=color or (40,50,90), width=2)
    if title and color:
        fnt = F(28)
        bb = d.textbbox((0,0), title, font=fnt)
        tw = bb[2]-bb[0]
        d.rounded_rectangle([x1,y1,x1+tw+24,y1+44], radius=8,
                             fill=tuple(int(v*0.35) for v in color))
        d.text((x1+12, y1+10), title, font=fnt, fill=color)

def arrow_h(d, x1, y, x2, color, width=4):
    d.line([(x1,y),(x2,y)], fill=color, width=width)
    sz = 14
    d.polygon([(x2,y),(x2-sz,y-sz//2),(x2-sz,y+sz//2)], fill=color)

def arrow_v(d, x, y1, y2, color, width=4):
    d.line([(x,y1),(x,y2)], fill=color, width=width)
    sz = 14
    d.polygon([(x,y2),(x-sz//2,y2-sz),(x+sz//2,y2-sz)], fill=color)

def progress(d, pct, color):
    y = H-8
    d.rectangle([0,y-4,W,y+4], fill=(20,24,50))
    d.rectangle([0,y-4,int(W*pct),y+4], fill=color)

def chapter_tag(d, num, text, color):
    """左上に章番号タグ"""
    fnt_n = F(26); fnt_t = Fr(28)
    # 番号
    d.rounded_rectangle([24,24,76,72], radius=6,
                         fill=tuple(int(v*0.3) for v in color), outline=color, width=2)
    bb = d.textbbox((0,0), str(num), font=fnt_n)
    d.text((50-(bb[2]-bb[0])//2, 36), str(num), font=fnt_n, fill=color)
    d.text((86, 36), text, font=fnt_t, fill=GRAY)

def draw_agent(d, cx2, cy, role, sz=70):
    cmap = {"Worker":L0_C,"Guardian":(255,80,80),"Trader":GOLD,
            "Observer":L3_C,"Governor":(200,120,60)}
    c = cmap.get(role, WHITE)
    dk = tuple(max(0,v-50) for v in c)
    # 体
    d.rounded_rectangle([cx2-sz//2,cy-sz//4,cx2+sz//2,cy+sz//2],
                         radius=sz//6, fill=c, outline=WHITE, width=2)
    # 頭
    d.ellipse([cx2-sz//2+4,cy-sz-sz//4,cx2+sz//2-4,cy-sz//4+2],
              fill=c, outline=WHITE, width=2)
    # 目
    ey = cy - sz*3//4; es = sz//9
    d.ellipse([cx2-sz//4-es,ey-es,cx2-sz//4+es,ey+es], fill=dk)
    d.ellipse([cx2+sz//4-es,ey-es,cx2+sz//4+es,ey+es], fill=dk)
    # 足
    d.rounded_rectangle([cx2-sz//3,cy+sz//2,cx2-sz//10,cy+sz//2+sz//3],
                         radius=5, fill=dk, outline=WHITE, width=1)
    d.rounded_rectangle([cx2+sz//10,cy+sz//2,cx2+sz//3,cy+sz//2+sz//3],
                         radius=5, fill=dk, outline=WHITE, width=1)

# ═══════════════════════════════════════════════════════════════
# シーン
# ═══════════════════════════════════════════════════════════════

def s_title():
    """タイトルカード"""
    img = base_img(); d = ImageDraw.Draw(img)
    # 背景六角形装飾
    for hx,hy,hr,col in [(200,400,180,L0_C),(880,600,150,L2_C),
                          (150,1100,120,L1_C),(950,1200,160,L3_C)]:
        draw_hex_accent(d, hx, hy, hr, col, alpha=30)

    # メインタイトル
    cx(d, "家庭で", 260, F(110))
    cx(d, "自律文明を", 390, F(110))
    cx(d, "作ってみた", 520, F(110), GOLD)

    # サブタイトル
    cx(d, "Layer 0 → 3  完全解説", 670, Fr(46), GRAY)

    # レイヤーバッジ横並び
    badges = [(L0_C,"L0"),(L1_C,"L1"),(L2_C,"L2"),(L3_C,"L3")]
    bw = 200; total = bw*4 + 16*3; sx = (W-total)//2
    for i,(col,lbl) in enumerate(badges):
        bx = sx + i*(bw+16)
        d.rounded_rectangle([bx,800,bx+bw,860], radius=10,
                             fill=tuple(int(v*0.2) for v in col), outline=col, width=2)
        bb = d.textbbox((0,0),lbl,font=F(36)); tw=bb[2]-bb[0]
        d.text((bx+(bw-tw)//2, 812), lbl, font=F(36), fill=col)

    # キャラクター5体
    roles = ["Worker","Guardian","Trader","Observer","Governor"]
    for i,role in enumerate(roles):
        draw_agent(d, 130+i*210, 1150, role, sz=95)
    # ラベル
    for i,role in enumerate(roles):
        bb=d.textbbox((0,0),role,font=Fr(24)); tw=bb[2]-bb[0]
        d.text((130+i*210-tw//2, 1270), role, font=Fr(24), fill=GRAY)

    cx(d, "HACS — Home Autonomous Civilization System", 1380, Fr(32), GRAY)
    progress(d, 0.0, WHITE)
    return img


def s_overview():
    """全体アーキテクチャ図"""
    img = base_img(); d = ImageDraw.Draw(img)
    chapter_tag(d, 1, "全体像", WHITE)

    cx(d, "4層で構成される", 100, F(72))
    cx(d, "文明 OS", 190, F(90), GOLD)

    # 縦積みレイヤー図
    layers = [
        (L3_C, "Layer 3", "City OS", "都市の意思決定・政策・AI統合"),
        (L2_C, "Layer 2", "Communication", "MQTT通信・イベントバス・神経系"),
        (L1_C, "Layer 1", "Physical World", "実機ロボット・センサー・ドローン"),
        (L0_C, "Layer 0", "Simulation", "仮想シミュレーター・検証環境"),
    ]
    y = 340; lh = 170
    for col,lbl,name,desc in layers:
        d.rounded_rectangle([60,y,W-60,y+lh-16], radius=14,
                             fill=tuple(int(v*0.12) for v in col), outline=col, width=2)
        # レイヤー番号バー
        d.rounded_rectangle([60,y,200,y+lh-16], radius=14,
                             fill=tuple(int(v*0.25) for v in col))
        bb=d.textbbox((0,0),lbl,font=F(34)); tw=bb[2]-bb[0]
        d.text((130-tw//2, y+20), lbl, font=F(34), fill=col)
        bb2=d.textbbox((0,0),name,font=F(28)); tw2=bb2[2]-bb2[0]
        d.text((130-tw2//2, y+62), name, font=F(28), fill=WHITE)
        d.text((220, y+18), desc, font=Fr(34), fill=WHITE)
        if y < 340+lh*3:
            arrow_v(d, W//2, y+lh-16, y+lh, col, width=3)
        y += lh

    # 右サイド: 完成度
    status = [(L0_C,"完成","Sim+Safety+Policy"), (L2_C,"完成","MQTT+LiveDash"),
              (L1_C,"設計中","実機接続待ち"), (L3_C,"設計中","City OS構築中")]
    sy = 340
    for col,st,detail in status:
        sc = (0,200,80) if st=="完成" else (200,120,0)
        bb=d.textbbox((0,0),st,font=F(26)); tw=bb[2]-bb[0]
        d.rounded_rectangle([W-160,sy+30,W-60,sy+80], radius=8,
                             fill=tuple(int(v*0.3) for v in sc), outline=sc, width=1)
        d.text((W-110-tw//2, sy+42), st, font=F(26), fill=sc)
        sy += lh

    progress(d, 0.07, WHITE)
    return img


def s_l0_world():
    """Layer0: ワールドとエージェント"""
    img = base_img(); d = ImageDraw.Draw(img)
    chapter_tag(d, 2, "Layer 0 — Simulation", L0_C)

    cx(d, "仮想世界に", 100, F(78))
    cx(d, "17体のロボットが生きる", 190, F(70), L0_C)

    # グリッドマップ（20×20）の小さい表現
    GX,GY = 60,320; CS=44; COLS=18; ROWS=11
    for gy in range(ROWS):
        for gx in range(COLS):
            x1=GX+gx*CS; y1=GY+gy*CS
            # 壁
            is_wall = (gx==0 or gy==0 or gx==COLS-1 or gy==ROWS-1 or
                       (3<=gx<=5 and 3<=gy<=4) or (10<=gx<=12 and 6<=gy<=8))
            fill = (25,35,70) if is_wall else (14,18,42)
            d.rectangle([x1+1,y1+1,x1+CS-1,y1+CS-1], fill=fill)
    # 充電スポット
    for (cgx,cgy) in [(2,9),(15,9),(8,1)]:
        x1=GX+cgx*CS; y1=GY+cgy*CS
        d.rectangle([x1+4,y1+4,x1+CS-4,y1+CS-4], fill=(0,60,40))
        d.text((x1+8,y1+8),"⚡",font=Fr(22),fill=L0_C)

    # エージェント配置
    agents_pos = [(2,2,"W"),(5,5,"W"),(10,3,"W"),(14,8,"W"),(7,8,"W"),
                  (15,2,"G"),(3,9,"G"),(8,6,"T"),(13,5,"T"),(3,8,"O"),
                  (9,9,"V")]
    agent_colors = {"W":L0_C,"G":(255,80,80),"T":GOLD,"O":L3_C,"V":(180,100,50)}
    for (ax,ay,at) in agents_pos:
        cx2=GX+ax*CS+CS//2; cy2=GY+ay*CS+CS//2
        col=agent_colors[at]
        d.ellipse([cx2-10,cy2-10,cx2+10,cy2+10], fill=col)

    # 凡例（右下）
    legend_x = GX+COLS*CS+20
    for i,(role,short,col) in enumerate([("Worker","W",L0_C),("Guardian","G",(255,80,80)),
                                           ("Trader","T",GOLD),("Observer","O",L3_C),("Governor","V",(180,100,50))]):
        ly = GY+i*52
        d.ellipse([legend_x,ly+18,legend_x+20,ly+38], fill=col)
        d.text((legend_x+28,ly+14), role, font=Fr(28), fill=WHITE)
        counts = {"W":10,"G":2,"T":2,"O":2,"V":1}
        d.text((legend_x+28,ly+44), f"{counts[short]}体", font=Fr(22), fill=GRAY)

    # 下部: 5種エージェント詳細
    panel(d, 60,810,W-60,1150, L0_C, "5種のエージェント")
    roles_info = [
        ("Worker",  L0_C,  "仕事をこなす\n主力部隊"),
        ("Guardian",(255,80,80),"安全を守る\n警備ロボ"),
        ("Trader",  GOLD,  "資源を売買\n商人AI"),
        ("Observer",L3_C,  "情報収集\nセンサー役"),
        ("Governor",(180,100,50),"政策を決める\n統治者"),
    ]
    rx = 90
    for role,col,desc in roles_info:
        draw_agent(d, rx+40, 970, role, sz=58)
        lines = desc.split("\n")
        d.text((rx,1060), lines[0], font=Fr(22), fill=col)
        d.text((rx,1086), lines[1], font=Fr(20), fill=GRAY)
        rx += 196

    # stats
    stats = [("20×20","グリッド世界"),("17体","エージェント"),("100 tick","シミュレーション"),("615件","総イベント数")]
    sy = 1200
    for i,(val,label) in enumerate(stats):
        sx2 = 60 + i*250
        panel(d, sx2,sy,sx2+230,sy+140, L0_C)
        cx_val_bb = d.textbbox((0,0),val,font=F(52)); vw=cx_val_bb[2]-cx_val_bb[0]
        d.text((sx2+(230-vw)//2, sy+14), val, font=F(52), fill=L0_C)
        lb_bb = d.textbbox((0,0),label,font=Fr(26)); lw=lb_bb[2]-lb_bb[0]
        d.text((sx2+(230-lw)//2, sy+80), label, font=Fr(26), fill=GRAY)

    progress(d, 0.14, L0_C)
    return img


def s_l0_auction():
    """Layer0: オークション経済"""
    img = base_img(); d = ImageDraw.Draw(img)
    chapter_tag(d, 3, "Layer 0 — Economy", L0_C)

    cx(d, "仕事はオークションで決まる", 100, F(64))
    cx(d, "入札 → 最安値が落札", 180, F(56), L0_C)

    # フロー図（横矢印）
    steps = [
        ("タスク\n発生",GOLD,"⭐"),
        ("全員\n入札",L0_C,"💰"),
        ("最安値\n落札",L2_C,"🏆"),
        ("移動\n→作業",L1_C,"🤖"),
        ("報酬\n受取",GOLD,"💎"),
    ]
    SW = 160; SH = 140; SY = 290; GAP = 40
    total_w = len(steps)*SW + (len(steps)-1)*GAP
    sx = (W-total_w)//2
    for i,(label,col,icon) in enumerate(steps):
        bx = sx + i*(SW+GAP)
        d.rounded_rectangle([bx,SY,bx+SW,SY+SH], radius=12,
                             fill=tuple(int(v*0.2) for v in col), outline=col, width=2)
        lines = label.split("\n")
        d.text((bx+(SW-d.textbbox((0,0),lines[0],font=F(28))[2])//2, SY+16),
               lines[0], font=F(28), fill=col)
        d.text((bx+(SW-d.textbbox((0,0),lines[1],font=F(28))[2])//2, SY+52),
               lines[1], font=F(28), fill=col)
        if i < len(steps)-1:
            arrow_h(d, bx+SW+4, SY+SH//2, bx+SW+GAP-4, col, width=3)

    # 入札シーン詳細パネル
    panel(d, 60,500,W-60,940, L0_C, "入札の仕組み")
    # タスク
    tx,ty = 200,620
    d.rounded_rectangle([tx-60,ty-30,tx+60,ty+30], radius=10, fill=(50,50,10), outline=GOLD, width=2)
    cx(d, "Task #42", ty-16, Fr(30), GOLD)
    cx(d, "報酬: 12.5 EC", ty+18, Fr(26), GRAY)

    # 4エージェントの入札
    bids = [("W1","5.2 EC",False),("W2","4.8 EC",True),("G1","5.9 EC",False),("T1","6.1 EC",False)]
    bx_list = [130,370,610,850]; by=730
    for i,(aid,bid,winner) in enumerate(bids):
        col = L0_C if not winner else GOLD
        border = GOLD if winner else (40,50,90)
        bxp = bx_list[i]
        draw_agent(d, bxp, by, "Worker" if aid[0]=="W" else "Guardian" if aid[0]=="G" else "Trader", sz=52)
        d.rounded_rectangle([bxp-55,by+62,bxp+55,by+96], radius=6,
                             fill=tuple(int(v*0.3) for v in col), outline=col, width=2)
        bb=d.textbbox((0,0),bid,font=F(24)); tw=bb[2]-bb[0]
        d.text((bxp-tw//2, by+68), bid, font=F(24), fill=col)
        if winner:
            d.text((bxp-32,by+100), "WIN!  落札", font=F(22), fill=GOLD)
            # W2 → タスクへ矢印
            arrow_v(d, bxp, ty+30, by-60, GOLD, width=3)

    # 台帳
    panel(d, 60,980,W-60,1280, L2_C, "取引台帳（自動記録）")
    rows=[("tx_a3f2","city","W2","9.5 EC","task_reward"),
          ("tx_a3f3","W2","city","0.5 EC","tax 5%"),
          ("tx_a3f4","city","W1","8.1 EC","task_reward")]
    cols_x=[80,230,380,520,680]
    headers=["tx_id","from","to","金額","理由"]
    ty2=1010
    for j,h in enumerate(headers):
        d.text((cols_x[j],ty2),h,font=Fr(24),fill=L2_C)
    ty2+=36
    d.line([(70,ty2),(W-70,ty2)],fill=(40,50,90),width=1); ty2+=8
    for tx_id,frm,to,amt,reason in rows:
        col = L0_C if reason=="task_reward" else (200,80,80)
        for j,val in enumerate([tx_id,frm,to,amt,reason]):
            d.text((cols_x[j],ty2),val,font=Fr(26),fill=col if j>=3 else WHITE)
        ty2+=52

    # EC説明
    cx(d, "1 EC = 1 Wh　エネルギー = 通貨", 1330, Fr(38), GOLD)
    cx(d, "全取引は永続記録 / 5%が都市へ税還元", 1380, Fr(34), GRAY)

    progress(d, 0.22, L0_C)
    return img


def s_l0_safety():
    """Layer0: Safety Gate + Policy Engine"""
    img = base_img(); d = ImageDraw.Draw(img)
    chapter_tag(d, 4, "Layer 0 — Safety & Policy", L0_C)

    cx(d, "文明には「憲法」がある", 100, F(70))
    cx(d, "Safety > Economy > Efficiency", 190, F(50), (255,100,100))

    # 優先順位ピラミッド
    PX,PY = W//2, 460; lv_h=90
    levels = [
        ("Safety", (255,80,80), "人・機械の安全最優先"),
        ("Stability", GOLD, "経済・エネルギーの安定"),
        ("Economy", L0_C, "効率的なタスク・収益"),
        ("Efficiency", GRAY, "速さ・コスト最適化"),
    ]
    for i,(name,col,desc) in enumerate(levels):
        w2 = 180 + i*100
        d.rounded_rectangle([PX-w2,PY+i*lv_h,PX+w2,PY+(i+1)*lv_h-4],
                             radius=6, fill=tuple(int(v*0.2) for v in col), outline=col, width=2)
        cx(d, name, PY+i*lv_h+16, F(36), col)
        cx(d, desc, PY+i*lv_h+54, Fr(24), GRAY)

    # Hard / Soft 説明
    panel(d, 60,870,490,1160, (255,80,80), "Hard Constraint")
    hard_rules = ["エネルギー切れ → 即停止","Guardian 夜間 → 移動禁止","緊急停止 → 全Agent停止"]
    for i,r in enumerate(hard_rules):
        d.text((80,920+i*66), "✕  "+r, font=Fr(28), fill=(255,130,130))

    panel(d, 530,870,W-60,1160, GOLD, "Soft Constraint")
    soft_rules = ["残高不足 → ペナルティ-0.5EC","効率低下 → 優先度下げ","夜間作業 → コスト増加"]
    for i,r in enumerate(soft_rules):
        d.text((550,920+i*66), "△  "+r, font=Fr(28), fill=GOLD)

    # SafetyGate フロー
    panel(d, 60,1200,W-60,1480, (255,80,80), "Safety Gate の動き方")
    flow = ["毎 tick 先頭に実行（Policy より前）",
            "違反検知 → Agent を即停止",
            "SafetyTriggered イベントを発行",
            "Policy Engine はその後に動く"]
    for i,f in enumerate(flow):
        icon = "🛡" if i==0 else "⚡" if i==1 else "📡" if i==2 else "📜"
        d.text((80,1230+i*60), f"{i+1}.  {f}", font=Fr(30), fill=WHITE)

    progress(d, 0.30, (255,80,80))
    return img


def s_l1():
    """Layer1: 物理世界"""
    img = base_img(); d = ImageDraw.Draw(img)
    chapter_tag(d, 5, "Layer 1 — Physical World", L1_C)

    cx(d, "Layer0を", 100, F(88))
    cx(d, "現実世界へ接続する", 200, F(72), L1_C)

    # Layer0 vs Layer1 比較
    panel(d, 60,320,490,820, L0_C, "Layer 0（仮想）")
    l0_items = ["Python Simulator","Agent クラス（仮想）","Grid World","仮想エネルギー","ログ・再現性"]
    for i,it in enumerate(l0_items):
        d.text((80,380+i*72), "→  "+it, font=Fr(30), fill=L0_C)

    panel(d, 530,320,W-60,820, L1_C, "Layer 1（実機）")
    l1_items = ["Raspberry Pi / ESP32","実ロボット / ドローン","物理空間（家の中）","バッテリー(Wh)","センサー・カメラ"]
    for i,it in enumerate(l1_items):
        d.text((550,380+i*72), "→  "+it, font=Fr(30), fill=L1_C)

    # 真ん中の矢印
    arrow_h(d, 490, 570, 530, WHITE, width=3)
    bb=d.textbbox((0,0),"共通\nスキーマ",font=Fr(20))
    d.text((498,548),"共通\nスキーマ",font=Fr(18),fill=GRAY)

    # 共有スキーマ強調
    panel(d, 60,860,W-60,1100, GOLD, "Layer0 と Layer1 が完全共有するもの")
    shared = ["Event Schema  (イベントの型定義)",
              "Command Schema (命令の型定義)",
              "State Snapshot (状態の型定義)",
              "Policy Rules  (ルール・制約)"]
    for i,s in enumerate(shared):
        d.text((80,910+i*50), "✓  "+s, font=Fr(30), fill=GOLD)

    cx(d, "違うのはハードウェアだけ", 1140, F(52), WHITE)
    cx(d, "コードは同じ → そのまま実機へ移植可能", 1210, Fr(38), GRAY)

    # 将来デバイス
    panel(d, 60,1280,W-60,1540, L1_C, "対応予定デバイス")
    devices=[("Raspberry Pi","エッジ処理"),("ESP32","センサー/通信"),("自走ロボット","Worker実機"),("ドローン","空中Guardian")]
    dx=90
    for dev,role in devices:
        d.rounded_rectangle([dx,1320,dx+210,1520],radius=10,
                             fill=tuple(int(v*0.15) for v in L1_C),outline=L1_C,width=1)
        bb=d.textbbox((0,0),dev,font=F(28)); tw=bb[2]-bb[0]
        d.text((dx+(210-tw)//2,1340),dev,font=F(28),fill=L1_C)
        bb2=d.textbbox((0,0),role,font=Fr(24)); tw2=bb2[2]-bb2[0]
        d.text((dx+(210-tw2)//2,1382),role,font=Fr(24),fill=GRAY)
        dx+=242

    progress(d, 0.40, L1_C)
    return img


def s_l2_concept():
    """Layer2: MQTT概念"""
    img = base_img(); d = ImageDraw.Draw(img)
    chapter_tag(d, 6, "Layer 2 — Communication", L2_C)

    cx(d, "全てのデータは", 100, F(80))
    cx(d, "Event Bus を経由する", 190, F(74), L2_C)
    cx(d, "直接通信は禁止", 280, Fr(44), GRAY)

    # MQTT図解: Broker中心
    BX,BY = W//2, 780
    # Broker
    d.ellipse([BX-100,BY-100,BX+100,BY+100], fill=(10,20,60), outline=L2_C, width=4)
    cx(d, "MQTT", BY-36, F(48), L2_C)
    cx(d, "Broker", BY+16, Fr(32), L2_C)

    # 接続ノード
    nodes = [
        (200,460,"Simulator\n(Layer0)",L0_C,"Publisher"),
        (880,460,"City OS\n(Layer3)",L3_C,"Publisher"),
        (130,820,"Dashboard\n(Browser)",L2_C,"Subscriber"),
        (950,820,"Home\nAssistant",L1_C,"Subscriber"),
        (200,1150,"Logger\n(Replay)",GOLD,"Subscriber"),
        (880,1150,"Safety\nMonitor",(255,80,80),"Subscriber"),
    ]
    for nx,ny,label,col,role in nodes:
        d.rounded_rectangle([nx-90,ny-44,nx+90,ny+44],radius=10,
                             fill=tuple(int(v*0.18) for v in col),outline=col,width=2)
        lines=label.split("\n")
        d.text((nx-d.textbbox((0,0),lines[0],font=F(26))[2]//2,ny-38),lines[0],font=F(26),fill=col)
        d.text((nx-d.textbbox((0,0),lines[1] if len(lines)>1 else "",font=Fr(22))[2]//2,ny+2),
               lines[1] if len(lines)>1 else "",font=Fr(22),fill=GRAY)
        rb=d.textbbox((0,0),role,font=Fr(18))
        d.text((nx-(rb[2]-rb[0])//2,ny+26),role,font=Fr(18),fill=GRAY)
        # ブローカーへの矢印
        dx2=BX-nx; dy2=BY-ny; dist=math.sqrt(dx2*dx2+dy2*dy2)
        if dist>0:
            nx2=int(nx+dx2*0.5); ny2=int(ny+dy2*0.5)
            d.line([(nx,ny),(nx2,ny2)],fill=tuple(int(v*0.5) for v in col),width=2)

    # Topic階層
    panel(d, 60,1300,W-60,1560, L2_C, "MQTT Topic 階層")
    topics_col=[
        ("city/task/new",L0_C),("city/task/bid",L0_C),("city/task/assigned",L0_C),
        ("agent/{id}/event",L2_C),("safety/alert",(255,80,80)),
        ("energy/usage",GOLD),("network/health",GRAY),
    ]
    tx2=80; ty3=1340
    for i,(t,c) in enumerate(topics_col):
        col2=c if i<4 else c
        d.text((tx2+(i%4)*250, ty3+(i//4)*56), t, font=Fr(24), fill=col2)

    progress(d, 0.50, L2_C)
    return img


def s_l2_realtime():
    """Layer2: リアルタイム実証"""
    img = base_img(); d = ImageDraw.Draw(img)
    chapter_tag(d, 7, "Layer 2 — Live Demo", L2_C)

    cx(d, "実際に流れた", 100, F(80))
    cx(d, "イベントストリーム", 190, F(76), L2_C)

    # 実際のイベントシーケンス
    events_log = [
        ("tick 1",  "city/policy/update",   "PolicyChanged",  "Guardian G1 夜間制限", (255,100,80)),
        ("tick 5",  "city/task/new",         "TaskCreated",    "タスク #42 発生 (x=8,y=5)", L0_C),
        ("tick 5",  "city/task/bid",         "BidSubmitted",   "W1: 5.2 EC 入札", L0_C),
        ("tick 5",  "city/task/bid",         "BidSubmitted",   "W2: 4.8 EC 入札 (最安)", L0_C),
        ("tick 5",  "city/task/bid",         "BidSubmitted",   "G1: 5.9 EC 入札", L0_C),
        ("tick 5",  "city/task/assigned",    "TaskAssigned",   "W2 落札 → 移動開始", L2_C),
        ("tick 6",  "agent/simulator/event", "AgentMoved",     "W2 (3,3) → (4,4)", GOLD),
        ("tick 7",  "agent/simulator/event", "AgentMoved",     "W2 (4,4) → (5,5)", GOLD),
        ("tick 8",  "city/task/completed",   "TaskCompleted",  "W2 完了 → 報酬 9.5 EC", L0_C),
    ]
    y=300
    for tick,topic,etype,detail,col in events_log:
        d.rounded_rectangle([60,y,W-60,y+78],radius=8,
                             fill=tuple(int(v*0.10) for v in col),outline=tuple(int(v*0.4) for v in col),width=1)
        d.text((76,y+8),tick,font=Fr(22),fill=GRAY)
        d.text((170,y+8),topic,font=Fr(26),fill=col)
        d.text((76,y+44),etype,font=F(26),fill=WHITE)
        d.text((300,y+44),detail,font=Fr(26),fill=GRAY)
        y+=90

    # 結果サマリー
    panel(d, 60,1130,W-60,1300, L2_C, "テスト結果")
    results=[("Published","23件",L2_C),("Received","23件",L0_C),("Loss率","0%",GOLD)]
    rx2=100
    for label,val,col in results:
        d.text((rx2,1170),label,font=Fr(30),fill=GRAY)
        d.text((rx2,1210),val,font=F(52),fill=col)
        rx2+=320

    # Mosquitto
    panel(d, 60,1340,W-60,1540, GRAY, "使用技術")
    d.text((80,1370),"Mosquitto 2.1.2  — MQTT Broker (ローカル・無料)",font=Fr(30),fill=WHITE)
    d.text((80,1420),"paho-mqtt  — Python MQTT クライアント",font=Fr(30),fill=WHITE)
    d.text((80,1470),"WebSocket (port 9001)  — ブラウザから直接接続",font=Fr(30),fill=WHITE)

    progress(d, 0.60, L2_C)
    return img


def s_l3_overview():
    """Layer3: City OS概要"""
    img = base_img(); d = ImageDraw.Draw(img)
    chapter_tag(d, 8, "Layer 3 — City OS", L3_C)

    cx(d, "都市OS = 文明の頭脳", 100, F(80))
    cx(d, "全レイヤーを統合制御する", 200, F(62), L3_C)

    # 10サブモジュール（2列5行）
    modules = [
        ("3-1","State Mgmt","都市状態を一元管理",L3_C),
        ("3-2","Event Orch","イベントを処理・変換",(180,50,255)),
        ("3-3","Command Dispatch","Agentへ命令送信",(130,0,200)),
        ("3-4","Policy Engine","文明の憲法・安全制御",(255,80,80)),
        ("3-5","Task Scheduler","タスク市場を統括",GOLD),
        ("3-6","Agent Registry","全Agent の戸籍管理",L1_C),
        ("3-7","Workflow Engine","イベント連鎖管理",L0_C),
        ("3-8","Alert System","危機管理・緊急対応",(255,80,80)),
        ("3-9","Observability","全ログ・メトリクス",L2_C),
        ("3-10","Replay Bridge","Layer0と同期・再現",L0_C),
    ]
    for i,( num,name,desc,col) in enumerate(modules):
        row,c2 = i//2, i%2
        bx2 = 60 + c2*510
        by2 = 320 + row*192
        d.rounded_rectangle([bx2,by2,bx2+490,by2+176],radius=10,
                             fill=tuple(int(v*0.12) for v in col),outline=col,width=2)
        d.rounded_rectangle([bx2,by2,bx2+72,by2+176],radius=10,
                             fill=tuple(int(v*0.25) for v in col))
        bb=d.textbbox((0,0),num,font=F(26))
        d.text((bx2+36-(bb[2]-bb[0])//2,by2+20),num,font=F(26),fill=col)
        d.text((bx2+84,by2+16),name,font=F(34),fill=WHITE)
        d.text((bx2+84,by2+60),desc,font=Fr(26),fill=GRAY)

    # Emergency Level
    panel(d, 60,1300,W-60,1520, (255,80,80), "緊急レベル")
    levels=[("L0 Normal","通常運転",L0_C),("L1 Warning","警告",GOLD),
            ("L2 Critical","重大",L1_C),("L3 Emergency","緊急停止",(255,60,60))]
    lx2=80
    for lv,name,col in levels:
        d.rounded_rectangle([lx2,1330,lx2+220,1510],radius=8,
                             fill=tuple(int(v*0.2) for v in col),outline=col,width=2)
        d.text((lx2+8,1348),lv,font=F(24),fill=col)
        bb=d.textbbox((0,0),name,font=Fr(28)); tw=bb[2]-bb[0]
        d.text((lx2+(220-tw)//2,1400),name,font=Fr(28),fill=WHITE)
        lx2+=248

    progress(d, 0.70, L3_C)
    return img


def s_l3_ai():
    """Layer3: AI統合思想"""
    img = base_img(); d = ImageDraw.Draw(img)
    chapter_tag(d, 9, "Layer 3 — AI Safety Design", L3_C)

    cx(d, "AIは提案するだけ", 100, F(82))
    cx(d, "実行権限は渡さない", 190, F(78), (255,100,100))

    # AI→Policy→Execution フロー
    flow_items = [
        (L3_C,  "AI / LLM",      "予測・最適化・提案"),
        (GOLD,  "Proposal",      "提案として出力（未検証）"),
        ((255,80,80), "Policy Engine","安全・制約チェック"),
        (L2_C,  "City OS",       "承認された命令のみ実行"),
        (L1_C,  "Robot / Device","物理世界で実行"),
    ]
    FX=W//2; FY=340; FH=120; GAP=20
    for i,(col,title,desc) in enumerate(flow_items):
        fy=FY+i*(FH+GAP)
        d.rounded_rectangle([FX-340,fy,FX+340,fy+FH],radius=12,
                             fill=tuple(int(v*0.18) for v in col),outline=col,width=2)
        cx(d, title, fy+14, F(40), col)
        cx(d, desc,  fy+62, Fr(28), GRAY)
        if i < len(flow_items)-1:
            arrow_v(d, FX, fy+FH, fy+FH+GAP, col, width=4)

    # 禁止事項
    panel(d, 60,1120,W-60,1380, (255,80,80), "AIがやってはいけないこと")
    forbidden=["直接 Actuator（モーター）を制御する",
               "Safety Constraint を上書き・無視する",
               "Policy Gate を通らずに Command を発行する"]
    for i,f in enumerate(forbidden):
        d.text((80,1160+i*68), "✕  "+f, font=Fr(30), fill=(255,120,120))

    # 許可事項
    panel(d, 60,1420,W-60,1620, L3_C, "AIができること")
    allowed=["タスクの優先順位を提案する","エネルギー最適化プランを提案する","異常パターンを検知・警告する"]
    for i,a in enumerate(allowed):
        d.text((80,1450+i*56), "✓  "+a, font=Fr(30), fill=L3_C)

    progress(d, 0.82, L3_C)
    return img


def s_fullflow():
    """全体フロー図"""
    img = base_img(); d = ImageDraw.Draw(img)
    chapter_tag(d, 10, "まとめ — 全体フロー", WHITE)

    cx(d, "1つのイベントが", 100, F(74))
    cx(d, "文明全体を動かす", 190, F(78), GOLD)

    # 「タスク完了」のフルフロー
    cx(d, "例: Worker がタスクを完了する流れ", 310, Fr(36), GRAY)

    full_flow = [
        (L0_C,  "Layer0","Simulator: TaskCompleted イベント生成"),
        (L2_C,  "Layer2","MQTT: city/task/completed トピックへ発行"),
        (L3_C,  "Layer3","City OS: イベント受信 → State更新"),
        (L3_C,  "Layer3","Policy Engine: 報酬計算 → 検証"),
        (L3_C,  "Layer3","Command Dispatch: next_task Command発行"),
        (L2_C,  "Layer2","MQTT: agent/W2/command へ配信"),
        (L0_C,  "Layer0","Simulator: 次タスクへ移動開始"),
        (L1_C,  "Layer1","（将来）実機ロボットが実際に動く"),
    ]
    y=380
    for col,layer,desc in full_flow:
        d.rounded_rectangle([60,y,W-60,y+82],radius=8,
                             fill=tuple(int(v*0.12) for v in col),outline=tuple(int(v*0.5) for v in col),width=1)
        # レイヤーラベル
        d.rounded_rectangle([60,y,200,y+82],radius=8,
                             fill=tuple(int(v*0.25) for v in col))
        bb=d.textbbox((0,0),layer,font=F(24))
        d.text((130-(bb[2]-bb[0])//2, y+28), layer, font=F(24), fill=col)
        d.text((216,y+22), desc, font=Fr(28), fill=WHITE)
        if y < 380+(len(full_flow)-1)*92:
            arrow_v(d, W//2, y+82, y+92, col, width=2)
        y+=92

    # 締め言葉
    panel(d,60,1150,W-60,1330,GOLD)
    cx(d,"Simulation → Physical への移植が目標",1175,Fr(36),GOLD)
    cx(d,"同じコード・スキーマで Layer0 → Layer1 へ",1235,Fr(32),GRAY)
    cx(d,"クラウドが死んでも文明は生きる",1295,Fr(32),L2_C)

    progress(d, 0.92, GOLD)
    return img


def s_cta():
    """CTA"""
    img = base_img(); d = ImageDraw.Draw(img)
    # 背景アクセント
    for hx,hy,hr,col in [(W//2,800,400,L3_C),(200,300,200,L0_C),(880,1400,200,L2_C)]:
        draw_hex_accent(d, hx, hy, hr, col, alpha=20)

    cx(d, "ここまで見てくれて", 200, F(72))
    cx(d, "ありがとう！", 295, F(90), GOLD)

    # いいねボタン
    d.rounded_rectangle([W//2-280,440,W//2+280,560],radius=30,fill=(200,20,20),outline=WHITE,width=3)
    cx(d, "いいね！", 470, F(72), WHITE)
    d.rounded_rectangle([W//2-280,590,W//2+280,710],radius=30,fill=(20,20,200),outline=WHITE,width=3)
    cx(d, "チャンネル登録！", 618, F(60), WHITE)

    d.line([(80,760),(W-80,760)],fill=(40,50,90),width=2)
    cx(d, "次の目標", 800, F(56), L2_C)

    nexts = [
        (L1_C, "Layer1: 実機ロボット接続（Raspberry Pi）"),
        (L3_C, "Layer3: City OS 実装（FastAPI + MQTT）"),
        (GOLD, "Home Assistant 統合 → スマホから制御"),
        (L2_C, "ドローン × メッシュ通信 — 室内 Starlink"),
    ]
    ny=870
    for col,text in nexts:
        d.rounded_rectangle([80,ny,W-80,ny+64],radius=8,
                             fill=tuple(int(v*0.12) for v in col),outline=tuple(int(v*0.4) for v in col),width=1)
        d.text((100,ny+16), "→  "+text, font=Fr(28), fill=WHITE)
        ny+=80

    # 全キャラ
    roles=["Worker","Guardian","Trader","Observer","Governor"]
    for i,role in enumerate(roles):
        draw_agent(d, 110+i*216, 1530, role, sz=90)
    for i,role in enumerate(roles):
        bb=d.textbbox((0,0),role,font=Fr(24)); tw=bb[2]-bb[0]
        d.text((110+i*216-tw//2,1640),role,font=Fr(24),fill=GRAY)

    cx(d, "HACS — Home Autonomous Civilization System", 1720, Fr(30), GRAY)
    progress(d, 1.0, GOLD)
    return img


# ═══════════════════════════════════════════════════════════════
# シーン定義
# ═══════════════════════════════════════════════════════════════
SCENES = [
    {"fn": s_title,      "dur": 3.0,
     "narration": "家庭で自律文明を作ってみた。Layer0から3まで、全て解説します。"},
    {"fn": s_overview,   "dur": 5.0,
     "narration": "HACSは4層で構成される文明OSです。シミュレーション、物理、通信、都市OSの4層が積み重なっています。"},
    {"fn": s_l0_world,   "dur": 5.5,
     "narration": "Layer0はPythonで動く仮想シミュレーター。20×20のグリッド世界に17体のロボットが住んでいます。Worker、Guardian、Trader、Observer、Governorの5種類です。"},
    {"fn": s_l0_auction, "dur": 6.0,
     "narration": "仕事はオークションで決まります。タスクが発生すると全員が同時に入札し、最安値を提示したロボットが落札します。全取引は台帳に自動記録され、報酬の5パーセントが税として都市に還元されます。"},
    {"fn": s_l0_safety,  "dur": 5.5,
     "narration": "文明には憲法があります。Safety、Stability、Economy、Efficiencyの順で優先されます。Safety Gateが毎ティック先に動き、エネルギー切れや夜間侵入を即停止します。"},
    {"fn": s_l1,         "dur": 5.0,
     "narration": "Layer1は物理世界への拡張です。Raspberry PiやESP32の実機ロボットと接続します。Layer0と同じEvent・Commandスキーマを使うため、コードをそのまま実機へ移植できます。"},
    {"fn": s_l2_concept, "dur": 5.5,
     "narration": "Layer2は文明の神経系です。全データは必ずMQTT Brokerを経由し、直接通信は禁止です。Simulator、City OS、ダッシュボード、Home Assistantが全てここに接続されます。"},
    {"fn": s_l2_realtime,"dur": 5.5,
     "narration": "実際のテストでは23件のイベントを発行し、23件全てを受信。ロスなしで疎通確認できました。タスク生成から落札、移動、完了まで全て流れています。"},
    {"fn": s_l3_overview,"dur": 6.0,
     "narration": "Layer3は都市OSです。10個のサブモジュールで構成され、State管理、Event処理、Command発行、Policy、タスク調整、Agent戸籍、Workflow、アラート、ログ、再現機能を持ちます。"},
    {"fn": s_l3_ai,      "dur": 5.5,
     "narration": "AIの扱いには慎重です。AIは提案するだけ。Policy Engineが検証し、承認された命令だけが実行されます。AIに直接ハードウェア権限を渡しません。"},
    {"fn": s_fullflow,   "dur": 6.0,
     "narration": "全体フローをまとめます。Layer0でイベントが発生し、Layer2のMQTTを経由してLayer3の都市OSが受け取り、Policy検証後にCommandを返す。将来はLayer1の実機ロボットまで届きます。"},
    {"fn": s_cta,        "dur": 4.0,
     "narration": "面白かったらいいねとチャンネル登録してね！次は実機ロボット接続と都市OS実装に進みます。また次の動画でお会いしましょう！"},
]

# ═══════════════════════════════════════════════════════════════
# 音声 & ビルド
# ═══════════════════════════════════════════════════════════════
async def _tts(text, voice, path):
    await edge_tts.Communicate(text, voice).save(path)

def make_audio(text, speed=SPEED, voice=VOICE):
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f: orig=f.name
    asyncio.run(_tts(text, voice, orig))
    if FFMPEG is None or speed == 1.0: return orig
    out = orig.replace(".mp3","_fast.mp3")
    af  = f"atempo={speed}" if speed<=2.0 else f"atempo=2.0,atempo={speed/2.0}"
    subprocess.run([FFMPEG,"-y","-i",orig,"-filter:a",af,"-vn",out],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.unlink(orig); return out

def build():
    clips=[]; tmp=[]
    total=len(SCENES)
    print(f"HACS Full Explainer - {total} scenes")
    print(f"Voice: {VOICE}  Speed: {SPEED}x\n")
    for i,sc in enumerate(SCENES):
        print(f"[{i+1:2}/{total}] {sc['narration'][:35]}...")
        img = sc["fn"]()
        ap  = make_audio(sc["narration"])
        tmp.append(ap)
        ac  = AudioFileClip(ap)
        dur = max(sc["dur"], ac.duration + 0.3)
        clips.append(ImageClip(np.array(img)).with_duration(dur).with_audio(ac))
    print(f"\nMerging {total} clips...")
    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(OUT, fps=FPS, codec="libx264", audio_codec="aac", logger=None)
    print(f"\n完了 → {OUT}  ({final.duration:.1f}秒)")
    for f in tmp:
        try: os.unlink(f)
        except: pass

if __name__ == "__main__":
    build()
