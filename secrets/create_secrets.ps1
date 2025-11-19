<#
    create_secrets.ps1 - Docker Swarm secrets bootstrapper (PowerShell edition)
    -------------------------------------------------------------------------
    Usage:
        powershell -ExecutionPolicy Bypass -File .\create_secrets.ps1 [-FromEnvFile ..\.env] [-Force] [-Verbose]

    Notes:
        - Reads secret values from an .env file, falling back to interactive prompts.
        - Creates the secrets required by docker-stack-n8n_TTRPG.yml.
        - Safe to re-run; existing secrets are skipped unless -Force is supplied.
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter()]
    [string]$FromEnvFile = "..\.env",

    [Parameter()]
    [switch]$Force
)

function Write-Info    ([string]$Message) { Write-Host "[INFO]  $Message" -ForegroundColor Cyan }
function Write-Success ([string]$Message) { Write-Host "[OK]    $Message" -ForegroundColor Green }
function Write-Warn    ([string]$Message) { Write-Host "[WARN]  $Message" -ForegroundColor Yellow }
function Write-ErrorLn ([string]$Message) { Write-Host "[ERROR] $Message" -ForegroundColor Red }

function Invoke-Docker {
    param(
        [string[]]$Args,
        [string]$InputText
    )

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "docker"
    $psi.Arguments = ($Args -join " ")
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.RedirectStandardInput = [string]::IsNullOrEmpty($InputText) -eq $false

    try {
        $proc = New-Object System.Diagnostics.Process
        $proc.StartInfo = $psi
        $proc.Start() | Out-Null

        if ($psi.RedirectStandardInput) {
            $proc.StandardInput.Write($InputText)
            $proc.StandardInput.Close()
        }

        $stdout = $proc.StandardOutput.ReadToEnd()
        $stderr = $proc.StandardError.ReadToEnd()
        $proc.WaitForExit()

        return [pscustomobject]@{
            ExitCode = $proc.ExitCode
            StdOut   = $stdout.TrimEnd()
            StdErr   = $stderr.TrimEnd()
        }
    }
    catch {
        return [pscustomobject]@{
            ExitCode = 1
            StdOut   = ""
            StdErr   = $_.Exception.Message
        }
    }
}

function Test-DockerSwarm {
    $result = Invoke-Docker -Args @("info", "--format", "{{.Swarm.LocalNodeState}}")
    if ($result.ExitCode -ne 0 -or $result.StdOut -ne "active") {
        throw "Docker Swarm is not initialized. Run 'docker swarm init' first."
    }
}

function Test-SecretExists([string]$Name) {
    $result = Invoke-Docker -Args @("secret", "inspect", $Name)
    return $result.ExitCode -eq 0
}

function New-DockerSecret([string]$Name, [string]$Value) {
    if ([string]::IsNullOrEmpty($Value)) {
        Write-Warn "Skipping '$Name' because no value was provided."
        return $false
    }

    if (Test-SecretExists $Name) {
        if ($Force) {
            Write-Warn "Secret '$Name' already exists. Remove it with 'docker secret rm $Name' to recreate."
        } else {
            Write-Warn "Secret '$Name' already exists. Skipping."
        }
        return $false
    }

    Write-Info "Creating secret '$Name'..."

    if ($PSCmdlet.ShouldProcess($Name, "Create Docker secret")) {
        $result = Invoke-Docker -Args @("secret", "create", $Name, "-") -InputText ($Value + "`n")
        if ($result.ExitCode -eq 0) {
            Write-Success "Created secret: $Name"
            return $true
        }
        Write-ErrorLn "Failed to create '$Name': $($result.StdErr)"
    }
    return $false
}

function Read-EnvFile([string]$Path) {
    $dict = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $dict
    }

    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line) { return }
        if ($line.StartsWith("#")) { return }

        $idx = $line.IndexOf("=")
        if ($idx -le 0) { return }

        $key = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim()

        if ($value.StartsWith('"') -and $value.EndsWith('"')) {
            $value = $value.Trim('"')
        } elseif ($value.StartsWith("'") -and $value.EndsWith("'")) {
            $value = $value.Trim("'")
        }

        $dict[$key] = $value
    }
    return $dict
}

