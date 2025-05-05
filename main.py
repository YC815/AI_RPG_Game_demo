# main.py
# -*- coding: utf-8 -*-
"""
主程式: 使用 Pygame 載入 map.json，呈現 16x7 地圖背景並繪製動態角色
並在畫面下方新增：
  - 上方輸入區與綠色 Send 按鈕
  - 下方錯誤顯示區 (error box)
供未來 LLM 串接使用，並支持繁體中文注音輸入 (IME) 及平滑移動動畫。
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
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-4o"

# 移動與動畫
ENABLE_MOVEMENT = True
MOVE_SPEED = 200       # 像素/秒
ANIM_INTERVAL = 0.02   # 動畫切換間隔 (秒)
IDLE_DELAY = 0.8       # 停止後延遲切回
LAVA_TILE = "200"
IDLE_TILE = "300"
ANIM_TILES = {
    (0, 1): ["310", "311"],
    (1, 0): ["320", "321"],
    (-1, 0): ["330", "331"],
    (0, -1): ["340", "341"],
}
KEY_DIR_MAP = {pygame.K_w:(0,1), pygame.K_s:(0,-1), pygame.K_a:(-1,0), pygame.K_d:(1,0)}

# UI 參數
INPUT_HEIGHT = 50
ERROR_HEIGHT = 50
UI_HEIGHT = INPUT_HEIGHT + ERROR_HEIGHT
FONT_SIZE = 24
FONT_PATH = "font/Cubic_11.ttf"
FONT_NAME = None
INPUT_PADDING = 10
BUTTON_WIDTH = 100
BUTTON_HEIGHT = 30
BUTTON_COLOR = (0,200,0)
BUTTON_TEXT_COLOR = (255,255,255)
ERROR_BG = (80,80,80)
ERROR_TEXT_COLOR = (255,0,0)

IGNORE_RE = re.compile(r"^\s*$")

# 呼叫 LLM
def call_openai(user_input, position, can_talk):
    # 強制 JSON-only 模式
    json_mode_instruction = "請僅回傳純 JSON 格式，勿額外說明或文字。"
    messages = [
        {"role":"system","content":PROMPT_TEMPLATE},
        {"role":"system","content":json_mode_instruction},
        {"role":"user","content":(
            f"{{\"x\":{position['x']},\"y\":{position['y']},"
            f"\"can_talk\":{str(can_talk).lower()}}} {user_input}"
        )}
    ]
    resp = client.chat.completions.create(model=MODEL, messages=messages)
    # 印出 API 原始回傳 content
    raw_text = resp.choices[0].message.content
    print("LLM 原始回傳內容：", raw_text)
    text = resp.choices[0].message.content.strip()
    text = re.sub(r"```(?:json)?", "", text).replace("```","\n").strip()
    try:
        return json.loads(text)
    except:
        return {"mode":"error","content":text}


def main():
    pygame.init()
    pygame.key.set_repeat(200,150)
    pygame.key.start_text_input()

    # 字體
    if FONT_PATH and os.path.exists(FONT_PATH): font = pygame.font.Font(FONT_PATH, FONT_SIZE)
    elif FONT_NAME: font = pygame.font.SysFont(FONT_NAME, FONT_SIZE)
    else: font = pygame.font.Font(None, FONT_SIZE)

    # 讀地圖
    with open("map.json","r",encoding="utf-8") as f: data = json.load(f)
    bg = data.get("background",[])
    objects = data.get("objects",[])
    npc_positions = {(c['x'],c['y']) for c in data.get('npc',[])}
    cols,rows = len(bg[0]),len(bg)

    # 視窗
    w = 800
    tile = int(500*(w/(16*500)))
    h = rows*tile + UI_HEIGHT
    screen = pygame.display.set_mode((w,h))
    pygame.display.set_caption("遊戲 + 錯誤顯示介面")

    # 圖片
    images={}
    ids = set(sum(bg,[]))|{o['type'] for o in objects}|{IDLE_TILE}
    for fr in ANIM_TILES.values(): ids|=set(fr)
    for tid in ids:
        img=pygame.image.load(os.path.join("images",f"{tid}.png")).convert_alpha()
        images[tid]=pygame.transform.scale(img,(tile,tile))
    lava_set={(o['x'],o['y'])for o in objects if o['type']==LAVA_TILE}
    obj_set={(o['x'],o['y'])for o in objects}

    # 玩家
    tx,ty=1,2
    pos={'x':tx,'y':ty}
    px,py=tx*tile,(rows-1-ty)*tile
    q=collections.deque()
    moving=False;ld=(0,0);anim_t=0;anim_i=0;idle_t=IDLE_DELAY
    tpx,tpy=px,py

    # UI
    input_text=''
    input_rect=pygame.Rect(INPUT_PADDING,h-UI_HEIGHT+INPUT_PADDING,w-3*INPUT_PADDING-BUTTON_WIDTH, BUTTON_HEIGHT)
    btn_rect=pygame.Rect(w-INPUT_PADDING-BUTTON_WIDTH,h-UI_HEIGHT+(INPUT_HEIGHT-BUTTON_HEIGHT)//2,BUTTON_WIDTH,BUTTON_HEIGHT)
    error_msg=''

    clock=pygame.time.Clock();run=True
    while run:
        dt=clock.tick(60)/1000
        for e in pygame.event.get():
            if e.type==pygame.QUIT: run=False
            elif e.type==pygame.TEXTINPUT and input_rect.collidepoint(pygame.mouse.get_pos()): input_text+=e.text
            elif e.type==pygame.KEYDOWN:
                if e.key==pygame.K_BACKSPACE: input_text=input_text[:-1]
                elif e.key==pygame.K_RETURN:
                    if input_text.strip() and not IGNORE_RE.match(input_text):
                        ct=(pos['x'],pos['y']) in npc_positions
                        res=call_openai(input_text,pos,ct)
                        if res.get('mode')=='move' and ENABLE_MOVEMENT:
                            error_msg='';
                            for st in res['steps']:
                                dx,dy={'up':(0,1),'down':(0,-1),'left':(-1,0),'right':(1,0)}[st['dir']]
                                for _ in range(st.get('times',1)): q.append((dx,dy))
                        elif res.get('mode')=='talk': error_msg=''; print(res.get('content'))
                        else: error_msg=res.get('content','')
                    input_text=''
            elif e.type==pygame.MOUSEBUTTONDOWN and e.button==1 and btn_rect.collidepoint(e.pos):
                if input_text.strip() and not IGNORE_RE.match(input_text):
                    ct=(pos['x'],pos['y']) in npc_positions
                    res=call_openai(input_text,pos,ct)
                    if res.get('mode')=='move' and ENABLE_MOVEMENT:
                        error_msg='';
                        for st in res['steps']:
                            dx,dy={'up':(0,1),'down':(0,-1),'left':(-1,0),'right':(1,0)}[st['dir']]
                            for _ in range(st.get('times',1)): q.append((dx,dy))
                    elif res.get('mode')=='talk': error_msg=''; print(res.get('content'))
                    else: error_msg=res.get('content','')
                input_text=''
        # 平滑移動
        if not moving and q:
            dx,dy=q.popleft();nx,ny=pos['x']+dx,pos['y']+dy
            if 0<=nx<cols and 0<=ny<rows and (nx,ny) not in lava_set:
                pos['x'],pos['y']=nx,ny; tpx, tpy = px, py
                tpx, tpy = px, py;target_px,target_py=nx*tile,(rows-1-ny)*tile
                moving=True;ld=(dx,dy);anim_t=0;anim_i=0;idle_t=0
        if moving:
            dxp=target_px-px; dyp=target_py-py;step=MOVE_SPEED*dt
            px += step*(dxp/abs(dxp)) if abs(dxp)>step else dxp
            py += step*(dyp/abs(dyp)) if abs(dyp)>step else dyp
            if abs(px-target_px)<1e-3 and abs(py-target_py)<1e-3: px,py=target_px,target_py; moving=False
        # 動畫
        if moving:
            anim_t+=dt
            if anim_t>=ANIM_INTERVAL: anim_t-=ANIM_INTERVAL;anim_i=(anim_i+1)%len(ANIM_TILES[ld])
            curr=ANIM_TILES[ld][anim_i];idle_t=0
        else:
            idle_t+=dt
            curr=IDLE_TILE if idle_t>=IDLE_DELAY else ANIM_TILES.get(ld,[IDLE_TILE])[anim_i]
        # 繪圖
        screen.fill((0,0,0))
        floor=obj_set.union({(pos['x'],pos['y'])})
        for ry,row in enumerate(bg):
            for rx,tid in enumerate(row): screen.blit(images['000' if (rx,ry)in floor else tid],(rx*tile,(rows-1-ry)*tile))
        for o in objects: screen.blit(images[o['type']],(o['x']*tile,(rows-1-o['y'])*tile))
        screen.blit(images[curr],(px,py))
                        # 繪 UI
        # 背景灰框（輸入區＋錯誤區）
        pygame.draw.rect(screen, (50,50,50), (0, h-UI_HEIGHT, w, UI_HEIGHT))
        # 輸入框
        pygame.draw.rect(screen, (255,255,255), input_rect)
        screen.blit(font.render(input_text, True, (0,0,0)), (input_rect.x+5, input_rect.y+5))
        # Send 按鈕
        pygame.draw.rect(screen, BUTTON_COLOR, btn_rect)
        send_surf = font.render('Send', True, BUTTON_TEXT_COLOR)
        screen.blit(
            send_surf,
            (
                btn_rect.x + (BUTTON_WIDTH - send_surf.get_width())//2,
                btn_rect.y + (BUTTON_HEIGHT - send_surf.get_height())//2
            )
        )
        # 錯誤顯示區
        err_rect = pygame.Rect(
            INPUT_PADDING,
            h - ERROR_HEIGHT + 5,
            w - 2*INPUT_PADDING,
            ERROR_HEIGHT - 10
        )
        pygame.draw.rect(screen, ERROR_BG, err_rect)
        err_surf = font.render(f"error: {error_msg}", True, ERROR_TEXT_COLOR)
        screen.blit(err_surf, (err_rect.x+5, err_rect.y+5))

        pygame.display.flip()
    pygame.quit()
    pygame.key.stop_text_input()

if __name__=='__main__':
    main()
