# Еженедельная копия бэкапов Kira's Day с сервера на этот компьютер.
# Использует тот же SSH-ключ, что и обычный `ssh root@...` — отдельно
# настраивать ничего не нужно, если вход на сервер уже работает без пароля.

$ServerUser = "root"
$ServerHost = "37.27.181.64"
$RemotePath = "~/bot/backups/*.gz"
$LocalPath  = "$env:USERPROFILE\KirasDayBackups"

New-Item -ItemType Directory -Force -Path $LocalPath | Out-Null

scp -r "${ServerUser}@${ServerHost}:${RemotePath}" $LocalPath

Write-Host "Готово: бэкапы скопированы в $LocalPath"
