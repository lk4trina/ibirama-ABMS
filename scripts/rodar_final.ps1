<#
Roda os lotes finais do artigo no GAMA headless, UM processo por simulacao (plano XML, semente explicita),
no maximo $Paralelo ao mesmo tempo, em copias do projeto FORA do repositorio (cada "slot" tem a sua).

Cada execucao grava a sua linha em  <Raiz>\runs\<experimento>\<cenario>_<semente>.csv  (uma linha, 69 campos).
RETOMAVEL: ao reiniciar, pula o que ja tem arquivo com linha valida. Falha -> repete ate 2 vezes (3 tentativas
no total) e registra em <Raiz>\falhas.log. Para parar com seguranca: crie o arquivo <Raiz>\PARAR (termina o que
esta rodando e nao inicia novas).

Experimentos (sementes 1..10, as mesmas em todos os cenarios; D usa 1..5):
  A_principal    550  chuva 60 (padrao); nenhum=1 cenario; alagamento/erosao 3x3 (rede=falso);
                      deslizamento/combinado 3x3x{falso,verdadeiro}
  B_chuva        100  combinado e alagamento, alta, parcial, rede=falso, chuva 0/60/120/240/780
  C_horario      120  combinado e alagamento, alta, parcial, chuva 60 e 780, inicio 30/270/630
  D_persistente  275  os 55 cenarios de A com chuva 780, sementes 1..5

Uso (PowerShell):
  powershell -ExecutionPolicy Bypass -File scripts\rodar_final.ps1
  powershell -ExecutionPolicy Bypass -File scripts\rodar_final.ps1 -Experimentos A_principal -Limite 5
#>
param(
    [string]$Raiz = 'C:\Temp\ibirama_final',
    [string]$Repo = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)),
    [int]$Paralelo = 5,
    [string[]]$Experimentos = @('A_principal', 'B_chuva', 'C_horario', 'D_persistente'),
    [int]$MaxTentativas = 3,
    [int]$TimeoutMin = 25,
    [int]$Limite = 0,          # 0 = tudo; > 0 = no maximo N execucoes novas (para teste)
    [string]$MemoriaJava = '4g'
)
$ErrorActionPreference = 'Stop'
$inv = [Globalization.CultureInfo]::InvariantCulture
$Gama = Join-Path $Raiz 'GAMA\headless'
$FalhasLog = Join-Path $Raiz 'falhas.log'
$TemposCsv = Join-Path $Raiz 'runs\tempos.csv'
$Parar = Join-Path $Raiz 'PARAR'
$Progresso = Join-Path $Repo 'docs\PROGRESSO_final.md'
$NCampos = 69
$TotalEsperado = @{ A_principal = 550; B_chuva = 100; C_horario = 120; D_persistente = 275 }

function Log($msg) { $l = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg; Write-Host $l; Add-Content -Path (Join-Path $Raiz 'orquestrador.log') -Value $l -Encoding UTF8 }

# ---------------------------------------------------------------- definicao dos cenarios ----------
function Cenario($ev, $sev, $info, $rede, $chuva, $ini) {
    $r = if ($rede) { 1 } else { 0 }
    [pscustomobject]@{ ev = $ev; sev = $sev; info = $info; rede = $rede; chuva = [double]$chuva; ini = [double]$ini
        nome = ('{0}_{1}_{2}_rede{3}_chuva{4}_ini{5}' -f $ev, $sev, $info, $r, [int]$chuva, [int]$ini) }
}
function Cenarios-A($chuva) {
    $L = @(); $SEV = 'baixa', 'media', 'alta'; $INF = 'local', 'parcial', 'amplo'
    $L += Cenario 'nenhum' 'baixa' 'local' $false $chuva 60
    foreach ($e in 'alagamento', 'erosao') { foreach ($s in $SEV) { foreach ($i in $INF) { $L += Cenario $e $s $i $false $chuva 60 } } }
    foreach ($e in 'deslizamento', 'combinado') { foreach ($s in $SEV) { foreach ($i in $INF) { foreach ($r in $false, $true) { $L += Cenario $e $s $i $r $chuva 60 } } } }
    return $L
}
function Jobs-Do-Experimento($exp) {
    $cen = @(); $sementes = 1..10
    switch ($exp) {
        'A_principal' { $cen = Cenarios-A 60 }
        'B_chuva' { foreach ($e in 'combinado', 'alagamento') { foreach ($c in 0, 60, 120, 240, 780) { $cen += Cenario $e 'alta' 'parcial' $false $c 60 } } }
        'C_horario' { foreach ($e in 'combinado', 'alagamento') { foreach ($i in 30, 270, 630) { foreach ($c in 60, 780) { $cen += Cenario $e 'alta' 'parcial' $false $c $i } } } }
        'D_persistente' { $cen = Cenarios-A 780; $sementes = 1..5 }
        default { throw "experimento desconhecido: $exp" }
    }
    $jobs = @()
    foreach ($sd in $sementes) {      # semente por fora: um corte parcial ja cobre todos os cenarios
        foreach ($c in $cen) {
            $jobs += [pscustomobject]@{ exp = $exp; c = $c; seed = $sd; tentativas = 0
                arq = (Join-Path $Raiz ("runs\{0}\{1}_{2}.csv" -f $exp, $c.nome, $sd)) }
        }
    }
    return $jobs
}

