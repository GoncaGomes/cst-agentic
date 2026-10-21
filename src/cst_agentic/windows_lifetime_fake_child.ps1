# THROWAWAY: fake descendant only. Never starts or controls CST.
param([Parameter(Mandatory=$true)][string]$Scratch)
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class PrototypeJob {
    [DllImport("kernel32.dll")] public static extern IntPtr GetCurrentProcess();
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool IsProcessInJob(IntPtr process, IntPtr job, out bool result);
}
'@
$inJob = $false
if (-not [PrototypeJob]::IsProcessInJob([PrototypeJob]::GetCurrentProcess(), [IntPtr]::Zero, [ref]$inJob)) {
    exit 2
}
@{ pid = $PID; in_any_job = $inJob } | ConvertTo-Json -Compress | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $Scratch 'child-ready.writing')
Move-Item -LiteralPath (Join-Path $Scratch 'child-ready.writing') -Destination (Join-Path $Scratch 'child-ready.json')
$deadline = [DateTime]::UtcNow.AddSeconds(60)
while ([DateTime]::UtcNow -lt $deadline) {
    if (Test-Path -LiteralPath (Join-Path $Scratch 'child-stop.flag')) {
        Set-Content -Encoding UTF8 -LiteralPath (Join-Path $Scratch 'child-ended.txt') -Value 'requested'
        exit 0
    }
    Start-Sleep -Milliseconds 25
}
exit 3
