# main.py
# -*- coding: utf-8 -*-
"""
主程式: 使用 Pygame 載入 map.json，呈現 16x7 地圖背景並繪製動態角色
並在畫面下方新增輸入區與綠色 Send 按鈕，供未來 LLM 串接使用
支持繁體中文注音輸入 (IME)

若要自訂字體，可透過設定 FONT_PATH 或 FONT_NAME
"""
import pygame
import json
import os
import collections

# 平滑移動設定
MOVE_SPEED = 200       # 像素/秒
ANIM_INTERVAL = 0.02   # 動畫切換間隔 (秒)
IDLE_DELAY = 0.8       # 停止移動後切回待機貼圖延遲 (秒)
LAVA_TILE = "200"     # 岩漿物件編號

# 鍵位對應方向
KEY_DIR_MAP = {
    pygame.K_w: (0, 1),
    pygame.K_s: (0, -1),
    pygame.K_a: (-1, 0),
    pygame.K_d: (1, 0),
}

# 玩家貼圖編號與動畫貼圖
IDLE_TILE = "300"
ANIM_TILES = {
    (0, 1): ["310", "311"],
    (1, 0): ["320", "321"],
    (-1, 0): ["330", "331"],
    (0, -1): ["340", "341"],
}

# 禁用鍵位映射
DISABLE_KEY = {
    'left': pygame.K_d,
    'right': pygame.K_a,
    'top': pygame.K_s,
    'bottom': pygame.K_w,
}

# UI 參數
UI_HEIGHT = 100
FONT_SIZE = 24
# 如有 .ttf 字型檔，可放在專案根目錄並指定路徑
FONT_PATH = "font/Cubic_11.ttf"  # 或 None
# 如想使用系統字型，填入字型名稱，如 "Microsoft JhengHei"
FONT_NAME = None
INPUT_PADDING = 10
BUTTON_WIDTH = 100
BUTTON_HEIGHT = 40
BUTTON_COLOR = (0, 200, 0)
BUTTON_TEXT_COLOR = (255, 255, 255)


