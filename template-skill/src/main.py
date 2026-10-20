#!/usr/bin/env python3
"""photo_director_q1 —— 合影导演（Q1·真机验证版 Lv.3）

报幕 → 每张：报幕词 → 倒计时三二一（纯语音，机器人静止）
   → 「茄子——」与姿势动作【同一瞬间】起 → 动作进行中就是拍照窗口 → 定格收尾。

Q1 真机约束（实测）：
  · 室内模式（motion_mode=0）禁全身动作——只编排 upper_body 动作：
    3001 招手  3002 握手  3003 碰拳  3005 开心  3007 双手比心  3008 加油  3012-3014 讲话
  · whole_body 动作（3011 秀肌肉/3051 街舞等）室内被 reason 24 拒，工作坊不依赖
  · TTS 播完判定用音频状态轮询（state 1=播放中 2=空闲）
"""

import time

# ★★★ 现场开发者改这里 ★★★
INTRO = "各位注意！合影导演正式开工，我数三个数，大家一起看镜头！"
SHOTS = [
    # (姿势动作ID, 这张的报幕词, 倒计时秒)：倒计时纯语音，「茄子」与动作同时起
    (3001, "第一张，看镜头，准备招手！", 3),
    (3002, "第二张，准备握手！", 3),
    (3007, "第三张，准备双手比心！", 3),
]
OUTRO = "拍摄完成！成片都在我的相册里，这张我要发朋友圈！"
CELEBRATE = 3005    # 收尾：开心
POSE_HOLD = 6.0     # 「茄子」后动作进行/定格秒数 = 拍照窗口


def speak(text, tail=0.4):
    """说话并等它真的播完（音频状态 1=播放中 2=空闲）。"""
    robot.play_tts(text)
    deadline = time.time() + max(len(text) * 0.35, 2.0) + 8.0
    time.sleep(0.3)
    while time.time() < deadline:            # 等开始播
        st = robot.get_audio_play_state()
        v = st.get("state", {}).get("value", 2) if isinstance(st, dict) else 2
        if v == 1:
            break
        time.sleep(0.12)
    while time.time() < deadline:            # 等播完
        st = robot.get_audio_play_state()
        v = st.get("state", {}).get("value", 1) if isinstance(st, dict) else 1
        if v != 1:
            break
        time.sleep(0.12)
    time.sleep(tail)


speak(INTRO)

for pose_id, line, countdown in SHOTS:
    speak(line)                              # 这张的报幕词（无动作）
    for n in range(countdown, 0, -1):        # 倒计时：3、2、1（纯语音）
        robot.play_tts(str(n))
        time.sleep(0.9)
    # ★ 「茄子」与姿势动作同一瞬间起——说的同时动作已经在摆
    robot.play_tts("茄子——")
    robot.play_animation(pose_id, interrupt=True)
    time.sleep(POSE_HOLD)                    # 动作进行中 = 按快门的窗口

speak(OUTRO)
robot.play_animation(CELEBRATE, interrupt=True)
time.sleep(4.0)
print("PHOTO_SHOOT_DONE shots=%d" % len(SHOTS), flush=True)
