#!/usr/bin/env python3
"""一键部署：建 .venv、离线装基础依赖、冒烟测试。

由 setup.bat 调用，也可以手动跑：
    python tools/bootstrap.py            # 安装出 PPTX 的基础依赖
    python tools/bootstrap.py --with-pdf-check  # 额外安装 PDF 几何检查依赖
    python tools/bootstrap.py --check    # 只检查，不安装

设计约定：
  * 只用一个解释器建 venv，并由调用方（setup.bat）显式传入，避免多解释器歧义
  * 依赖优先从 tools/wheels/ 离线装；缺包或 wheel 与 Python 不兼容时联网重试（并明确告知）
  * 装完立刻做冒烟测试：出 3 页 pptx 再读回来，确认引擎真能跑
退出码：0 成功 / 1 失败
"""
import argparse
import os
import shlex
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VENV = os.path.join(ROOT, ".venv")
VENV_PY = os.path.join(VENV, "Scripts", "python.exe") if os.name == "nt" else os.path.join(VENV, "bin", "python")
WHEELS = os.path.join(HERE, "wheels")
BASE_REQS = [("python-pptx", "1.0.2")]
PDF_CHECK_REQS = [("PyMuPDF", "1.24.14"), ("comtypes", "1.4.17")]
MIRROR = "https://mirrors.aliyun.com/pypi/simple/"


def echo(msg=""):
    print(msg, flush=True)


def step(msg):
    echo(f"\n[>] {msg}")


def ok(msg):
    echo(f"  [OK] {msg}")


def fail(msg):
    echo(f"  [FAIL] {msg}")


def sub(cmd, **kw):
    """跑子进程，返回 (退出码, 合并输出)。不抛异常，错误交给调用方判定。"""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=900, **kw)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def ensure_venv(python_cmd: list[str]) -> bool:
    step("创建虚拟环境 .venv")
    if os.path.exists(VENV_PY):
        code, out = sub([VENV_PY, "-c", "import sys;print(sys.version_info[:3])"])
        if code == 0:
            ok(f"已存在，复用：{out.strip()}")
            return True
        echo("  已有 .venv 但不可用，重建")
        shutil.rmtree(VENV, ignore_errors=True)

    code, out = sub([*python_cmd, "-m", "venv", VENV])
    if code != 0 or not os.path.exists(VENV_PY):
        fail("建 venv 失败：\n" + out.strip()[-800:])
        return False
    ok(f"已创建：{VENV}")
    return True


def install(with_pdf_check: bool = False) -> bool:
    step("安装依赖")
    reqs = BASE_REQS + (PDF_CHECK_REQS if with_pdf_check else [])
    local = sorted(f for f in os.listdir(WHEELS)) if os.path.isdir(WHEELS) else []
    has_wheels = any(f.lower().startswith("python_pptx") for f in local)

    if has_wheels:
        wheel_mb = sum(os.path.getsize(os.path.join(WHEELS, f)) for f in local) / 1024 / 1024
        echo(f"  离线安装，使用 tools/wheels/（{len(local)} 个文件，{wheel_mb:.1f} MB）")
        code, out = sub([VENV_PY, "-m", "pip", "install", "--no-index",
                         "--find-links", WHEELS, "--disable-pip-version-check",
                         "-q"] + [f"{n}=={v}" for n, v in reqs])
        if code == 0:
            ok("离线安装完成")
        else:
            echo("  [提示] 本地 wheel 不完整或与当前 Python 不兼容，改用联网安装重试。")
    else:
        echo("  tools/wheels/ 里没有可用 wheel，改用联网安装")

    if not has_wheels or code != 0:
        code, out = sub([VENV_PY, "-m", "pip", "install", "--disable-pip-version-check",
                         "-q", "-i", MIRROR, "--trusted-host", "mirrors.aliyun.com"]
                        + [f"{n}=={v}" for n, v in reqs])
        if code != 0:
            fail("联网安装失败（检查网络，或在受支持的 Python 环境中重试）：\n" + out.strip()[-1200:])
            return False
        ok("联网安装完成")

    imports = "import pptx;print(pptx.__version__)"
    if with_pdf_check:
        imports = "import pptx,pymupdf,comtypes;print(pptx.__version__, comtypes.__version__)"
    code, out = sub([VENV_PY, "-c", imports])
    if code != 0:
        fail("依赖装完但仍无法导入：\n" + out.strip()[-600:])
        return False
    ok("导入检查通过（python-pptx = %s）" % out.strip())
    return True


