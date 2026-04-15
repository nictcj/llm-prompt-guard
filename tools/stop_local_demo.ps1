$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$statePath = Join-Path $repoRoot "test-artifacts\demo-processes.json"

if (-not (Test-Path $statePath)) {
	Write-Host "No demo process state file found."
	return
}

$state = Get-Content $statePath -Raw | ConvertFrom-Json
$pids = @($state.backend, $state.frontend) | Where-Object { $_ }

foreach ($processId in $pids) {
	Stop-Process -Id $processId -ErrorAction SilentlyContinue
}

Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue

Write-Host "Stopped demo launcher processes."