# ---------------------------------------------------------------- validacao de uma linha ----------
function Test-Linha($path, $job) {
    if (-not (Test-Path $path)) { return 'arquivo ausente' }
    $linhas = @(Get-Content -Path $path -Encoding UTF8 | Where-Object { $_.Trim() -ne '' })
    if ($linhas.Count -ne 1) { return "esperava 1 linha, achei $($linhas.Count)" }
    $f = $linhas[0].Split(',')
    if ($f.Count -ne $NCampos) { return "esperava $NCampos campos, achei $($f.Count)" }
    $c = $job.c
    if ($f[0] -ne $c.ev -or $f[1] -ne $c.sev -or $f[2] -ne $c.info) { return 'evento/severidade/informacao diferentes do pedido' }
    if ($f[3] -ne $c.rede.ToString().ToLower()) { return 'rede_energizada diferente do pedido' }
    if ([double]::Parse($f[7], $inv) -ne $c.chuva) { return 'duracao_chuva_min diferente do pedido' }
    if ([double]::Parse($f[10], $inv) -ne [double]$job.seed) { return 'semente diferente do pedido' }
    if ([double]::Parse($f[68], $inv) -ne $c.ini) { return 'inicio_evento_min diferente do pedido' }
    foreach ($x in $f) { if ($x.Trim() -eq '') { return 'campo vazio' } }
    return $null
}

