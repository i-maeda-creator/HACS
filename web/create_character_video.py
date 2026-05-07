"""
HACS Character Introduction Video
- Resolution: 1080x1920 (YouTube Shorts / vertical)
- ~110 seconds total
- edge-tts narration (ja-JP-NanamiNeural)
- PIL frame generation
- ffmpeg for final assembly
"""

import sys, os, subprocess, tempfile, asyncio, math, shutil
sys.path.insert(0, ".")

from PIL import Image, ImageDraw, ImageFont
import edge_tts

# ── Constants ─────────────────────────────────────────────────────────────────
W, H   = 1080, 1920
FPS    = 30
OUT    = "web/hacs_character_intro.mp4"
VOICE  = "ja-JP-NanamiNeural"

BG_DARK   = (10, 10, 18)
BG_PANEL  = (20, 20, 35)
DOT_COLOR = (30, 30, 50)
WHITE     = (255, 255, 255)
GRAY      = (160, 160, 190)
LGRAY     = (100, 100, 130)

ROLE_COLOR = {
    "Worker":   (0,   230, 118),   # #00E676 green
    "Guardian": (255,  68,  68),   # #FF4444 red
    "Trader":   (255, 109,   0),   # #FF6D00 orange
    "Observer": (  0, 176, 255),   # #00B0FF cyan
    "Governor": (170,   0, 255),   # #AA00FF purple
}

# Scene durations (seconds)
SCENE_DURATIONS = {
    "opening":  8,
    "Worker":  18,
    "Guardian":18,
    "Trader":  18,
    "Observer":18,
    "Governor":20,
    "closing": 10,
}

# Narration scripts
NARRATION = {
    "opening":
        "HACSには5つの役職があります。それぞれが異なる戦略で自律都市を支えています。",
    "Worker":
        "Workerは都市の主力労働者です。30体が全域に分散し、オークションで仕事を奪い合います。"
        "近くのタスクほど強く入札し、遠いタスクは控えます。"
        "sector学習で市場を把握しながら効率よく稼ぎます。"
        "エネルギーが30パーセントを切ると充電スポットへ向かいます。",
    "Guardian":
        "Guardianは都市の守護者です。6体が5点パトロールルートを永続巡回します。"
        "タスクには一切入札せず、経済活動には参加しません。"
        "夜間フェーズにはSafetyGateから行動制限を受け、"
        "エネルギーが40パーセントを切ると充電を優先します。",
    "Trader":
        "Traderは市場を学習する戦略家です。6体が市場平均報酬をリアルタイムで学習し、"
        "平均の70パーセント以上の高マージンタスクだけに絞り込んで入札します。"
        "入札回数は少なくても、1件あたりの獲得報酬はWorkerより高くなります。",
    "Observer":
        "Observerは都市の観察者です。5体が東西南北と中央の担当エリアに分散し、"
        "8tickごとに巡回します。タスクには入札せず情報収集に専念します。"
        "都市全体の目として、Governorの判断を支える存在です。",
    "Governor":
        "Governorは都市の統治者です。3体が5つの監視拠点を巡回しながら、"
        "25tickごとにKPIを分析して政策を提案します。"
        "Workerの半数以上が仕事を取れていなければworker_supportを発動し、"
        "全Workerの入札にボーナスを付与します。"
        "Giniが高ければ増税を、タスク完了率が低ければ報酬倍率アップを提案します。"
        "提案は即座に世界に反映されます。",
    "closing":
        "5つの役職が協調して動く自律都市、HACS。"
        "Safety優先、Stability重視、Economy管理、Efficiency最大化。"
        "これが都市自律の設計思想です。",
}

