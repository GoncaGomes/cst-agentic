$ErrorActionPreference = 'Stop'
$root = 'C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-solver-stop-dipole-01'
$launch = 'C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-solver-stop-dipole-01-launch.json'
$driver = 'C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifetime-offline\src\cst_agentic\windows_solver_stop.py'
if ((Test-Path -LiteralPath $root -ErrorAction Stop) -or (Test-Path -LiteralPath $launch -ErrorAction Stop)) {
    throw 'One-time experiment target or wrapper marker already exists. Do not replay.'
}
$watch = [System.Diagnostics.Stopwatch]::StartNew()
$started = [DateTime]::UtcNow.ToString('o')
$null = New-Item -Path $launch -ItemType File -ErrorAction Stop
$record = [ordered]@{
    id = 'dipole-stop-01'
    started_utc = $started
    driver_sha256 = (Get-FileHash -LiteralPath $driver -Algorithm SHA256 -ErrorAction Stop).Hash
    maximum_calls = 50
    maximum_seconds = 1800
    state = 'admitted_once'
}
$record | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $launch -Encoding UTF8 -ErrorAction Stop
$code = $null
$launchError = $null
try {
    uv run --offline --no-sync --project 'C:\dev\cst-agentic' python $driver --run-approved-once
    $code = $LASTEXITCODE
} catch {
    $launchError = $_.Exception.GetType().Name
} finally {
    $watch.Stop()
    $elapsed = [double]$watch.Elapsed.TotalSeconds
    $result = [ordered]@{
        id = 'dipole-stop-01'
        started_utc = $started
        ended_utc = [DateTime]::UtcNow.ToString('o')
        outer_elapsed_s = $elapsed
        exit_code = $code
        launch_error_type = $launchError
        total_ceiling_exceeded = ($elapsed -gt 1800)
    }
    $observations = Join-Path $root 'observations.json'
    if (Test-Path -LiteralPath $observations -ErrorAction Stop) {
        $report = Get-Content -LiteralPath $observations -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        $overhead = [Math]::Max([double]0.0, [double]($elapsed - [double]$report.total_driver_s))
        $result.outer_overhead_s = $overhead
        $result.startup_upper_s = if ($null -ne $report.startup_s) { [double]$report.startup_s + $overhead } else { $null }
        $result.cleanup_upper_s = if ($null -ne $report.cleanup_s) { [double]$report.cleanup_s + $overhead } else { $null }
        $result.complete_allowances_verified = ($null -ne $result.startup_upper_s -and $result.startup_upper_s -le 120 -and $null -ne $result.cleanup_upper_s -and $result.cleanup_upper_s -le 30)
        $destination = Join-Path $root 'outer-observation.json'
    } else {
        $result.complete_allowances_verified = $false
        $destination = $launch + '.outer.json'
    }
    $result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $destination -Encoding UTF8 -ErrorAction Stop
    $result | ConvertTo-Json -Depth 5
}
if ($null -ne $launchError -or $null -eq $code -or $code -ne 0) {
    throw 'The single attempt failed. Evidence retained; no retry authorized.'
}
if ($result.total_ceiling_exceeded -or -not $result.complete_allowances_verified) {
    throw 'Complete time allowance verification failed. Review evidence; do not replay.'
}
