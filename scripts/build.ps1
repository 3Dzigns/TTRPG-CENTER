param([string]$AppDir = ".\app", [string]$OutDir = ".\builds")

$ts = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$buildId = "${ts}_build-$(Get-Random -Minimum 1000 -Maximum 9999)"
$dest = Join-Path $OutDir $buildId
New-Item -ItemType Directory -Path $dest -Force | Out-Null

Write-Host "Building $buildId..."

# Copy app source
Copy-Item -Path $AppDir -Destination (Join-Path $dest "app") -Recurse -Force

# Lock deps & build (adapt to your stack)
# python -m pip freeze > "$dest\requirements.lock.txt"
# npm ci && npm run build && Copy-Item ".\app\ui\dist" "$dest\dist" -Recurse

# Source hash
if (Get-Command "7z" -ErrorAction SilentlyContinue) {
    $zipPath = Join-Path $dest "source.7z"
    & 7z a $zipPath $AppDir | Out-Null
} else {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zipPath = Join-Path $dest "source.zip"
    [IO.Compression.ZipFile]::CreateFromDirectory($AppDir, $zipPath)
}

$sha256 = (Get-FileHash $zipPath -Algorithm SHA256).Hash.ToLower()

$manifest = @{
  build_id = $buildId
  created_at = (Get-Date).ToString("s")
  source_hash = "sha256:$sha256"
  env_support = @("dev","test","prod")
}
($manifest | ConvertTo-Json -Depth 5) | Set-Content (Join-Path $dest "build-manifest.json")

Write-Host "Built $buildId at $dest"
Write-Host "Manifest: $(Join-Path $dest 'build-manifest.json')"