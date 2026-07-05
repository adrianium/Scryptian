$log = $env:TEMP + '\scryptian_uninstall.log'
Add-Content $log "=== uninstall started ==="

$id = 'unknown'
$f = $env:LOCALAPPDATA + '\Scryptian\.id'
Add-Content $log ("id file exists: " + (Test-Path $f))
if (Test-Path $f) { $id = (Get-Content $f -Raw).Trim() }
Add-Content $log ("id: " + $id)

$body = '{"api_key":"phc_nyYF49YRbnnsjJbMqFwZbXxpiPfU249NAnmnZHuPavei","event":"uninstalled","distinct_id":"' + $id + '","properties":{}}'
Add-Content $log ("body: " + $body)

try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri 'https://us.i.posthog.com/capture/' -Method POST -ContentType 'application/json' -Body $body -TimeoutSec 5
    Add-Content $log ("sent ok: " + $r.StatusCode)
} catch {
    Add-Content $log ("error: " + $_)
}
