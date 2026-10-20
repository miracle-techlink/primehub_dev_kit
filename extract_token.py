#!/usr/bin/env python3
"""extract_token.py —— 从本机 Firefox localStorage 提取 PrimeHub 登录 token

原理：登录 primehub.primebot.com 后，JWT 存在 Firefox profile 的
storage/default/https+++primehub.primebot.com/ls/data.sqlite
（运行中的 Firefox 会锁库 → 先拷快照再查；value 是 snappy 压缩 BLOB →
解压（uvarint 长度头 + literal/copy tag 流）→ 取 skillhub_token 键。

用法：python3 extract_token.py [输出文件(默认 /tmp/ph_token.txt)]
前提：Firefox 登录过 PrimeHub 且在 7 天内（token exp 7 天）。
"""
import glob
import os
import shutil
import sqlite3
import sys
import tempfile

PROFILE_GLOB = os.path.expanduser(
    "~/snap/firefox/common/.mozilla/firefox/*/storage/default/"
    "https+++primehub.primebot.com/ls/data.sqlite")


def snappy_decompress(data: bytes) -> bytes:
    """纯 stdlib snappy 解压：uvarint 声明长度 + literal/copy tag 流。"""
    def uvarint(d, i):
        v = s = 0
        while True:
            b = d[i]; i += 1
            v |= (b & 0x7F) << s; s += 7
            if not (b & 0x80):
                break
        return v, i

    declared, i = uvarint(data, 0)
    out = bytearray(); n = len(data)
    while i < n:
        tag = data[i]; i += 1
        t = tag & 0x03
        if t == 0:                                  # literal
            ln = tag >> 2
            if ln < 60:
                ln += 1
            else:
                extra = ln - 59
                ln = int.from_bytes(data[i:i + extra], "little") + 1
                i += extra
            out += data[i:i + ln]; i += ln
        else:                                       # copy
            if t == 1:
                ln = ((tag >> 2) & 0x07) + 4
                off = ((tag >> 5) << 8) | data[i]; i += 1
            elif t == 2:
                ln = (tag >> 2) + 1
                off = int.from_bytes(data[i:i + 2], "little"); i += 2
            else:
                ln = (tag >> 2) + 1
                off = int.from_bytes(data[i:i + 4], "little"); i += 4
            for _ in range(ln):
                out.append(out[-off])
    assert len(out) == declared, (len(out), declared)
    return bytes(out)


def main():
    out_file = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ph_token.txt"
    dbs = glob.glob(PROFILE_GLOB)
    assert dbs, "没找到 Firefox 的 primehub localStorage（先在 Firefox 登录一次 PrimeHub）"
    for db in dbs:
        tmp = tempfile.mktemp(suffix=".sqlite")
        shutil.copy(db, tmp)
        try:
            rows = dict(sqlite3.connect(tmp).execute("SELECT key, value FROM data").fetchall())
        finally:
            os.unlink(tmp)
        if "skillhub_token" in rows:
            tok = snappy_decompress(rows["skillhub_token"]).decode().strip('"')
            open(out_file, "w").write(tok)
            print("token → %s（%d 字符，7 天内有效）" % (out_file, len(tok)))
            return
    print("没找到 skillhub_token——Firefox 登录态过期，重新登录一次", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
