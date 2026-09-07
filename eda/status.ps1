# status.ps1 — Computational R&D Engine status monitor
# Shows container health, disk, memory, and recent receipts.

param(
    [switch]$Watch
)

function Show-Status {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "`n=== R&D Engine Status ($timestamp) ===" -ForegroundColor Cyan

    # Docker container status
    $container = docker ps -a --filter "name=rnd-engine-eda" --format "{{.Names}}\t{{.Status}}\t{{.Image}}" 2>$null
    if ($container) {
        Write-Host "`nContainer:" -ForegroundColor Yellow
        Write-Host "  $container"
    } else {
        Write-Host "`nContainer: NOT RUNNING" -ForegroundColor Red
    }

    # Docker health
    $health = docker inspect --format '{{.State.Health.Status}}' rnd-engine-eda 2>$null
    if ($health) {
        $color = if ($health -eq "healthy") { "Green" } elseif ($health -eq "unhealthy") { "Red" } else { "Yellow" }
        Write-Host "  Health: $health" -ForegroundColor $color
    }

    # Memory & CPU
    $stats = docker stats rnd-engine-eda --no-stream --format "CPU: {{.CPUPerc}}  MEM: {{.MemUsage}}  LIMIT: {{.MemPerc}}" 2>$null
    if ($stats) {
        Write-Host "  $stats"
    }

    # Disk usage
    $disk = Get-PSDrive C
    $freeGB = [math]::Round($disk.Free / 1GB, 1)
    $usedPct = [math]::Round($disk.Used / ($disk.Used + $disk.Free) * 100, 1)
    Write-Host "`nDisk (C:):" -ForegroundColor Yellow
    Write-Host "  Free: ${freeGB}GB  Used: ${usedPct}%"

    # Docker disk usage
    $dockerDisk = docker system df --format "Images: {{.Images}}  Containers: {{.Containers}}  Volumes: {{.Volumes}}" 2>$null
    if ($dockerDisk) {
        Write-Host "  Docker: $dockerDisk"
    }

    # Recent receipts
    $receipts = Get-ChildItem -Path "..\output\receipts\*.json" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 5

    if ($receipts) {
        Write-Host "`nRecent Receipts:" -ForegroundColor Yellow
        foreach ($r in $receipts) {
            $data = Get-Content $r.FullName | ConvertFrom-Json
            $status = $data.status
            $stage = $data.stage
            $time = $r.LastWriteTime.ToString("HH:mm:ss")
            $color = if ($status -eq "pass") { "Green" } elseif ($status -eq "blocked") { "Yellow" } else { "Red" }
            Write-Host "  $time  $stage  $status" -ForegroundColor $color
        }
    }

    # WSL status
    $wsl = wsl --list --running 2>$null
    if ($wsl) {
        Write-Host "`nWSL: Running" -ForegroundColor Green
    } else {
        Write-Host "`nWSL: Not running" -ForegroundColor Yellow
    }
}

if ($Watch) {
    while ($true) {
        Clear-Host
        Show-Status
        Start-Sleep -Seconds 5
    }
} else {
    Show-Status
}
