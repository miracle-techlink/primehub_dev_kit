# PrimeHub 机器人技能：开发到上架通用手册

> 给谁看：外部开发者——想给启元 Q1/T1 机器人做技能、用 AI agent（Claude Code/Cursor 等）vibe coding、最终发上 PrimeHub 技能市场。
> 走「普通用户路径」（lumina 运行时），不需要开发者模式。
> 技能类型不限：迎宾、讲故事、互动问答、表情秀、定时提醒……本手册只讲通用开发流程。
> 所有命令、接口、失败码均为真机（Q1/T1）与线上实测（2026-10）。

---

## 开始前：拿到开发工具包（dev kit）

本手册的命令基于一个 5 文件工具包（模板技能 + 打包器 + 真机调试 harness + PrimeHub 发布客户端 + token 提取器），拿到手解压即用：

```
primehub_dev_kit/
├── template-skill/      技能模板（cfg/pkg.yaml + src/main.py + readme.md）——复制成你的技能
├── example-jukebox/     完整真实案例：点歌台（联网搜歌+节拍分析+随机伴舞，已上架 PrimeHub）
├── pack.py              打包器：技能目录 → .rpk
├── deploy_test.py       真机调试 harness（scp 到机器人跑）
├── primehub_publish.py  PrimeHub 发布/删除/查询（依赖同目录 primehub_client.py）
├── primehub_client.py   SM4 传输层（primehub_publish 的依赖，别删）
└── extract_token.py     从 Firefox 登录态自动提取 PrimeHub token
```

获取方式（任一）：
- 问平台/同事拿 `primehub_dev_kit.zip`，或
- 拿到本文档所在目录时 zip 就在旁边（`primehub_dev_kit.zip`）

环境要求：Python 3（`python3 --version`）、`curl`、`sshpass`。
依赖说明：全部纯 stdlib + `gmssl`（SM4 加密用；没有的话 `pip install gmssl`）。

**下文所有命令默认你已解压 dev kit 并在其目录里**（`cd primehub_dev_kit`）。

---

## 开发顺序总览

```
第 0 步  环境与资产盘点（开工前要有什么）
第 1 步  注册 PrimeHub（拿账号）
第 2 步  给 agent 喂机器人契约（它不知道这些就写不出能跑的代码）
第 3 步  vibe coding：从模板改出你的技能
第 4 步  打包 .rpk
第 5 步  真机调试环（跑 → 看输出 → 看动作日志 → 改 → 再跑）
第 6 步  验收检查表
第 7 步  提取登录 token（发布凭证）
第 8 步  上传 PrimeHub + 管理在架列表
```

| 步骤 | 产出 | 存放 |
|---|---|---|
| 0 | dev kit 解压、SSH 通、（可选）出网确认 | 开发机 |
| 1 | PrimeHub 账号 + 本机 Firefox 登录态 | primehub.primebot.com |
| 2 | agent 可读的契约（本文件 §2） | 本文档 |
| 3 | `my-skill/src/main.py` + `cfg/pkg.yaml` | 开发机 |
| 4 | `my-skill.rpk` | 开发机 |
| 5-6 | 真机 success + 动作日志全命中 | 机器人 |
| 7 | `/tmp/ph_token.txt`（JWT） | 开发机 |
| 8 | PrimeHub 在架条目（可搜、可被 App 部署） | 云端 |

---

## 第 0 步：环境与资产盘点

1. **开发机**：任意系统，有 Python 3（`python3 --version`）、`curl`、`sshpass`；
   装 dev kit 依赖 `pip install gmssl`
2. **机器人**：Q1 或 T1，与开发机同网段，知道 IP；SSH 用户 `run`，密码 `1`
   ```bash
   sshpass -p '1' ssh -o StrictHostKeyChecking=no run@192.168.112.222 'echo OK'   # Q1 示例
   ```
3. **机器人出网**（技能要联网时才需要）：
   ```bash
   sshpass -p '1' ssh run@<IP> 'curl -sI --max-time 8 https://www.baidu.com | head -1'
   ```
