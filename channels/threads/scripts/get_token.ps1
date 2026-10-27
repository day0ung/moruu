$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$envPath = Join-Path $PSScriptRoot '..\..\..\.env'
$cfg = [ordered]@{}
foreach ($line in Get-Content $envPath) {
  if ($line -match '^\s*([A-Z_]+)\s*=\s*(.*)$') { $cfg[$matches[1]] = $matches[2].Trim() }
}
if (-not $cfg['THREADS_APP_SECRET']) {
  $sec = Read-Host 'Threads 앱 시크릿 붙여넣기 (화면에 안 보임)' -AsSecureString
  $cfg['THREADS_APP_SECRET'] = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)).Trim()
}
foreach ($k in 'THREADS_APP_ID', 'THREADS_APP_SECRET', 'THREADS_AUTH_CODE') {
  if (-not $cfg[$k]) { Write-Output "$k 값이 비어 있습니다 (.env 확인)"; exit 1 }
}

$secret = $cfg['THREADS_APP_SECRET']
$code = $cfg['THREADS_AUTH_CODE'] -replace '#_$', ''

try {
  $short = Invoke-RestMethod -Method Post -Uri 'https://graph.threads.net/oauth/access_token' -Body @{
    client_id     = $cfg['THREADS_APP_ID']
    client_secret = $secret
    grant_type    = 'authorization_code'
    redirect_uri  = 'https://threads-auth.netlify.app/'
    code          = $code
  }
  $long = Invoke-RestMethod -Uri ("https://graph.threads.net/access_token?grant_type=th_exchange_token&client_secret={0}&access_token={1}" -f $secret, $short.access_token)
  $me = Invoke-RestMethod -Uri ("https://graph.threads.net/v1.0/me?fields=id,username&access_token={0}" -f $long.access_token)
} catch {
  $detail = if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }
  Write-Output "실패: $detail"
  exit 1
}

# 코드는 한 번 쓰면 끝이라 지우고, 토큰과 발급일을 남긴다
$cfg.Remove('THREADS_AUTH_CODE')
$cfg['THREADS_USER_ID'] = $me.id
$cfg['THREADS_ACCESS_TOKEN'] = $long.access_token
$cfg['THREADS_TOKEN_ISSUED'] = Get-Date -Format 'yyyy-MM-dd'
$cfg.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" } | Set-Content -Encoding ascii $envPath

Write-Output ("성공: @{0} / 유효기간 {1}일" -f $me.username, [int]($long.expires_in / 86400))
