#!/usr/bin/env python3
"""PrimeHub 发布客户端（curl transport 版）

2026-10-19 实测：本机 python urllib 对 primehub SSL 握手会被服务端掐断
（UNEXPECTED_EOF_WHILE_READING），curl 正常 → 全链路改走 subprocess curl。

关键端点（均 https://primehub.primebot.com）：
  POST /app-api/content-server/file/upload                multipart 明文 + Bearer → fileUrl
  POST /app-api/content-server/skillCenter/publishSkill   SM4 加密体（本模块 call()）
  POST /app-api/search-server/portal/querySkillList       SM4 加密体（免登录可查）
    · 参数名是 PC 端约定：keywords / queryType / page / rows（pageNum/pageSize 会 9999）
  POST /app-api/content-server/skillCenter/queryPageByUserCode  我的发布列表

用法：
  python3 primehub_publish.py search '<keywords>'
  python3 primehub_publish.py publish <rpk路径> '<publishJson>'
"""
import json, uuid, time, subprocess, urllib.parse, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from primehub_client import KEY, IV  # SM4 key/iv + unscramble
from gmssl.sm4 import CryptSM4, SM4_ENCRYPT, SM4_DECRYPT

BASE = "https://primehub.primebot.com"
TOKEN_FILE = "/tmp/ph_token.txt"   # Firefox localStorage 提取的 JWT（手机验证码登录换取）


def call(path, params, token=None, ns="content-server"):
    params = dict(params); params["timestamp"] = int(time.time() * 1000)
    params["requestId"] = str(uuid.uuid4())
    inner = urllib.parse.quote(json.dumps(params, separators=(",", ":")), safe="")
    c = CryptSM4(); c.set_key(KEY, SM4_ENCRYPT)
    ct = c.crypt_cbc(IV, inner.encode()).hex()
    out = subprocess.run(
        ["curl", "-s", "--max-time", "40", "-X", "POST",
         BASE + "/app-api/" + ns + "/" + path,
         "-H", "Content-Type: application/json", "-H", "request-t: true",
         "-H", "Origin: " + BASE, "-H", "Referer: BASE + '/'",
         ] + (["-H", "Authorization: Bearer " + token] if token else [])
        + ["-d", json.dumps({"data": ct})],
        capture_output=True, text=True).stdout
    d = json.loads(out)
    if isinstance(d.get("data"), str) and d.get("code") == 1000:
        c2 = CryptSM4(); c2.set_key(KEY, SM4_DECRYPT)
        d["data"] = json.loads(urllib.parse.unquote(
            c2.crypt_cbc(IV, bytes.fromhex(d["data"])).decode()))
    return d


def upload(rpk_path, token):
    boundary = "----" + uuid.uuid4().hex
    fn = os.path.basename(rpk_path)
    part = ("--" + boundary + "\r\nContent-Disposition: form-data; name=\"file\"; "
            "filename=\"" + fn + "\"\r\nContent-Type: application/octet-stream\r\n\r\n")
    body = part.encode() + open(rpk_path, "rb").read() + ("\r\n--" + boundary + "--\r\n").encode()
    out = subprocess.run(
        ["curl", "-s", "--max-time", "120", "-X", "POST",
         BASE + "/app-api/content-server/file/upload",
         "-H", "Content-Type: multipart/form-data; boundary=" + boundary,
         "-H", "Authorization: Bearer " + token, "-H", "request-t: true",
         "-H", "Origin: " + BASE, "-H", "Referer: " + BASE + "/",
         "--data-binary", "@-"], input=body, capture_output=True).stdout.decode()
    d = json.loads(out)
    if isinstance(d.get("data"), str):
        c = CryptSM4(); c.set_key(KEY, SM4_DECRYPT)
        d["data"] = json.loads(urllib.parse.unquote(
            c.crypt_cbc(IV, bytes.fromhex(d["data"])).decode()))
    return d["data"]["fileUrl"]


def my_skills(token):
    r = call("skillCenter/queryPage", {"page": 1, "rows": 50}, token)
    return (r.get("data") or {}).get("records") or []


def delete(skill_id, token):
    return call("skillCenter/deleteSkillById", {"id": skill_id}, token)


def search(keywords, token=None):
    r = call("portal/querySkillList", {"keywords": keywords, "queryType": 1, "page": 1, "rows": 30},
             token, ns="search-server")
    recs = (r.get("data") or {}).get("records") or []
    return [{"id": s.get("id"), "name": s.get("skillName"), "models": s.get("robotModels")} for s in recs]


if __name__ == "__main__":
    token = open(TOKEN_FILE).read().strip()
    if sys.argv[1] == "search":
        for s in search(sys.argv[2], token):
            print(s["id"], s["name"], s["models"])
    elif sys.argv[1] == "my":
        for s in my_skills(token):
            print(s.get("id"), s.get("skillName"))
    elif sys.argv[1] == "delete":
        print(delete(int(sys.argv[2]), token))
    elif sys.argv[1] == "publish":
        rpk, meta = sys.argv[2], json.loads(sys.argv[3])
        meta["packageUrl"] = upload(rpk, token)
        print(call("skillSkill/publishSkill", meta, token) if False else call("skillCenter/publishSkill", meta, token))
