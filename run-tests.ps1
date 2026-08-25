# Test Automation Script
# 在代码提交前（或 CI 环境）自动运行所有测试用例
# 用法: .\run-tests.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Photographer Booking - 自动化测试套件" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ---- 后端测试 ----
Write-Host ""
Write-Host "[1/2] 运行后端测试 (pytest)..." -ForegroundColor Yellow
Push-Location "$ProjectRoot"
$venvPython = "$ProjectRoot\venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "  ERROR: 未找到虚拟环境，请先创建 venv" -ForegroundColor Red
    exit 1
}

& $venvPython -m pytest backend/tests/ -v --tb=short --cov=backend/app/services --cov=backend/app/core --cov=backend/app/utils --cov-report=term --cov-fail-under=60

if ($LASTEXITCODE -ne 0) {
    Write-Host "  FAILED: 后端测试未通过或覆盖率低于 60%" -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "  PASSED: 后端测试全部通过" -ForegroundColor Green

# ---- 前端测试 ----
Write-Host ""
Write-Host "[2/2] 运行前端测试 (vitest)..." -ForegroundColor Yellow
Push-Location "$ProjectRoot\frontend"
npx vitest run --coverage

if ($LASTEXITCODE -ne 0) {
    Write-Host "  FAILED: 前端测试未通过" -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "  PASSED: 前端测试全部通过" -ForegroundColor Green

Pop-Location
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  所有测试通过！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
