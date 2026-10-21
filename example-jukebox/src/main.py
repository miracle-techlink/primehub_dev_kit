#!/usr/bin/env python3
"""jukebox_q1 —— 点歌台（Q1·联网点歌 + 任意歌自动卡点自由舞）

流程：报幕（TTS）→ 联网搜歌（gdstudio→netease）→ 下载 → ffmpeg 转 wav(mono/22050)
   → 能量包络+自相关离线节拍分析 → 音乐起（锚点=播放态翻 1）
   → 舞步在节拍网格上排队（anim interrupt=False，与音乐共存）→ 音乐停谢幕。

真机实测的三条仲裁铁律（编排全靠它们）：
  ① TTS 抢占杀音乐，且 TTS 结束后音乐不自动恢复 → 报幕/谢幕词全部在音乐外说
  ② play_animation(interrupt=True) 杀音乐 → 卡点舞全程禁用
  ③ play_animation(interrupt=False) 与音乐共存（动作在运动队列里依次执行）
     → 动作发起提前量 LAT_ANIM=0.30s（请求→task_engine 真正创建动画的实测延迟）

音频格式：板载只吃 wav（mp3 放了没声）；ffmpeg 转码 -ac 1 -ar 22050。
"""

import json
import os
import random
import subprocess
import sys
import time
import urllib.parse
import urllib.request

# ★★★ 现场开发者改这里 ★★★
# 点歌优先级（从高到低，取到第一个就点它）：
#   ① 用户语音/启动参数：机器人把用户说的话传进来（argv[1:] 每词一个，或环境变量 JUKEBOX_REQUEST），
#      例如「放稻香」→ 机器人传"放稻香" → 代码剥掉"放/来一首/我想听"等口癖 → 搜"稻香"
#   ② 固定歌单：技能包 media/songlist.txt（一行一首）或下面 PLAYLIST
#   ③ 兜底：联网热歌榜随机抽（纯 API，不写死任何歌）
# 搜不到/下不动自动换下一首重试；已播记录 /tmp/jukebox_history.txt
PLAYLIST = []               # 常驻歌单（可选）；空 = 语音参数 → 热歌榜
REQUEST_ENV = "JUKEBOX_REQUEST"   # 机器人传歌名的环境变量名（和 argv 二选一）
LAT_ANIM = 0.30           # anim 请求→真正起跳的实测延迟（提前发）
LAT_MUSIC = 0.06          # 音频状态翻 1 与真实出声的差（实测 +0.056s）
INTRO = "收到点歌！我去网上找这首歌，找到就马上开跳！"
SONG_ANNOUNCE = "歌曲就位！歌名 %s，节奏 %d 拍每分钟，开跳！"
OUTRO = "这首歌跳完了，还想听什么，尽管点！"
MAX_DANCE_SEC = 90        # 最多跳这么久就收尾（保护电机）
SEARCH_API = "https://music-api.gdstudio.xyz/api.php"
HOT_CHART_API = "https://music.163.com/api/search/get?s=%E7%83%AD%E9%97%A8%E6%AD%8C%E6%9B%B2&type=1&limit=10"  # 网易云「热门歌曲」搜索
HISTORY = "/tmp/jukebox_history.txt"
WAV = "/tmp/jukebox_song.wav"

# 自由舞步池（全部 upper_body，室内模式安全）：持续随机抽取，舞蹈类加权
MOVE_POOL = [
    3046, 3047, 3048,          # 舞蹈A/B/C —— 主力舞步
    3008,                       # 加油
    3001, 3002, 3003, 3004,     # 招手/握手/碰拳/挥手
    3005, 3007,                 # 开心/比心
    3010,                       # 伸懒腰
    3046, 3046, 3047,           # 舞蹈加权（更常跳）
]


def next_move(prev):
    """持续随机：小节级随机抽取，避免和上一个小节重复。"""
    pool = [m for m in MOVE_POOL if m != prev]
    return random.choice(pool)


