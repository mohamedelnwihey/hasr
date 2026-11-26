# Build the add-in for every supported Revit year (needs .NET SDK 8 and 10; run on Windows or Linux).
foreach ($y in 2022..2027) { dotnet build Addin -c Release -p:RevitYear=$y }
