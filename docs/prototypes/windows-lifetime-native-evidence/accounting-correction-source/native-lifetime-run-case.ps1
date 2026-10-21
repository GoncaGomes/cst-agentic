param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('leave-open', 'authorized-close')]
    [string]$Case
)

# THROWAWAY: measures outer uv entry/exit; never retries or deletes recovery state.
$ErrorActionPreference = 'Stop'
$Root = 'C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifetime-native'
$Driver = 'C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifetime-offline\src\cst_agentic\windows_lifetime_native.py'
$label = $Case
if ($Case -eq 'leave-open') { $label = 'leave-open-logging-fix-1' }
$scratch = Join-Path $Root ('evidence\' + $label)
$launchPath = Join-Path $Root ('evidence\' + $label + '-wrapper-start.json')
$roundPath = Join-Path $Root 'round.json'

function Write-DurableJson([string]$Path, $Value, [bool]$Exclusive) {
    $json = $Value | ConvertTo-Json -Depth 20
    $encoding = New-Object System.Text.UTF8Encoding($false)
    $bytes = $encoding.GetBytes($json)
    $writePath = $Path
    if (-not $Exclusive) { $writePath = $Path + '.outer-writing' }
    $stream = [System.IO.File]::Open($writePath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try {
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally {
        $stream.Dispose()
    }
    if (-not $Exclusive) { [System.IO.File]::Replace($writePath, $Path, $null) }
}

if (Test-Path -LiteralPath $scratch) { throw 'Attempt directory exists; no replay permitted.' }
$before = Get-Content -LiteralPath $roundPath -Raw | ConvertFrom-Json
$argsForDriver = @('run', '--offline', '--no-sync', 'python', $Driver, $Case)
if ($Case -eq 'leave-open') { $argsForDriver += '--resume-approved-logging-fix' }
Write-DurableJson $launchPath ([ordered]@{
    case = $Case
    utc = [DateTime]::UtcNow.ToString('o')
    driver_sha256 = (Get-FileHash -LiteralPath $Driver -Algorithm SHA256).Hash
    peer_sha256 = (Get-FileHash -LiteralPath (Join-Path (Split-Path $Driver) 'windows_lifetime_native_peer.py') -Algorithm SHA256).Hash
    wrapper_sha256 = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash
    ledger_before = $before
}) $true

$clock = [System.Diagnostics.Stopwatch]::StartNew()
$nativeInvocationError = $null
$code = -1
try {
    & uv @argsForDriver 2>$null
    $code = $LASTEXITCODE
} catch {
    $nativeInvocationError = $_.Exception.GetType().Name
    if ($null -ne $LASTEXITCODE) { $code = $LASTEXITCODE }
} finally {
    $clock.Stop()
}
$outerSeconds = $clock.Elapsed.TotalSeconds
$observationPath = Join-Path $scratch 'observations.json'
if (-not (Test-Path -LiteralPath $observationPath)) {
    Write-DurableJson (Join-Path $Root ('evidence\' + $label + '-outer-failure.json')) ([ordered]@{
        exit_code = $code
        native_invocation_error_type = $nativeInvocationError
        outer_uv_seconds = $outerSeconds
        observation_available = $false
        manual_confirmation_required = $true
    }) $true
    throw 'Driver did not produce observations. Stop; do not replay or start the second case.'
}
$observed = Get-Content -LiteralPath $observationPath -Raw | ConvertFrom-Json
$admission = Get-Content -LiteralPath (Join-Path $scratch 'ledger-at-admission.json') -Raw | ConvertFrom-Json
$after = Get-Content -LiteralPath $roundPath -Raw | ConvertFrom-Json
$overhead = [Math]::Max([double]0, [double]($outerSeconds - $observed.total_s))
$dispatched = @($observed.attempts | Where-Object { $_.PSObject.Properties.Name -contains 'dispatch' }).Count
$matches = ($after.tool_calls -eq ($admission.tool_calls + $dispatched)) -and ([Math]::Abs($after.active_seconds - ($admission.active_seconds + $observed.total_s)) -lt 0.002)
$reserveExceeded = $overhead -gt 30
if ($reserveExceeded) {
    $after.active_seconds += ($overhead - 30)
    Write-DurableJson $roundPath $after $false
}
$roundExceeded = ($after.active_seconds -gt 900) -or ($after.tool_calls -gt 12)
$startupUpper = $observed.startup_s + $overhead
$cleanupAvailable = $observed.PSObject.Properties.Name -contains 'cleanup_s'
$cleanupUpper = $null
if ($cleanupAvailable) { $cleanupUpper = $observed.cleanup_s + $overhead }
$allowanceExceeded = ($startupUpper -gt 120) -or (-not $cleanupAvailable) -or ($cleanupUpper -gt 30)
$result = [ordered]@{
    case = $Case
    exit_code = $code
    native_invocation_error_type = $nativeInvocationError
    driver_process_exit_observed = $true
    outer_uv_seconds = [Math]::Round($outerSeconds, 6)
    inner_driver_seconds = $observed.total_s
    outer_overhead_seconds = [Math]::Round($overhead, 6)
    wrapper_reserve_seconds = 30
    wrapper_reserve_exceeded = $reserveExceeded
    startup_with_all_outer_overhead_upper_seconds = $startupUpper
    cleanup_with_all_outer_overhead_upper_seconds = $cleanupUpper
    complete_allowance_exceeded = $allowanceExceeded
    ledger_matches = $matches
    round_ceiling_exceeded = $roundExceeded
    cumulative_calls = $after.tool_calls
    cumulative_charged_seconds = $after.active_seconds
    qualification = 'Prior attempt charged conservatively, not retrospectively timed. All outer uv overhead is included in each startup/cleanup upper bound. Evidence-writing time is covered by retained reserve, not separately measured.'
}
Write-DurableJson (Join-Path $scratch 'outer-observation.json') $result $true
$result | ConvertTo-Json -Depth 5
if (($code -ne 0) -or ($null -ne $nativeInvocationError)) { throw 'Driver failed. Stop for reconciliation; no native replay.' }
if ($reserveExceeded -or (-not $matches) -or $roundExceeded -or $allowanceExceeded) {
    throw 'Accounting or complete allowance check failed. Stop; do not start another case.'
}
