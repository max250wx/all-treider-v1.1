# ============================================================
# inventory.ps1 — инвентаризация файлов для торгового советника
# Читает ТОЛЬКО метаданные (имя, размер, дата). Содержимое не трогает.
# ============================================================

# --- Настройки (правьте только этот блок) ---
$Roots  = @("C:\ai-advisor", "$env:USERPROFILE\Documents", "$env:USERPROFILE\Downloads")
$OutDir = "C:\ai-advisor\_inventory"
# --------------------------------------------

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$Categories = @{
  "data"   = @("*.csv","*.parquet","*.feather","*.h5","*.hdf5","*.xlsx","*.xls","*.jsonl")
  "code"   = @("*.py","*.mq4","*.mq5","*.mqh","*.pine","*.ipynb","*.r","*.jl")
  "config" = @("*.yaml","*.yml","*.json","*.toml","*.ini","*.cfg","*.env")
  "model"  = @("*.pkl","*.joblib","*.pt","*.pth","*.onnx","*.h5","*.safetensors","*.gguf")
  "logs"   = @("*.log","trades*.csv","orders*.csv","backtest*.csv","signals*.csv")
  "notes"  = @("*.md","*.txt","*.docx","*.pdf","*.rst")
}

$Exclude = @(
  "$env:USERPROFILE\AppData",
  "$env:USERPROFILE\.cache",
  "node_modules",
  ".git",
  "__pycache__",
  ".venv",
  "venv",
  "site-packages"
)

$all = @()

foreach ($root in $Roots) {
  if (-not (Test-Path $root)) {
    Write-Host "Пропуск (нет папки): $root" -ForegroundColor DarkYellow
    continue
  }
  Write-Host "Сканирую: $root" -ForegroundColor Cyan

  $files = Get-ChildItem -Path $root -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object {
      $p = $_.FullName
      -not ($Exclude | Where-Object { $p -like "*$_*" })
    }

  foreach ($f in $files) {
    $cat = "other"
    foreach ($k in $Categories.Keys) {
      foreach ($pat in $Categories[$k]) {
        if ($f.Name -like $pat) { $cat = $k; break }
      }
      if ($cat -ne "other") { break }
    }
    $all += [pscustomobject]@{
      Category = $cat
      Name     = $f.Name
      Ext      = $f.Extension
      SizeKB   = [math]::Round($f.Length / 1KB, 2)
      Modified = $f.LastWriteTime.ToString("yyyy-MM-dd HH:mm")
      Path     = $f.FullName
    }
  }
}

$all | Export-Csv -NoTypeInformation -Encoding UTF8 -Path "$OutDir\files_all.csv"
$all | Where-Object { $_.Category -ne "other" } |
  Sort-Object Category, @{Expression="SizeKB"; Descending=$true} |
  Export-Csv -NoTypeInformation -Encoding UTF8 -Path "$OutDir\files_relevant.csv"

Write-Host ""
Write-Host "=== Сводка по категориям ===" -ForegroundColor Green
$all | Group-Object Category | Sort-Object Count -Descending |
  Format-Table Name, Count -AutoSize

Write-Host ""
Write-Host "Результаты:"
Write-Host "  $OutDir\files_all.csv        (все файлы)"
Write-Host "  $OutDir\files_relevant.csv   (только релевантные)"