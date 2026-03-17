@echo off
chcp 65001 >nul
echo.
echo   ╔═══════════════════════════════════════╗
echo   ║   GeoAgent Development Server         ║
echo   ║   Frontend + Backend + MCP Runtime    ║
echo   ╚═══════════════════════════════════════╝
echo.

cd /d %~dp0
npm run dev

pause
