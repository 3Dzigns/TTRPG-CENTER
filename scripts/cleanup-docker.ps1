#!/usr/bin/env pwsh
# Docker cleanup script for TTRPG Center
# Removes unused images, containers, and volumes

param(
    [switch]$DryRun = $false,
    [switch]$Aggressive = $false,
    [switch]$KeepRecent = $true
)

Write-Host "🧹 Docker Cleanup Script for TTRPG Center" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Show current Docker disk usage
Write-Host "`n📊 Current Docker disk usage:" -ForegroundColor Yellow
docker system df

if ($DryRun) {
    Write-Host "`n🔍 DRY RUN MODE - No changes will be made" -ForegroundColor Yellow
}

# 1. Remove dangling images
Write-Host "`n🗑️ Cleaning up dangling images..." -ForegroundColor Green
if ($DryRun) {
    docker image prune --filter dangling=true
} else {
    docker image prune -f --filter dangling=true
}

# 2. Remove unused containers
Write-Host "`n🗑️ Cleaning up stopped containers..." -ForegroundColor Green
if ($DryRun) {
    docker container prune
} else {
    docker container prune -f
}

# 3. Remove unused networks
Write-Host "`n🗑️ Cleaning up unused networks..." -ForegroundColor Green
if ($DryRun) {
    docker network prune
} else {
    docker network prune -f
}

# 4. Remove unused volumes (be careful with this)
if ($Aggressive) {
    Write-Host "`n⚠️ AGGRESSIVE MODE: Cleaning up unused volumes..." -ForegroundColor Red
    if ($DryRun) {
        docker volume prune
    } else {
        docker volume prune -f
    }
}

# 5. Remove old TTRPG images (keep only most recent)
if ($KeepRecent) {
    Write-Host "`n🗑️ Cleaning up old TTRPG images (keeping most recent)..." -ForegroundColor Green
    $ttrpgImages = docker images --format "table {{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}" --filter "reference=ttrpg*" --filter "reference=*ttrpg*"

    if ($ttrpgImages.Count -gt 3) {  # Keep latest 2 images
        Write-Host "Found $($ttrpgImages.Count - 2) old TTRPG images to remove"

        # Get all but the 2 most recent images
        $imagesToRemove = docker images --format "{{.ID}}" --filter "reference=ttrpg*" --filter "reference=*ttrpg*" | Select-Object -Skip 2

        foreach ($imageId in $imagesToRemove) {
            if ($imageId) {
                Write-Host "  Removing image: $imageId" -ForegroundColor Yellow
                if (-not $DryRun) {
                    docker rmi $imageId --force
                }
            }
        }
    } else {
        Write-Host "Only $($ttrpgImages.Count) TTRPG images found - nothing to cleanup"
    }
}

# 6. System-wide cleanup (if aggressive)
if ($Aggressive) {
    Write-Host "`n⚠️ AGGRESSIVE MODE: Running system-wide cleanup..." -ForegroundColor Red
    Write-Host "This will remove ALL unused Docker resources!" -ForegroundColor Red

    if ($DryRun) {
        docker system prune -a --volumes
    } else {
        docker system prune -a --volumes --force
    }
}

Write-Host "`n📊 Docker disk usage after cleanup:" -ForegroundColor Yellow
docker system df

Write-Host "`n✅ Docker cleanup completed!" -ForegroundColor Green

# Show remaining TTRPG images
Write-Host "`n📦 Remaining TTRPG images:" -ForegroundColor Cyan
docker images --filter "reference=ttrpg*" --filter "reference=*ttrpg*"