def main():
    pygame.init()
    pygame.key.set_repeat(200, 150)
    pygame.key.start_text_input()

    # 字體載入：優先使用 FONT_PATH，其次使用 FONT_NAME，否則預設
    if FONT_PATH and os.path.exists(FONT_PATH):
        font = pygame.font.Font(FONT_PATH, FONT_SIZE)
    elif FONT_NAME:
        font = pygame.font.SysFont(FONT_NAME, FONT_SIZE)
    else:
        font = pygame.font.Font(None, FONT_SIZE)

    # 讀取地圖 JSON
    with open("map.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    background = data.get("background", [])
    objects = data.get("objects", [])
    lava_block = data.get("lava_block", {})

    # 解析 lava_block
    block_sets = {side: {(c['x'], c['y']) for c in lava_block.get(side, [])}
                   for side in ['left','right','top','bottom']}

    # 地圖尺寸
    ORIGINAL_TILE = 500
    cols = len(background[0]); rows = len(background)
    game_w = cols * ORIGINAL_TILE; game_h = rows * ORIGINAL_TILE
    DESIRED_W = 800
    scale = DESIRED_W / game_w
    tile_size = int(ORIGINAL_TILE * scale)
    screen_w = DESIRED_W; screen_h = int(game_h * scale) + UI_HEIGHT

    screen = pygame.display.set_mode((screen_w, screen_h))
    pygame.display.set_caption("遊戲 + 注音輸入介面")

    # 載入圖檔
    images = {}
    ids = set(sum(background, []))
    ids.update(o['type'] for o in objects)
    ids.add(IDLE_TILE)
    for frames in ANIM_TILES.values(): ids.update(frames)
    for tid in ids:
        img = pygame.image.load(os.path.join("images", f"{tid}.png")).convert_alpha()
        images[tid] = pygame.transform.scale(img, (tile_size, tile_size))

    lava_pos = {(o['x'], o['y']) for o in objects if o['type'] == LAVA_TILE}
    object_pos = {(o['x'], o['y']) for o in objects}

    # 玩家初始位置
    tile_x, tile_y = 1, 2
    px = tile_x * tile_size; py = (rows - 1 - tile_y) * tile_size
    tgt_x, tgt_y = px, py; moving=False
    last_dir=(0,0); anim_t=0; anim_i=0; idle_t=IDLE_DELAY
    queue = collections.deque()

    # 輸入框與按鈕
    input_text = ''
    input_rect = pygame.Rect(
        INPUT_PADDING,
        screen_h - UI_HEIGHT + INPUT_PADDING,
        screen_w - 3*INPUT_PADDING - BUTTON_WIDTH,
        BUTTON_HEIGHT
    )
    button_rect = pygame.Rect(
        screen_w - INPUT_PADDING - BUTTON_WIDTH,
        screen_h - UI_HEIGHT + (UI_HEIGHT - BUTTON_HEIGHT)//2,
        BUTTON_WIDTH, BUTTON_HEIGHT
    )

    clock = pygame.time.Clock(); running=True
    while running:
        dt = clock.tick(60)/1000
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.TEXTINPUT:
                if input_rect.collidepoint(pygame.mouse.get_pos()):
                    input_text += e.text
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_BACKSPACE:
                    input_text = input_text[:-1]
                elif e.key == pygame.K_RETURN:
                    print("送出:", input_text)
                    input_text = ''
                elif e.key in KEY_DIR_MAP and not input_rect.collidepoint(pygame.mouse.get_pos()):
                    pos = (tile_x, tile_y)
                    disabled = any(
                        pos in block_sets[side] and e.key == DISABLE_KEY[side]
                        for side in block_sets
                    )
                    if not disabled:
                        queue.append(KEY_DIR_MAP[e.key])
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if button_rect.collidepoint(e.pos):
                    print("Send 點擊:", input_text)
                    input_text = ''

        # 處理移動
        if not moving and queue:
            dx, dy = queue.popleft()
            nx, ny = tile_x + dx, tile_y + dy
            if 0 <= nx < cols and 0 <= ny < rows and (nx, ny) not in lava_pos:
                tile_x, tile_y = nx, ny
                tgt_x = tile_x * tile_size; tgt_y = (rows - 1 - tile_y) * tile_size
                moving=True; last_dir=(dx,dy); anim_t=0; anim_i=0; idle_t=0
        if moving:
            diff_x, diff_y = tgt_x - px, tgt_y - py
            px += max(-MOVE_SPEED*dt, min(MOVE_SPEED*dt, diff_x))
            py += max(-MOVE_SPEED*dt, min(MOVE_SPEED*dt, diff_y))
            if px == tgt_x and py == tgt_y: moving=False

        # 動畫更新
        if moving:
            anim_t += dt
            if anim_t >= ANIM_INTERVAL:
                anim_t -= ANIM_INTERVAL
                frames = ANIM_TILES.get(last_dir, [])
                anim_i = (anim_i + 1) % len(frames)
            curr = ANIM_TILES.get(last_dir, [IDLE_TILE])[anim_i]
            idle_t = 0
        else:
            idle_t += dt
            if idle_t >= IDLE_DELAY:
                curr = IDLE_TILE
            else:
                frames = ANIM_TILES.get(last_dir, [])
                curr = frames[anim_i] if frames else IDLE_TILE

        # 繪製遊戲畫面
        screen.fill((0,0,0))
        floor = object_pos.union({(tile_x, tile_y)})
        for ry, row in enumerate(background):
            for rx, tid in enumerate(row):
                use = "000" if (rx,ry) in floor else tid
                screen.blit(images[use], (rx*tile_size, (rows-1-ry)*tile_size))
        for o in objects:
            screen.blit(images[o['type']], (o['x']*tile_size, (rows-1-o['y'])*tile_size))
        screen.blit(images[curr], (px, py))

        # 繪製 UI 區域
        pygame.draw.rect(screen, (50,50,50), (0, screen_h-UI_HEIGHT, screen_w, UI_HEIGHT))
        pygame.draw.rect(screen, (255,255,255), input_rect)
        text_surf = font.render(input_text, True, (0,0,0))
        screen.blit(text_surf, (input_rect.x+5, input_rect.y+5))
        pygame.draw.rect(screen, BUTTON_COLOR, button_rect)
        btn = font.render('Send', True, BUTTON_TEXT_COLOR)
        bx = button_rect.x + (BUTTON_WIDTH-btn.get_width())//2
        by = button_rect.y + (BUTTON_HEIGHT-btn.get_height())//2
        screen.blit(btn, (bx, by))

        pygame.display.flip()

    pygame.quit()
    pygame.key.stop_text_input()

if __name__ == '__main__':
    main()
