#!/usr/bin/env python3
"""pack.py —— 把技能目录打成 .rpk（普通 zip，固定结构）

用法：
    python3 pack.py skill-voice-commander [输出目录]

产出 skill-xxx.rpk，内部结构：
    cfg/pkg.yaml
    src/main.py（必需）
    src/*.py
    readme.md
另有 media/ 目录（可选）原样打包，用于放 mp4/mp3 资源。
"""
import sys
import tempfile
import zipfile
from pathlib import Path


def pack(skill_dir: Path, out_dir: Path) -> Path:
    manifest = skill_dir / "cfg" / "pkg.yaml"
    source = skill_dir / "src"
    for required in (manifest, source / "main.py"):
        if not required.is_file():
            raise ValueError(f"{skill_dir} 缺 {required.relative_to(skill_dir).as_posix()}")

    out = out_dir / f"{skill_dir.name}.rpk"
    files = [manifest]
    readme = skill_dir / "readme.md"
    if readme.is_file():
        files.append(readme)
    files.extend(path for path in sorted(source.glob("*.py")) if path.is_file())
    files.extend(
        path for path in sorted((skill_dir / "media").rglob("*")) if path.is_file()
    )

    # 完整写入 ZIP 后才替换现有包，写入失败时保留上次结果。
    with tempfile.NamedTemporaryFile(dir=out_dir, suffix=".tmp", delete=False) as tmp:
        temporary_path = Path(tmp.name)
    try:
        with zipfile.ZipFile(temporary_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, path.relative_to(skill_dir).as_posix())
        size = temporary_path.stat().st_size
        temporary_path.replace(out)
    finally:
        temporary_path.unlink(missing_ok=True)
    print(f"OK {out} ({size} B, {len(files)} files)")
    return out


if __name__ == "__main__":
    skill = Path(sys.argv[1] if len(sys.argv) > 1 else "skill-voice-commander")
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
    try:
        pack(skill, out_dir)
    except (OSError, ValueError) as error:
        sys.exit(f"打包失败：{error}")
