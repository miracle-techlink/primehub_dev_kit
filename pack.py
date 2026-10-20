#!/usr/bin/env python3
"""pack.py —— 把技能目录打成 .rpk（普通 zip，固定结构）

用法：
    python3 pack.py skill-voice-commander [输出目录]

产出 skill-xxx.rpk，内部结构：
    cfg/pkg.yaml
    src/*.py
    readme.md
另有 media/ 目录（可选）原样打包，用于放 mp4/mp3 资源。
"""
import sys
import zipfile
from pathlib import Path


def pack(skill_dir: Path, out_dir: Path) -> Path:
    assert (skill_dir / "cfg" / "pkg.yaml").exists(), f"{skill_dir} 缺 cfg/pkg.yaml"
    py_files = list((skill_dir / "src").glob("*.py"))
    assert py_files, f"{skill_dir} 缺 src/*.py"

    out = out_dir / f"{skill_dir.name}.rpk"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(skill_dir / "cfg" / "pkg.yaml", "cfg/pkg.yaml")
        readme = skill_dir / "readme.md"
        if readme.exists():
            z.write(readme, "readme.md")
        for f in py_files:
            z.write(f, f"src/{f.name}")
        # 可选媒体资源目录
        media = skill_dir / "media"
        if media.exists():
            for f in media.rglob("*"):
                if f.is_file():
                    z.write(f, f"media/{f.relative_to(media)}")
    # 校验
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert "cfg/pkg.yaml" in names
        assert any(n.startswith("src/") and n.endswith(".py") for n in names)
        print(f"OK {out} ({out.stat().st_size} B, {len(names)} files)")
    return out


if __name__ == "__main__":
    skill = Path(sys.argv[1] if len(sys.argv) > 1 else "skill-voice-commander")
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
    pack(skill, out_dir)
