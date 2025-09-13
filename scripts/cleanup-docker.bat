@echo off
REM Docker cleanup script for TTRPG Center (Windows batch version)

echo 🧹 Docker Cleanup Script for TTRPG Center
echo ========================================

echo.
echo 📊 Current Docker disk usage:
docker system df

echo.
echo 🗑️ Cleaning up dangling images...
docker image prune -f

echo.
echo 🗑️ Cleaning up stopped containers...
docker container prune -f

echo.
echo 🗑️ Cleaning up unused networks...
docker network prune -f

echo.
echo 📊 Docker disk usage after cleanup:
docker system df

echo.
echo ✅ Docker cleanup completed!

echo.
echo 📦 Remaining TTRPG images:
docker images --filter "reference=ttrpg*" --filter "reference=*ttrpg*"