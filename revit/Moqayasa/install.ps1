# Installs Moqayasa for every Revit year found on this PC. Run from the folder that contains R2022..R2027.
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
foreach ($y in 2022..2027) {
  $src = Join-Path $here "R$y"
  if (-not (Test-Path $src)) { continue }
  $dest = Join-Path $env:APPDATA "Autodesk\Revit\Addins\$y"
  if (-not (Test-Path (Split-Path $dest))) { continue }          # that Revit year is not installed
  $bin = Join-Path $env:APPDATA "Moqayasa\bin\R$y"
  New-Item -ItemType Directory -Force $bin, $dest | Out-Null
  Copy-Item "$src\*" $bin -Recurse -Force
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
"@ | Set-Content -Encoding UTF8 (Join-Path $dest "Moqayasa.addin")
  Write-Host "Installed for Revit $y"
}
Write-Host "Done. Restart Revit and open the 'مقايسة' tab."
