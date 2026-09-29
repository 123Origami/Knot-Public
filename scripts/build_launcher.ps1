param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$python = Join-Path $ProjectRoot 'venv\Scripts\python.exe'
$launcher = Join-Path $ProjectRoot 'knot_launcher.py'

if (-not (Test-Path $python)) {
    throw "Python executable not found at $python"
}

& $python -m pip show pyinstaller | Out-Null
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install pyinstaller
}

Push-Location $ProjectRoot
try {
    & $python -m PyInstaller `
        --noconfirm `
        --onefile `
        --name knot-launcher `
        --paths "$ProjectRoot\backend" `
        --add-data "$ProjectRoot\db.sqlite3;." `
        --add-data "$ProjectRoot\frontend;frontend" `
        --add-data "$ProjectRoot\css;css" `
        --add-data "$ProjectRoot\assets;assets" `
        --add-data "$ProjectRoot\static;static" `
        --add-data "$ProjectRoot\media;media" `
        --add-data "$ProjectRoot\data;data" `
        --collect-submodules apps `
        --collect-submodules verify_email `
        --hidden-import backend.settings `
        --hidden-import backend.urls `
        --hidden-import backend.wsgi `
        --hidden-import verify_email `
        --hidden-import verify_email.apps `
        $launcher
} finally {
    Pop-Location
}