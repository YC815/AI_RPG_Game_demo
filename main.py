# main.py
# -*- coding: utf-8 -*-
"""
主程式: 使用 Pygame 載入 map.json，呈現 16x7 地圖背景並繪製動態角色
並在畫面下方新增輸入區與綠色 Send 按鈕，實作 LLM 串接：
- 過濾空訊息
- 從 prompt.txt 載入提示詞
- 呼叫 OpenAI API (v1介面) 並解析 JSON
- 自動執行移動或輸出對話
支持繁體中文注音輸入 (IME)。
"""
import pygame
import json
import os
import collections
import re
import openai

# 載入 Prompt
with open("prompt.txt", "r", encoding="utf-8") as pf:
    PROMPT_TEMPLATE = pf.read().strip()
# API 設定: 使用 openai-python v1 客戶端
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-4o"

# 移動設定
ENABLE_MOVEMENT = True  # 控制是否允許 WASD 或 AI 指令移動
MOVE_SPEED = 200
ANIM_INTERVAL = 0.02
IDLE_DELAY = 0.8
LAVA_TILE = "200"
# 玩家動畫定義
IDLE_TILE = "300"
ANIM_TILES = {(0,1):["310","311"], (1,0):["320","321"], (-1,0):["330","331"], (0,-1):["340","341"]}
# 鍵位對應方向
KEY_DIR_MAP = {pygame.K_w:(0,1), pygame.K_s:(0,-1), pygame.K_a:(-1,0), pygame.K_d:(1,0)}
# lava_block 禁用鍵位
DISABLE_KEY = {'left':pygame.K_d,'right':pygame.K_a,'top':pygame.K_s,'bottom':pygame.K_w}

# UI 參數
UI_HEIGHT = 100
FONT_SIZE = 24
FONT_PATH = "font/Cubic_11.ttf"
FONT_NAME = None
INPUT_PADDING = 10
BUTTON_WIDTH = 100
BUTTON_HEIGHT = 40
BUTTON_COLOR = (0,200,0)
BUTTON_TEXT_COLOR = (255,255,255)

# 過濾空白或純標點
IGNORE_RE = re.compile(r"^\s*$")

# 呼叫 OpenAI 並解析 JSON
def call_openai(user_input, position):
    messages = [
        {"role": "system", "content": PROMPT_TEMPLATE},
        {"role": "user", "content": f"{{\"x\":{position['x']},\"y\":{position['y']}}} {user_input}"}
    ]
    resp = client.chat.completions.create(model=MODEL, messages=messages)
    text = resp.choices[0].message.content.strip()
    # 移除 Markdown code fences
    text = re.sub(r"```(?:json)?", "", text)
    text = text.replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"mode": "error", "content": text}


