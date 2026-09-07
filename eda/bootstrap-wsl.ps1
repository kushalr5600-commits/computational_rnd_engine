#Requires -RunAsAdministrator
<#
Phase N (steps 1-2): bring up the Windows virtualization platform for WSL2.

Concrete failures captured on 2026-09-03 that this script resolves:
  - winget Microsoft.WSL 2.7.12 -> 0x80073d28 (admin required)
  - dism get-featureinfo VirtualMachinePlatform -> 740 (elevation required)
  - HypervisorPresent=False; vmcompute service absent

Idempotent: safe to re-run. A reboot IS required after the first enablement
before `wsl --install -d Ubuntu` will succeed.
#>
param([switch]$NoRebootPrompt)
$ErrorActionPreference = 'Continue'

Write-Host '== 1/3 VirtualMachinePlatform =='
dism /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

Write-Host '== 2/3 Microsoft-Windows-Subsystem-Linux =='
dism /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

Write-Host '== 3/3 WSL package (MSIX) =='
winget install --id Microsoft.WSL -e --silent --accept-source-agreements --accept-package-agreements

Write-Host ''
Write-Host 'REBOOT REQUIRED, then continue with:'
Write-Host '  wsl --install -d Ubuntu --no-launch'
Write-Host '  (all further steps run inside WSL; no more host elevation needed)'
if (-not $NoRebootPrompt) {
    Write-Host 'Reboot now with:  shutdown /r /t 0'
}
