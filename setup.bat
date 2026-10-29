@echo off
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"

REM ===================================================================
REM  StartUp-AI 一键部署
REM
REM  双击运行。做四件事：
REM    1. 找一个可用的 Python（3.9+）
REM    2. 在项目根目录建 .venv（不动系统 Python）
REM    3. 从 tools\wheels\ 离线装依赖（不需要联网）
REM    4. 出 3 页 pptx 做冒烟测试，再跑环境体检
REM
REM  两个实测踩过的坑，改之前先看：
REM  1. 本文件必须存为 UTF-8 with BOM。cmd.exe 按系统 ANSI 码页解析
REM     .bat，无 BOM 的 UTF-8 中文会把 "set PYTHONIOENCODING" 吃掉
REM     首字母，变成 "ONIOENCODING is not recognized"。
REM  2. `py -3.12` 在版本不存在时只往 stderr 报错、退出码仍是 0，
REM     用 errorlevel 判断会误选。必须用 for /f 捕获它打印的版本号。
REM ===================================================================

echo.
echo ============================================================
echo   StartUp-AI 部署
echo   项目目录：%CD%
echo ============================================================

echo.
echo [1/4] 查找 Python（需要 3.9 及以上）...
set "PYEXE="

REM 用 py 启动器按版本探测；只有真的打印出该版本号才认
for %%V in (3.12 3.11 3.13 3.10 3.9) do (
    if not defined PYEXE (
        for /f "delims=" %%O in ('py -%%V -c "import sys;print(%%V)" 2^>nul') do (
            if "%%O"=="%%V" set "PYEXE=py -%%V"
        )
    )
)

REM 没有 py 启动器时退回 PATH 里的 python
if not defined PYEXE (
    for /f "delims=" %%O in ('python -c "import sys;print('%%d.%%d'%%sys.version_info[:2])" 2^>nul') do (
        set "PYEXE=python"
        echo   [OK] python %%O
    )
)

if not defined PYEXE (
    echo.
    echo   [XX] 找不到可用的 Python（3.9+）。
    echo.
    echo        请先安装：https://www.python.org/downloads/
    echo        安装时务必勾选 "Add python.exe to PATH"，装完重跑本文件。
    echo.
    pause
    exit /b 1
)
if not "%PYEXE%"=="python" echo   [OK] %PYEXE%

echo.
echo [2/4] 创建虚拟环境并安装依赖...
%PYEXE% "tools\bootstrap.py" --python="%PYEXE%"
if errorlevel 1 goto :failed

echo.
echo [3/4] 环境体检...
".venv\Scripts\python.exe" "tools\doctor.py"
if errorlevel 1 (
    echo.
    echo ============================================================
    echo   部署未完成：环境体检有必需项缺失（见上）
    echo   按提示补齐后重跑 setup.bat
    echo ============================================================
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   [4/4] 部署完成，现在可以出 PPT 了。
echo.
echo   出稿：make-ppt.bat tools\briefs\01-chenghai-zhaoyiming.json 输出.pptx
echo   用例：make-ppt.bat --list
echo ============================================================
echo.
pause
exit /b 0

:failed
echo.
echo ============================================================
echo   [XX] 部署失败，看上面哪一步报了错。
echo        常见原因：磁盘空间不足、杀毒软件拦截、tools\wheels\ 被删。
echo ============================================================
echo.
pause
exit /b 1