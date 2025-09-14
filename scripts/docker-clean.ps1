#!/usr/bin/env pwsh
# Docker cleanup utility for TTRPG Center
# Safely prunes unused containers, networks, images and optionally
# trims older app images while keeping the most recent ones.

param(
    [switch]$DryRun = $false,
    [switch]$Aggressive = $false,          # include system-wide prune of images and volumes
    [switch]$BuilderCache = $false,        # prune build cache
    [switch]$PruneVolumes = $false,        # prune unused (dangling) volumes
    [switch]$RemoveUnusedImages = $false,  # remove all images not used by any container
    [int]$KeepRecent = 2,                  # keep this many recent images per repository filter
    [string[]]$RepositoryFilter = @('ttrpg/app','ttrpg_center-app-dev')
)

$ErrorActionPreference = 'Stop'

function Write-Status {
    param([string]$Message, [string]$Level = 'INFO')
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $color = switch ($Level) {
        'INFO' {'Green'}
        'WARN' {'Yellow'}
        'ERROR' {'Red'}
        'OK' {'Cyan'}
        Default {'White'}
    }
    Write-Host "[$ts] $($Level): $Message" -ForegroundColor $color
}

function Invoke-Cmd {
    param([string]$CommandLine)
    if ($DryRun) {
        Write-Status "DRY RUN: $CommandLine" 'WARN'
    } else {
        iex $CommandLine
    }
}

try {
    Write-Status 'Docker cleanup starting'

    Write-Status 'Docker disk usage (before):' 'INFO'
    docker system df | Out-Host

    # 1) Prune stopped containers
    Write-Status 'Pruning stopped containers'
    Invoke-Cmd 'docker container prune -f'

    # 2) Prune unused networks
    Write-Status 'Pruning unused networks'
    Invoke-Cmd 'docker network prune -f'

    # 2b) Optionally prune unused volumes
    if ($PruneVolumes) {
        Write-Status 'Pruning unused (dangling) volumes' 'WARN'
        Invoke-Cmd 'docker volume prune -f'
    }

    # 3) Prune dangling images (untagged)
    Write-Status 'Pruning dangling images'
    Invoke-Cmd 'docker image prune -f'

    # 4) Optionally prune builder cache
    if ($BuilderCache) {
        Write-Status 'Pruning builder cache'
        Invoke-Cmd 'docker builder prune -f'
    }

    # 4b) Optionally remove ALL images not used by any container
    if ($RemoveUnusedImages) {
        Write-Status 'Removing all images not used by any container (-a)'
        Invoke-Cmd 'docker image prune -a -f'
    }

    # 5) Trim older images for specified repositories
    if ($KeepRecent -ge 0 -and $RepositoryFilter -and $RepositoryFilter.Count -gt 0) {
        foreach ($repo in $RepositoryFilter) {
            Write-Status "Checking repository filter: $repo"
            # docker images default order is newest first; rely on that for selection
            $lines = docker images --format '{{.ID}}|{{.Repository}}:{{.Tag}}' --filter "reference=$repo" | Where-Object { $_ }
            if (-not $lines) {
                Write-Status "No images matched filter '$repo'" 'WARN'
                continue
            }

            # Deduplicate by image ID (multiple tags can point to same ID)
            $seen = @{}
            $orderedIds = @()
            foreach ($ln in $lines) {
                $parts = $ln -split '\|',2
                if ($parts.Length -lt 1) { continue }
                $id = $parts[0].Trim()
                if (-not $seen.ContainsKey($id)) {
                    $seen[$id] = $true
                    $orderedIds += $id
                }
            }

            if ($orderedIds.Count -le $KeepRecent) {
                Write-Status "Nothing to delete for '$repo' (count=$($orderedIds.Count), keep=$KeepRecent)" 'OK'
                continue
            }

            $toRemove = $orderedIds | Select-Object -Skip $KeepRecent
            foreach ($id in $toRemove) {
                Write-Status "Removing old image: $id (filter $repo)" 'WARN'
                Invoke-Cmd "docker rmi $id -f"
            }
        }
    }

    # 6) Aggressive system-wide prune (optional)
    if ($Aggressive) {
        Write-Status 'Running aggressive system prune (images, containers, networks, volumes)' 'WARN'
        Invoke-Cmd 'docker system prune -a --volumes --force'
    }

    Write-Status 'Docker disk usage (after):' 'INFO'
    docker system df | Out-Host

    Write-Status 'Docker cleanup completed' 'OK'
}
catch {
    Write-Status "Cleanup failed: $($_.Exception.Message)" 'ERROR'
    exit 1
}
