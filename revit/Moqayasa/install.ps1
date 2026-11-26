# Moqayasa installer. Copies prebuilt files only: no SDK, no build, no downloads.
#   .\install.ps1               install for every Revit year that is really installed on this PC
#   .\install.ps1 -Years 2026   install only for the listed years (the year must be installed)
#   .\install.ps1 -Uninstall    remove Moqayasa from every year (add -Years to limit it)
param([int[]]$Years = (2022..2027), [switch]$Uninstall)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

function Test-RevitInstalled([int]$y) {
  # A year counts as installed only if Revit.exe is there (Program Files, any drive layout) or the Autodesk registry says so.
  $roots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}) | Where-Object { $_ }
  foreach ($root in $roots) {
    if (Test-Path (Join-Path $root "Autodesk\Revit $y\Revit.exe")) { return $true }
  }
  foreach ($k in @('HKLM:\SOFTWARE\Autodesk\Revit', 'HKLM:\SOFTWARE\WOW6432Node\Autodesk\Revit')) {
    if (Test-Path $k) {
      $hit = Get-ChildItem $k -ErrorAction SilentlyContinue | Where-Object { $_.PSChildName -match "(^|\D)$y(\D|$)" }
      if ($hit) { return $true }
    }
  }
  return $false
}

$done = @(); $skipped = @()
foreach ($y in $Years) {
  $addinDir = Join-Path $env:APPDATA "Autodesk\Revit\Addins\$y"
  $manifest = Join-Path $addinDir "Moqayasa.addin"
  $bin = Join-Path $env:APPDATA "Moqayasa\bin\R$y"
  if ($Uninstall) {
    if (Test-Path $manifest) { Remove-Item $manifest -Force; $done += $y }
    if (Test-Path $bin) { Remove-Item $bin -Recurse -Force }
    continue
  }
  $src = Join-Path $here "R$y"
  if (-not (Test-Path $src)) { $skipped += "$y (no files for this year in the zip)"; continue }
  if (-not (Test-RevitInstalled $y)) { $skipped += "$y (Revit $y not found on this PC)"; continue }
  New-Item -ItemType Directory -Force $bin, $addinDir | Out-Null
  Copy-Item "$src\*" $bin -Recurse -Force
  # files from a download carry a web mark that makes Revit ask or refuse to load them
  try { Get-ChildItem $bin -Recurse -File | Unblock-File } catch { }
  $dll = Join-Path $bin "Moqayasa.dll"
  @"
<?xml version="1.0" encoding="utf-8"?>
<RevitAddIns>
  <AddIn Type="Application">
    <Name>Moqayasa</Name>
    <Assembly>$dll</Assembly>
    <FullClassName>Moqayasa.App</FullClassName>
    <AddInId>5b0b6f0e-7a51-4c1e-9a52-6f1a3a1d0a77</AddInId>
    <VendorId>HASR</VendorId>
    <VendorDescription>Hasr / Moqayasa, open source (MIT)</VendorDescription>
  </AddIn>
</RevitAddIns>
"@ | Set-Content -Encoding UTF8 $manifest
  $done += $y
}

if ($Uninstall) {
  if ($done.Count) { Write-Host "Removed Moqayasa from Revit: $($done -join ', ')" } else { Write-Host "Moqayasa was not installed." }
  Write-Host "Your files in $env:APPDATA\Moqayasa (prices.csv, systems.json) and reports in Documents\Moqayasa were left alone."
} else {
  if ($done.Count) { Write-Host "Installed for Revit: $($done -join ', ')" } else { Write-Host "Nothing installed." }
  foreach ($s in $skipped) { Write-Host "Skipped $s" }
  if ($done.Count) { Write-Host "Restart Revit and open the Moqayasa tab (Arabic name on the ribbon)." }
  else { Write-Host "No supported Revit (2022-2027) was found. Use -Years <year> only if that Revit is installed." }
}
