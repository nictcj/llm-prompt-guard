$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$statePath = Join-Path $repoRoot "test-artifacts\demo-processes.json"

if (-not (Test-Path $statePath)) {
	Write-Host "No demo process state file found."
	return
}

$state = Get-Content $statePath -Raw | ConvertFrom-Json
$pids = @($state.backend, $state.frontend) | Where-Object { $_ }

function Stop-ProcessTree {
	param(
		[int]$ProcessId
	)

	$children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" -ErrorAction SilentlyContinue
	foreach ($child in $children) {
		Stop-ProcessTree -ProcessId $child.ProcessId
	}

	Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

foreach ($processId in $pids) {
	Stop-ProcessTree -ProcessId $processId
}

Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue

Write-Host "Stopped demo launcher processes."