# ---------------------------------------------------------------- slots ---------------------------
function Preparar-Slot($id) {
    $s = Join-Path $Raiz "slots\$id"
    foreach ($d in 'models', 'includes\dados') { New-Item -ItemType Directory -Force -Path (Join-Path $s $d) | Out-Null }
    Copy-Item -Force (Join-Path $Repo 'models\ibirama.gaml') (Join-Path $s 'models\ibirama.gaml')
    Get-ChildItem (Join-Path $Repo 'includes\dados') -File | Where-Object { $_.Name -notmatch 'TESTE|SINTETICO' } |
        ForEach-Object { Copy-Item -Force $_.FullName (Join-Path $s 'includes\dados\') }
    $ic = Join-Path $Repo 'includes\dados\icones'
    if (Test-Path $ic) { Copy-Item -Recurse -Force $ic (Join-Path $s 'includes\dados\') }
    New-Item -ItemType Directory -Force -Path (Join-Path $Raiz "ws\$id") | Out-Null
    return $s
}

function Iniciar-Job($slot, $job) {
    $s = $slot.dir
    $csv = Join-Path $s 'includes\resultados_gama_dc.csv'
    if (Test-Path $csv) { Remove-Item -Force $csv }            # a linha desta execucao sera a unica
    $out = Join-Path $Raiz "logs\out_$($slot.id)"
    if (Test-Path $out) { Remove-Item -Recurse -Force $out }
    $c = $job.c
    $xml = @"
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<Experiment_plan>
  <Simulation id="1" sourcePath="$s\models\ibirama.gaml" finalStep="4682" experiment="Interativo" seed="$($job.seed)">
    <Parameters>
      <Parameter var="tipo_evento" type="STRING" value="$($c.ev)"/>
      <Parameter var="severidade" type="STRING" value="$($c.sev)"/>
      <Parameter var="info_nivel" type="STRING" value="$($c.info)"/>
      <Parameter var="rede_energizada" type="BOOLEAN" value="$($c.rede.ToString().ToLower())"/>
      <Parameter var="duracao_chuva_min" type="FLOAT" value="$($c.chuva.ToString($inv))"/>
      <Parameter var="inicio_evento_min" type="FLOAT" value="$($c.ini.ToString($inv))"/>
      <Parameter var="pausar_no_fim" type="BOOLEAN" value="false"/>
    </Parameters>
    <Outputs/>
  </Simulation>
</Experiment_plan>
"@
    $plano = Join-Path $Raiz "plans\$($slot.id).xml"
    New-Item -ItemType Directory -Force -Path (Join-Path $Raiz 'plans') | Out-Null
    [IO.File]::WriteAllText($plano, $xml, (New-Object Text.UTF8Encoding($false)))
    $logo = Join-Path $Raiz "logs\$($slot.id).out.log"; $loge = Join-Path $Raiz "logs\$($slot.id).err.log"
    $job.tentativas++
    $slot.job = $job; $slot.t0 = Get-Date
    $slot.proc = Start-Process -FilePath (Join-Path $Gama 'gama-headless.bat') `
        -ArgumentList @('-m', $MemoriaJava, '-ws', "`"$(Join-Path $Raiz "ws\$($slot.id)")`"", "`"$plano`"", "`"$out`"") `
        -WorkingDirectory $Gama -RedirectStandardOutput $logo -RedirectStandardError $loge -WindowStyle Hidden -PassThru
}

function Finalizar-Job($slot, $motivoForcado) {
    $job = $slot.job
    $dur = [int]((Get-Date) - $slot.t0).TotalSeconds
    $csv = Join-Path $slot.dir 'includes\resultados_gama_dc.csv'
    $erro = if ($motivoForcado) { $motivoForcado } else { Test-Linha $csv $job }
    if (-not $erro) {
        New-Item -ItemType Directory -Force -Path (Split-Path $job.arq) | Out-Null
        Copy-Item -Force $csv ($job.arq + '.tmp'); Move-Item -Force ($job.arq + '.tmp') $job.arq
        if (-not (Test-Path $TemposCsv)) { Set-Content $TemposCsv 'quando,experimento,arquivo,segundos,slot' -Encoding UTF8 }
        Add-Content $TemposCsv ('{0},{1},{2},{3},{4}' -f (Get-Date -Format 's'), $job.exp, (Split-Path $job.arq -Leaf), $dur, $slot.id) -Encoding UTF8
        $script:feitos++
        $slot.proc = $null; $slot.job = $null
        return $true
    }
    $trecho = ''
    $lo = Join-Path $Raiz "logs\$($slot.id).out.log"
    if (Test-Path $lo) { $trecho = ((Get-Content $lo -Tail 400 -ErrorAction SilentlyContinue | Select-String -Pattern 'rror|xception|ailed|Could not' | Select-Object -Last 3) -join ' | ') }
    Add-Content $FalhasLog ('{0} {1} {2} semente={3} tentativa={4}/{5} dur={6}s motivo="{7}" {8}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $job.exp, $job.c.nome, $job.seed, $job.tentativas, $MaxTentativas, $dur, $erro, $trecho) -Encoding UTF8
    $slot.proc = $null; $slot.job = $null
    if ($job.tentativas -lt $MaxTentativas) { $script:fila.Enqueue($job) }
    else { Add-Content $FalhasLog ('{0} DESISTI {1} {2} semente={3} apos {4} tentativas' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $job.exp, $job.c.nome, $job.seed, $job.tentativas) -Encoding UTF8; $script:desistidos++ }
    return $false
}

# ---------------------------------------------------------------- progresso -----------------------
function Escrever-Progresso($fim) {
    $linhas = @()
    $linhas += "Atualizado em: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  |  estado: " + $(if ($fim) { 'PARADO' } else { 'RODANDO' })
    $linhas += ''
    $linhas += '| Experimento | Feitas (arquivo valido) | Esperado | Falta |'
    $linhas += '|---|---|---|---|'
    $tot = 0; $totE = 0
    foreach ($e in 'A_principal', 'B_chuva', 'C_horario', 'D_persistente') {
        $d = Join-Path $Raiz "runs\$e"
        $n = if (Test-Path $d) { @(Get-ChildItem $d -Filter '*.csv').Count } else { 0 }
        $tot += $n; $totE += $TotalEsperado[$e]
        $linhas += "| $e | $n | $($TotalEsperado[$e]) | $($TotalEsperado[$e] - $n) |"
    }
    $linhas += "| **Total** | **$tot** | **$totE** | **$($totE - $tot)** |"
    $linhas += ''
    $nf = if (Test-Path $FalhasLog) { @(Get-Content $FalhasLog).Count } else { 0 }
    $linhas += "Linhas em falhas.log: $nf (desistidos nesta sessao: $script:desistidos)."
    if (Test-Path $TemposCsv) {
        $t = @(Import-Csv $TemposCsv | Select-Object -Last 50 | ForEach-Object { [double]$_.segundos })
        if ($t.Count -gt 0) { $m = ($t | Measure-Object -Average).Average
            $linhas += ('Tempo medio por execucao (ultimas {0}): {1:N0} s; com {2} em paralelo, faltam ~{3:N1} h.' -f $t.Count, $m, $Paralelo, (($totE - $tot) * $m / $Paralelo / 3600)) }
    }
    $bloco = ($linhas -join "`r`n")
    if (-not (Test-Path $Progresso)) { return }
    $txt = [IO.File]::ReadAllText($Progresso, [Text.Encoding]::UTF8)
    $novo = [regex]::Replace($txt, '(?s)<!-- STATUS:INICIO -->.*?<!-- STATUS:FIM -->', ('<!-- STATUS:INICIO -->' + "`r`n" + $bloco + "`r`n" + '<!-- STATUS:FIM -->'))
    [IO.File]::WriteAllText($Progresso, $novo, (New-Object Text.UTF8Encoding($false)))
}

# ---------------------------------------------------------------- principal -----------------------
New-Item -ItemType Directory -Force -Path (Join-Path $Raiz 'logs'), (Join-Path $Raiz 'runs') | Out-Null
$script:feitos = 0; $script:desistidos = 0
if (Test-Path $Parar) { Remove-Item -Force $Parar }

# o mesmo modelo em todas as execucoes: guarda o SHA-256 e avisa se mudar entre sessoes
$sha = (Get-FileHash (Join-Path $Repo 'models\ibirama.gaml') -Algorithm SHA256).Hash
$shaArq = Join-Path $Raiz 'runs\modelo_sha256.txt'
if (Test-Path $shaArq) {
    $antigo = (Get-Content $shaArq -TotalCount 1).Trim()
    if ($antigo -ne $sha) { throw "models\ibirama.gaml mudou desde as primeiras execucoes ($antigo -> $sha). Nao misture modelos; ajuste $shaArq de proposito se for o caso." }
} else { Set-Content $shaArq $sha -Encoding ASCII }
Log "modelo SHA-256 $sha"

$slots = @(); for ($k = 1; $k -le $Paralelo; $k++) { $id = "s$k"; $slots += @{ id = $id; dir = (Preparar-Slot $id); proc = $null; job = $null; t0 = $null } }

$script:fila = New-Object System.Collections.Generic.Queue[object]
$pend = 0; $ja = 0
foreach ($exp in $Experimentos) {
    foreach ($j in (Jobs-Do-Experimento $exp)) {
        $erro = Test-Linha $j.arq $j
        if (-not $erro) { $ja++ } else { if (Test-Path $j.arq) { Remove-Item -Force $j.arq }; $script:fila.Enqueue($j); $pend++ }
    }
}
Log "Retomada: $ja execucoes ja validas, $pend a fazer. Paralelo=$Paralelo."
$ultimoProg = Get-Date; $iniciados = 0
while ($true) {
    $parando = (Test-Path $Parar) -or ($Limite -gt 0 -and $iniciados -ge $Limite)
    foreach ($s in $slots) {
        if ($s.proc -ne $null) {
            if ($s.proc.HasExited) { $ok = Finalizar-Job $s $null }
            elseif (((Get-Date) - $s.t0).TotalMinutes -gt $TimeoutMin) {
                & taskkill /PID $s.proc.Id /T /F | Out-Null
                $ok = Finalizar-Job $s "timeout de $TimeoutMin min"
            }
        }
        if ($s.proc -eq $null -and -not $parando -and $script:fila.Count -gt 0) {
            $j = $script:fila.Dequeue(); Iniciar-Job $s $j; $iniciados++
        }
    }
    $ativos = @($slots | Where-Object { $_.proc -ne $null }).Count
    if ($ativos -eq 0 -and ($parando -or $script:fila.Count -eq 0)) { break }
    if (((Get-Date) - $ultimoProg).TotalSeconds -gt 60) { Escrever-Progresso $false; $ultimoProg = Get-Date }
    Start-Sleep -Seconds 2
}
Escrever-Progresso $true
Log "Fim da sessao: $script:feitos feitas, $script:desistidos desistidas, $($script:fila.Count) na fila."
