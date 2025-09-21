# build.ps1
# Скрипт для сборки wxPython-проекта с pandas и openpyxl в onedir

$mainScript = "main.py"
$appName = "seismicfilter"
$iconPath = "app.ico"  # оставь пустым, если иконки нет

# Папка dict должна оказаться рядом с _internal внутри dist
# Формат: "source;destination" (Windows использует ;)
$resources = @(
    "dict;_internal\dict"
)

# Формируем аргументы --add-data
$addDataArgs = $resources | ForEach-Object { "--add-data `"$($_)`"" } | Out-String
$addDataArgs = $addDataArgs -replace "\r?\n"," "

# Формируем команду PyInstaller
$cmd = "pyinstaller --onedir --noconsole --name $appName"

if (Test-Path $iconPath) {
    $cmd += " --icon `"$iconPath`""
}

if ($addDataArgs) {
    $cmd += " $addDataArgs"
}

$cmd += "--hidden-import watchdog.observers.winapi `"$mainScript`""

Write-Host "Запускаем PyInstaller:"
Write-Host $cmd

Invoke-Expression $cmd