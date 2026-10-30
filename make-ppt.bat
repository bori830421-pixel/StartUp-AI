@echo off
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"

REM ===================================================================
REM  出 PPT：渲染 + 几何检查
REM
REM  用法：
REM    make-ppt.bat tools\briefs\01-chenghai-zhaoyiming.json 输出.pptx
REM    make-ppt.bat --list                  列出现有用例
REM    make-ppt.bat b.json out.pptx --png   顺带导出逐页图
REM
REM  检查不通过会明确说卡在哪，不会静默降级成「已生成」。
REM  本文件必须存为 UTF-8 with BOM（原因见 setup.bat）。
REM ===================================================================

set "VPY=.venv\Scripts\python.exe"

if /i "%~1"=="--list" goto :list
if /i "%~1"=="-h"     goto :usage
if /i "%~1"=="--help" goto :usage
if "%~1"==""          goto :usage

if not exist "%VPY%" (
    echo.
    echo   [XX] 还没部署：找不到 .venv
    echo        先双击 setup.bat
    echo.
    pause
    exit /b 1
)

set "BRIEF=%~1"
set "OUT=%~2"
if "%OUT%"=="" set "OUT=output.pptx"

if not exist "%BRIEF%" (
    echo.
    echo   [XX] 找不到 brief 文件：%BRIEF%
    echo        可用 make-ppt.bat --list 查看现成用例
    echo.
    pause
    exit /b 1
)

set "EXTRA="
shift
shift
:collect
if "%~1"=="" goto :run
set "EXTRA=%EXTRA% %~1"
shift
goto :collect

:run
echo.
echo [1/2] 渲染  %BRIEF%  ^-^>  %OUT%
"%VPY%" "tools\deck_engine.py" "%BRIEF%" "%OUT%"
set RENDER=%errorlevel%
if not "%RENDER%"=="0" (
    echo.
    if "%RENDER%"=="2" (
        echo   [XX] 缺依赖：重新跑 setup.bat
    ) else if "%RENDER%"=="3" (
        echo   [XX] brief 结构有错，按上面提示改 JSON
    ) else (
        echo   [XX] 渲染失败，退出码 %RENDER%
    )
    echo.
    pause
    exit /b %RENDER%
)

echo.
echo [2/2] 几何检查...
"%VPY%" "tools\deck_lint.py" "%OUT%" %EXTRA%
set LINT=%errorlevel%
echo.
if "%LINT%"=="0" (
    echo ============================================================
    echo   完成：%OUT%（几何检查 0 必改）
    echo ============================================================
) else if "%LINT%"=="1" (
    echo ============================================================
    echo   文件已生成，但几何检查有必改项（见上清单）。
    echo   改 brief 里的文案或数据，再跑一次。
    echo ============================================================
) else (
    echo ============================================================
    echo   文件已生成，但检查工具没跑起来（退出码 %LINT%）。
    echo   首选渲染器 Microsoft PowerPoint 不可用，兜底也没跑通。
    echo   先装 PowerPoint，再双击 setup.bat 复检；具体原因看：
    echo     python tools\doctor.py
    echo ============================================================
)
echo.
pause
exit /b %LINT%

:list
echo.
echo 现成用例（tools\briefs\）：
echo.
for %%F in ("tools\briefs\*.json") do echo   %%~nxF
echo.
echo 用法：make-ppt.bat tools\briefs\01-chenghai-zhaoyiming.json 输出.pptx
echo.
exit /b 0

:usage
echo.
echo 用法：
echo   make-ppt.bat tools\briefs\01-chenghai-zhaoyiming.json 输出.pptx
echo   make-ppt.bat --list        列出现有用例
echo   make-ppt.bat b.json o.pptx --png preview\    顺带导出逐页图
echo.
exit /b 0