4. **dev kit 解压并自检**：
   ```bash
   unzip primehub_dev_kit.zip && cd primehub_dev_kit
   python3 primehub_publish.py search "你好"      # 不带 token 能搜 = 网络+传输层 OK
   ```

---

## 第 1 步：注册 PrimeHub + 建立登录态（发版凭证的根）

这一步做两件事：**注册账号** + **在本机 Firefox 里登录一次**（第 7 步的 token 就从这次登录里自动提取）。

1. 用**本机 Firefox**（后面 token 提取只支持 Firefox 的落盘格式；别的浏览器登录了也提不出来）打开
   **https://primehub.primebot.com**
2. 手机号 + 短信验证码注册/登录。验证码真实下发，无绕过方案
3. 登录成功后随便点一个页面（确保 token 已写入 localStorage），Firefox 不用关
4. 到 `#/search` 逛市场，看别人技能的标题/简介写法（决定你第 8 步的文案质量）

**为什么必须真人登录**：发布/上传/删除全部 API 要求 Bearer token（JWT），
token 只能由验证码登录换取。登录后 Firefox 把它存进本地 localStorage（`skillhub_token` 键），
dev kit 的 `extract_token.py` 能从磁盘直接读出（无需开 DevTools 手动复制），**7 天内有效**，
期间发布不用再登录。

第 7 步只需要一条命令，不用理解 token 的任何细节。想了解原理见该步的「工作原理」小节。

---

## 第 2 步：给 agent 喂机器人契约

AI agent 默认按 ROS2/rclpy 常识写机器人代码——装上必死（ImportError）。
把本节（或整个文档路径）发给它，这是 vibe coding 成败的分水岭。

### 2.1 运行时契约（lumina）

- 技能包 = zip 改名 `.rpk`：`cfg/pkg.yaml` + `src/main.py` + 可选 `readme.md`、`media/`
- 机器人上由 `lumina_server` 拉起 `src/main.py`，**注入全局对象 `robot`**
- 环境是 Python 3.10 **标准库**（numpy 1.26 在，其余第三方不可用）
- **没有** rclpy、ROS2 节点、ASR 订阅、相机抓帧——只有 `robot` 对象
- 机器人在本机暴露 lumina HTTP API（`127.0.0.1:58080`），这是调试通道（见 §5）

### 2.2 `robot` 对象 API（实测签名）

```python
robot.play_tts(text)                        # 说话，异步无完成回调 → 用 2.4 的轮询法等播完
robot.play_animation(anim_id, interrupt)    # 预设动作；返回 bool（True=已受理）
robot.play_audio_file(path)                 # 播音频文件；板载只吃 wav（mp3 无声）
robot.play_light(color, mode)               # 灯带（mode 3 律动）
robot.play_emotion(emotion_ids, ...)        # 屏幕表情
robot.get_audio_play_state()                # → {'pkg_name':..,'state':{'value':1播放中/2空闲}}
robot.get_t1_robot_form()                   # T1 专属：'biped'/'quadruped'
robot.wait("time", seconds)                 # 等待
```

### 2.3 动作 ID 权威表（在机器人上，不在任何 SDK 文档）

```bash
# Q1：58 个动作（3000 系），分 upper_body / whole_body 两个文件
sshpass -p '1' ssh run@<Q1_IP> \
  'cat /robot/software/task_engine/bin/cfg/motions/q1/upper_body.yaml'
# T1：1-72
sshpass -p '1' ssh run@<T1_IP> \
  'cat /robot/software/task_engine/bin/cfg/motions/t1/*.yaml'
```

Q1 常用 upper_body 动作：

```
3001 招手  3002 握手  3003 碰拳  3004 挥手  3005 开心  3007 双手比心
3008 加油  3010 伸懒腰  3012-3014 讲话  3046/3047/3048 舞蹈A/B/C  3052-3057
```

