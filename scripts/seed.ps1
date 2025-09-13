# seed.ps1
# FR-006: Container Data Seeding Script
# Seeds containerized databases with sample data for development and testing

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("dev", "test", "prod")]
    [string]$Env = "dev",
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("all", "postgres", "mongodb", "neo4j")]
    [string]$Database = "all",
    
    [Parameter(Mandatory=$false)]
    [switch]$Reset,
    
    [Parameter(Mandatory=$false)]
    [switch]$Verbose,
    
    [Parameter(Mandatory=$false)]
    [string]$SampleDataPath = "test_fixtures"
)

# Script configuration
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Project configuration
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

# Functions
function Write-Status {
    param([string]$Message, [string]$Level = "Info")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    switch ($Level) {
        "Info" { Write-Host "[$timestamp] INFO: $Message" -ForegroundColor Green }
        "Warning" { Write-Host "[$timestamp] WARN: $Message" -ForegroundColor Yellow }
        "Error" { Write-Host "[$timestamp] ERROR: $Message" -ForegroundColor Red }
        "Success" { Write-Host "[$timestamp] SUCCESS: $Message" -ForegroundColor Cyan }
        "Seed" { Write-Host "[$timestamp] SEED: $Message" -ForegroundColor Blue }
    }
}

function Test-Prerequisites {
    # Check if stack is running
    try {
        $runningContainers = docker ps --filter "name=ttrpg" --format "{{.Names}}"
        if (-not $runningContainers) {
            throw "No TTRPG containers are running. Please start the stack first with: .\scripts\deploy.ps1 -Action up"
        }
        Write-Status "Found running containers: $($runningContainers -join ', ')"
    }
    catch {
        throw "Failed to check running containers: $($_.Exception.Message)"
    }
    
    # Check sample data path
    if (-not (Test-Path $SampleDataPath)) {
        Write-Status "Sample data path not found: $SampleDataPath" -Level "Warning"
        Write-Status "Creating minimal sample data..." -Level "Info"
        New-Item -ItemType Directory -Path $SampleDataPath -Force | Out-Null
    }
}

function Test-StackHealth {
    Write-Status "Testing stack health before seeding..." -Level "Seed"
    
    try {
        $healthUrl = "http://localhost:8000/healthz"
        $response = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 10 -UseBasicParsing
        
        if ($response.StatusCode -eq 200) {
            $health = $response.Content | ConvertFrom-Json
            Write-Status "Stack health status: $($health.status)" -Level "Success"
            return $true
        } else {
            Write-Status "Stack health check failed: HTTP $($response.StatusCode)" -Level "Error"
            return $false
        }
    }
    catch {
        Write-Status "Stack health check error: $($_.Exception.Message)" -Level "Error"
        return $false
    }
}

function Seed-PostgreSQL {
    Write-Status "Seeding PostgreSQL database..." -Level "Seed"
    
    try {
        # Create sample user data
        $seedUserSQL = @"
-- Sample users for development
INSERT INTO users (id, username, email, created_at, is_active) VALUES 
('dev-user-1', 'gm_alice', 'alice@example.com', NOW(), true),
('dev-user-2', 'player_bob', 'bob@example.com', NOW(), true),
('dev-user-3', 'player_carol', 'carol@example.com', NOW(), true)
ON CONFLICT (id) DO NOTHING;

-- Sample tiers
INSERT INTO user_tiers (id, name, description, max_queries_per_day) VALUES 
('basic', 'Basic', 'Basic tier for development', 100),
('premium', 'Premium', 'Premium tier for development', 1000)
ON CONFLICT (id) DO NOTHING;

-- Link users to tiers
INSERT INTO user_tier_assignments (user_id, tier_id, assigned_at) VALUES 
('dev-user-1', 'premium', NOW()),
('dev-user-2', 'basic', NOW()),
('dev-user-3', 'basic', NOW())
ON CONFLICT (user_id, tier_id) DO NOTHING;
"@
        
        # Write SQL to temp file
        $tempSqlFile = [System.IO.Path]::GetTempFileName() + ".sql"
        $seedUserSQL | Out-File -FilePath $tempSqlFile -Encoding UTF8
        
        # Copy SQL file to container and execute
        docker cp $tempSqlFile ttrpg-postgres-dev:/tmp/seed_data.sql
        
        $pgSeedCmd = @("docker", "exec", "ttrpg-postgres-dev", "psql", "-U", "ttrpg_user", "-d", "ttrpg_dev", "-f", "/tmp/seed_data.sql")
        & $pgSeedCmd[0] $pgSeedCmd[1..($pgSeedCmd.Length-1)]
        
        if ($LASTEXITCODE -eq 0) {
            Write-Status "PostgreSQL seeding completed successfully" -Level "Success"
            
            # Verify data
            $verifyCmd = @("docker", "exec", "ttrpg-postgres-dev", "psql", "-U", "ttrpg_user", "-d", "ttrpg_dev", "-c", "SELECT COUNT(*) FROM users;")
            $userCount = & $verifyCmd[0] $verifyCmd[1..($verifyCmd.Length-1)]
            Write-Status "Users in database: $($userCount | Select-String -Pattern '\d+' | ForEach-Object { $_.Matches.Value })"
        } else {
            Write-Status "PostgreSQL seeding failed with exit code: $LASTEXITCODE" -Level "Error"
            return $false
        }
        
        # Cleanup
        Remove-Item $tempSqlFile -ErrorAction SilentlyContinue
        docker exec ttrpg-postgres-dev rm -f /tmp/seed_data.sql
        
        return $true
    }
    catch {
        Write-Status "PostgreSQL seeding error: $($_.Exception.Message)" -Level "Error"
        return $false
    }
}

