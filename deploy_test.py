import json, urllib.request, zipfile, sys, time

fp = sys.argv[1]
TASK_TIMEOUT = int(sys.argv[2]) if len(sys.argv) > 2 else 120   # 必须 ≥ 技能总时长
z = zipfile.ZipFile(fp)
# lumina 包根是 src/main.py; script 路径要包级 main.py 内容
src = z.read("src/main.py").decode()
meta = {}
for line in z.read("cfg/pkg.yaml").decode().splitlines():
    if ":" in line and not line.startswith("#"):
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip()

body = json.dumps({"package_name": meta["package_name"], "script": src,
                   "version": meta.get("version", "1.0.0"),
                   "author": meta.get("author", "workshop"),
                   "description": meta.get("description", "")}).encode()
req = urllib.request.Request("http://127.0.0.1:58080/packages/script", data=body,
                             headers={"Content-Type": "application/json"})
r = json.loads(urllib.request.urlopen(req, timeout=15).read())
print("install:", r.get("pkg_id"), r.get("version"))

req = urllib.request.Request("http://127.0.0.1:58080/tasks",
                             data=json.dumps({"pkg_id": meta["package_name"], "timeout": TASK_TIMEOUT}).encode(),
                             headers={"Content-Type": "application/json"})
tid = json.loads(urllib.request.urlopen(req, timeout=15).read())["task_id"]
print("task:", tid)
for _ in range(30):
    time.sleep(5)
    d = json.loads(urllib.request.urlopen(f"http://127.0.0.1:58080/tasks/{tid}", timeout=10).read())
    if d["status"] != "running":
        print("final:", d["status"])
        print("stdout:", d["stdout"])
        print("error:", repr(d["error"])[:200])
        break
else:
    print("still running...")
