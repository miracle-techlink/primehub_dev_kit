# 示例技能：点歌台（jukebox）

一个完整真实技能：**任意点歌** → 机器人联网搜歌（网易云源）→ 下载 → ffmpeg 转 wav →
离线节拍分析（每首歌现场算 BPM，不写死任何节奏）→ 音乐起 → 舞步按小节在节拍网格上持续随机触发 → 音乐停谢幕。

已上架 PrimeHub（搜索「点歌台」），全链路真机验证。

## 怎么点歌（三层入口，优先级从高到低）

1. **歌单文件**：`media/songlist.txt`，一行一首（`歌名 歌手`，歌手可省）。
   想让机器人跳什么就改这个文件 → `python3 pack.py example-jukebox` → 重新上传。
   没有网络时只播这个歌单也够用（搜索下载才需要联网）。
2. **默认歌单**：`src/main.py` 顶部的 `PLAYLIST` 列表（songlist.txt 缺失时兜底）。
3. **热门榜单**：前两者都为空时，自动抓网易云热歌榜随机一首（每次不同）。

选取策略：从歌单随机抽、尽量不重样（已播记录在机器人 `/tmp/jukebox_history.txt`）。
下载失败/搜不到时换下一首重试，整单失败才退出。

## 看什么（学习点）

| 文件位置 | 学什么 |
|---|---|
| `load_songlist()` / `pick_song()` | 点歌入口：三层歌单 + 随机不重样 + 历史记录 |
| `find_song()` / `download_song()` | 联网取资源：urllib + 重试 + ffmpeg 转码（板载只吃 wav） |
| `analyze_beats()` | 纯 stdlib 离线节拍分析：能量包络 + 自相关 → BPM |
| `speak()` | TTS 轮询等真实播完的标准写法（无完成回调平台必用） |
| `music_really_over()` | 音频状态抖动的滤波处理（长音频状态 1↔2 抖动） |
| 主循环 `play_animation(anim, interrupt=False)` | 音频持续时动作排队执行的唯一正确姿势 |
| `MOVE_POOL` + `next_move()` | 持续随机动作池（避免重复上一拍） |

## 跑起来

打包：`python3 pack.py example-jukebox`；调试按 SKILL_PUBLISH_GUIDE.md 第 5 步。
`MAX_DANCE_SEC`（默认 90s）保护电机；`MOVE_POOL` 换舞池动作。
