@echo off
chcp 65001 >nul
echo ========================================
echo 灾害监测系统 - 快速测试脚本
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python 未安装或不在 PATH 中
    pause
    exit /b 1
)

echo [1/4] 检查数据库...
if not exist "database\disaster.db" (
    echo    数据库不存在，正在初始化...
    python database\init_db.py
    if errorlevel 1 (
        echo ❌ 数据库初始化失败
        pause
        exit /b 1
    )
    echo    ✅ 数据库初始化完成
    echo.
    echo    创建管理员账户...
    python database\create_admin.py
    echo.
    echo    创建 API Token...
    python database\create_token.py
    echo.
    echo    ⚠️  请复制上面的 Token 并更新到 tests\test_gpu_simulator.py 第 12 行
    echo.
    pause
) else (
    echo    ✅ 数据库已存在
)

echo.
echo [2/4] 创建测试任务...
python tests\create_test_event.py --ready
if errorlevel 1 (
    echo ❌ 测试任务创建失败
    pause
    exit /b 1
)

echo.
echo [3/4] 启动服务器（后台）...
echo    服务器将在后台启动，监听端口 2335
start /B python main.py
timeout /t 3 /nobreak >nul

echo.
echo [4/4] 运行 GPU 模拟器...
echo    ⚠️  确保已在 tests\test_gpu_simulator.py 中配置正确的 API_TOKEN
echo.
pause
python tests\test_gpu_simulator.py

echo.
echo ========================================
echo 测试完成！
echo ========================================
echo.
echo 查看结果:
echo   - 管理后台: http://localhost:2335
echo   - API 文档: http://localhost:2335/docs
echo   - 成品池: http://localhost:2335 ^> 登录 ^> 成品池
echo.
echo 停止服务器:
echo   taskkill /F /IM python.exe
echo.
pause
