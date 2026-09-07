# recover.ps1 — Computational R&D Engine recovery procedures
# Handles common failure modes: stuck containers, corrupted state, disk pressure.

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("container", "disk", "wsl", "all")]
    [string]$Mode
)

$ErrorActionPreference = "Continue"

function Recover-Container {
    Write-Host "`n=== Container Recovery ===" -ForegroundColor Cyan

    # Check if container exists
    $exists = docker ps -a --filter "name=rnd-engine-eda" --format "{{.Names}}" 2>$null
    if (-not $exists) {
        Write-Host "Container not found. Building fresh..." -ForegroundColor Yellow
        docker compose build 2>&1
        return
    }

    # Check if running
    $running = docker ps --filter "name=rnd-engine-eda" --format "{{.Names}}" 2>$null
    if ($running) {
        Write-Host "Container is running. Checking health..." -ForegroundColor Green
        $health = docker inspect --format '{{.State.Health.Status}}' rnd-engine-eda 2>$null
        Write-Host "  Health: $health"

        if ($health -eq "unhealthy") {
            Write-Host "  Restarting unhealthy container..." -ForegroundColor Yellow
            docker restart rnd-engine-eda 2>&1
            Start-Sleep -Seconds 5
            $newHealth = docker inspect --format '{{.State.Health.Status}}' rnd-engine-eda 2>$null
            Write-Host "  New health: $newHealth"
        }
    } else {
        Write-Host "Container stopped. Restarting..." -ForegroundColor Yellow
        docker start rnd-engine-eda 2>&1
        Start-Sleep -Seconds 5
        $newStatus = docker ps --filter "name=rnd-engine-eda" --format "{{.Status}}" 2>$null
        Write-Host "  Status: $newStatus"
    }

    # Clean dangling images
    Write-Host "`nCleaning dangling images..." -ForegroundColor Yellow
    docker image prune -f 2>&1
}

function Recover-Disk {
    Write-Host "`n=== Disk Recovery ===" -ForegroundColor Cyan

    $before = Get-PSDrive C
    $freeBefore = [math]::Round($before.Free / 1GB, 1)
    Write-Host "Current free space: ${freeBefore}GB"

    # Docker cleanup
    Write-Host "`nDocker system prune..." -ForegroundColor Yellow
    docker system prune -f --volumes 2>&1

    # Clean temp
    Write-Host "Cleaning temp files..." -ForegroundColor Yellow
    $tempSize = (Get-ChildItem $env:TEMP -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB
    Remove-Item "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue

    # Clean pip cache
    Write-Host "Cleaning pip cache..." -ForegroundColor Yellow
    & python -m pip cache purge 2>$null

    # Clean npm cache
    Write-Host "Cleaning npm cache..." -ForegroundColor Yellow
    & npm cache clean --force 2>$null

    $after = Get-PSDrive C
    $freeAfter = [math]::Round($after.Free / 1GB, 1)
    $freed = [math]::Round($freeAfter - $freeBefore, 1)
    Write-Host "`nFreed: ${freed}GB (now ${freeAfter}GB free)" -ForegroundColor Green
}

function Recover-Wsl {
    Write-Host "`n=== WSL Recovery ===" -ForegroundColor Cyan

    # Check WSL status
    $running = wsl --list --running 2>$null
    if ($running) {
        Write-Host "WSL is running. Checking Docker..." -ForegroundColor Green
        $dockerStatus = wsl -e docker info --format '{{.ServerVersion}}' 2>$null
        if ($dockerStatus) {
            Write-Host "  Docker version: $dockerStatus"
        } else {
            Write-Host "  Docker not responding. Restarting WSL..." -ForegroundColor Yellow
            wsl --shutdown
            Start-Sleep -Seconds 3
            wsl -e echo "WSL restarted" 2>$null
        }
    } else {
        Write-Host "WSL not running. Starting..." -ForegroundColor Yellow
        wsl -e echo "WSL started" 2>$null
    }

    # Check .wslconfig
    $wslConfig = "$env:USERPROFILE\.wslconfig"
    if (Test-Path $wslConfig) {
        Write-Host "`n.wslconfig:" -ForegroundColor Yellow
        Get-Content $wslConfig | ForEach-Object { Write-Host "  $_" }
    } else {
        Write-Host "No .wslconfig found" -ForegroundColor Red
    }
}

switch ($Mode) {
    "container" { Recover-Container }
    "disk" { Recover-Disk }
    "wsl" { Recover-Wsl }
    "all" {
        Recover-Container
        Recover-Disk
        Recover-Wsl
    }
}

Write-Host "`nRecovery complete." -ForegroundColor Green