function Seed-MongoDB {
    Write-Status "Seeding MongoDB database..." -Level "Seed"
    
    try {
        # Create sample dictionary entries
        $sampleEntries = @(
            @{
                _id = "fireball"
                term_original = "Fireball"
                term_normalized = "fireball"
                definition = "A bright streak flashes from your pointing finger to a point you choose within range and then blossoms with a low roar into an explosion of flame."
                category = "spell"
                sources = @(@{ system = "pf2e"; book = "Core Rulebook"; page = 338 })
                created_at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
                updated_at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
            },
            @{
                _id = "sword"
                term_original = "Sword"
                term_normalized = "sword"
                definition = "A bladed weapon with a long metal blade and a hilt with a hand guard."
                category = "equipment"
                sources = @(@{ system = "pf2e"; book = "Core Rulebook"; page = 280 })
                created_at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
                updated_at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
            },
            @{
                _id = "ranger"
                term_original = "Ranger"
                term_normalized = "ranger"
                definition = "Rangers are skilled hunters and trackers who protect the wilderness and those who travel through it."
                category = "class"
                sources = @(@{ system = "pf2e"; book = "Core Rulebook"; page = 168 })
                created_at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
                updated_at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
            }
        )
        
        # Convert to JSON
        $jsonEntries = $sampleEntries | ConvertTo-Json -Depth 10
        
        # Write JSON to temp file
        $tempJsonFile = [System.IO.Path]::GetTempFileName() + ".json"
        $jsonEntries | Out-File -FilePath $tempJsonFile -Encoding UTF8
        
        # Copy JSON file to container
        docker cp $tempJsonFile ttrpg-mongo-dev:/tmp/seed_data.json
        
        # Import data using mongoimport
        $mongoSeedCmd = @("docker", "exec", "ttrpg-mongo-dev", "mongoimport", 
                         "--db", "ttrpg_dev", "--collection", "dictionary", 
                         "--file", "/tmp/seed_data.json", "--jsonArray", "--upsert")
        & $mongoSeedCmd[0] $mongoSeedCmd[1..($mongoSeedCmd.Length-1)]
        
        if ($LASTEXITCODE -eq 0) {
            Write-Status "MongoDB seeding completed successfully" -Level "Success"
            
            # Verify data
            $verifyCmd = @("docker", "exec", "ttrpg-mongo-dev", "mongosh", "ttrpg_dev", 
                          "--eval", "db.dictionary.countDocuments()")
            $entryCount = & $verifyCmd[0] $verifyCmd[1..($verifyCmd.Length-1)]
            Write-Status "Dictionary entries in database: $($entryCount | Select-String -Pattern '\d+' | ForEach-Object { $_.Matches.Value })"
        } else {
            Write-Status "MongoDB seeding failed with exit code: $LASTEXITCODE" -Level "Error"
            return $false
        }
        
        # Cleanup
        Remove-Item $tempJsonFile -ErrorAction SilentlyContinue
        docker exec ttrpg-mongo-dev rm -f /tmp/seed_data.json
        
        return $true
    }
    catch {
        Write-Status "MongoDB seeding error: $($_.Exception.Message)" -Level "Error"
        return $false
    }
}