T1 常用：1 打招呼 / 2 握手 / 6 比心 / 7、10、11 跳舞 / 20-22 拍照姿势 / 26 喜悦 / 31 欢呼 / 43 律动 / 52 太空步。

### 2.4 平台约束（写代码前必须知道的物理事实，实测）

1. **室内模式禁全身动作（Q1）**：`motion_mode=0` 时 whole_body 动作全部被拒（reason 24）→ 上架给普通用户的技能**只用 upper_body ID**
2. **T1 形态分支**：四足形态只能用 1/7/26/43（其余 reason 19）→ 用 `get_t1_robot_form()` 分支
3. **音频与动作互斥关系**：
   - `play_tts` 会停掉正在播的音频（且 TTS 结束后**不自动恢复**）→ 台词和音乐/音效别同时发
   - `play_animation(interrupt=True)` 也会停当前音频 → 需要音频持续时一律用 `interrupt=False`（动作进队列依次执行）
4. **音频状态轮询**：`get_audio_play_state` 对长音频会 1↔2 抖动 → 判播完别信单次采样，轮询到稳定空闲或用已知时长计时
5. **时长感**：TTS 短句起声延迟 ≈0.5s、4-6 字约 1.1s；anim 受理→真正起跳 ≈0.3s——编排等待时长时心里有数
6. **输出必须 `flush=True`**：stdout 走缓冲，不 flush 调试时看不到 print

### 2.5 给 agent 的提示词模板

> 读 `SKILL_PUBLISH_GUIDE.md` 的 §2 契约。基于 dev kit 的 `template-skill/` 模板
>（参考 `example-jukebox/` 真实案例），改成：〈你的场景描述〉。
> 约束：只用 upper_body 动作、纯 stdlib、遵守 §2.4 平台约束。

---

## 第 3 步：vibe coding：从模板改出你的技能

**不要从零写。** 从模板复制改起：

```bash
cd primehub_dev_kit
cp -r template-skill my-skill               # 复制模板（想直接学全功能真实案例，看 example-jukebox/）
```

任何技能的通用编程模型都是一样的：

```
技能 = 一张「(动作ID, 台词, 保持秒)」编排表 + 起场白 + 收场白 + 可选分支逻辑
```

要改的就三处：
1. `cfg/pkg.yaml`：`package_name`（snake_case 唯一）、`version`、`robot_model: q1|t1`
2. `src/main.py` 顶部的编排表和台词
3. `readme.md`

**通用骨架**（任何台词+动作技能直接抄，`speak()` 是标准写法——TTS 无完成回调，必须轮询音频状态等真实播完）：

```python
import time

STEPS = [(3001, "台词一", 3), (3007, "台词二", 3)]   # (动作ID, 台词, 保持秒)

def speak(text):
    """说话并等它真的播完（音频状态 1=播放中 2=空闲）。"""
    robot.play_tts(text)
    deadline = time.time() + max(len(text) * 0.35, 3.0) + 8.0
    time.sleep(0.3)
    while time.time() < deadline:
        st = robot.get_audio_play_state()
        if st.get("state", {}).get("value") == 1: break
        time.sleep(0.12)
    while time.time() < deadline:
        st = robot.get_audio_play_state()
        if st.get("state", {}).get("value") != 1: break
        time.sleep(0.12)

speak("开场白")
for anim, line, hold in STEPS:
    speak(line)
    robot.play_animation(anim, interrupt=True)   # 无人声/音乐并行时允许 interrupt=True
    time.sleep(hold)
speak("收场白")
print("MY_SKILL_DONE steps=%d" % len(STEPS), flush=True)   # flush 必须
```

**agent 写代码的三条硬约束**（当 lint 规则用）：
1. 纯 stdlib + `robot` 全局对象（不 import robot、不传参）
2. 只用 §2.3 查到的动作 ID（Q1 上架版 = upper_body 白名单）
3. 台词用 `speak()` 轮询真实播完；涉及音频并行时按 §2.4 第 3 条处理

---

## 第 4 步：打包 .rpk

