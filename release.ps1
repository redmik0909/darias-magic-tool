# ============================================================
#  Daria's Magic Tool — Script de release automatique
# ============================================================

param(
    [string]$version = ""
)

# Demande la version si pas fournie
if (-not $version) {
    $version = Read-Host "Numero de version (ex: 2.2)"
}

Write-Host ""
Write-Host "==> Release v$version" -ForegroundColor Cyan
Write-Host ""

# 1. Met a jour version.txt
Write-Host "[1/6] Mise a jour version.txt..." -ForegroundColor Yellow
Set-Content -Path "version.txt" -Value $version

# 2. Met a jour CURRENT_VERSION dans app.py
Write-Host "[2/6] Mise a jour app.py..." -ForegroundColor Yellow
(Get-Content app.py) -replace 'CURRENT_VERSION = ".*"', "CURRENT_VERSION = `"$version`"" | Set-Content app.py

# 3. Recompile avec PyInstaller
Write-Host "[3/6] Compilation PyInstaller..." -ForegroundColor Yellow
venv\Scripts\activate
pyinstaller --onefile --windowed --name "Darias-Magic-Tool" --icon "revolvit.ico" --add-data "zones.json;." --add-data "pages;pages" app.py --noconfirm

# 4. Copie les fichiers dans dist
Write-Host "[4/6] Copie des fichiers..." -ForegroundColor Yellow
copy zones.json dist\
xcopy pages dist\pages /E /I /Y | Out-Null

# 5. Compile l'installateur
Write-Host "[5/6] Compilation Inno Setup..." -ForegroundColor Yellow
(Get-Content installer.iss) -replace 'OutputBaseFilename=DariasMagicTool-Setup-v.*', "OutputBaseFilename=DariasMagicTool-Setup-v$version" | Set-Content installer.iss
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss

# 6. Copie le setup en "latest"
Write-Host "[6/6] Preparation du fichier latest..." -ForegroundColor Yellow
copy "installer_output\DariasMagicTool-Setup-v$version.exe" "installer_output\DariasMagicTool-Setup-latest.exe"

# 7. Git commit + push
Write-Host ""
Write-Host "==> Git commit et push..." -ForegroundColor Cyan
git add .
git commit -m "Release v$version"
git push

Write-Host ""
Write-Host "==> Release v$version terminee!" -ForegroundColor Green
Write-Host ""
Write-Host "Etapes manuelles restantes:" -ForegroundColor Yellow
Write-Host "  1. Aller sur github.com/redmik0909/darias-magic-tool/releases/new"
Write-Host "  2. Tag: v$version"
Write-Host "  3. Uploader: installer_output\DariasMagicTool-Setup-latest.exe"
Write-Host "  4. Publier la release"
Write-Host ""
