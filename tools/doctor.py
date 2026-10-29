#!/usr/bin/env python3
"""环境体检：出 PPT 需要的东西，逐项查清并给出明确结论。

    python tools/doctor.py
    python tools/doctor.py --json     # 机器可读，给脚本用

判定分三档：
  [必需] 缺一项就不能出稿 → 退出码 1
  [告警] 缺了会少一项能力，但能出稿 → 退出码仍是 0
  [信息] 只报告，不判定

LibreOffice 按项目决定列为必需（deck_lint 的几何检查依赖它转 PDF）。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VENV_PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe") if os.name == "nt" \
    else os.path.join(ROOT, ".venv", "bin", "python")
SOFFICE_CANDIDATES = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/usr/bin/soffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
]
FONT = "微软雅黑"


def echo(msg=""):
    print(msg, flush=True)


def find_soffice():
    """与 deck_lint.py 用同一套查找顺序，保证体检结论和实际行为一致。"""
    for path in SOFFICE_CANDIDATES:
        if os.path.exists(path):
            return path
    return shutil.which("soffice") or shutil.which("libreoffice")


def run(cmd, timeout=60):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def check_python():
    if not os.path.exists(VENV_PY):
        return False, "缺少 .venv，先跑 setup.bat", ""
    code, out = run([VENV_PY, "-c", "import sys;print('%d.%d.%d' % sys.version_info[:3])"])
    if code != 0:
        return False, ".venv 里的解释器不可用", ""
    version = out.strip()
    major, minor = (int(x) for x in version.split(".")[:2])
    if (major, minor) < (3, 9):
        return False, f"Python {version} 过低，需要 3.9+", version
    return True, "", version


def check_module(name, label):
    if not os.path.exists(VENV_PY):
        return False, "先跑 setup.bat", ""
    code, out = run([VENV_PY, "-c", f"import {name};print(getattr({name},'__version__','?'))"])
    if code != 0:
        return False, "未安装", ""
    return True, "", out.strip().splitlines()[-1] if out.strip() else "?"


def check_renderer():
    """几何检查要靠一个渲染器把 pptx 转 PDF。三选一，不要求装哪一个。

    顺序与 deck_lint.to_pdf 一致：PowerPoint > LibreOffice > WPS。

    全部靠运行时探测，不假设任何一种存在：别人的机器上可能只装了 LibreOffice，
    也可能三种都没有。三种都没有时返回 False，由 main 判「不能出稿」。
    """
    if not os.path.exists(VENV_PY):
        return False, "先跑 setup.bat", ""
    found, failed = [], []
    for key, label in (("PowerPoint.Application", "PowerPoint"),
                       ("Kwpp.Application", "WPS")):
        code, out = run([VENV_PY, "-c",
                         "import comtypes.client as c;app=c.CreateObject('%s');"
                         "print(app.Version);app.Quit()" % key], timeout=120)
        if code == 0 and out.strip():
            found.append(label)
        else:
            failed.append(label)
    soffice = find_soffice()
    if soffice:
        found.insert(1 if "PowerPoint" in found else 0, "LibreOffice")

    if not found:
        return False, "三种渲染器都不可用，几何检查跑不了", ""
    return True, "", " / ".join(found) + ("（首选 " + found[0] + "）" if found else "")


def check_font():
    """字体缺失只告警：会出稿，但版式可能被替代字体撑坏。

    查注册表而不是 System.Drawing：微软雅黑的家族名是 "Microsoft YaHei"，
    中文名「微软雅黑」在字体集合里匹配不到，会误报。
    """
    if os.name != "nt":
        return None, "非 Windows，跳过字体检查", ""
    ps = (r"$k='HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts';"
          r"$n=(Get-ItemProperty $k).PSObject.Properties.Name -join ';';"
          r"if ($n -match 'YaHei') { '1' } else { '0' }")
    code, out = run(["powershell", "-NoProfile", "-Command", ps], timeout=90)
    if code != 0:
        return None, "无法读取字体列表", ""
    if out.strip().endswith("1"):
        return True, "", FONT
    return False, f"未装「{FONT}」，将用替代字体，版式可能偏移", ""


def check_png_export():
    """--png 逐页导图依赖 comtypes。comtypes 已进离线 wheel，正常都会有。

    只报信息，不判定：没有它照样能出稿，只是少了逐页看图这一步。
    """
    if os.name != "nt":
        return None, "非 Windows，跳过", ""
    if not os.path.exists(VENV_PY):
        return None, "先跑 setup.bat", ""
    code, _ = run([VENV_PY, "-c", "import comtypes.client"], timeout=60)
    if code != 0:
        return None, "缺 comtypes，--png 导图不可用（不影响出 PPT）", ""
    return True, "", "可用"


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description="StartUp-AI 环境体检")
    ap.add_argument("--json", action="store_true", help="输出机器可读结果")
    args = ap.parse_args()

    rows = []
    py_ok, py_msg, py_ver = check_python()
    rows.append(("必需", "Python（.venv）", py_ok, py_msg, py_ver))
    for mod, label in (("pptx", "python-pptx"), ("pymupdf", "PyMuPDF（几何检查）")):
        ok_, msg_, ver = check_module(mod, label)
        rows.append(("必需", label, ok_, msg_, ver))
    rd_ok, rd_msg, rd_ver = check_renderer()
    rows.append(("必需", "PDF 渲染器（三选一）", rd_ok, rd_msg, rd_ver))
    ft_ok, ft_msg, ft_ver = check_font()
    rows.append(("告警", f"字体 {FONT}", ft_ok, ft_msg, ft_ver))
    pp_ok, pp_msg, pp_ver = check_png_export()
    rows.append(("信息", "--png 导图（comtypes）", pp_ok, pp_msg, pp_ver))
    wheels = os.path.join(HERE, "wheels")
    n_wheels = len([f for f in os.listdir(wheels) if f.endswith(".whl")]) if os.path.isdir(wheels) else 0
    rows.append(("信息", "离线 wheel 包", n_wheels > 0, "" if n_wheels else "缺失，下次重装需联网",
                 f"{n_wheels} 个文件"))

    if args.json:
        echo(json.dumps([{"level": r[0], "name": r[1], "ok": r[2], "msg": r[3], "detail": r[4]}
                         for r in rows], ensure_ascii=False, indent=2))
    else:
        echo("=" * 62)
        echo("  StartUp-AI 环境体检")
        echo("=" * 62)
        for level, name, ok_, msg, detail in rows:
            if ok_ is True:
                mark, tail = "[OK]  ", detail
            elif ok_ is False:
                mark, tail = "[XX]  ", msg
            else:
                mark, tail = "[--]  ", msg
            echo(f"  {mark}{level}  {name:<24}{tail}")

        blocking = [r for r in rows if r[0] == "必需" and r[2] is not True]
        warn = [r for r in rows if r[0] == "告警" and r[2] is False]
        echo("-" * 62)
        if blocking:
            echo("  结论：当前不能出稿。缺：")
            for _, name, _, msg, _ in blocking:
                echo(f"        - {name}：{msg}")
            if any("渲染器" in r[1] for r in blocking):
                echo("        装任意一个即可（推荐顺序）：")
                echo("          1) Microsoft PowerPoint —— 最快，且与最终观感一致")
                echo("          2) LibreOffice —— https://zh-cn.libreoffice.org/download/")
                echo("          3) WPS Office —— 兜底，渲染细节可能与 PowerPoint 有差异")
        else:
            echo("  结论：现在可以出 PPT。")
            echo("        make-ppt.bat briefs/01-chenghai-zhaoyiming.json 输出.pptx")
        if warn:
            echo("  告警：" + "；".join(f"{r[1]}（{r[3]}）" for r in warn))

    return 1 if any(r[0] == "必需" and r[2] is not True for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
