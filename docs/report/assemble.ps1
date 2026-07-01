# Assemble the project documentation PDF from the LIVING docs + synthesized chapters.
#
# Pipeline: read source markdown -> fence-aware heading transform -> emoji/glyph
# sanitize -> concatenate into one build .md -> pandoc (--pdf-engine=tectonic) -> PDF.
#
# Run:  powershell -File docs/report/assemble.ps1
# Out:  docs/report/TempestFaunaTrail-Documentation.pdf

$ErrorActionPreference = "Stop"

# Ensure pandoc + tectonic are reachable in this (possibly stale) shell.
$env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")

$RepoRoot   = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ReportDir  = $PSScriptRoot
$Sections   = Join-Path $ReportDir "sections"
$BuildDir   = Join-Path $ReportDir "build"
$Combined   = Join-Path $BuildDir "combined.md"
$OutPdf     = Join-Path $ReportDir "TempestFaunaTrail-Documentation.pdf"

New-Item -ItemType Directory -Force $BuildDir | Out-Null

# --- helpers ---------------------------------------------------------------

# Map emoji/symbols that xelatex fonts don't cover to plain-text tokens.
# Keys built from codepoints so this .ps1 stays pure-ASCII (PS 5.1 reads
# non-BOM files as ANSI, which would mangle literal emoji).
function U([int]$cp) { return [char]::ConvertFromUtf32($cp) }
$Replacements = [ordered]@{
  (U 0x2705)  = "[done]";    (U 0x1F536) = "[stub]"; (U 0x1F7E1) = "[partial]"; (U 0x1F4CB) = "[planned]";
  (U 0x25B6)  = ">";         (U 0x25C0)  = "<";      (U 0x25BC)  = "v";         (U 0x25B2)  = "^";
  (U 0x2192)  = "->";        (U 0x2190)  = "<-";     (U 0x27F6)  = "-->";      (U 0x21D2)  = "=>";        (U 0x21D0) = "<=";
  (U 0x2194)  = "<->";       (U 0x2260)  = "!=";     (U 0x226A)  = "<<";       (U 0x226B)  = ">>";        (U 0x222A) = "U";
  (U 0x2229)  = "^";         (U 0x2208)  = "in";     (U 0x2A00)  = " Amber";    (U 0x27C2)  = "perp";      (U 0x221D)  = "proportional to";
  (U 0x2248)  = "~=";        (U 0x2264)  = "<=";     (U 0x2265)  = ">=";
  (U 0x00D7)  = "x";         (U 0x00B7)  = "-";      (U 0x2014)  = "--";        (U 0x2013)  = "-";        (U 0x2026) = "...";
  (U 0x201C)  = '"';         (U 0x201D)  = '"';      (U 0x2018)  = "'";         (U 0x2019)  = "'";
}
function Sanitize([string]$text) {
  foreach ($k in $Replacements.Keys) { $text = $text.Replace($k, $Replacements[$k]) }
  return $text
}

# Read a markdown file and transform its ATX headings, skipping fenced code blocks.
#   mode = "replace-title":       swap the first H1 for $title, leave the rest.
#   mode = "replace-title-denum": as above, and strip leading "N." / "N.M"
#                                 section numbers from lower headings (they'd
#                                 collide with pandoc's auto section numbers).
#   mode = "shift":               add $shift '#' to every heading (h1 -> h(1+shift)).
function Transform([string]$path, [string]$mode, [string]$title, [int]$shift) {
  $lines = Get-Content -LiteralPath $path -Encoding UTF8
  $out = New-Object System.Collections.Generic.List[string]
  $inFence = $false
  $fenceTok = $null
  $titleDone = $false
  foreach ($line in $lines) {
    $trim = $line.TrimStart()
    # Toggle fenced code blocks (``` or ~~~).
    if (-not $inFence -and ($trim -match '^(```|~~~)')) {
      $inFence = $true; $fenceTok = $Matches[1]; $out.Add($line); continue
    } elseif ($inFence -and ($trim -match ('^' + [regex]::Escape($fenceTok)))) {
      $inFence = $false; $fenceTok = $null; $out.Add($line); continue
    }
    if (-not $inFence -and ($line -match '^(#{1,6}) (.*)$')) {
      $hashes = $Matches[1]; $rest = $Matches[2]
      if ($mode -eq "replace-title" -or $mode -eq "replace-title-denum") {
        if (-not $titleDone -and $hashes.Length -eq 1) {
          $out.Add("# $title"); $titleDone = $true; continue
        }
        if ($mode -eq "replace-title-denum") {
          $rest = $rest -replace '^\d+(\.\d+)*\.?\s+', ''
        }
        $out.Add("$hashes $rest"); continue
      } elseif ($mode -eq "shift") {
        $out.Add(("#" * $shift) + $hashes + " " + $rest); continue
      }
    }
    $out.Add($line)
  }
  return ($out -join "`n")
}

# --- document structure ----------------------------------------------------

$parts = New-Object System.Collections.Generic.List[string]
function AddRaw([string]$text) { $parts.Add($text); $parts.Add("`n`n") }
function AddFile([string]$path, [string]$mode, [string]$title, [int]$shift) {
  AddRaw (Transform $path $mode $title $shift)
}

$live = Join-Path $RepoRoot "docs\live"

# Ch1 Overview  <- README (title replaced so it becomes the numbered chapter).
AddFile (Join-Path $RepoRoot "README.md") "replace-title" "Overview" 0

# Ch2 Architecture <- ARCHITECTURE (strip its own "1./2." section numbers).
AddFile (Join-Path $RepoRoot "ARCHITECTURE.md") "replace-title-denum" "Architecture" 0

# Ch3 Systems & Features <- authored intro (owns the chapter H1) + every docs/live doc, shifted to H2.
AddFile (Join-Path $Sections "03_systems_intro.md") "none" "" 0
$liveOrder = @(
  "systems\combat.md","systems\effects.md","systems\weather.md","systems\formation.md",
  "systems\encounter.md","systems\scaling.md","systems\weather_api.md","systems\save.md",
  "systems\items.md","systems\kit_design_conventions.md",
  "content\rosters.md","content\abilities.md","content\traits.md","content\items.md","content\augments.md"
)
foreach ($rel in $liveOrder) { AddFile (Join-Path $live $rel) "shift" "" 1 }

# Ch4 & Ch5 <- authored (synthesized) chapters, own their H1.
AddFile (Join-Path $Sections "04_ai_collaboration.md") "none" "" 0
AddFile (Join-Path $Sections "05_implementation.md") "none" "" 0

# --- write + render --------------------------------------------------------

$doc = Sanitize ($parts -join "")
Set-Content -LiteralPath $Combined -Value $doc -Encoding UTF8
Write-Host "Wrote $Combined ($(($doc -split "`n").Count) lines)"

$meta   = Join-Path $ReportDir "meta.yaml"
$header = Join-Path $ReportDir "header.tex"

$luaFit = Join-Path $ReportDir "fit-tables.lua"

pandoc $meta $Combined `
  --pdf-engine=tectonic `
  --include-in-header=$header `
  --lua-filter=$luaFit `
  --from=gfm+yaml_metadata_block `
  -o $OutPdf

if (Test-Path $OutPdf) {
  Write-Host "PDF OK: $OutPdf ($([math]::Round((Get-Item $OutPdf).Length/1kb)) KB)"
} else {
  throw "PDF not produced"
}