function Seed-Neo4j {
    Write-Status "Seeding Neo4j database..." -Level "Seed"
    
    try {
        # Create sample graph data (documents, sections, chunks)
        $sampleCypher = @"
// Clear existing data (if reset requested)
MATCH (n) DETACH DELETE n;

// Create sample document
CREATE (doc:Document {
    id: 'sample-doc-1', 
    title: 'Sample RPG Document', 
    created_at: timestamp(), 
    updated_at: timestamp()
});

// Create sample sections
CREATE (sec1:Section {
    id: 'sample-doc-1#intro', 
    title: 'Introduction', 
    level: 1, 
    page: 1, 
    updated_at: timestamp()
});

CREATE (sec2:Section {
    id: 'sample-doc-1#spells', 
    title: 'Spells', 
    level: 1, 
    page: 10, 
    updated_at: timestamp()
});

CREATE (sec3:Section {
    id: 'sample-doc-1#spells-fire', 
    title: 'Fire Spells', 
    level: 2, 
    page: 15, 
    updated_at: timestamp()
});

// Create sample chunks
CREATE (chunk1:Chunk {
    id: 'sample-doc-1#chunk-1', 
    text: 'This is the introduction to our sample RPG system. It covers the basic rules and mechanics.', 
    page: 1, 
    index: 0, 
    tokens: 20, 
    updated_at: timestamp()
});

CREATE (chunk2:Chunk {
    id: 'sample-doc-1#chunk-2', 
    text: 'Fireball is a powerful evocation spell that creates a burst of flame at a targeted location.', 
    page: 15, 
    index: 1, 
    tokens: 18, 
    updated_at: timestamp()
});

// Create relationships
MATCH (doc:Document {id: 'sample-doc-1'})
MATCH (sec1:Section {id: 'sample-doc-1#intro'})
MATCH (sec2:Section {id: 'sample-doc-1#spells'})
MATCH (sec3:Section {id: 'sample-doc-1#spells-fire'})
MATCH (chunk1:Chunk {id: 'sample-doc-1#chunk-1'})
MATCH (chunk2:Chunk {id: 'sample-doc-1#chunk-2'})

CREATE (doc)-[:HAS_SECTION]->(sec1)
CREATE (doc)-[:HAS_SECTION]->(sec2)
CREATE (sec2)-[:HAS_SUBSECTION]->(sec3)
CREATE (doc)-[:HAS_CHUNK]->(chunk1)
CREATE (doc)-[:HAS_CHUNK]->(chunk2)
CREATE (sec1)-[:HAS_CHUNK]->(chunk1)
CREATE (sec3)-[:HAS_CHUNK]->(chunk2);
"@
        
        # Write Cypher to temp file
        $tempCypherFile = [System.IO.Path]::GetTempFileName() + ".cypher"
        $sampleCypher | Out-File -FilePath $tempCypherFile -Encoding UTF8
        
        # Copy Cypher file to container
        docker cp $tempCypherFile ttrpg-neo4j-dev:/tmp/seed_data.cypher
        
        # Execute Cypher script
        $neo4jSeedCmd = @("docker", "exec", "ttrpg-neo4j-dev", "cypher-shell", 
                         "-u", "neo4j", "-p", "dev_password", 
                         "-f", "/tmp/seed_data.cypher")
        & $neo4jSeedCmd[0] $neo4jSeedCmd[1..($neo4jSeedCmd.Length-1)]
        
        if ($LASTEXITCODE -eq 0) {
            Write-Status "Neo4j seeding completed successfully" -Level "Success"
            
            # Verify data
            $verifyCmd = @("docker", "exec", "ttrpg-neo4j-dev", "cypher-shell", 
                          "-u", "neo4j", "-p", "dev_password", 
                          "MATCH (n) RETURN count(n) as total")
            $nodeCount = & $verifyCmd[0] $verifyCmd[1..($verifyCmd.Length-1)]
            Write-Status "Nodes in graph: $($nodeCount | Select-String -Pattern '\d+' | ForEach-Object { $_.Matches.Value })"
        } else {
            Write-Status "Neo4j seeding failed with exit code: $LASTEXITCODE" -Level "Error"
            return $false
        }
        
        # Cleanup
        Remove-Item $tempCypherFile -ErrorAction SilentlyContinue
        docker exec ttrpg-neo4j-dev rm -f /tmp/seed_data.cypher
        
        return $true
    }
    catch {
        Write-Status "Neo4j seeding error: $($_.Exception.Message)" -Level "Error"
        return $false
    }
}