# ---------- 联网搜歌+下载 ----------
def http_json(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            return json.load(urllib.request.urlopen(req, timeout=20))
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(2)


def find_song(name):
    q = urllib.parse.quote(name)
    songs = http_json(SEARCH_API + "?types=search&source=netease&name=" + q + "&count=5")
    for s in songs:
        if s.get("id") and s.get("url_id"):
            return s
    return songs[0] if songs else None


# ---------- 点歌：① 语音/启动参数 ② 固定歌单 ③ 热歌榜兜底 ----------
# 机器人侧把用户说的话传进来的两条通道（都试）：
#   a) 启动参数 argv：python main.py 稻香 / "放稻香"
#   b) 环境变量 JUKEBOX_REQUEST="放稻香"
VOICE_FILLERS = ("放", "来一首", "我想听", "我要听", "帮我放", "给我放", "点一首", "播一首",
                 "唱一首", "跳一首", "放首", "来首", "听首", "点歌", "跳个舞", "点个",
                 "请放", "想听", "音乐", "首歌", "点首歌")


def user_request():
    """剥掉口癖取歌名：「放稻香」→「稻香」；「放 周杰伦 晴天」→「周杰伦 晴天」。
    剥完只剩口癖（「点首歌」）→ 没点歌，返回 None。"""
    words = [w for w in sys.argv[1:] if w.strip()]
    env = os.environ.get(REQUEST_ENV, "").strip()
    if env and not words:
        words = [env]
    if not words:
        return None
    text = " ".join(words).strip()
    # 反复剥口癖前缀（「帮我放来一首晴天」这种叠加也要剥干净；允许剥到空=全是口癖）
    changed = True
    while changed:
        changed = False
        for f in VOICE_FILLERS:
            if text.startswith(f) and text:
                text = text[len(f):].lstrip("一首个的 ")
                changed = True
    text = text.strip()
    return text or None


def load_songlist():
    """固定歌单（可选）：技能包 media/songlist.txt + PLAYLIST。"""
    candidates = []
    here = os.path.dirname(os.path.abspath(__file__))
    for rel in ("media/songlist.txt", "../media/songlist.txt", "../../media/songlist.txt"):
        p = os.path.join(here, rel)
        if os.path.exists(p):
            lines = [l.strip() for l in open(p, encoding="utf-8") if l.strip() and not l.startswith("#")]
            candidates += lines
    candidates += [p for p in PLAYLIST if p.strip()]
    return candidates


def hot_chart():
    """兜底歌单：联网热歌榜。"""
    try:
        d = http_json(HOT_CHART_API)
        return ["%s %s" % (s.get("name"), "/".join(a["name"] for a in s.get("artists", [])))
                for s in d.get("result", {}).get("songs", [])]
    except Exception:
        return []


def pick_song():
    """点歌决策：① 用户说的歌名（原样优先，绝不随机换）→ ② 固定歌单随机 → ③ 热歌榜随机。
    返回 (歌名, 来源标记)。①/② 记历史防重样；① 不挑重样（用户点名就是要这首）。"""
    req = user_request()
    if req:
        return req, "user"
    songs = load_songlist()
    source = "list"
    if not songs:
        songs = hot_chart()
        source = "chart"
    if not songs:
        return None, "none"
    try:
        played = set(l.strip() for l in open(HISTORY, encoding="utf-8"))
    except OSError:
        played = set()
    fresh = [s for s in songs if s not in played]
    pool = fresh or songs          # 全播过了就允许重复
    song = random.choice(pool)
    try:
        with open(HISTORY, "a", encoding="utf-8") as f:
            f.write(song + "\n")
    except OSError:
        pass
    return song, source


def download_song(song):
    """下载+转 wav。提速三招（实测 CDN 会随机掐连接、整首从 145KB/s 掉到 0B/s 停死）：
    ① 先要 128k mp3（无损 flac 一首 100MB+；跳舞音质 128k 足够，小 30 倍）
    ② 慢速自杀 + 断点续传：--speed-limit 12s<2KB/s 就主动断，-C - 从断点续（不从头再下）
    ③ 外层续传循环：单次 curl 限 45s，断了循环补，最多 6 轮——10 次实测 8 次一次成、2 次靠续传补齐，0 失败
    """
    import os
    d = http_json(SEARCH_API + "?types=url&source=netease&id=" + str(song["url_id"]) + "&br=128")
    if not d.get("url"):
        d = http_json(SEARCH_API + "?types=url&source=netease&id=" + str(song["url_id"]))
    if not d.get("url"):
        return None
    want = d.get("size") or 0
    url = d["url"]
    raw = "/tmp/jukebox_raw"
    # ②+③：限速自杀 → 断点续传 → 外层循环补
    for _ in range(6):
        subprocess.run(
            ["curl", "-s", "-A", "Mozilla/5.0", "-o", raw, "-C", "-",
             "--speed-limit", "2048", "--speed-time", "12",
             "--connect-timeout", "6", "--max-time", "45", url],
            timeout=50)
        got = os.path.getsize(raw) if os.path.exists(raw) else 0
        if want and got >= want:
            break
        if not want and got > 1024:
            # API 没给 size：下到了且这轮没断（curl 正常返回）就收
            break
    got = os.path.getsize(raw) if os.path.exists(raw) else 0
    if got < 1024 or (want and got < want):
        try:
            os.remove(raw)
        except OSError:
            pass
        return None
    # 转 wav（板载只吃 wav）
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw,
                    "-ac", "1", "-ar", "22050", WAV], timeout=120)
    return WAV if os.path.exists(WAV) else None


