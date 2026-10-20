# PrimeHub Skill Dev Kit

启元机器人（Q1 / T1）技能开发工具包——从零做出一个机器人技能，真机调试，发布到
[PrimeHub 技能市场](https://primehub.primebot.com)。

## 快速开始

```bash
unzip primehub-dev-kit.zip && cd primehub-dev-kit   # 或直接 clone 本仓库
python3 primehub_publish.py search "你好"           # 自检：能搜 = 网络和传输层 OK
```

然后按 `SKILL_PUBLISH_GUIDE.md` 的 0→8 步走：

```
注册 PrimeHub → 给 AI agent 喂机器人契约 → vibe coding 改模板 → 打包 .rpk
→ 真机调试 → 提取登录 token → 一条命令发布上架
```

## 里面有什么

| 文件 | 用途 |
|---|---|
| `SKILL_PUBLISH_GUIDE.md` | 完整手册（开发顺序、调试判读、失败码表、发布流程） |
| `template-skill/` | 技能模板（复制成你的技能） |
| `example-jukebox/` | 完整真实案例：点歌台（联网搜歌+节拍分析+随机伴舞，已上架 PrimeHub） |
| `pack.py` | 打包器：技能目录 → `.rpk` |
| `deploy_test.py` | 真机调试 harness（scp 到机器人跑） |
| `primehub_publish.py` | PrimeHub 发布/删除/查询客户端 |
| `primehub_client.py` | SM4 传输层（发布客户端的依赖） |
| `extract_token.py` | 从 Firefox 登录态自动提取 PrimeHub token |

## 环境要求

- Python 3 + `pip install gmssl`
- `curl`、`sshpass`
- 一台同网段的 Q1/T1 机器人（SSH `run`）
- 本机 Firefox（用于 PrimeHub 登录态，发布凭证自动提取）

## 支持

动作 ID 表、平台约束（室内模式/音频互斥/状态轮询）等机器人侧知识都在
`SKILL_PUBLISH_GUIDE.md` §2——AI agent（Claude Code / Cursor）可直接读它 vibe coding。