```bash
cd primehub_dev_kit
python3 pack.py my-skill          # → my-skill.rpk（固定结构 cfg/pkg.yaml + src/*.py）
python3 -m zipfile -l my-skill.rpk   # 校验：必须含 cfg/pkg.yaml 和 src/main.py
```

`media/` 目录可选（放 mp4/mp3 资源原样落盘）。包体控制在 200MB 内（上传限制）。

---

## 第 5 步：真机调试环（开发主循环）

### 5.1 布置调试环境（一次）

```bash
sshpass -p '1' scp -o StrictHostKeyChecking=no \
    deploy_test.py run@<机器人IP>:/tmp/
```

### 5.2 主循环（每轮迭代 3 条命令）

```bash
cd primehub_dev_kit
python3 pack.py my-skill                                     # ① 重打包
sshpass -p '1' scp my-skill.rpk run@<IP>:/tmp/               # ② 上机器人
sshpass -p '1' ssh run@<IP> \
    'python3 /tmp/deploy_test.py /tmp/my-skill.rpk 300'      # ③ 跑+看结果
#                                                             ↑ timeout 秒数必须 ≥ 技能总时长（默认 120 常常不够）
```

`deploy_test.py` 做的事：解 rpk → POST `127.0.0.1:58080/packages/script` 建包 →
POST `/tasks` 跑 → 轮询 → 打 `final/stdout/error`。

**输出判读**：

- `final: success` + stdout 到 DONE 标记 → 脚本逻辑通
- `final: failed` + `error: ImportError...` → 契约写错（回 §2.2）
- `final: timeout` → harness timeout 没给够
- stdout 空白 → print 忘了 `flush=True`

### 5.3 动作到底触没触发（stdout 只能证明「受理」）

`play_animation` 返回 True 只代表受理，真执行要看机器人日志：

```bash
sshpass -p '1' ssh run@<IP> \
    'grep "Animation task成功" /robot/persist/log/task_engine/task_engine.log | tail -8'
```

每个预期动作 ID 都要有「创建Animation task成功， animation_id: XXXX」一行。
缺了就搜失败原因（同一日志）：

| reason | 含义 | 修法 |
|---|---|---|
| 24 | 室内模式禁全身动作（Q1 whole_body） | 换 upper_body ID |
| 19 | 形态不符（T1 四足调双足动作） | `get_t1_robot_form()` 分支 |
| 42 | 上一动作还占着队列 | 加等待/无音频并行时 interrupt=True |
| 28 | 动作不可打断（如 T1 greet ~15s） | 等够时长或换动作 |
| 17 | 动作 ID 不存在 | 回 §2.3 查权威表 |

### 5.4 清理与进阶 API

```bash
sshpass -p '1' ssh run@<IP> 'curl -s -X DELETE 127.0.0.1:58080/packages/my_skill'   # 删调试残留包
# 其它：GET /packages（列表） GET /tasks/running DELETE /tasks/{id}
```

---

## 第 6 步：验收检查表（全绿才进第 7 步）

- [ ] `deploy_test.py` 一轮 `final: success`
- [ ] stdout 到达 DONE 标记（有 flush）
- [ ] 动作日志里每个预期动作 ID 都「创建成功」，无 reason 24/19/42/28 拒绝
- [ ] 台词全部实际播出（听现场/回放确认无吞句）
- [ ] 音频类技能：音频从头活到尾（日志无中途 `AudioSkill::接收到停止指令`）
- [ ] 连跑两轮不炸（包可重复安装）
- [ ] 安全：机器人周围 1 米清空测试过

---

## 第 7 步：提取登录 token（自动，一条命令）

第 1 步 Firefox 登录过之后，这一步就是把磁盘上的 token 拿出来给发布工具用：

```bash
cd primehub_dev_kit
python3 extract_token.py
# 输出：token → /tmp/ph_token.txt（1036 字符，7 天内有效）
```

