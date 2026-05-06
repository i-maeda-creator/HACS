"""
HACS YouTube Shorts — Layer2 MQTT通信編
「自律文明にリアルタイム通信を繋げてみた」
"""
import sys, os, subprocess, tempfile, asyncio, math
sys.path.insert(0, "..")

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import edge_tts
from moviepy import *

W, H  = 1080, 1920
FPS   = 30
OUT   = "hacs_layer2_shorts.mp4"
SPEED = 1.85
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

BG1=(8,8,20); BG2=(18,18,45)
BLUE=(100,160,255); GREEN=(80,220,140); YELLOW=(255,200,60)
RED=(255,100,100); PURPLE=(200,100,255); WHITE=(255,255,255); GRAY=(170,170,200)
ORANGE=(255,150,60); CYAN=(60,220,220)
ROLE_COLOR={"Worker":BLUE,"Guardian":RED,"Trader":ORANGE,"Observer":PURPLE,"Governor":(160,120,80)}

def grad_bg(c1=BG1,c2=BG2):
    img=Image.new("RGB",(W,H)); d=ImageDraw.Draw(img)
    for y in range(H):
        t=y/H; r=int(c1[0]+(c2[0]-c1[0])*t); g=int(c1[1]+(c2[1]-c1[1])*t); b=int(c1[2]+(c2[2]-c1[2])*t)
        d.line([(0,y),(W,y)],fill=(r,g,b))
    return img

def grid_overlay(img):
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(ov)
    for x in range(0,W,60): d.line([(x,0),(x,H)],fill=(80,100,255,15))
    for y in range(0,H,60): d.line([(0,y),(W,y)],fill=(80,100,255,15))
    return Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")

def cx_text(draw,text,y,fnt,color=WHITE,shadow=True):
    bb=draw.textbbox((0,0),text,font=fnt); tw=bb[2]-bb[0]; x=(W-tw)//2
    if shadow: draw.text((x+3,y+3),text,font=fnt,fill=(0,0,0,160))
    draw.text((x,y),text,font=fnt,fill=color)

def tag_box(draw,text,y,fnt,bg,fg=(10,10,30)):
    bb=draw.textbbox((0,0),text,font=fnt); tw=bb[2]-bb[0]; th=bb[3]-bb[1]
    x=(W-tw)//2; pad=18
    draw.rounded_rectangle([x-pad,y-pad,x+tw+pad,y+th+pad],radius=14,fill=bg)
    draw.text((x,y),text,font=fnt,fill=fg)

def progress_bar(draw,pct,color=BLUE):
    y=H-50; draw.rectangle([0,y,W,y+10],fill=(30,30,60))
    draw.rectangle([0,y,int(W*pct),y+10],fill=color)

def arrow(draw,x1,y1,x2,y2,color,width=6):
    draw.line([(x1,y1),(x2,y2)],fill=color,width=width)
    ang=math.atan2(y2-y1,x2-x1); sz=22
    draw.polygon([(x2,y2),(int(x2-sz*math.cos(ang-0.5)),int(y2-sz*math.sin(ang-0.5))),
                  (int(x2-sz*math.cos(ang+0.5)),int(y2-sz*math.sin(ang+0.5)))],fill=color)

