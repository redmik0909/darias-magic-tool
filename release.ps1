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

# Recupere le token GitHub depuis le keyring
$token = (python -c "import keyring; t=keyring.get_password('DariasMagicTool','github_token'); print(t if t else '')" 2>$null).Trim()
if (-not $token -or $token -eq "None") {
    Write-Host "ERREUR: Token GitHub introuvable dans le keyring!" -ForegroundColor Red
    exit 1
}

$repo = "redmik0909/darias-magic-tool"

# 0. Pull les derniers changements
Write-Host "[0/7] Git pull..." -ForegroundColor Yellow
git pull origin main --rebase

# 1. Met a jour version.txt
Write-Host "[1/7] Mise a jour version.txt..." -ForegroundColor Yellow
Set-Content -Path "version.txt" -Value $version -NoNewline

# 2. Met a jour CURRENT_VERSION dans app.py
Write-Host "[2/7] Mise a jour app.py..." -ForegroundColor Yellow
(Get-Content app.py) -replace 'CURRENT_VERSION = ".*"', "CURRENT_VERSION = `"$version`"" | Set-Content app.py

# 3. Recompile avec PyInstaller
Write-Host "[3/7] Compilation PyInstaller..." -ForegroundColor Yellow
venv\Scripts\activate
pyinstaller --onefile --windowed --name "Darias-Magic-Tool" --icon "revolvit.ico" --add-data "zones.json;." --add-data "pages;pages" app.py --noconfirm | Out-Null
Write-Host "    PyInstaller termine!" -ForegroundColor Green

# 4. Copie les fichiers dans dist — supprime d'abord pour eviter dist\pages\pages\
Write-Host "[4/7] Copie des fichiers..." -ForegroundColor Yellow
Copy-Item "zones.json" -Destination "dist\" -Force
Remove-Item "dist\pages" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item "pages\*" -Destination "dist\pages" -Recurse -Force
Write-Host "    Pages copiees!" -ForegroundColor Green

# 5. Compile l'installateur
Write-Host "[5/7] Compilation Inno Setup..." -ForegroundColor Yellow
(Get-Content installer.iss) `
    -replace 'OutputBaseFilename=DariasMagicTool-Setup-v.*', "OutputBaseFilename=DariasMagicTool-Setup-v$version" `
    -replace 'AppVersion=.*', "AppVersion=$version" | Set-Content installer.iss
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss | Out-Null
Write-Host "    Inno Setup termine!" -ForegroundColor Green

# 6. Copie le setup en "latest" et supprime les anciens
Write-Host "[6/7] Preparation du fichier latest..." -ForegroundColor Yellow
Copy-Item "installer_output\DariasMagicTool-Setup-v$version.exe" -Destination "installer_output\DariasMagicTool-Setup-latest.exe" -Force
Get-ChildItem "installer_output\DariasMagicTool-Setup-v*.exe" | Where-Object { $_.Name -ne "DariasMagicTool-Setup-v$version.exe" } | Remove-Item -Force

# 7. Git commit + push
Write-Host "[7/7] Git commit et push..." -ForegroundColor Yellow
git add .
git commit -m "Release v$version"
git push

# 8. Cree la release GitHub via API
Write-Host ""
Write-Host "==> Creation de la release GitHub..." -ForegroundColor Cyan

$headers = @{
    "Authorization" = "Bearer $token"
    "Accept"        = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

$body = @{
    tag_name = "v$version"
    name     = "Daria's Magic Tool v$version"
    body     = "Release v$version"
    draft    = $false
    prerelease = $false
} | ConvertTo-Json

$release = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/releases" `
    -Method Post -Headers $headers -Body $body -ContentType "application/json"

Write-Host "    Release creee! ID: $($release.id)" -ForegroundColor Green

# 9. Upload le fichier latest.exe
Write-Host "==> Upload de DariasMagicTool-Setup-latest.exe..." -ForegroundColor Cyan

$uploadUrl = "https://uploads.github.com/repos/$repo/releases/$($release.id)/assets?name=DariasMagicTool-Setup-latest.exe"
$filePath  = "installer_output\DariasMagicTool-Setup-latest.exe"
$fileBytes = [System.IO.File]::ReadAllBytes((Resolve-Path $filePath))

$uploadHeaders = @{
    "Authorization" = "Bearer $token"
    "Accept"        = "application/vnd.github+json"
    "Content-Type"  = "application/octet-stream"
}

Invoke-RestMethod -Uri $uploadUrl -Method Post -Headers $uploadHeaders -Body $fileBytes | Out-Null

Write-Host "    Fichier uploade!" -ForegroundColor Green
Write-Host ""
Write-Host "==> Release v$version completement automatisee!" -ForegroundColor Green
Write-Host "    https://github.com/$repo/releases/tag/v$version" -ForegroundColor Cyan
Write-Host ""