SMOKE_BRIEF = {
    "meta": {"title": "部署自检", "audience": "setup.bat", "date": "自检"},
    "slides": [
        {"type": "cover", "kicker": "部署自检",
         "title_lines": ["部署成功，", "引擎可以出图"],
         "meta": "setup.bat · tools/wheels/ · 离线安装",
         "conclusion": "三页读得回来才算装好，不靠文档声称。",
         "footer_left": "StartUp-AI 自检", "footer_right": "SMOKE TEST"},
        {"type": "three-col", "title": "基础出图环境已就位",
         "source": "Source：setup.bat 自动生成，非业务数据。",
         "cols": [
             {"tag": "RENDER", "label": "出图", "body": "python-pptx 负责生成 pptx 文件。",
              "num": "必需", "unit": "python-pptx"},
             {"tag": "OPTIONAL", "label": "几何检查", "body": "按需安装，普通出稿不需要。",
              "num": "可选", "unit": "PDF 检查依赖"},
             {"tag": "OUTPUT", "label": "交付", "body": "基础环境已能生成可编辑的 PPTX。",
              "num": "PPTX", "unit": "默认产物"},
         ]},
        {"type": "closing", "statement": ["现在可以出 PPT 了"],
         "supports": ["make-ppt.bat briefs/01-chenghai-zhaoyiming.json 输出.pptx"],
         "footer": "StartUp-AI 自检通过"},
    ],
}


def smoke() -> bool:
    """出 3 页 pptx 再读回来。验证的是「装完立刻能用」，不是在文档里声称能用。"""
    step("冒烟测试：渲染一份 3 页 pptx")
    import json
    import tempfile
    # Windows 安全策略可能禁止子进程在系统 TEMP 下写入 PPTX。部署刚
    # 创建/验证过项目内的 .venv，因此把冒烟文件放在该可写目录里。
    tmpdir = tempfile.mkdtemp(prefix="startupai-smoke-", dir=VENV)
    try:
        src = os.path.join(tmpdir, "smoke.json")
        out = os.path.join(tmpdir, "smoke.pptx")
        with open(src, "w", encoding="utf-8") as fh:
            json.dump(SMOKE_BRIEF, fh, ensure_ascii=False)
        code, log = sub([VENV_PY, os.path.join(HERE, "deck_engine.py"), src, out])
        if code != 0 or not os.path.exists(out):
            fail("渲染失败，退出码 %d：\n%s" % (code, log.strip()[-1200:]))
            return False
        code, log = sub([VENV_PY, "-c",
                         "from pptx import Presentation;import sys;"
                         "p=Presentation(sys.argv[1]);print(len(p.slides))", out])
        if code != 0:
            fail("生成的文件读不回来：\n" + log.strip()[-600:])
            return False
        ok(f"渲染并读回成功（{log.strip()} 页）")
        return True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description="StartUp-AI 一键部署")
    ap.add_argument("--python", default=sys.executable, help="用于创建 venv 的解释器路径或启动器命令")
    ap.add_argument("--check", action="store_true", help="只检查现状，不安装")
    ap.add_argument("--with-pdf-check", action="store_true", help="额外安装 PDF 几何检查依赖")
    args = ap.parse_args()
    python_cmd = [args.python] if os.path.isfile(args.python) else shlex.split(args.python)
    if not python_cmd:
        echo("  [FAIL] 基础解释器命令为空")
        return 1

    echo("=" * 56)
    echo("  StartUp-AI 版式引擎部署")
    echo("=" * 56)
    echo(f"  项目目录 : {ROOT}")
    echo(f"  基础解释器: {' '.join(python_cmd)}")

    if args.check:
        for path, label in ((VENV_PY, ".venv"), (WHEELS, "tools/wheels")):
            echo(f"  {label:<14}{'存在' if os.path.exists(path) else '缺失'}")
        return 0

    if not ensure_venv(python_cmd):
        return 1
    if not install(args.with_pdf_check):
        return 1
    if not smoke():
        return 1

    echo("\n" + "=" * 56)
    echo("  依赖安装完成。接下来：")
    echo("    1) python tools/doctor.py     检查基础 PPTX 环境")
    echo("       python tools/doctor.py --pdf  按需检查 PDF 几何环境")
    echo("    2) make-ppt.bat --list        看出厂用例")
    echo("=" * 56)
    return 0


if __name__ == "__main__":
    sys.exit(main())