# ── Font helpers ──────────────────────────────────────────────────────────────
def get_font(size, bold=True):
    candidates = []
    if bold:
        candidates = [
            "C:/Windows/Fonts/YuGothB.ttc",
            "C:/Windows/Fonts/meiryob.ttc",
            "C:/Windows/Fonts/msgothic.ttc",
        ]
    else:
        candidates = [
            "C:/Windows/Fonts/YuGothR.ttc",
            "C:/Windows/Fonts/meiryo.ttc",
            "C:/Windows/Fonts/msgothic.ttc",
        ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()

# ── Drawing utilities ─────────────────────────────────────────────────────────
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def draw_dot_grid(draw, w=W, h=H, spacing=40):
    """Subtle dot-grid background."""
    for x in range(0, w, spacing):
        for y in range(0, h, spacing):
            draw.ellipse([x-1, y-1, x+1, y+1], fill=DOT_COLOR)

def draw_gradient_bg(img):
    """Dark vertical gradient background."""
    pix = img.load()
    for y in range(H):
        t = y / H
        r = int(BG_DARK[0] + (BG_PANEL[0] - BG_DARK[0]) * t)
        g = int(BG_DARK[1] + (BG_PANEL[1] - BG_DARK[1]) * t)
        b = int(BG_DARK[2] + (BG_PANEL[2] - BG_DARK[2]) * t)
        for x in range(W):
            pix[x, y] = (r, g, b)

def draw_role_circle(draw, cx, cy, r, color, letter, font_big):
    """Large filled circle with role initial letter."""
    # Glow rings
    for i in range(4, 0, -1):
        glow_a = int(30 + i * 15)
        glow_r = r + i * 8
        glow_color = color + (glow_a,)
        # Use a temp image for alpha composite glow
    # Outer ring
    draw.ellipse([cx-r-6, cy-r-6, cx+r+6, cy+r+6],
                 outline=color, width=3)
    # Inner fill (darker version)
    dark = tuple(max(0, v - 80) for v in color)
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=dark, outline=color, width=4)
    # Letter
    bbox = draw.textbbox((0, 0), letter, font=font_big)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2 - 4), letter, fill=color, font=font_big)

