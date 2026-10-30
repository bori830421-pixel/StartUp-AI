#!/usr/bin/env python3
"""环境体检：出 PPT 需要的东西，逐项查清并给出明确结论。

    python tools/doctor.py
    python tools/doctor.py --json     # 机器可读，给脚本用

判定分三档：
  [必需] 缺一项就不能出稿 → 退出码 1
  [告警] 缺了会少一项能力，但能出稿 → 退出码仍是 0
  [信息] 只报告，不判定

渲染器分两层判：Microsoft PowerPoint 是首选，单列一行（缺了只告警，但结论区会
单独给一段安装指引，明确让用户装完重跑 setup.bat）；LibreOffice / WPS 是兜底，
三者全无才算不能出稿——几何检查要靠其中一个把 pptx 转 PDF。
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

POWERPNT_CANDIDATES = [
    r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE",
    r"C:\Program Files (x86)\Microsoft Office\root\Office16\POWERPNT.EXE",
    r"C:\Program Files\Microsoft Office\Office16\POWERPNT.EXE",
    r"C:\Program Files (x86)\Microsoft Office\Office16\POWERPNT.EXE",
    "/Applications/Microsoft PowerPoint.app",
]


def echo(msg=""):
    print(msg, flush=True)


def pad(text, width):
    """按显示宽度补空格：中文占两格，不补的话各行的值列会歪。"""
    w = sum(2 if ord(c) > 0x2E80 else 1 for c in text)
    return text + " " * max(0, width - w)


def find_powerpoint():
    """找 PowerPoint 本体，不信 COM 的 ProgID。

    WPS 会注册 PowerPoint.Application 这个兼容 ProgID，只探 COM 会把 WPS
    误判成 PowerPoint——本机实测就是这样：CreateObject 成功，调用即失败。
    所以先查安装路径与 App Paths 注册表，两者都没有才算没装。
    """
    for path in POWERPNT_CANDIDATES:
        if os.path.exists(path):
            return path
    if os.name != "nt":
        return None
    for hive in ("HKLM:", "HKCU:"):
        key = hive + r"\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\POWERPNT.EXE"
        code, out = run(["powershell", "-NoProfile", "-Command",
                         "(Get-ItemProperty '%s' -ErrorAction SilentlyContinue).'(default)'" % key],
                        timeout=60)
        if code == 0 and out.strip():
            return out.strip()
    return None


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
    # 宿主环境可能往 stderr 塞告警（本机就有一条 sitecustomize 的 PermissionError），
    # 直接取最后一行会把告警当版本号。只认以数字开头的那行。
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    vers = [ln for ln in lines if ln[0].isdigit()]
    return True, "", vers[-1] if vers else (lines[-1] if lines else "?")


def check_powerpoint():
    """首选渲染器单独判：装没装是事实，不问 COM 能不能调通。"""
    path = find_powerpoint()
    if path:
        return True, "", path
    return False, "未检测到。先装 PowerPoint，再运行 setup.bat 复检", ""


def check_renderer():
    """几何检查要靠一个渲染器把 pptx 转 PDF。

    PowerPoint 是首选，单列判定；LibreOffice 与 WPS 只作兜底，
    三者全无才算「不能出稿」。兜底渲染器的版式可能与 PowerPoint 有差异，
    所以缺 PowerPoint 时即使能出稿，也要在结论里点名提示安装。
    """
    if not os.path.exists(VENV_PY):
        return False, "先跑 setup.bat", ""
    found = []
    for key, label in (("Kwpp.Application", "WPS"),):
        code, out = run([VENV_PY, "-c",
                         "import comtypes.client as c;app=c.CreateObject('%s');"
                         "print(app.Version);app.Quit()" % key], timeout=120)
        if code == 0 and out.strip():
            found.append(label)
    if find_soffice():
        found.insert(0, "LibreOffice")

    if not found:
        return False, "三种渲染器都不可用，几何检查跑不了", ""
    return True, "", "兜底可用：" + " / ".join(found)


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
    pw_ok, pw_msg, pw_ver = check_powerpoint()
    rows.append(("告警", "Microsoft PowerPoint", pw_ok, pw_msg, pw_ver))
    rd_ok, rd_msg, rd_ver = check_renderer()
    rows.append(("必需", "PDF 渲染器兜底", rd_ok, rd_msg, rd_ver))
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
            echo(f"  {mark}{level}  {pad(name, 26)}{tail}")

        blocking = [r for r in rows if r[0] == "必需" and r[2] is not True]
        warn = [r for r in rows if r[0] == "告警" and r[2] is False]
        echo("-" * 62)
        if blocking:
            echo("  结论：当前不能出稿。缺：")
            for _, name, _, msg, _ in blocking:
                echo(f"        - {name}：{msg}")
            if any("渲染器" in r[1] for r in blocking):
                echo("        兜底渲染器装任意一个即可：")
                echo("          1) LibreOffice —— https://zh-cn.libreoffice.org/download/")
                echo("          2) WPS Office —— 兜底，渲染细节可能与 PowerPoint 有差异")
        else:
            echo("  结论：现在可以出 PPT。")
            echo("        make-ppt.bat briefs/01-chenghai-zhaoyiming.json 输出.pptx")
        if warn:
            echo("  告警：" + "；".join(f"{r[1]}（{r[3]}）" for r in warn))

        # 缺 PowerPoint 单独成段：它是首选渲染器，缺了仍能出稿，但几何检查的
        # 基准会换成兜底引擎，版式与客户在 PowerPoint 里看到的不是同一个东西。
        # 这段必须点名「装什么」和「装完跑哪个文件」，否则用户只知道缺，不知道怎么补。
        if pw_ok is not True:
            echo()
            echo("  建议安装：Microsoft PowerPoint")
            echo("        它是首选渲染器，几何检查的断行与行距与你在 PowerPoint 里")
            echo("        看到的完全一致；兜底引擎能转 PDF，但基准不同，结论会偏。")
            echo("        怎么装：")
            echo("          1) 双击项目根目录的 setup.bat，按它的提示装 PowerPoint")
            echo("          2) 装完再双击一次 setup.bat 复检 —— 这一行要变成 [OK]")
            echo("          3) 之后再用 make-ppt.bat 出稿，几何检查才有可信基准")

    return 1 if any(r[0] == "必需" and r[2] is not True for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
