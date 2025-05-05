# main.py
# -*- coding: utf-8 -*-
"""
主程式: 使用 Pygame 載入 map.json，呈現 16x7 地圖背景並繪製物件與動態角色
可設定視窗寬度，高度將等比例縮放
並確保物件與角色下方永遠是石磚地板

增加 WASD 平滑移動功能
"""
import pygame
import json
import os

# 平滑移動設定
MOVE_SPEED = 200  # 像素/秒 確定每秒移動距離

def main():
    # 初始化 Pygame
    pygame.init()

    # 讀取 map.json
    with open("map.json", "r", encoding="utf-8") as f:
        map_data = json.load(f)
    background = map_data.get("background", [])
    objects = map_data.get("objects", [])

    # --- 在程式端定義玩家（player）格子座標 ---
    PLAYER_TILE = "300"
    start_tile_x, start_tile_y = 1, 2  # 起始格子位置

    # 原始圖塊設定
    ORIGINAL_TILE_SIZE = 500  # 原始圖塊像素
    MAP_COLS = len(background[0])
    MAP_ROWS = len(background)

    # 設定視窗寬度與等比例縮放
    DESIRED_WIDTH = 800
    scale = DESIRED_WIDTH / (ORIGINAL_TILE_SIZE * MAP_COLS)
    SCREEN_WIDTH = DESIRED_WIDTH
    SCREEN_HEIGHT = int(ORIGINAL_TILE_SIZE * MAP_ROWS * scale)
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("地圖與角色平滑移動 (WASD 控制)")

    # 每格顯示大小
    tile_size = int(ORIGINAL_TILE_SIZE * scale)

    # 載入並縮放所有圖片
    images = {}
    tile_ids = set()
    for row in background:
        tile_ids.update(row)
    for o in objects:
        tile_ids.add(o["type"])
    tile_ids.add(PLAYER_TILE)
    for tid in tile_ids:
        path = os.path.join("images", f"{tid}.png")
        img = pygame.image.load(path).convert_alpha()
        images[tid] = pygame.transform.scale(img, (tile_size, tile_size))

    # 石磚地板編號
    FLOOR_TILE = "000"
    object_positions = {(o['x'], o['y']) for o in objects}

    # 玩家像素與格子位置
    player_tile_x, player_tile_y = start_tile_x, start_tile_y
    # 初始時 pixel 位置置中
    player_px = player_tile_x * tile_size
    player_py = (MAP_ROWS - 1 - player_tile_y) * tile_size
    # 移動目標 pixel
    target_px, target_py = player_px, player_py
    moving = False

    clock = pygame.time.Clock()
    running = True

    while running:
        dt = clock.tick(60) / 1000.0  # delta time (秒)
        # 處理事件
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and not moving:
                # 只在不移動時接受新方向鍵
                dx, dy = 0, 0
                if event.key == pygame.K_w:
                    dy = 1
                elif event.key == pygame.K_s:
                    dy = -1
                elif event.key == pygame.K_a:
                    dx = -1
                elif event.key == pygame.K_d:
                    dx = 1
                nx = player_tile_x + dx
                ny = player_tile_y + dy
                # 檢查邊界與物件阻礙（可加入障礙邏輯）
                if 0 <= nx < MAP_COLS and 0 <= ny < MAP_ROWS:
                    player_tile_x, player_tile_y = nx, ny
                    # 計算目標像素座標 (Pygame 原點在左上)
                    target_px = player_tile_x * tile_size
                    target_py = (MAP_ROWS - 1 - player_tile_y) * tile_size
                    moving = True
        # 平滑插值移動
        if moving:
            # X 軸移動
            if abs(target_px - player_px) < MOVE_SPEED * dt:
                player_px = target_px
            else:
                player_px += MOVE_SPEED * dt * ((target_px - player_px) / abs(target_px - player_px))
            # Y 軸移動
            if abs(target_py - player_py) < MOVE_SPEED * dt:
                player_py = target_py
            else:
                player_py += MOVE_SPEED * dt * ((target_py - player_py) / abs(target_py - player_py))
            # 檢查是否到達目標
            if player_px == target_px and player_py == target_py:
                moving = False

        # 重新繪製畫面
        screen.fill((0,0,0))
        # floor_positions 包含物件與玩家當前格子
        # 當移動中，也確保目標格鋪底
        floor_positions = object_positions.union({(player_tile_x, player_tile_y)})
        for ry, row in enumerate(background):
            for rx, tid in enumerate(row):
                use_tid = FLOOR_TILE if (rx, ry) in floor_positions else tid
                x = rx * tile_size
                y = (MAP_ROWS - 1 - ry) * tile_size
                screen.blit(images[use_tid], (x, y))
        # 繪製物件
        for o in objects:
            ox = o['x'] * tile_size
            oy = (MAP_ROWS - 1 - o['y']) * tile_size
            screen.blit(images[o['type']], (ox, oy))
        # 繪製玩家
        screen.blit(images[PLAYER_TILE], (player_px, player_py))

        pygame.display.flip()

    pygame.quit()

if __name__ == '__main__':
    main()