成功判读：打印 `token → /tmp/ph_token.txt（N 字符…）`，文件里是一串 `eyJhbG...` 开头的 JWT。
失败判读：
- `没找到 Firefox 的 primehub localStorage` → Firefox 没登录过 / 用了别的浏览器 → 回第 1 步用 Firefox 登录一次
- `没找到 skillhub_token` → 登录态过期 → Firefox 重新登录，再跑一次

`extract_token.py` 做的事（全自动，无需 DevTools）：
1. 找到本机 Firefox profile 里的 primehub localStorage 数据库（`storage/default/https+++primehub.primebot.com/ls/data.sqlite`）
2. 拷贝快照（Firefox 运行中会锁库，直接读会报 database is locked）
3. 查 `skillhub_token` 键——值是 snappy 压缩的二进制
4. 纯 stdlib 解压（uvarint 长度头 + literal/copy tag 流），JWT 写入 `/tmp/ph_token.txt`

之后第 8 步的 `primehub_publish.py` 自动读这个文件，**你全程不接触 token 本身**。
token 过期（7 天）后：Firefox 重新登录一次 PrimeHub → 再跑 `extract_token.py` → 继续发布。

---

## 第 8 步：上传 PrimeHub + 管理

### 8.1 发布（一条命令，token 自动读取）

```bash
cd primehub_dev_kit
python3 primehub_publish.py publish my-skill.rpk '{
  "skillName": "我的技能名",
  "version": "1.0.0",
  "skillDesc": "一句话简介（列表卡片显示，30 字内最好）",
  "long_description": "详细说明（详情页显示，写清玩法和改法）",
  "categoryIds": [104],      "categoryCodeList": ["action"],
  "tagsIds": [127],          "tagsCodeList": ["companion"],
  "robotModelIds": [100],    "robotModelCodeList": ["robot_q"],
  "iconUrl": "skill-music.svg"
}'
# 成功回 {'code': 1000, 'msg': '成功'}
```

发布工具内部链路（出错时知道卡在哪一环）：
① 读 `/tmp/ph_token.txt`（第 7 步产出，没有就先跑 extract_token.py）
② 把 .rpk multipart 上传到 `primehub.primebot.com/app-api/content-server/file/upload` → 拿 fileUrl
③ 调 `skillCenter/publishSkill`（SM4 加密传输）带上 fileUrl + 上面 json 的元数据
→ 平台建条目，几十秒后全网可搜。

失败判读：
- 报 `FileNotFoundError: /tmp/ph_token.txt` → 回第 7 步
- 报 `1001 …不能为空` → json 缺字段/拼错（对照 §8.1 模板，双字段都要）
- 报 9999 / SSL / 超时 → 网络抖动，直接重跑一遍命令（上传幂等，重试无害）

---

## 第 8 步：上传 PrimeHub + 管理

### 8.1 发布（一条命令）

```bash
cd primehub_dev_kit
python3 primehub_publish.py publish my-skill.rpk '{
  "skillName": "我的技能名",
  "version": "1.0.0",
  "skillDesc": "一句话简介（列表卡片显示，30 字内最好）",
  "long_description": "详细说明（详情页显示，写清玩法和改法）",
  "categoryIds": [104],      "categoryCodeList": ["action"],
  "tagsIds": [127],          "tagsCodeList": ["companion"],
  "robotModelIds": [100],    "robotModelCodeList": ["robot_q"],
  "iconUrl": "skill-music.svg"
}'
# 成功回 {'code': 1000, 'msg': '成功'}
```

**字典 ID 速查**（双字段必填，缺了报 1001）：

| 项 | ID → 值 | codeList 对应 |
|---|---|---|
| 分类 | 102 视觉 / 103 语言 / 104 动作 / 105 听力 / 106 规划 / 107 表情 | vision/language/action/hearing/plan/expression |
| 标签 | 115 音乐 / 124 拍照 / 127 陪伴 / 20 亲子 | music/take_photo/companion/parent_child |
| 机型 | 100 = 机器人Q / 101 = 机器人T | robot_q / robot_t |
| 图标 | 站内 svg 名：skill-music / skill-video / skill-radio / skill-game / skill-verify | 同名 .svg |

