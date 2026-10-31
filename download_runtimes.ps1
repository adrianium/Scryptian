# download_runtimes.ps1 — Scryptian runtime components (like Chrome's stub downloader).
# Downloads ffmpeg and ghostscript into <AppDir>\runtimes\ in the background.
param([Parameter(Mandatory=$true)][string]$AppDir)

$ErrorActionPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$base = Join-Path $AppDir 'runtimes'
$ffmpegDir = Join-Path $base 'ffmpeg'
$gsDir = Join-Path $base 'ghostscript'

New-Item -ItemType Directory -Force -Path $ffmpegDir | Out-Null
New-Item -ItemType Directory -Force -Path $gsDir | Out-Null

# ffmpeg essentials (Gyan). build.txt marks a finished extract so an old
# stripped ffmpeg.exe gets replaced once.
$ffmpeg = Join-Path $ffmpegDir 'ffmpeg.exe'
$marker = Join-Path $ffmpegDir 'build.txt'
$haveEssentials = (Test-Path $ffmpeg) -and (Test-Path $marker) -and ((Get-Content -Raw $marker) -match 'essentials')
if (-not $haveEssentials) {
  $seven = Join-Path $AppDir '7zr.exe'
  if (-not (Test-Path $seven)) { $seven = Join-Path $AppDir '_internal\7zr.exe' }
  $archive = Join-Path $ffmpegDir 'essentials.7z.part'
  try {
    Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.7z' -OutFile $archive -UseBasicParsing
    & $seven e $archive "-o$ffmpegDir" -y -r ffmpeg.exe ffprobe.exe | Out-Null
    if (Test-Path $ffmpeg) {
      Set-Content -Path $marker -Value "essentials" -Encoding ascii
    }
  } catch { }
  finally {
    if (Test-Path $archive) { Remove-Item $archive -Force -ErrorAction SilentlyContinue }
  }
}

# ghostscript
$gsExe = Join-Path $gsDir 'bin\gswin64c.exe'
if (-not (Test-Path $gsExe)) {
  $gsZip = Join-Path $base 'ghostscript.zip'
  try {
    Invoke-WebRequest -Uri 'https://qvihfoeouvfveacexcol.supabase.co/storage/v1/object/public/actions/ghostscript.zip' -OutFile $gsZip -UseBasicParsing
    Expand-Archive -Path $gsZip -DestinationPath $gsDir -Force
    Remove-Item $gsZip -Force
  } catch { }
}