def draw_character(d,cx,cy,role,size=110,mood="normal"):
    c=ROLE_COLOR.get(role,WHITE); dark=tuple(max(0,v-60) for v in c); s=size
    d.rounded_rectangle([cx-s//2,cy-s//4,cx+s//2,cy+s//2],radius=s//5,fill=c,outline=WHITE,width=2)
    d.ellipse([cx-s//2+4,cy-s-s//4,cx+s//2-4,cy-s//4+4],fill=c,outline=WHITE,width=2)
    ey=cy-s*3//4; es=s//8
    if mood=="happy":
        d.arc([cx-s//4-es,ey-es,cx-s//4+es,ey+es],200,340,fill=dark,width=3)
        d.arc([cx+s//4-es,ey-es,cx+s//4+es,ey+es],200,340,fill=dark,width=3)
    else:
        d.ellipse([cx-s//4-es,ey-es,cx-s//4+es,ey+es],fill=dark)
        d.ellipse([cx+s//4-es,ey-es,cx+s//4+es,ey+es],fill=dark)
        d.arc([cx-s//6,ey+es,cx+s//6,ey+es*3],0,180,fill=dark,width=3)
    d.rounded_rectangle([cx-s//3,cy+s//2,cx-s//10,cy+s//2+s//3],radius=6,fill=dark,outline=WHITE,width=1)
    d.rounded_rectangle([cx+s//10,cy+s//2,cx+s//3,cy+s//2+s//3],radius=6,fill=dark,outline=WHITE,width=1)

# ── シーン1: フック ─────────────────────────────────────────────
def scene_hook():
    img=grad_bg(); img=grid_overlay(img); d=ImageDraw.Draw(img)
    tag_box(d,"Layer2 通信編",110,font(40),CYAN,(10,10,30))
    cx_text(d,"自律文明に",280,font(96))
    cx_text(d,"リアルタイム",390,font(96),CYAN)
    cx_text(d,"通信を繋げた",500,font(96))
    # キャラクター下段
    for (cx2,cy2),role in [((130,1560),"Worker"),((330,1580),"Guardian"),
                            ((540,1560),"Trader"),((750,1580),"Observer"),((960,1560),"Governor")]:
        draw_character(d,cx2,cy2,role,size=105,mood="happy")
    labels=[("Worker",130),("Guardian",330),("Trader",540),("Observer",750),("Governor",960)]
    for name,lx in labels:
        bb=d.textbbox((0,0),name,font=font_r(26)); tw=bb[2]-bb[0]
        d.text((lx-tw//2,1685),name,font=font_r(26),fill=GRAY)
    progress_bar(d,0.0,CYAN)
    return img

# ── シーン2: 前回のおさらい ─────────────────────────────────────
def scene_recap():
    img=grad_bg(); img=grid_overlay(img); d=ImageDraw.Draw(img)
    tag_box(d,"前回まで",110,font(42),GREEN)
    cx_text(d,"Layer0 完成済み",250,font(76),GREEN)
    items=[
        ("17体のロボットが動く","仮想シミュレーター"),
        ("入札でタスクを奪い合う","オークション経済"),
        ("Safety Gate","ルール違反を自動処理"),
    ]
    y=370
    for t1,t2 in items:
        d.rounded_rectangle([80,y,W-80,y+110],radius=14,fill=(20,20,50),outline=GREEN,width=2)
        cx_text(d,t1,y+8,font(50),WHITE); cx_text(d,t2,y+62,font_r(38),GRAY)
        y+=130
    cx_text(d,"今回はここに",780,font(62),CYAN)
    cx_text(d,"通信を追加！",860,font(72),CYAN)
    draw_character(d,W//2,1120,"Observer",size=130,mood="happy")
    progress_bar(d,0.12,GREEN)
    return img

# ── シーン3: Layer構成図 ─────────────────────────────────────────
def scene_layers():
    img=grad_bg(); img=grid_overlay(img); d=ImageDraw.Draw(img)
    tag_box(d,"HACS アーキテクチャ",110,font(40),BLUE)
    cx_text(d,"Layer 構造",250,font(84))

    layers=[
        ("Layer0","仮想シミュレーター",GREEN,"完成"),
        ("Layer2","通信 / MQTT",CYAN,"今回"),
        ("Layer1","実機ロボット",ORANGE,"将来"),
        ("Layer3","都市OS / AI",PURPLE,"将来"),
    ]
    y=390
    for name,desc,col,badge in layers:
        alpha=255 if badge!="将来" else 100
        c=tuple(int(v*(alpha/255)) for v in col)
        d.rounded_rectangle([80,y,W-80,y+114],radius=14,fill=(20,20,50),outline=c,width=3)
        cx_text(d,name,y+6,font(56),c); cx_text(d,desc,y+66,font_r(42),GRAY)
        if badge=="今回":
            tag_box(d,"今回",y+28,font(32),CYAN,(10,10,30))
        elif badge=="完成":
            tag_box(d,"完成",y+28,font(32),GREEN,(10,10,30))
        y+=134
    draw_character(d,W//2,1620,"Governor",size=120,mood="happy")
    progress_bar(d,0.25,CYAN)
    return img

# ── シーン4: MQTTとは ──────────────────────────────────────────
def scene_mqtt():
    img=grad_bg(); img=grid_overlay(img); d=ImageDraw.Draw(img)
    tag_box(d,"Layer2-1 Event Bus",110,font(40),CYAN,(10,10,30))
    cx_text(d,"MQTTとは？",250,font(90))

    # Broker 中央
    BX,BY=W//2,740; BR=130
    d.ellipse([BX-BR,BY-BR,BX+BR,BY+BR],fill=(20,30,80),outline=CYAN,width=4)
    cx_text(d,"MQTT",BY-40,font(60),CYAN)
    cx_text(d,"Broker",BY+30,font(48),CYAN)

    # Publisher / Subscriber
    nodes=[
        (180,460,"Publisher\n(Simulator)",GREEN),
        (900,460,"Subscriber\n(Dashboard)",YELLOW),
        (180,1020,"Subscriber\n(HomeAssist)",ORANGE),
        (900,1020,"Subscriber\n(Logger)",PURPLE),
    ]
    for nx,ny,label,col in nodes:
        d.rounded_rectangle([nx-110,ny-50,nx+110,ny+50],radius=12,fill=(20,20,50),outline=col,width=2)
        lines=label.split("\n")
        d.text((nx-d.textbbox((0,0),lines[0],font=font_r(26))[2]//2,ny-34),lines[0],font=font_r(26),fill=col)
        d.text((nx-d.textbbox((0,0),lines[1],font=font_r(22))[2]//2,ny+4),lines[1],font=font_r(22),fill=GRAY)
        arrow(d,nx,ny+50 if ny<BY else ny-50,BX+int((nx-BX)*0.5),BY,col,width=4)

    cx_text(d,"全イベントが",1180,font(54),WHITE)
    cx_text(d,"Brokerを経由して流れる",1250,font_r(42),GRAY)
    progress_bar(d,0.42,CYAN)
    return img

# ── シーン5: イベントフロー ────────────────────────────────────
def scene_eventflow():
    img=grad_bg(); img=grid_overlay(img); d=ImageDraw.Draw(img)
    tag_box(d,"実際のイベント",110,font(42),GREEN)
    cx_text(d,"こんな風に流れる",250,font(76))

    events=[
        ("city/task/new",     "TaskCreated",    GREEN),
        ("city/task/bid",     "BidSubmitted x4",ORANGE),
        ("city/task/assigned","TaskAssigned W2", CYAN),
        ("agent/*/event",     "AgentMoved W2",  BLUE),
        ("city/task/completed","TaskCompleted",  YELLOW),
        ("city/policy/update","PolicyChanged G1",RED),
    ]
    y=360
    for topic,etype,col in events:
        d.rounded_rectangle([60,y,W-60,y+98],radius=12,fill=(15,15,38),outline=col,width=2)
        d.text((80,y+10),topic,font=font_r(30),fill=col)
        d.text((80,y+56),etype,font=font_r(34),fill=WHITE)
        y+=118

    cx_text(d,"Published 23 / Received 23",1110,font(46),GREEN)
    cx_text(d,"完全疎通確認済み！",1170,font_r(40),GRAY)
    draw_character(d,W//2,1620,"Worker",size=110,mood="happy")
    progress_bar(d,0.62,GREEN)
    return img

# ── シーン6: Liveダッシュボード ────────────────────────────────
def scene_dashboard():
    img=grad_bg((10,5,30),(20,10,50)); img=grid_overlay(img); d=ImageDraw.Draw(img)
    tag_box(d,"Live Dashboard",110,font(42),CYAN,(10,10,30))
    cx_text(d,"ブラウザで",250,font(88))
    cx_text(d,"リアルタイム表示！",360,font(80),CYAN)

    # ダッシュボードUI のモック
    DX,DY,DW,DH=60,490,960,800
    d.rounded_rectangle([DX,DY,DX+DW,DY+DH],radius=12,fill=(10,15,35),outline=CYAN,width=2)
    # ヘッダ
    d.rectangle([DX,DY,DX+DW,DY+44],fill=(20,30,70))
    d.text((DX+16,DY+10),"HACS — LIVE DASHBOARD",font=font_r(28),fill=CYAN)
    d.ellipse([DX+DW-30,DY+12,DX+DW-12,DY+30],fill=GREEN)

    # KPI
    kpis=[("615","Total Events"),("95%","Task Rate"),("20","Bids"),("100","Tick")]
    kx=DX+16
    for val,label in kpis:
        d.rounded_rectangle([kx,DY+60,kx+210,DY+160],radius=8,fill=(15,20,55),outline=BLUE,width=1)
        cx2=(kx+kx+210)//2
        bb=d.textbbox((0,0),val,font=font(52)); tw=bb[2]-bb[0]
        d.text((cx2-tw//2,DY+68),val,font=font(52),fill=BLUE)
        bb2=d.textbbox((0,0),label,font=font_r(24)); tw2=bb2[2]-bb2[0]
        d.text((cx2-tw2//2,DY+128),label,font=font_r(24),fill=GRAY)
        kx+=238

    # Topic Flow
    topics=[("city/task/bid",8,ORANGE),("city/task/new",2,GREEN),
            ("agent/*/event",5,BLUE),("city/policy/update",4,RED)]
    ty2=DY+180
    for topic,count,col in topics:
        d.text((DX+16,ty2),topic,font=font_r(24),fill=col)
        bar_w=int((count/8)*400)
        d.rounded_rectangle([DX+320,ty2+2,DX+320+bar_w,ty2+28],radius=4,fill=col)
        d.text((DX+740,ty2),str(count),font=font_r(26),fill=col)
        ty2+=44

    # Event Stream
    log_events=[("t10","city/task/new","TaskCreated",GREEN),
                ("t10","city/task/bid","BidSubmitted",ORANGE),
                ("t10","city/task/assigned","TaskAssigned",CYAN),
                ("t11","agent/sim/event","AgentMoved",BLUE)]
    ty3=DY+380
    for tick,topic,etype,col in log_events:
        d.text((DX+16,ty3),tick,font=font_r(22),fill=GRAY)
        d.text((DX+90,ty3),topic[:22],font=font_r(22),fill=BLUE)
        d.text((DX+540,ty3),etype,font=font_r(22),fill=col)
        ty3+=42

    cx_text(d,"http://localhost:8080/live_dashboard.html",1340,font_r(34),CYAN)
    draw_character(d,W//2,1650,"Observer",size=110,mood="happy")
    progress_bar(d,0.80,CYAN)
    return img

# ── シーン7: CTA ───────────────────────────────────────────────
def scene_cta():
    img=grad_bg((10,5,30),(25,10,60)); img=grid_overlay(img); d=ImageDraw.Draw(img)
    tag_box(d,"お願いがあります！",110,font(42),YELLOW,(10,10,30))
    cx_text(d,"面白かったら",260,font(78))
    bx=W//2; bw,bh=420,120
    d.rounded_rectangle([bx-bw//2,360-bh//2,bx+bw//2,360+bh//2],radius=30,fill=RED,outline=WHITE,width=3)
    cx_text(d,"いいね！",360-34,font(72),WHITE)
    d.rounded_rectangle([bx-bw//2,510-bh//2,bx+bw//2,510+bh//2],radius=30,fill=(50,50,200),outline=WHITE,width=3)
    cx_text(d,"チャンネル登録！",510-34,font(60),WHITE)
    cx_text(d,"してね！",640,font(78))
    d.line([(120,760),(W-120,760)],fill=(60,60,100),width=2)
    cx_text(d,"次の目標",820,font(58),CYAN)
    for txt,y in [("Layer1：実際のロボットに接続",890),
                   ("ドローン × メッシュ通信",950),
                   ("Home Assistant 統合",1010)]:
        cx_text(d,f"-> {txt}",y,font_r(40),GRAY)
    for (cx2,cy2),role in [((130,1530),"Worker"),((310,1560),"Guardian"),
                            ((540,1530),"Trader"),((770,1560),"Observer"),((960,1530),"Governor")]:
        draw_character(d,cx2,cy2,role,size=105,mood="happy")
    progress_bar(d,1.0,YELLOW)
    return img

# ── 音声 ─────────────────────────────────────────────────────
async def _tts(text,voice,path):
    await edge_tts.Communicate(text,voice).save(path)

def make_audio_fast(text,speed=SPEED,voice=VOICE):
    with tempfile.NamedTemporaryFile(suffix=".mp3",delete=False) as f: orig=f.name
    asyncio.run(_tts(text,voice,orig))
    if FFMPEG is None or speed==1.0: return orig
    out=orig.replace(".mp3","_fast.mp3")
    af=f"atempo={speed}" if speed<=2.0 else f"atempo=2.0,atempo={speed/2.0}"
    subprocess.run([FFMPEG,"-y","-i",orig,"-filter:a",af,"-vn",out],
                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    os.unlink(orig); return out

SCENES=[
    {"narration":"自律文明にリアルタイム通信を繋げてみた！","fn":scene_hook,"min_dur":2.5},
    {"narration":"前回はシミュレーターを完成させました。17体のロボットが自律的に動く世界です。","fn":scene_recap,"min_dur":4.0},
    {"narration":"今回はLayer2、つまり文明の神経系となる通信レイヤーを実装します。","fn":scene_layers,"min_dur":4.0},
    {"narration":"使うのはMQTT。全てのイベントがBrokerを経由して流れる仕組みです。","fn":scene_mqtt,"min_dur":4.0},
    {"narration":"実際にこんなイベントが流れます。タスク生成、入札、落札、移動、完了。全部リアルタイムで！","fn":scene_eventflow,"min_dur":4.5},
    {"narration":"ブラウザのLiveダッシュボードで全てが見えます。615イベントが完全疎通しました！","fn":scene_dashboard,"min_dur":4.0},
    {"narration":"面白かったらいいねとチャンネル登録してね！また次の動画でお会いしましょう！","fn":scene_cta,"min_dur":4.0},
]

def build_video():
    clips=[]; tmp_files=[]
    print(f"Voice: {VOICE}, Scenes: {len(SCENES)}")
    for i,sc in enumerate(SCENES):
        print(f"  [{i+1}/{len(SCENES)}] {sc['narration'][:30]}...")
        img=sc["fn"](); audio_path=make_audio_fast(sc["narration"])
        tmp_files.append(audio_path)
        audio_clip=AudioFileClip(audio_path)
        duration=max(sc["min_dur"],audio_clip.duration+0.2)
        clips.append(ImageClip(np.array(img)).with_duration(duration).with_audio(audio_clip))
    print("\nMerging...")
    final=concatenate_videoclips(clips,method="compose")
    final.write_videofile(OUT,fps=FPS,codec="libx264",audio_codec="aac",logger=None)
    print(f"Done! --> {OUT}  ({final.duration:.1f}sec)")
    for f in tmp_files:
        try: os.unlink(f)
        except: pass

if __name__=="__main__":
    build_video()
