# main.py
# -*- coding: utf-8 -*-
"""
主程式: 使用 Pygame 載入 map.json，呈現 16x7 地圖背景並繪製物件與動態角色
可設定視窗寬度，高度將等比例縮放
並確保物件與角色下方永遠是石磚地板

增加 WASD 平滑連續移動與走路動畫功能：
- 支援按鍵佇列，依先後順序移動
- 長按自動重複，產生連續移動效果
- 行走時以方向動畫貼圖切換，每 0.02 秒更新一次
- 停止移動後保持最後動畫貼圖 0.8 秒，之後才切回待機貼圖
- 阻止玩家移動到岩漿 (物件編號 "200")
- 當玩家站在 lava_block 中指定的格子，禁用對應方向鍵 (left->D, right->A, top->S, bottom->W)
"""
import pygame
import json
import os
import collections

# 平滑移動設定
MOVE_SPEED = 200       # 像素/秒
ANIM_INTERVAL = 0.02   # 動畫切換間隔 (秒)
IDLE_DELAY = 0.8       # 停止移動後回到待機貼圖的延遲時間 (秒)
LAVA_TILE = "200"     # 岩漿物件編號

# 鍵位對應方向 (dx, dy)
KEY_DIR_MAP = {
    pygame.K_w: (0, 1),  # 上
    pygame.K_s: (0, -1), # 下
    pygame.K_a: (-1, 0), # 左
    pygame.K_d: (1, 0),  # 右
}

# 玩家貼圖編號與動畫貼圖
IDLE_TILE = "300"
ANIM_TILES = {
    (0, 1): ["310", "311"],    # 上走
    (1, 0): ["320", "321"],    # 右走
    (-1, 0): ["330", "331"],   # 左走
    (0, -1): ["340", "341"],   # 下走
}

# lava_block 禁用鍵位對應
DISABLE_KEY = {
    'left': pygame.K_d,
    'right': pygame.K_a,
    'top': pygame.K_s,
    'bottom': pygame.K_w,
}

def main():
    pygame.init()
    pygame.key.set_repeat(200, 150)  # 長按重複 KEYDOWN

    # 讀取地圖 JSON
    with open("map.json", "r", encoding="utf-8") as f:
        map_data = json.load(f)
    background = map_data.get("background", [])
    objects = map_data.get("objects", [])
    lava_block = map_data.get("lava_block", {})

    # 解析 lava_block 中的格子集合
    side_sets = {}
    for side in ['left', 'right', 'top', 'bottom']:
        coords = lava_block.get(side, [])
        side_sets[side] = {(c['x'], c['y']) for c in coords}

    # 玩家起始格子座標
    start_tile_x, start_tile_y = 1, 2

    # 建立岩漿位置集合
    lava_positions = {(o['x'], o['y']) for o in objects if o['type'] == LAVA_TILE}

    ORIGINAL_TILE_SIZE = 500
    MAP_COLS = len(background[0])
    MAP_ROWS = len(background)
    DESIRED_WIDTH = 800
    scale = DESIRED_WIDTH / (ORIGINAL_TILE_SIZE * MAP_COLS)
    tile_size = int(ORIGINAL_TILE_SIZE * scale)
    SCREEN_WIDTH = DESIRED_WIDTH
    SCREEN_HEIGHT = int(ORIGINAL_TILE_SIZE * MAP_ROWS * scale)

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("平滑連續移動與走路動畫 (WASD)")

    # 載入所有圖檔
    images = {}
    tile_ids = set()
    for row in background:
        tile_ids.update(row)
    for o in objects:
        tile_ids.add(o['type'])
    tile_ids.add(IDLE_TILE)
    for frames in ANIM_TILES.values():
        tile_ids.update(frames)
    for tid in tile_ids:
        path = os.path.join("images", f"{tid}.png")
        img = pygame.image.load(path).convert_alpha()
        images[tid] = pygame.transform.scale(img, (tile_size, tile_size))

    FLOOR_TILE = "000"
    object_positions = {(o['x'], o['y']) for o in objects}

    # 玩家初始格子與像素位置
    player_tile_x, player_tile_y = start_tile_x, start_tile_y
    player_px = player_tile_x * tile_size
    player_py = (MAP_ROWS - 1 - player_tile_y) * tile_size
    target_px, target_py = player_px, player_py
    moving = False

    # 動畫與狀態
    last_dir = (0, 0)
    anim_timer = 0.0
    anim_index = 0
    idle_timer = IDLE_DELAY

    dir_queue = collections.deque()
    clock = pygame.time.Clock()
    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key in KEY_DIR_MAP:
                # 檢查當前格子是否有禁用該鍵
                pos = (player_tile_x, player_tile_y)
                disabled = False
                for side, coords in side_sets.items():
                    if pos in coords and event.key == DISABLE_KEY[side]:
                        disabled = True
                        break
                if not disabled:
                    dir_queue.append(KEY_DIR_MAP[event.key])

        # 處理移動佇列
        if not moving and dir_queue:
            dx, dy = dir_queue.popleft()
            nx = player_tile_x + dx
            ny = player_tile_y + dy
            # 邊界檢查與岩漿阻擋
            if 0 <= nx < MAP_COLS and 0 <= ny < MAP_ROWS and (nx, ny) not in lava_positions:
                player_tile_x, player_tile_y = nx, ny
                target_px = player_tile_x * tile_size
                target_py = (MAP_ROWS - 1 - player_tile_y) * tile_size
                moving = True
                last_dir = (dx, dy)
                anim_timer = 0.0
                anim_index = 0
                idle_timer = 0.0

        # 平滑移動邏輯...
        if moving:
            # 同之前邏輯
            diff_x = target_px - player_px
            player_px += max(-MOVE_SPEED*dt, min(MOVE_SPEED*dt, diff_x))
            diff_y = target_py - player_py
            player_py += max(-MOVE_SPEED*dt, min(MOVE_SPEED*dt, diff_y))
            if player_px == target_px and player_py == target_py:
                moving = False

        # 動畫更新邏輯...
        if moving:
            anim_timer += dt
            if anim_timer >= ANIM_INTERVAL:
                anim_timer -= ANIM_INTERVAL
                frames = ANIM_TILES.get(last_dir, [])
                anim_index = (anim_index + 1) % len(frames)
            current_tile = ANIM_TILES.get(last_dir, [IDLE_TILE])[anim_index]
            idle_timer = 0.0
        else:
            idle_timer += dt
            if idle_timer >= IDLE_DELAY:
                current_tile = IDLE_TILE
            else:
                frames = ANIM_TILES.get(last_dir, [])
                current_tile = frames[anim_index] if frames else IDLE_TILE

        # 繪製背景、物件與玩家
        screen.fill((0, 0, 0))
        floor_positions = object_positions.union({(player_tile_x, player_tile_y)})
        for ry, row in enumerate(background):
            for rx, tid in enumerate(row):
                use_tid = FLOOR_TILE if (rx, ry) in floor_positions else tid
                screen.blit(images[use_tid], (rx*tile_size, (MAP_ROWS-1-ry)*tile_size))
        for o in objects:
            screen.blit(images[o['type']], (o['x']*tile_size, (MAP_ROWS-1-o['y'])*tile_size))
        screen.blit(images[current_tile], (player_px, player_py))

        pygame.display.flip()

    pygame.quit()

if __name__ == '__main__':
    main()