def main():
    pygame.init()
    pygame.key.set_repeat(200,150)
    pygame.key.start_text_input()

    # 載入字體
    if FONT_PATH and os.path.exists(FONT_PATH):
        font = pygame.font.Font(FONT_PATH, FONT_SIZE)
    elif FONT_NAME:
        font = pygame.font.SysFont(FONT_NAME, FONT_SIZE)
    else:
        font = pygame.font.Font(None, FONT_SIZE)

    # 讀取 map.json
    with open("map.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    background = data.get("background", [])
    objects = data.get("objects", [])
    lava_block = data.get("lava_block", {})
    cols, rows = len(background[0]), len(background)

    # 初始化 pygame 視窗
    screen_w = 800
    tile_px = int(500 * (screen_w / (16*500)))
    screen_h = rows * tile_px + UI_HEIGHT
    screen = pygame.display.set_mode((screen_w, screen_h))
    pygame.display.set_caption("遊戲 + LLM 輸入介面")

    # 載入圖像資源
    images = {}
    ids = set(sum(background, []))
    ids.update(o['type'] for o in objects)
    ids.add(IDLE_TILE)
    for frames in ANIM_TILES.values(): ids.update(frames)
    for tid in ids:
        img = pygame.image.load(os.path.join("images", f"{tid}.png")).convert_alpha()
        images[tid] = pygame.transform.scale(img, (tile_px, tile_px))
    lava_pos = {(o['x'], o['y']) for o in objects if o['type'] == LAVA_TILE}
    object_pos = {(o['x'], o['y']) for o in objects}

    # 玩家位置狀態
    tile_x, tile_y = 1, 2
    player_pos = {'x': tile_x, 'y': tile_y}
    move_queue = collections.deque()

    # 輸入框與按鈕
    input_text = ''
    input_rect = pygame.Rect(INPUT_PADDING, screen_h-UI_HEIGHT+INPUT_PADDING,
                              screen_w-3*INPUT_PADDING-BUTTON_WIDTH, BUTTON_HEIGHT)
    button_rect = pygame.Rect(screen_w-INPUT_PADDING-BUTTON_WIDTH,
                               screen_h-UI_HEIGHT+(UI_HEIGHT-BUTTON_HEIGHT)//2,
                               BUTTON_WIDTH, BUTTON_HEIGHT)

    clock = pygame.time.Clock()
    running = True
    while running:
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
                    # 按 Enter 送出
                    if input_text.strip() and not IGNORE_RE.match(input_text):
                        result = call_openai(input_text, player_pos)
                        # 處理 move 或 talk
                        if result.get("mode") == "move" and ENABLE_MOVEMENT:
                            for step in result.get("steps", []):
                                dx, dy = {"up":(0,1),"down":(0,-1),"left":(-1,0),"right":(1,0)}[step["dir"]]
                                for _ in range(step.get("times",1)):
                                    move_queue.append((dx, dy))
                        elif result.get("mode") == "talk":
                            print("NPC說：", result.get("content"))
                        else:
                            print("API 回傳：", result)
                    input_text = ''
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if button_rect.collidepoint(e.pos):
                    # 按鈕送出同上
                    if input_text.strip() and not IGNORE_RE.match(input_text):
                        result = call_openai(input_text, player_pos)
                        if result.get("mode") == "move" and ENABLE_MOVEMENT:
                            for step in result.get("steps", []):
                                dx, dy = {"up":(0,1),"down":(0,-1),"left":(-1,0),"right":(1,0)}[step["dir"]]
                                for _ in range(step.get("times",1)):
                                    move_queue.append((dx, dy))
                        elif result.get("mode") == "talk":
                            print("NPC說：", result.get("content"))
                        else:
                            print("API 回傳：", result)
                    input_text = ''

        # 執行佇列移動
        if ENABLE_MOVEMENT and move_queue:
            dx, dy = move_queue.popleft()
            nx, ny = player_pos['x']+dx, player_pos['y']+dy
            if 0 <= nx < cols and 0 <= ny < rows and (nx, ny) not in lava_pos:
                player_pos['x'], player_pos['y'] = nx, ny

        # 繪製地圖和玩家
        screen.fill((0,0,0))
        floor = object_pos.union({(player_pos['x'], player_pos['y'])})
        for ry, row in enumerate(background):
            for rx, tid in enumerate(row):
                use = '000' if (rx,ry) in floor else tid
                screen.blit(images[use], (rx*tile_px, (rows-1-ry)*tile_px))
        for o in objects:
            screen.blit(images[o['type']], (o['x']*tile_px, (rows-1-o['y'])*tile_px))
        # 玩家待機貼圖
        screen.blit(images[IDLE_TILE], (player_pos['x']*tile_px, (rows-1-player_pos['y'])*tile_px))

        # 繪製 UI 區域
        pygame.draw.rect(screen, (50,50,50), (0, screen_h-UI_HEIGHT, screen_w, UI_HEIGHT))
        pygame.draw.rect(screen, (255,255,255), input_rect)
        text_surf = font.render(input_text, True, (0,0,0))
        screen.blit(text_surf, (input_rect.x+5, input_rect.y+5))
        pygame.draw.rect(screen, BUTTON_COLOR, button_rect)
        btn_surf = font.render('Send', True, BUTTON_TEXT_COLOR)
        screen.blit(btn_surf, (button_rect.x+(BUTTON_WIDTH-btn_surf.get_width())//2,
                              button_rect.y+(BUTTON_HEIGHT-btn_surf.get_height())//2))
        pygame.display.flip()

    pygame.quit()
    pygame.key.stop_text_input()

if __name__ == '__main__':
    main()