### 8.2 发布后验证（先自助，再用户视角）

**自助验证（1 分钟）**：

```bash
python3 primehub_publish.py search "我的技能名"   # 能搜到+归属自己的账号 = 已上架
python3 primehub_publish.py my                    # 在架列表里有这条
```

浏览器开 https://primehub.primebot.com/#/search 搜技能名，详情页能看到简介/图标/机型。

**用户视角闭环（终极验证）**：拿一台装了启元官方手机 App 的手机（和你的机器人绑定同一账号或同局域网），
App 技能市场里搜技能名 → 下载/部署 → App 里点运行 → 机器人真的演一遍。
这一步通过，才算「外部用户不 SSH 也能用」，技能真正上架完成。

### 8.3 管理在架（发错了/要换版）

```bash
python3 primehub_publish.py my            # 列我的在架（id + 名字）
python3 primehub_publish.py delete <id>   # 删除
```

**关键平台行为**：同名技能再 publish **不会覆盖，会新建一条**。
发新版本：先 `delete` 旧条目，再 `publish` 新的。

### 8.4 已知 API 坑（客户端已内置规避，手动 curl 时注意）

- 本机 python urllib 打 primehub 会被掐 SSL（UNEXPECTED_EOF）→ 必须 curl 子进程
- 真实前缀 `/app-api/content-server/`（发布）/`/app-api/search-server/`（搜索）
- 搜索参数名 `keywords/page/rows`（用 pageNum/pageSize 报 9999）
- 传输层 SM4-CBC 加密（key/iv 在 web bundle 混淆，`primehub_client.py` 已实现）

---

## 附录 A：常见坑速查

| 症状 | 根因 | 修法 |
|---|---|---|
| 机器人装了技能没反应 | 代码用了 rclpy/ROS2 契约 | 用 `robot` 对象契约（§2.2） |
| 动作全部不执行 | whole_body + 室内模式 | 换 upper_body ID（§2.3） |
| 部分动作没触发 | 编排表索引越界（如循环 0-7 写了 8） | 检查编排索引 |
| 台词被吞/截断 | 没等上一句播完就发下一句 | 用 `speak()` 轮询（§3） |
| 音效放到一半消失 | 后发的 TTS/动画 interrupt=True 停了它 | §2.4 第 3 条 |
| mp3 放了没声 | 板载只吃 wav | ffmpeg 转 wav |
| stdout 看不到 print | 缓冲 | `flush=True` |
| deploy 显示 timeout | harness 超时 < 技能总时长 | 给足第二参数（§5.2） |
| publish 报 1001 缺字段 | 字段名拼错/漏 codeList | 对照 §8.1 模板 |
| querySkillList 报 9999 | 参数名 pageNum/pageSize | keywords/page/rows |
| 同名技能出现两条 | 平台不去重 | 先 delete 再 publish |

## 附录 B：完整真实案例（kit 自带）

**`example-jukebox/`（点歌台，已上架 PrimeHub）**——一个从联网到伴舞的全链路真实技能，
覆盖了绝大多数开发会遇到的写法：

| 想学什么 | 看 `example-jukebox/src/main.py` 哪里 |
|---|---|
| 台词轮询播完（所有技能的地基） | `speak()` |
| 联网取资源（任何 API 类技能通用） | `find_song()` / `download_song()`（urllib+重试+ffmpeg 转码） |
| 音频播放与状态处理 | `play_audio_file` 调用处 + `music_really_over()`（状态抖动滤波） |
| 音频持续时动作怎么发 | 主循环里 `play_animation(anim, interrupt=False)` |
| 持续随机动作池 | `MOVE_POOL` + `next_move()` |
| 换自己要的东西 | 顶部 `SONG_NAME` / `MOVE_POOL` 两个常量 |

改之前先把原版跑通（第 5 步流程），确认环境没问题再动手。