# ---------- 离线节拍分析（纯 stdlib） ----------
def analyze_beats(wav_path):
    import struct
    import wave
    w = wave.open(wav_path)
    sr, n = w.getframerate(), w.getnframes()
    ch = w.getnchannels()
    raw = w.readframes(n)
    samples = struct.unpack("<%dh" % (len(raw) // 2), raw)
    mono = [samples[i] for i in range(0, len(samples), ch)]
    # 能量包络 20ms
    hop = int(sr * 0.02)
    env = []
    for i in range(0, len(mono) - hop, hop):
        seg = mono[i:i + hop]
        env.append(sum(abs(x) for x in seg) / hop)
    if not env:
        return None
    # onset 强度 = 一阶差分（正部分）
    diff = [max(0.0, env[i] - env[i - 1]) for i in range(1, len(env))]
    mx = max(diff) or 1.0
    diff = [d / mx for d in diff]
    # 自相关找拍周期（0.3~1.2s = 50~200BPM）
    def mean(x):
        return sum(x) / len(x)
    m = mean(diff)
    cen = [x - m for x in diff]
    best_lag, best_v = None, -1e18
    for lag in range(int(0.3 / 0.02), int(1.2 / 0.02)):
        s = sum(cen[i] * cen[i + lag] for i in range(0, len(cen) - lag, 3))
        v = s / (len(cen) - lag)
        if v > best_v:
            best_v, best_lag = v, lag
    beat = best_lag * 0.02
    # 首拍 = 第一个强 onset
    thresh = 0.25
    first = None
    for i, d in enumerate(diff):
        if d > thresh:
            first = (i + 1) * 0.02
            break
    dur = n / sr
    return {"beat": beat, "first": first or 1.0, "dur": dur, "bpm": 60.0 / beat}


# ---------- 音频状态 ----------
def audio():
    s = robot.get_audio_play_state()
    if not isinstance(s, dict):
        return ("?", 0)
    return (s.get("pkg_name"), s.get("state", {}).get("value", 0))


def music_on():
    p, v = audio()
    return p == "interaction_slave" and v == 1


def music_really_over(anchor, dur):
    """音频状态对长音乐播放会 1↔2 抖动（实测），不能信瞬时值。
    判定标准：超过预计结束时刻 anchor+dur-0.5，或连续 3.5s 状态全空。"""
    if time.time() > anchor + dur - 0.5:
        return True
    quiet = 0.0
    t0 = time.time()
    while time.time() - t0 < 3.5:
        time.sleep(0.25)
        if audio() == ("interaction_slave", 1):
            return False
    return True


def speak(text):
    robot.play_tts(text)
    deadline = time.time() + max(len(text) * 0.35, 3.0) + 8.0
    time.sleep(0.3)
    while time.time() < deadline and audio() != ("tts", 1):
        time.sleep(0.1)
    while time.time() < deadline and audio() == ("tts", 1):
        time.sleep(0.1)


# ---------- 演出 ----------
speak(INTRO)
requested, source = pick_song()
print("PICK: %s (source=%s)" % (requested, source), flush=True)
if not requested:
    speak("网上没拉到歌单，稍后再试一次！")
    raise SystemExit("NO_SONGLIST")
# 用户点名的歌搜不到/下不动 → 报歉 + 从热歌榜换一首继续（不静默换：点名失败要告诉用户）
song = None
path = None
tried = [requested]
for _ in range(3):
    song = find_song(requested)
    if not song:
        print("SEARCH_MISS: %s" % requested, flush=True)
    else:
        print("SONG: %s - %s" % (song.get("name"), "/".join(song.get("artist", []) or [])), flush=True)
        path = download_song(song)
        if path:
            break
        print("DOWNLOAD_RETRY", flush=True)
    if source == "user":
        speak("这首 %s 没找到能下载的版本，我换首热门的接着跳！" % requested)
        source = "chart"
    songs = [s for s in hot_chart() if s not in tried]
    if not songs:
        songs = [s for s in load_songlist() or hot_chart() if s not in tried]
    if not songs:
        break
    requested = random.choice(songs)
    tried.append(requested)
    print("PICK: %s (source=fallback)" % requested, flush=True)
if not path:
    speak("这首歌下载失败了，换一首试试！")
    raise SystemExit("DOWNLOAD_FAILED")

info = analyze_beats(path)
print("BEATS: %s" % info, flush=True)
if not info:
    speak("这首歌节奏太怪，我先随便跳了！")
    beat, first = 0.5, 1.0
else:
    beat, first = info["beat"], info["first"]

speak(SONG_ANNOUNCE % (song.get("name"), round(60.0 / beat)))
time.sleep(0.5)
robot.play_light(color=1, mode=3)

robot.play_audio_file(path)
t0 = time.time()
anchor = None
while time.time() - t0 < 6.0 and anchor is None:
    if music_on():
        time.sleep(1.0)
        # 1s 后还在播(或刚好处在抖动空档也算)→可信锚点
        if time.time() - t0 > 0.8:
            anchor = time.time() - 1.0
    time.sleep(0.05)
if anchor is None:
    anchor = time.time() + 0.2   # 兜底
    time.sleep(0.2)
print("MUSIC_ANCHOR +%.3f" % (anchor - t0), flush=True)

# 自由卡点：每 4 拍（一小节）从动作池取下一个，按拍点提前 LAT_ANIM 排队
i = 0
prev_anim = None
dur_est = info["dur"] if info else 60.0
stop_at = time.time() + min(dur_est - first - 1.0, MAX_DANCE_SEC)
events = []
while time.time() < stop_at:
    bar = i
    target = anchor + first + bar * 4 * beat - LAT_MUSIC - LAT_ANIM
    d = target - time.time()
    if d > 0:
        time.sleep(d)
    if music_really_over(anchor, dur_est):
        break          # 音乐真结束了(抖动滤波)
    anim = next_move(prev_anim)
    prev_anim = anim
    robot.play_animation(anim, interrupt=False)     # 铁律③：不打断=与音乐共存
    events.append((round(time.time() - anchor, 3), bar, anim))
    i += 1
    if i > 200:
        break

print("FIRED %d bars, tail:" % len(events), events[-4:], flush=True)
# 音乐自然结束后谢幕（铁律①：TTS 只在音乐外说；按已知时长等待，状态抖动不可信）
remaining = max(0.5, min(dur_est - (time.time() - anchor), MAX_DANCE_SEC))
deadline = time.time() + remaining
while time.time() < deadline and not music_really_over(anchor, dur_est):
    time.sleep(0.5)
speak(OUTRO)
robot.play_animation(3005, interrupt=True)
time.sleep(4.0)
print("JUKEBOX_DONE bars=%d" % len(events), flush=True)