function Reset-Database {
    param([string]$DatabaseType)
    
    Write-Status "Resetting $DatabaseType database..." -Level "Warning"
    
    switch ($DatabaseType) {
        "postgres" {
            $resetCmd = @("docker", "exec", "ttrpg-postgres-dev", "psql", 
                         "-U", "ttrpg_user", "-d", "ttrpg_dev", 
                         "-c", "DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
            & $resetCmd[0] $resetCmd[1..($resetCmd.Length-1)]
        }
        "mongodb" {
            $resetCmd = @("docker", "exec", "ttrpg-mongo-dev", "mongosh", "ttrpg_dev", 
                         "--eval", "db.dropDatabase()")
            & $resetCmd[0] $resetCmd[1..($resetCmd.Length-1)]
        }
        "neo4j" {
            $resetCmd = @("docker", "exec", "ttrpg-neo4j-dev", "cypher-shell", 
                         "-u", "neo4j", "-p", "dev_password", 
                         "MATCH (n) DETACH DELETE n")
            & $resetCmd[0] $resetCmd[1..($resetCmd.Length-1)]
        }
    }
    
    if ($LASTEXITCODE -eq 0) {
        Write-Status "$DatabaseType reset completed" -Level "Success"
    } else {
        Write-Status "$DatabaseType reset failed" -Level "Error"
    }
}

# Main execution
try {
    Write-Status "TTRPG Center Database Seeding Script"
    Write-Status "Environment: $Env, Database: $Database"
    
    # Change to project root
    Set-Location $ProjectRoot
    Write-Status "Working directory: $ProjectRoot"
    
    # Check prerequisites
    Test-Prerequisites
    
    # Test stack health
    if (-not (Test-StackHealth)) {
        throw "Stack is not healthy. Please ensure all services are running properly."
    }
    
    # Reset databases if requested
    if ($Reset) {
        if ($Database -eq "all") {
            Reset-Database "postgres"
            Reset-Database "mongodb"
            Reset-Database "neo4j"
        } else {
            Reset-Database $Database
        }
        
        # Wait for databases to recover
        Write-Status "Waiting for databases to recover after reset..."
        Start-Sleep -Seconds 10
    }
    
    # Seed databases
    $seedResults = @()
    
    if ($Database -in @("all", "postgres")) {
        Write-Status "`nSeeding PostgreSQL..." -Level "Seed"
        $pgResult = Seed-PostgreSQL
        $seedResults += @{ Database = "PostgreSQL"; Success = $pgResult }
    }
    
    if ($Database -in @("all", "mongodb")) {
        Write-Status "`nSeeding MongoDB..." -Level "Seed"
        $mongoResult = Seed-MongoDB
        $seedResults += @{ Database = "MongoDB"; Success = $mongoResult }
    }
    
    if ($Database -in @("all", "neo4j")) {
        Write-Status "`nSeeding Neo4j..." -Level "Seed"
        $neo4jResult = Seed-Neo4j
        $seedResults += @{ Database = "Neo4j"; Success = $neo4jResult }
    }
    
    # Summary
    Write-Status "`nSeeding Summary:" -Level "Success"
    Write-Status "=" * 50 -Level "Success"
    
    $successful = 0
    $failed = 0
    
    foreach ($result in $seedResults) {
        if ($result.Success) {
            Write-Status "$($result.Database): SUCCESS" -Level "Success"
            $successful++
        } else {
            Write-Status "$($result.Database): FAILED" -Level "Error"
            $failed++
        }
    }
    
    Write-Status "Successful: $successful, Failed: $failed" -Level "Success"
    
    if ($failed -eq 0) {
        Write-Status "`nAll databases seeded successfully!" -Level "Success"
        Write-Status "You can now test the application with sample data." -Level "Success"
    } else {
        Write-Status "`nSome database seeding failed. Check the logs above for details." -Level "Warning"
        exit 1
    }
}
catch {
    Write-Status "Database seeding failed: $($_.Exception.Message)" -Level "Error"
    exit 1
}
finally {
    $ProgressPreference = "Continue"
}