# Secrets required by docker-stack-n8n_TTRPG.yml
$secretMap = @(
    @{ Name = "openai_api_key";    Env = "OPENAI_API_KEY";    Description = "OpenAI API key for embeddings and analysis"; Mask = $true  },
    @{ Name = "neo4j_user";        Env = "NEO4J_USER";        Description = "Neo4j database username";                   Mask = $false },
    @{ Name = "neo4j_password";    Env = "NEO4J_PASSWORD";    Description = "Neo4j database password";                   Mask = $true  },
    @{ Name = "postgres_user";     Env = "POSTGRES_USER";     Description = "PostgreSQL username";                       Mask = $false },
    @{ Name = "postgres_password"; Env = "POSTGRES_PASSWORD"; Description = "PostgreSQL password";                       Mask = $true  },
    @{ Name = "postgres_db";       Env = "POSTGRES_DB";       Description = "PostgreSQL database name";                  Mask = $false }
)

Write-Host "============================================================"
Write-Host " Docker Swarm Secrets Setup (PowerShell)"
Write-Host "============================================================"
Write-Host ""

try {
    Test-DockerSwarm
    Write-Success "Docker Swarm is active."
} catch {
    Write-ErrorLn $_.Exception.Message
    return
}

$envValues = Read-EnvFile -Path $FromEnvFile
if ($envValues.Count -gt 0) {
    Write-Info "Loaded $($envValues.Count) values from '$FromEnvFile'."
} else {
    Write-Warn "Environment file '$FromEnvFile' not found or empty. Values will be prompted."
}

$created = 0
$skipped = 0
$failed = 0

foreach ($entry in $secretMap) {
    $name = $entry.Name
    $envKey = $entry.Env
    $description = $entry.Description

    $value = $null
    if ($envValues.ContainsKey($envKey)) {
        $value = $envValues[$envKey]
    } elseif ($envKey) {
        $value = [Environment]::GetEnvironmentVariable($envKey)
    }

    if ([string]::IsNullOrEmpty($value)) {
        Write-Host ""
        Write-Info "Secret: $name"
        Write-Host "  Description: $description"
        if ($entry.Mask) {
            $secure = Read-Host -AsSecureString "  Enter value (input hidden)"
            if ($secure) {
                $ptr = [System.Runtime.InteropServices.Marshal]::SecureStringToGlobalAllocUnicode($secure)
                try {
                    $value = [System.Runtime.InteropServices.Marshal]::PtrToStringUni($ptr)
                }
                finally {
                    if ($ptr -ne [IntPtr]::Zero) {
                        [System.Runtime.InteropServices.Marshal]::ZeroFreeGlobalAllocUnicode($ptr)
                    }
                }
            }
        } else {
            $value = Read-Host "  Enter value"
        }
    }

    if (New-DockerSecret -Name $name -Value $value) {
        $created++
    } else {
        if (Test-SecretExists $name) {
            $skipped++
        } else {
            $failed++
        }
    }
}

Write-Host ""
Write-Host "============================================================"
Write-Host " Summary"
Write-Host "============================================================"
Write-Success "Created: $created"
if ($skipped -gt 0) { Write-Warn "Skipped: $skipped" }
if ($failed -gt 0)  { Write-ErrorLn "Failed: $failed" }

Write-Host ""
Write-Info "Current secrets in Swarm:"
$secretsList = Invoke-Docker -Args @("secret", "ls")
if ($secretsList.ExitCode -eq 0 -and $secretsList.StdOut) {
    Write-Host $secretsList.StdOut
} else {
    Write-ErrorLn "Unable to list secrets automatically. Run 'docker secret ls' to verify."
}

Write-Host ""
Write-Info "Next steps:"
Write-Host "  docker stack deploy -c docker-stack-n8n_TTRPG.yml ttrpg"
