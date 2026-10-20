# 示例技能：点歌台（jukebox）

一个完整真实技能：**纯 API 点歌**——每次运行联网抓网易云热歌榜 → 随机点一首 →
gdstudio API 搜+下载（128k）→ ffmpeg 转 wav → 离线节拍分析（每首歌现场算 BPM，
不写死任何节奏）→ 音乐起 → 舞步按小节在节拍网格上持续随机触发 → 音乐停谢幕。

已上架 PrimeHub（搜索「点歌台」）。

## 点歌方式

- **默认（不写死任何歌）**：每次运行走 API——热歌榜随机抽，尽量不重样
  （已播记录在机器人 `/tmp/jukebox_history.txt`），搜不到/下不动自动换下一首重试。
- **固定曲目（可选覆盖）**：`media/songlist.txt` 一行一首「歌名 歌手」，或
  `src/main.py` 顶部 `PLAYLIST` 加歌 → re-pack 上传后机器人只跳这个单子。

## 看什么（学习点）

| 文件位置 | 学什么 |
|---|---|
| `load_songlist()` / `pick_song()` | API 点歌入口：热歌榜随机 + 不重样 + 可选固定歌单 |
| `find_song()` / `download_song()` | 联网取资源：urllib + 重试 + ffmpeg 转码（板载只吃 wav） |
| `analyze_beats()` | 纯 stdlib 离线节拍分析：能量包络 + 自相关 → BPM |
| `speak()` | TTS 轮询等真实播完的标准写法（无完成回调平台必用） |
| `music_really_over()` | 音频状态抖动的滤波处理（长音频状态 1↔2 抖动） |
| 主循环 `play_animation(anim, interrupt=False)` | 音频持续时动作排队执行的唯一正确姿势 |
| `MOVE_POOL` + `next_move()` | 持续随机动作池（避免重复上一拍） |

## 跑起来

打包：`python3 pack.py example-jukebox`；调试按 SKILL_PUBLISH_GUIDE.md 第 5 步。
`MAX_DANCE_SEC`（默认 90s）保护电机；`MOVE_POOL` 换舞池动作。
