$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
	$python = "python"
}

$backendProcess = Start-Process -FilePath $python -ArgumentList @("-m", "uvicorn", "main:app", "--reload") -WorkingDirectory $repoRoot -PassThru
$frontendProcess = Start-Process -FilePath $python -ArgumentList @("-m", "http.server", "5500") -WorkingDirectory (Join-Path $repoRoot "web-ui") -PassThru

$statePath = Join-Path $repoRoot "test-artifacts\demo-processes.json"
$state = @{
	backend = $backendProcess.Id
	frontend = $frontendProcess.Id
} | ConvertTo-Json
Set-Content -Path $statePath -Value $state -Encoding utf8

Write-Host "Started backend process: $($backendProcess.Id)"
Write-Host "Started frontend process: $($frontendProcess.Id)"
Write-Host "Backend:  http://127.0.0.1:8000/docs"
Write-Host "Frontend: http://127.0.0.1:5500"
Write-Host ""
Write-Host "To stop later, run: .\tools\demo.ps1 stop"
