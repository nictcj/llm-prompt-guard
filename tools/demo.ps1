param(
	[ValidateSet("start", "stop")]
	[string]$Action = "start"
)

$ErrorActionPreference = "Stop"

$scriptPath = if ($Action -eq "start") {
	Join-Path $PSScriptRoot "run_local_demo.ps1"
}
else {
	Join-Path $PSScriptRoot "stop_local_demo.ps1"
}

& $scriptPath
