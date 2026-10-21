$ErrorActionPreference = 'Stop'
$root = 'C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifecycle-final-01'
$marker = 'C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifecycle-final-01-launch.json'
$driver = 'C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifetime-offline\src\cst_agentic\windows_lifecycle_final.py'
if ((Test-Path -LiteralPath $root -ErrorAction Stop) -or (Test-Path -LiteralPath $marker -ErrorAction Stop)) {
    throw 'The final lifecycle round is already admitted or consumed. No replay authorized.'
}
$watch = [System.Diagnostics.Stopwatch]::StartNew()
$started = [DateTime]::UtcNow.ToString('o')
$null = New-Item -Path $marker -ItemType File -ErrorAction Stop
[ordered]@{
    state = 'admitted_once'
    started_utc = $started
    maximum_seconds = 300
    maximum_scenarios = 4
    driver_sha256 = (Get-FileHash -LiteralPath $driver -Algorithm SHA256 -ErrorAction Stop).Hash
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $marker -Encoding UTF8 -ErrorAction Stop
$code = $null
$failure = $null
try {
    uv run --offline --no-sync --project 'C:\dev\cst-agentic' python $driver --run-authorized-once
    $code = $LASTEXITCODE
} catch {
    $failure = $_.Exception.GetType().Name
} finally {
    $watch.Stop()
    $result = [ordered]@{
        started_utc = $started
        ended_utc = [DateTime]::UtcNow.ToString('o')
        outer_elapsed_s = [double]$watch.Elapsed.TotalSeconds
        maximum_seconds = 300
        exit_code = $code
        invocation_error_type = $failure
        within_total_allowance = ($watch.Elapsed.TotalSeconds -le 300)
    }
    $destination = if (Test-Path -LiteralPath $root -PathType Container -ErrorAction Stop) {
        Join-Path $root 'outer-observation.json'
    } else { $marker + '.outer.json' }
    $result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $destination -Encoding UTF8 -ErrorAction Stop
    $result | ConvertTo-Json -Depth 5
}
if ($null -ne $failure -or $null -eq $code -or $code -ne 0 -or -not $result.within_total_allowance) {
    throw 'Final lifecycle round stopped or failed verification. Preserve evidence; no retry authorized.'
}
