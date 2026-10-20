# 示例技能：点歌台（jukebox）

一个完整真实技能：说出歌名 → 机器人联网搜歌（网易云源）→ 下载 → ffmpeg 转 wav →
离线节拍分析（任意歌自动算 BPM）→ 音乐起 → 舞步按小节在节拍网格上持续随机触发 → 音乐停谢幕。

已上架 PrimeHub（搜索「点歌台」），全链路真机验证。

## 看什么（学习点）

| 文件位置 | 学什么 |
|---|---|
| `find_song()` / `download_song()` | 联网取资源：urllib + 重试 + ffmpeg 转码（板载只吃 wav） |
| `analyze_beats()` | 纯 stdlib 离线节拍分析：能量包络 + 自相关 → BPM |
| `speak()` | TTS 轮询等真实播完的标准写法（无完成回调平台必用） |
| `music_really_over()` | 音频状态抖动的滤波处理（长音频状态 1↔2 抖动） |
| 主循环 `play_animation(anim, interrupt=False)` | 音频持续时动作排队执行的唯一正确姿势 |
| `MOVE_POOL` + `next_move()` | 持续随机动作池（避免重复上一拍） |

## 跑起来

改 `src/main.py` 顶部 `SONG_NAME` 一行即可换歌；`MOVE_POOL` 换舞池动作。
打包：`python3 pack.py example-jukebox`；调试按 SKILL_PUBLISH_GUIDE.md 第 5 步。