def draw_separator(draw, y, color, width=W-120, cx=W//2):
    x0 = cx - width // 2
    x1 = cx + width // 2
    draw.line([x0, y, x1, y], fill=color, width=2)
    # End dots
    draw.ellipse([x0-4, y-4, x0+4, y+4], fill=color)
    draw.ellipse([x1-4, y-4, x1+4, y+4], fill=color)

def draw_bullet(draw, x, y, text, color, font_obj, dot_r=8):
    draw.ellipse([x-dot_r, y-dot_r, x+dot_r, y+dot_r], fill=color)
    draw.text((x + dot_r*2 + 4, y - dot_r), text, fill=WHITE, font=font_obj)

# ── Minimap visualizations ────────────────────────────────────────────────────
MINIMAP_SIZE = 320   # square size
GRID_N = 8

def _minimap_base(draw, ox, oy, size, color):
    """Draw minimap frame and grid lines."""
    # Background
    draw.rectangle([ox, oy, ox+size, oy+size], fill=(15, 15, 28), outline=color, width=2)
    cell = size // GRID_N
    for i in range(1, GRID_N):
        lc = (30, 30, 55)
        draw.line([ox + i*cell, oy, ox + i*cell, oy+size], fill=lc, width=1)
        draw.line([ox, oy + i*cell, ox+size, oy + i*cell], fill=lc, width=1)
    return cell

def draw_minimap_worker(draw, ox, oy, size, color, tick=0):
    """Scattered workers with arrows to tasks."""
    cell = _minimap_base(draw, ox, oy, size, color)
    import random
    rng = random.Random(42)
    # Task positions (marked ★)
    tasks = [(2,1),(5,3),(1,5),(6,6),(3,7),(7,2),(4,4)]
    for (gx, gy) in tasks:
        px = ox + gx*cell + cell//2
        py = oy + gy*cell + cell//2
        draw.text((px-6, py-8), "★", fill=(255,220,50), font=get_font(14, bold=False))
    # Worker dots + arrows toward nearest task
    workers = [(1,2),(3,1),(6,1),(0,4),(2,4),(5,5),(7,4),(4,6),(0,7),(6,0)]
    for (wx, wy) in workers:
        px = ox + wx*cell + cell//2
        py = oy + wy*cell + cell//2
        # Find nearest task
        nearest = min(tasks, key=lambda t: (t[0]-wx)**2 + (t[1]-wy)**2)
        tx = ox + nearest[0]*cell + cell//2
        ty = oy + nearest[1]*cell + cell//2
        # Arrow
        draw.line([px, py, tx, ty], fill=(*color, 120) if len(color)==3 else color, width=1)
        # Worker dot
        draw.ellipse([px-5, py-5, px+5, py+5], fill=color)

def draw_minimap_guardian(draw, ox, oy, size, color, tick=0):
    """5-point patrol route connected as polygon."""
    cell = _minimap_base(draw, ox, oy, size, color)
    # 5 patrol points arranged as pentagon
    cx_m = ox + size // 2
    cy_m = oy + size // 2
    R = size // 2 - cell
    pts = []
    for i in range(5):
        angle = math.radians(-90 + i * 72)
        px = int(cx_m + R * math.cos(angle))
        py = int(cy_m + R * math.sin(angle))
        pts.append((px, py))
    # Draw route lines
    for i in range(len(pts)):
        p1 = pts[i]
        p2 = pts[(i+1) % len(pts)]
        draw.line([p1, p2], fill=color, width=2)
    # Draw patrol points
    for i, (px, py) in enumerate(pts):
        draw.ellipse([px-8, py-8, px+8, py+8], fill=color, outline=WHITE, width=2)
        lbl = get_font(14, bold=True)
        draw.text((px-4, py-8), str(i+1), fill=WHITE, font=lbl)
    # Animated guardian position (pulsing dot on current segment)
    seg_idx = (tick // 12) % len(pts)
    next_idx = (seg_idx + 1) % len(pts)
    t_frac = (tick % 12) / 12.0
    gx = int(pts[seg_idx][0] + (pts[next_idx][0] - pts[seg_idx][0]) * t_frac)
    gy = int(pts[seg_idx][1] + (pts[next_idx][1] - pts[seg_idx][1]) * t_frac)
    draw.ellipse([gx-7, gy-7, gx+7, gy+7], fill=WHITE, outline=color, width=2)

def draw_minimap_trader(draw, ox, oy, size, color, tick=0):
    """Few selective dots at high-reward spots."""
    cell = _minimap_base(draw, ox, oy, size, color)
    # All available tasks (grayed out - low margin)
    all_tasks = [(1,1),(1,4),(1,6),(2,2),(3,0),(3,5),(4,3),(5,1),(5,6),(6,2),(6,5),(7,3),(7,7),(0,3)]
    for (gx, gy) in all_tasks:
        px = ox + gx*cell + cell//2
        py = oy + gy*cell + cell//2
        draw.ellipse([px-3, py-3, px+3, py+3], fill=(60,60,80))
    # High-margin tasks (trader targets)
    high_margin = [(2,2),(5,1),(6,5),(4,3)]
    for (gx, gy) in high_margin:
        px = ox + gx*cell + cell//2
        py = oy + gy*cell + cell//2
        # Highlight ring
        draw.ellipse([px-12, py-12, px+12, py+12], outline=color, width=2)
        draw.text((px-7, py-10), "★", fill=(255,220,50), font=get_font(14, bold=False))
    # Trader agents (few, near high-margin spots)
    traders = [(1,3),(5,2),(6,4)]
    for i, (gx, gy) in enumerate(traders):
        px = ox + gx*cell + cell//2
        py = oy + gy*cell + cell//2
        draw.ellipse([px-6, py-6, px+6, py+6], fill=color, outline=WHITE, width=1)
    # Label
    lbl_font = get_font(13, bold=False)
    draw.text((ox+4, oy+size-20), "high margin only", fill=color, font=lbl_font)

def draw_minimap_observer(draw, ox, oy, size, color, tick=0):
    """4 quadrant boxes with O markers."""
    cell = _minimap_base(draw, ox, oy, size, color)
    half = size // 2
    quad_labels = ["NW","NE","SW","SE"]
    # Quadrant positions
    quads = [
        (ox,       oy,        ox+half,  oy+half),   # NW
        (ox+half,  oy,        ox+size,  oy+half),   # NE
        (ox,       oy+half,   ox+half,  oy+size),   # SW
        (ox+half,  oy+half,   ox+size,  oy+size),   # SE
    ]
    # Observer positions (one per quadrant, animating within it)
    observer_cells = [(1,1), (5,1), (1,5), (5,5)]
    active_q = (tick // 20) % 4
    for i, (qx0, qy0, qx1, qy1) in enumerate(quads):
        qcx = (qx0+qx1)//2
        qcy = (qy0+qy1)//2
        # Quad border highlight
        border_col = color if i == active_q else (40, 40, 70)
        draw.rectangle([qx0+2, qy0+2, qx1-2, qy1-2], outline=border_col, width=2)
        # Observer "O" marker
        gx, gy = observer_cells[i]
        px = ox + gx*cell + cell//2
        py = oy + gy*cell + cell//2
        marker_col = color if i == active_q else (80, 80, 120)
        draw.ellipse([px-8, py-8, px+8, py+8], outline=marker_col, width=3)
        lbl_f = get_font(13, bold=True)
        draw.text((qcx-8, qcy+half//3), quad_labels[i], fill=marker_col, font=lbl_f)
    # Central fifth observer
    cx5 = ox + size//2
    cy5 = oy + size//2
    draw.ellipse([cx5-8, cy5-8, cx5+8, cy5+8], outline=color, width=3)
    draw.text((cx5-4, cy5+10), "C", fill=color, font=get_font(13, bold=True))

def draw_minimap_governor(draw, ox, oy, size, color, tick=0):
    """5 monitoring posts connected, with policy icons."""
    cell = _minimap_base(draw, ox, oy, size, color)
    cx_m = ox + size // 2
    cy_m = oy + size // 2
    R = size // 2 - cell
    # 5 posts
    posts = []
    for i in range(5):
        angle = math.radians(-90 + i * 72)
        px = int(cx_m + R * math.cos(angle))
        py = int(cy_m + R * math.sin(angle))
        posts.append((px, py))
    # Center post
    posts.append((cx_m, cy_m))
    # Draw connections from center to each outer post
    for i in range(5):
        draw.line([cx_m, cy_m, posts[i][0], posts[i][1]], fill=(*color[:3], 80) if len(color)==4 else color, width=1)
    # Draw outer post ring connections
    for i in range(5):
        p1 = posts[i]
        p2 = posts[(i+1) % 5]
        draw.line([p1, p2], fill=color, width=1)
    # Post icons
    policy_icons = ["📊","⚖","💰","✓","👁"]
    policy_text  = ["KPI","TAX","RWD","OK","OBS"]
    lbl_f = get_font(13, bold=False)
    active_post = (tick // 30) % 5
    for i, (px, py) in enumerate(posts[:5]):
        col = WHITE if i == active_post else LGRAY
        draw.ellipse([px-9, py-9, px+9, py+9], fill=(30,10,50) if i == active_post else (20,20,35),
                     outline=color if i == active_post else LGRAY, width=2)
        draw.text((px-10, py+10), policy_text[i], fill=col, font=lbl_f)
    # Governor agent dot (animated)
    gov_post = active_post
    next_post = (active_post + 1) % 5
    t_frac = (tick % 30) / 30.0
    gx = int(posts[gov_post][0] + (posts[next_post][0] - posts[gov_post][0]) * t_frac)
    gy = int(posts[gov_post][1] + (posts[next_post][1] - posts[gov_post][1]) * t_frac)
    draw.ellipse([gx-7, gy-7, gx+7, gy+7], fill=color, outline=WHITE, width=2)
    # Policy broadcast pulse
    if tick % 15 < 5:
        pulse_r = 20 + (tick % 15) * 4
        draw.ellipse([cx_m-pulse_r, cy_m-pulse_r, cx_m+pulse_r, cy_m+pulse_r],
                     outline=(*color[:3],), width=1)

# ── Frame generators ──────────────────────────────────────────────────────────

def make_opening_frame(tick, total_ticks):
    img = Image.new("RGB", (W, H), BG_DARK)
    draw_gradient_bg(img)
    draw = ImageDraw.Draw(img)
    draw_dot_grid(draw)

    t = tick / total_ticks  # 0..1

    # Title
    title_font = get_font(90, bold=True)
    sub_font   = get_font(44, bold=False)
    tag_font   = get_font(32, bold=False)

    # Animated glow behind title
    glow_r = int(200 + 30 * math.sin(tick * 0.08))
    gx, gy = W//2, H//2 - 120
    for ri in range(5, 0, -1):
        a_val = int(15 * ri)
        rc = glow_r + ri * 25
        c_glow = (40, 30, 70)
        draw.ellipse([gx-rc, gy-rc//2, gx+rc, gy+rc//2], fill=c_glow)

    draw.text((W//2, H//2 - 200), "HACS", fill=WHITE, font=get_font(130, bold=True),
              anchor="mm")
    draw.text((W//2, H//2 - 80), "役職図鑑", fill=WHITE, font=title_font, anchor="mm")
    draw.text((W//2, H//2 + 20), "Home Autonomous Civilization System",
              fill=GRAY, font=tag_font, anchor="mm")

    # 5 role color circles arranged in an arc
    roles = ["Worker", "Guardian", "Trader", "Observer", "Governor"]
    arc_y = H//2 + 200
    arc_r = 300
    for i, role in enumerate(roles):
        angle = math.radians(-45 + i * 22.5)
        # Actually spread them in a row
        sx = W//2 - 240 + i * 120
        sy = arc_y
        col = ROLE_COLOR[role]
        # Pulse animation
        pulse = math.sin(tick * 0.1 + i * 1.2)
        cr = int(42 + 6 * pulse)
        draw.ellipse([sx-cr, sy-cr, sx+cr, sy+cr], fill=col, outline=WHITE, width=2)
        # Initial letter
        ltr_font = get_font(32, bold=True)
        draw.text((sx, sy), role[0], fill=WHITE, font=ltr_font, anchor="mm")

    draw.text((W//2, arc_y + 90), "5 つの役職", fill=GRAY, font=sub_font, anchor="mm")

    # Progress bar at bottom
    bar_w = int((W - 120) * t)
    draw.rectangle([60, H-60, 60+bar_w, H-45], fill=(60, 60, 100))
    draw.rectangle([60, H-60, W-60, H-45], outline=LGRAY, width=1)

    return img


def make_role_frame(tick, total_ticks, role):
    """Generic character scene frame."""
    color = ROLE_COLOR[role]
    img = Image.new("RGB", (W, H), BG_DARK)
    draw_gradient_bg(img)
    draw = ImageDraw.Draw(img)
    draw_dot_grid(draw)

    t = tick / max(1, total_ticks - 1)

    # Role-specific content
    ROLE_DATA = {
        "Worker": {
            "subtitle": "都市の労働者",
            "count":    "最多 30 体 ・ 全域分散",
            "bullets": [
                "オークションで仕事を入札・獲得",
                "近いタスクほど高く入札",
                "sector 熱量マップで学習最適化",
                "エネルギー 30% 未満 → 充電へ",
            ],
            "initial": "W",
        },
        "Guardian": {
            "subtitle": "都市の守護者",
            "count":    "6 体 ・ 5 点パトロールルート",
            "bullets": [
                "タスク入札ゼロ（完全非経済）",
                "永続巡回で治安を維持",
                "夜間は SafetyGate に制限",
                "エネルギー 40% 未満 → 充電優先",
            ],
            "initial": "G",
        },
        "Trader": {
            "subtitle": "都市の商人",
            "count":    "6 体 ・ 市場戦略家",
            "bullets": [
                "市場平均報酬を EMA で継続学習",
                "平均の 70% 以上の高マージンのみ入札",
                "少ない入札で高報酬を獲得",
                "MIN_MARGIN=3 EC 以下は自動スキップ",
            ],
            "initial": "T",
        },
        "Observer": {
            "subtitle": "都市の観察者",
            "count":    "4 象限 分担カバー",
            "bullets": [
                "担当エリアを 8 tick ごとに巡回",
                "タスク入札ゼロ（情報収集専門）",
                "エネルギー 25% 未満 → 充電",
                "Governor の判断を支援",
            ],
            "initial": "O",
        },
        "Governor": {
            "subtitle": "都市の統治者",
            "count":    "3 体 ・ 5 監視拠点 巡回",
            "bullets": [
                "25 tick ごとに KPI 分析 → 政策提案",
                "idle > 50% → worker_support (入札ボーナス)",
                "Gini > 0.25 → tax_increase (増税)",
                "完了率 < 60% → reward_boost (報酬倍率 UP)",
            ],
            "initial": "G" if role != "Guardian" else "GV",
        },
    }
    # Fix Governor initial conflict
    if role == "Governor":
        ROLE_DATA["Governor"]["initial"] = "GV"

    data = ROLE_DATA[role]

    # ── Layout constants ───────────────────────────────────
    CIRCLE_CX  = W // 2
    CIRCLE_CY  = 280
    CIRCLE_R   = 120
    NAME_Y     = CIRCLE_CY + CIRCLE_R + 40
    SUBTITLE_Y = NAME_Y + 80
    SEP_Y      = SUBTITLE_Y + 55
    BULLETS_Y0 = SEP_Y + 40
    BULLET_DY  = 70
    MINIMAP_Y  = BULLETS_Y0 + len(data["bullets"]) * BULLET_DY + 60
    MINIMAP_X  = (W - MINIMAP_SIZE) // 2

    # ── Draw elements ──────────────────────────────────────

    # Animated top glow
    pulse = math.sin(tick * 0.12)
    glow_c = tuple(min(255, v + 20) for v in color)
    for ri in range(6, 0, -1):
        rc = CIRCLE_R + 10 + ri * 12
        alpha_approx = max(5, 30 - ri * 4)
        dark_c = tuple(max(0, v - 180 + ri * 8) for v in color)
        draw.ellipse([CIRCLE_CX-rc, CIRCLE_CY-rc, CIRCLE_CX+rc, CIRCLE_CY+rc],
                     fill=dark_c)

    # Main circle
    initial = data["initial"]
    ltr_font = get_font(88, bold=True) if len(initial) == 1 else get_font(56, bold=True)
    draw_role_circle(draw, CIRCLE_CX, CIRCLE_CY, CIRCLE_R, color, initial, ltr_font)

    # Role name
    name_font = get_font(80, bold=True)
    draw.text((W//2, NAME_Y), role, fill=color, font=name_font, anchor="mm")

    # Subtitle
    sub_font = get_font(40, bold=False)
    draw.text((W//2, SUBTITLE_Y), data["subtitle"], fill=GRAY, font=sub_font, anchor="mm")

    # Count line
    count_font = get_font(32, bold=False)
    draw.text((W//2, SUBTITLE_Y + 44), data["count"], fill=LGRAY, font=count_font, anchor="mm")

    # Separator
    draw_separator(draw, SEP_Y, color)

    # Bullets
    bullet_font = get_font(34, bold=False)
    bx = 90
    for i, bullet in enumerate(data["bullets"]):
        by = BULLETS_Y0 + i * BULLET_DY + 8
        draw_bullet(draw, bx, by, bullet, color, bullet_font, dot_r=7)

    # Minimap label
    map_lbl_font = get_font(28, bold=False)
    draw.text((W//2, MINIMAP_Y - 28), "行動パターン", fill=LGRAY, font=map_lbl_font, anchor="mm")

    # Draw minimap
    minimap_funcs = {
        "Worker":   draw_minimap_worker,
        "Guardian": draw_minimap_guardian,
        "Trader":   draw_minimap_trader,
        "Observer": draw_minimap_observer,
        "Governor": draw_minimap_governor,
    }
    minimap_funcs[role](draw, MINIMAP_X, MINIMAP_Y, MINIMAP_SIZE, color, tick=tick)

    # Progress bar
    bar_w = int((W - 120) * t)
    draw.rectangle([60, H-60, 60+bar_w, H-45], fill=color)
    draw.rectangle([60, H-60, W-60, H-45], outline=LGRAY, width=1)

    # Scene label top-left
    scene_num = ["Worker","Guardian","Trader","Observer","Governor"].index(role) + 2
    scene_font = get_font(24, bold=False)
    draw.text((30, 30), f"Scene {scene_num}/7", fill=LGRAY, font=scene_font)

    return img


def make_closing_frame(tick, total_ticks):
    img = Image.new("RGB", (W, H), BG_DARK)
    draw_gradient_bg(img)
    draw = ImageDraw.Draw(img)
    draw_dot_grid(draw)

    t = tick / max(1, total_ticks - 1)

    # Title
    title_font = get_font(80, bold=True)
    sub_font   = get_font(38, bold=False)
    tag_font   = get_font(30, bold=False)

    draw.text((W//2, 340), "HACS", fill=WHITE, font=get_font(120, bold=True), anchor="mm")
    draw.text((W//2, 460), "自律都市シミュレーション", fill=GRAY, font=sub_font, anchor="mm")

    draw_separator(draw, 530, WHITE, width=500)

    # 5 pillars
    pillars = [
        ("Safety",    "最優先", ROLE_COLOR["Guardian"]),
        ("Stability", "重視",   ROLE_COLOR["Governor"]),
        ("Economy",   "管理",   ROLE_COLOR["Trader"]),
        ("Efficiency","最大化", ROLE_COLOR["Worker"]),
        ("Observe",   "支援",   ROLE_COLOR["Observer"]),
    ]
    py0 = 600
    pf  = get_font(40, bold=True)
    sf  = get_font(28, bold=False)
    for i, (name, desc, col) in enumerate(pillars):
        py = py0 + i * 105
        # Colored box
        draw.rectangle([80, py-4, 86+8, py+44], fill=col)
        draw.text((110, py), name, fill=col, font=pf)
        draw.text((110, py+48), desc, fill=GRAY, font=sf)

    draw_separator(draw, 1150, WHITE, width=500)

    # Role circles
    roles = ["Worker", "Guardian", "Trader", "Observer", "Governor"]
    arc_y = 1260
    for i, role in enumerate(roles):
        sx = W//2 - 240 + i * 120
        col = ROLE_COLOR[role]
        pulse = math.sin(tick * 0.1 + i * 1.2)
        cr = int(38 + 5 * pulse)
        draw.ellipse([sx-cr, arc_y-cr, sx+cr, arc_y+cr], fill=col, outline=WHITE, width=2)
        draw.text((sx, arc_y), role[0], fill=WHITE, font=get_font(30, bold=True), anchor="mm")

    draw.text((W//2, arc_y + 90), "5 つの役職が協調する自律都市", fill=WHITE,
              font=get_font(44, bold=True), anchor="mm")

    # GitHub / URL placeholder
    draw.text((W//2, 1520), "github.com/hacs-sim", fill=LGRAY, font=tag_font, anchor="mm")
    draw.text((W//2, 1570), "#HACS #自律エージェント #シミュレーション",
              fill=LGRAY, font=get_font(26, bold=False), anchor="mm")

    # Progress bar
    bar_w = int((W - 120) * t)
    draw.rectangle([60, H-60, 60+bar_w, H-45], fill=WHITE)
    draw.rectangle([60, H-60, W-60, H-45], outline=LGRAY, width=1)

    return img


# ── Audio generation ──────────────────────────────────────────────────────────
async def generate_audio(text, out_path, voice=VOICE):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_path)


def gen_audio_sync(text, out_path):
    asyncio.run(generate_audio(text, out_path))


# ── Video assembly ────────────────────────────────────────────────────────────
def find_ffmpeg():
    """Find ffmpeg executable."""
    # Check PATH first
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path
    # Try imageio_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    # Common locations
    for p in [
        "C:/ffmpeg/bin/ffmpeg.exe",
        "C:/Program Files/ffmpeg/bin/ffmpeg.exe",
        "ffmpeg",
    ]:
        if os.path.exists(p):
            return p
    return "ffmpeg"


def write_video_frames(frames, video_path, fps=FPS):
    """Write list of PIL Images as raw video using ffmpeg."""
    ffmpeg = find_ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{W}x{H}",
        "-pix_fmt", "rgb24",
        "-r", str(fps),
        "-i", "pipe:0",
        "-c:v", "libx264",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        video_path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    for frame in frames:
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()


def combine_video_audio(video_path, audio_path, out_path, pad_audio=True):
    """Merge silent video with audio using ffmpeg."""
    ffmpeg = find_ffmpeg()
    # shortest flag: trim to the shorter of video/audio
    cmd = [
        ffmpeg, "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        out_path,
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def concat_videos(video_paths, out_path, tmp_dir):
    """Concatenate multiple mp4 files using ffmpeg concat demuxer."""
    ffmpeg = find_ffmpeg()
    list_file = os.path.join(tmp_dir, "concat_list.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for vp in video_paths:
            # Use forward slashes or escaped backslashes
            vp_escaped = vp.replace("\\", "/")
            f.write(f"file '{vp_escaped}'\n")
    cmd = [
        ffmpeg, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        out_path,
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


# ── Scene builder ─────────────────────────────────────────────────────────────
def build_scene(scene_name, frame_gen_fn, narration_text, tmp_dir, scene_idx):
    """Generate frames, audio, then merge for one scene."""
    duration = SCENE_DURATIONS[scene_name]
    total_frames = duration * FPS

    print(f"  Generating {total_frames} frames for scene '{scene_name}'...")
    frames = []
    for tick in range(total_frames):
        frame = frame_gen_fn(tick, total_frames)
        frames.append(frame)

    # Write video (no audio)
    silent_path = os.path.join(tmp_dir, f"scene_{scene_idx:02d}_silent.mp4")
    write_video_frames(frames, silent_path)

    # Generate audio
    audio_path = os.path.join(tmp_dir, f"scene_{scene_idx:02d}_audio.mp3")
    print(f"  Generating narration audio for '{scene_name}'...")
    gen_audio_sync(narration_text, audio_path)

    # Combine
    scene_out = os.path.join(tmp_dir, f"scene_{scene_idx:02d}.mp4")
    combine_video_audio(silent_path, audio_path, scene_out)

    print(f"  Scene '{scene_name}' done -> {scene_out}")
    return scene_out


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=== HACS Character Introduction Video ===")
    print(f"Output: {OUT}")
    print(f"Resolution: {W}x{H}, FPS: {FPS}")
    print()

    # Ensure output directory exists
    out_dir = os.path.dirname(OUT)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    tmp_dir = tempfile.mkdtemp(prefix="hacs_char_vid_")
    print(f"Temp directory: {tmp_dir}")
    print()

    try:
        scene_files = []
        scene_idx = 0

        # Scene 1 - Opening
        print(f"[{scene_idx+1}/7] Opening scene...")
        sf = build_scene(
            "opening",
            lambda tick, total: make_opening_frame(tick, total),
            NARRATION["opening"],
            tmp_dir, scene_idx,
        )
        scene_files.append(sf)
        scene_idx += 1

        # Scenes 2-6: Character scenes
        roles_order = ["Worker", "Guardian", "Trader", "Observer", "Governor"]
        for role in roles_order:
            print(f"[{scene_idx+1}/7] {role} scene...")
            role_cap = role  # closure capture
            sf = build_scene(
                role,
                lambda tick, total, r=role_cap: make_role_frame(tick, total, r),
                NARRATION[role],
                tmp_dir, scene_idx,
            )
            scene_files.append(sf)
            scene_idx += 1

        # Scene 7 - Closing
        print(f"[{scene_idx+1}/7] Closing scene...")
        sf = build_scene(
            "closing",
            lambda tick, total: make_closing_frame(tick, total),
            NARRATION["closing"],
            tmp_dir, scene_idx,
        )
        scene_files.append(sf)
        scene_idx += 1

        # Concatenate all scenes
        print()
        print("Concatenating all scenes...")
        final_path = os.path.abspath(OUT)
        concat_videos(scene_files, final_path, tmp_dir)

        print()
        print(f"=== Done! Output: {final_path} ===")

    finally:
        print(f"Cleaning up temp directory: {tmp_dir}")
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
