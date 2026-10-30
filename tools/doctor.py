#!/usr/bin/env python3
"""环境体检：区分基础 PPTX 出稿与可选 PDF 几何检查。

    python tools/doctor.py
    python tools/doctor.py --pdf
    python tools/doctor.py --json     # 机器可读，给脚本用

判定分三档：
  [必需] 缺一项就不能出 PPTX → 退出码 1
  [可选] 缺了只影响 PDF 几何检查，不阻止出 PPTX
  [信息] 只报告，不判定

PDF 转换环境配置可能较繁琐，默认不测试，也不建议为了普通出稿安装。
只有显式传入 --pdf 才会尝试转换。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

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
    # Microsoft 365 按通道/位数装法不同，Office15/14 对应旧版与部分预装；
    # 本机 C:\Program Files (x86)\Microsoft Office\Office 是空壳目录，
    # 只按 App Paths 判定会漏，所以把这些真实落点一并列上。
    r"C:\Program Files\Microsoft Office\Office15\POWERPNT.EXE",
    r"C:\Program Files (x86)\Microsoft Office\Office15\POWERPNT.EXE",
    r"C:\Program Files\Microsoft Office\Office14\POWERPNT.EXE",
    r"C:\Program Files (x86)\Microsoft Office\Office14\POWERPNT.EXE",
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
    """报告 PowerPoint 是否存在；它是可选渲染器，不是出稿前提。"""
    path = find_powerpoint()
    if path:
        return True, "", path
    return False, "未检测到（可选）", ""


def _workdir(prefix):
    """在项目内建临时目录。

    不能用 %TEMP%：本机实测该目录可以 makedirs，但往里写文件报
    PermissionError（ACL 被沙箱收走）。项目目录父子进程都能写。
    """
    for base in (os.path.join(ROOT, ".venv"), ROOT):
        if os.path.isdir(base):
            try:
                return tempfile.mkdtemp(prefix=prefix, dir=base)
            except OSError:
                continue
    return tempfile.mkdtemp(prefix=prefix)


def _probe_convert():
    """真转一次：拿 _stress.json 出一份 pptx → 转 PDF → 验文字可读。

    为什么不信「文件存在」：soffice 装没装和「能不能用」是两回事。本机实测
    soffice.exe 在，但子进程被降到 Low IL，%TEMP% 不可写，每次启动都等约
    50 秒后失败——只看路径会判定可用，实际几何检查永远跑不起来。
    所以这里按真实结果判，把结论写进 detail，让「兜底可用」是测出来的。
    """
    brief = os.path.join(HERE, "briefs", "_stress.json")
    if not os.path.exists(brief):
        return None, "缺少 tools/briefs/_stress.json，无法实测兜底转换", ""
    tmp = _workdir("doctor-probe-")
    try:
        pptx = os.path.join(tmp, "_stress.pptx")
        # 第一步：出稿（纯 Python 层，不依赖渲染器）
        code, out = run([VENV_PY, os.path.join(HERE, "deck_engine.py"), brief, pptx],
                        timeout=180)
        if code != 0 or not os.path.exists(pptx):
            tail = (out.strip().splitlines() or [""])[-1][:80]
            return False, "deck_engine 出稿失败", tail
        # 第二步：走 deck_lint 自己的渲染器链真转一次。
        # pdf 目录也建在 tmp 里，别用 tempfile 默认值——那是 %TEMP%，不可写。
        probe = (
            "import sys, os;"
            "sys.path.insert(0, r'%s');"
            "import deck_lint as d;"
            "tmp = os.path.join(r'%s', 'pdf');"
            "os.makedirs(tmp, exist_ok=True);"
            "pdf, eng = d.to_pdf(r'%s', tmp);"
            "print(eng);"
            "print(d.pdf_text_ok(pdf))" % (HERE, tmp, pptx)
        )
        code, out = run([VENV_PY, "-c", probe], timeout=420)
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        if code != 0 or len(lines) < 2:
            tail = lines[-1][:120] if lines else "无输出"
            return False, "兜底渲染器实测失败", tail
        engine, text_ok = lines[-2], lines[-1]
        if text_ok != "True":
            return False, "转换成功但 PDF 文字取不出", engine
        return True, "", "%s（实测：出稿→PDF 成功，文字可读）" % engine
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_renderer():
    """几何检查要靠一个渲染器把 pptx 转 PDF。

    PowerPoint 是首选，LibreOffice 与 WPS 只作兜底。该检查只影响几何检查，
    不影响 PPTX 出稿。

    判定方式是**实际转换一次**，不是查文件存在——理由见 _probe_convert。
    """
    if not os.path.exists(VENV_PY):
        return False, "先跑 setup.bat", ""
    ok_, msg_, detail_ = _probe_convert()
    if ok_ is True:
        return True, "", "兜底可用：" + detail_
    # 实测失败时补上「装了哪些」，方便定位坏在哪一层
    found = []
    if find_soffice():
        found.insert(0, "LibreOffice")
    for key, label in (("Kwpp.Application", "WPS"),):
        code, out = run([VENV_PY, "-c",
                         "import comtypes.client as c;app=c.CreateObject('%s');"
                         "print(app.Version);app.Quit()" % key], timeout=120)
        if code == 0 and out.strip():
            found.append(label)
    hint = ("（已装：" + " / ".join(found) + "，但转换失败）") if found else ""
    return False, "兜底渲染器实测不可用%s：%s" % (hint, detail_ or msg_), detail_


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
    """--png 逐页导图依赖可选的 comtypes。

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
    ap.add_argument("--pdf", action="store_true", help="按需实际测试 PDF 几何检查环境")
    args = ap.parse_args()

    rows = []
    py_ok, py_msg, py_ver = check_python()
    rows.append(("必需", "Python（.venv）", py_ok, py_msg, py_ver))
    for mod, label in (("pptx", "python-pptx"),):
        ok_, msg_, ver = check_module(mod, label)
        rows.append(("必需", label, ok_, msg_, ver))
    if args.pdf:
        pm_ok, pm_msg, pm_ver = check_module("pymupdf", "PyMuPDF")
        rows.append(("可选", "PyMuPDF（PDF 几何检查）", pm_ok, pm_msg, pm_ver))
        pw_ok, pw_msg, pw_ver = check_powerpoint()
        rows.append(("可选", "Microsoft PowerPoint", pw_ok, pw_msg, pw_ver))
        rd_ok, rd_msg, rd_ver = check_renderer() if pm_ok else (None, "先装 PDF 检查依赖", "")
        rows.append(("可选", "PDF 转换实测", rd_ok, rd_msg, rd_ver))
        pp_ok, pp_msg, pp_ver = check_png_export()
        rows.append(("信息", "--png 导图（comtypes）", pp_ok, pp_msg, pp_ver))
    else:
        rows.append(("可选", "PDF 几何检查", None,
                     "未运行；环境配置可能较繁琐，默认建议跳过", "使用 --pdf 按需测试"))
    ft_ok, ft_msg, ft_ver = check_font()
    rows.append(("信息", f"字体 {FONT}", ft_ok, ft_msg, ft_ver))
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
        echo("-" * 62)
        if blocking:
            echo("  结论：当前不能生成 PPTX。缺：")
            for _, name, _, msg, _ in blocking:
                echo(f"        - {name}：{msg}")
        else:
            echo("  结论：基础环境可生成 PPTX。")
            echo("        make-ppt.bat tools/briefs/01-chenghai-zhaoyiming.json 输出.pptx")
        if not args.pdf:
            echo("  PDF 转换与几何检查是可选项，配置可能较繁琐，默认建议跳过。")
            echo("        需要时先运行 setup.bat --with-pdf-check，再用 doctor.py --pdf 检查。")
        elif any(r[0] == "可选" and r[2] is not True for r in rows):
            echo("  PDF 几何检查未就绪；这不影响 PPTX 出稿。可按需补齐可选依赖与系统渲染器。")

    return 1 if any(r[0] == "必需" and r[2] is not True for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
