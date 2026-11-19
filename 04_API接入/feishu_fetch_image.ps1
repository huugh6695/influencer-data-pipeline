param(
  [Parameter(Mandatory=$true)][string]$MessageId,
  [string]$OutFile = ".\image.jpg"
)
$ErrorActionPreference = 'Stop'

# 入口：凭证从环境变量读
$appId     = $env:FEISHU_APP_ID
$appSecret = $env:FEISHU_APP_SECRET
if (-not $appId -or -not $appSecret) { throw 'FEISHU_APP_ID / FEISHU_APP_SECRET missing' }

$body = @{ app_id = $appId; app_secret = $appSecret } | ConvertTo-Json
$tok  = Invoke-RestMethod -Method Post -ContentType 'application/json; charset=utf-8' `
        -Uri 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal' `
        -Body ([Text.Encoding]::UTF8.GetBytes($body))
if ($tok.code -ne 0) { throw "token: $($tok.code) $($tok.msg)" }
$bearer = 'Bearer ' + $tok.tenant_access_token
$h = @{ Authorization = $bearer }

# 读消息，content 是字符串形式的 JSON
$msg = Invoke-RestMethod -Uri "https://open.feishu.cn/open-apis/im/v1/messages/$MessageId" -Headers $h
$content = $msg.data.items[0].body.content
$fileKey = [regex]::Match($content, '"(image_key|file_key)"\s*:\s*"([^"]+)"').Groups[2].Value
if (-not $fileKey) { throw "no image_key: $content" }

# 出口：下载资源，type 必填
Invoke-WebRequest -Uri "https://open.feishu.cn/open-apis/im/v1/messages/$MessageId/resources/$fileKey?type=image" `
  -Headers $h -OutFile $OutFile
Write-Output "saved $OutFile ($((Get-Item $OutFile).Length) bytes)"
