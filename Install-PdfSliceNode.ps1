<#
.SYNOPSIS
  Install a local n8n Community Node "PDF Slice (Local)" that slices pages x–y from a PDF using pdf-lib (no external APIs).

.DESCRIPTION
  This script:
    1) Creates the node project scaffold (TypeScript) under a target folder.
    2) Builds it using local npm or a Node Docker image (no internet APIs used by the node; only npm to fetch deps).
    3) Installs the compiled "dist" into a running n8n container at /home/node/.n8n/custom/n8n-nodes-pdf-slice/dist
    4) Restarts the n8n container.
  Optionally, it prints a Docker Compose volume/env snippet for persistent mounting instead of copying.

.PARAMETER ProjectRoot
  Directory where the node project will be created. Defaults to current directory.

.PARAMETER NodeFolderName
  Folder name for the project. Defaults to "n8n-nodes-pdf-slice".

.PARAMETER ContainerName
  The name (or ID) of your running n8n container. Defaults to "n8n".

.PARAMETER BuildInDocker
  If set, use a Node Docker image to run npm install/build (no need for local Node.js).

.PARAMETER PrintComposeSnippet
  If set, prints a docker-compose.yml snippet to use a bind mount for persistent installation.

.EXAMPLE
  .\Install-PdfSliceNode.ps1 -ContainerName n8n -BuildInDocker

.NOTES
  - Requires Docker to be installed and the n8n container running (for copy-install mode).
  - If your n8n container uses a different username home, adjust the DEST_PATH variable.
#>

param(
  [string]$ProjectRoot = (Get-Location).Path,
  [string]$NodeFolderName = "n8n-nodes-pdf-slice",
  [string]$ContainerName = "n8n",
  [switch]$BuildInDocker,
  [switch]$PrintComposeSnippet
)

$ErrorActionPreference = "Stop"

# --- Paths
$ProjectPath = Join-Path $ProjectRoot $NodeFolderName
$SrcPath = Join-Path $ProjectPath "src"
$NodePath = Join-Path $SrcPath "nodes"
$PdfSlicePath = Join-Path $NodePath "PdfSlice"

Write-Host "Project path: $ProjectPath"

# --- Create folders
New-Item -ItemType Directory -Force -Path $PdfSlicePath | Out-Null

# --- Write package.json
$packageJson = @'
{
  "name": "n8n-nodes-pdf-slice",
  "version": "0.1.0",
  "description": "Local PDF slicer node for n8n using pdf-lib (no external APIs).",
  "author": "Local",
  "license": "MIT",
  "type": "module",
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc -p tsconfig.json",
    "clean": "rimraf dist",
    "prepare": "npm run build"
  },
  "dependencies": {
    "pdf-lib": "^1.17.1"
  },
  "devDependencies": {
    "@types/node": "^20.11.0",
    "rimraf": "^5.0.5",
    "typescript": "^5.4.0"
  },
  "n8n": {
    "nodes": [
      "dist/nodes/PdfSlice/PdfSlice.node.js"
    ]
  }
}
'@
Set-Content -Path (Join-Path $ProjectPath "package.json") -Value $packageJson -Encoding UTF8

# --- Write tsconfig.json
$tsconfig = @'
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ES2020",
    "moduleResolution": "Bundler",
    "outDir": "dist",
    "rootDir": "src",
    "declaration": false,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  },
  "include": ["src/**/*.ts"]
}
'@
Set-Content -Path (Join-Path $ProjectPath "tsconfig.json") -Value $tsconfig -Encoding UTF8

# --- Write README.md
$readme = @'
# n8n-nodes-pdf-slice (Local)

Slicing pages X–Y from an input PDF using [pdf-lib]; no external APIs.
Place the node in n8n and wire it like any transform node with a binary input.

**Inputs:**
- Binary Property: name that contains `application/pdf` (default: `data`)
- Start Page: integer (1-based)
- End Page: integer (1-based)

**Outputs:**
- Adds a binary property (default: `sliced`) holding the new PDF
- Adds `json.sliceInfo` metadata

'@
Set-Content -Path (Join-Path $ProjectPath "README.md") -Value $readme -Encoding UTF8

# --- Write src/nodes/PdfSlice/types.ts
$typesTs = @'
export type RangeInput = {
  startPage: number; // 1-based inclusive
  endPage: number;   // 1-based inclusive
  binaryPropertyName?: string; // default: "data"
  outputPropertyName?: string; // default: "sliced"
  carryMetadata?: boolean;     // default: true
};
'@
Set-Content -Path (Join-Path $PdfSlicePath "types.ts") -Value $typesTs -Encoding UTF8

# --- Write src/nodes/PdfSlice/PdfSlice.description.ts
$descTs = @'
import type { INodeTypeDescription } from "n8n-workflow";

export const PdfSliceDescription: INodeTypeDescription = {
  displayName: "PDF Slice (Local)",
  name: "pdfSliceLocal",
  group: ["transform"],
  version: 1,
  description: "Create a smaller PDF containing only pages X–Y (no external APIs).",
  defaults: {
    name: "PDF Slice (Local)",
  },
  inputs: ["main"],
  outputs: ["main"],
  icon: "fa:file-pdf",
  properties: [
    {
      displayName: "Binary Property",
      name: "binaryPropertyName",
      type: "string",
      default: "data",
      description: "Name of the incoming binary property that holds the source PDF.",
    },
    {
      displayName: "Start Page",
      name: "startPage",
      type: "number",
      typeOptions: { minValue: 1 },
      default: 1,
      description: "1-based inclusive start page.",
      required: true,
    },
    {
      displayName: "End Page",
      name: "endPage",
      type: "number",
      typeOptions: { minValue: 1 },
      default: 1,
      description: "1-based inclusive end page.",
      required: true,
    },
    {
      displayName: "Output Binary Property",
      name: "outputPropertyName",
      type: "string",
      default: "sliced",
      description: "Name for the output binary property containing the new PDF.",
    },
    {
      displayName: "Carry Over Metadata",
      name: "carryMetadata",
      type: "boolean",
      default: true,
      description: "Copy basic document metadata into the sliced PDF.",
    },
  ],
};
'@
Set-Content -Path (Join-Path $PdfSlicePath "PdfSlice.description.ts") -Value $descTs -Encoding UTF8

# --- Write src/nodes/PdfSlice/PdfSlice.node.ts
$nodeTs = @'
import type { IExecuteFunctions, INodeExecutionData, INodeType, NodeExecutionWithMetadata } from "n8n-workflow";
import { PdfSliceDescription } from "./PdfSlice.description.js";
import { PDFDocument } from "pdf-lib";

export class PdfSlice implements INodeType {
  description = PdfSliceDescription;

  async execute(this: IExecuteFunctions): Promise<NodeExecutionWithMetadata[]> {
    const items = this.getInputData();
    const returnData: INodeExecutionData[] = [];

    for (let i = 0; i < items.length; i++) {
      const binaryPropertyName = this.getNodeParameter("binaryPropertyName", i, "data") as string;
      const startPage = this.getNodeParameter("startPage", i, 1) as number;
      const endPage = this.getNodeParameter("endPage", i, 1) as number;
      const outputPropertyName = this.getNodeParameter("outputPropertyName", i, "sliced") as string;
      const carryMetadata = this.getNodeParameter("carryMetadata", i, true) as boolean;

      const item = items[i];
      if (!item.binary || !item.binary[binaryPropertyName]) {
        throw new Error(`Binary property "${binaryPropertyName}" not found on input item ${i}.`);
      }

      const inputBin = item.binary[binaryPropertyName]!;
      const mime = inputBin.mimeType ?? "application/pdf";
      if (mime !== "application/pdf") {
        throw new Error(`Binary "${binaryPropertyName}" must be application/pdf (got ${mime}).`);
      }

      const base64 = inputBin.data;
      if (!base64) throw new Error("Binary has no base64 data.");

      const srcBytes = Buffer.from(base64, "base64");
      if (!Number.isInteger(startPage) || startPage < 1) throw new Error("startPage must be integer >= 1.");
      if (!Number.isInteger(endPage) || endPage < startPage) throw new Error("endPage must be integer >= startPage.");

      const srcDoc = await PDFDocument.load(srcBytes, { ignoreEncryption: false });
      const totalPages = srcDoc.getPageCount();
      if (startPage > totalPages) throw new Error(`startPage (${startPage}) > total pages (${totalPages}).`);
      if (endPage > totalPages) throw new Error(`endPage (${endPage}) > total pages (${totalPages}).`);

      const dstDoc = await PDFDocument.create();

      if (carryMetadata) {
        try {
          const title = srcDoc.getTitle();      if (title) dstDoc.setTitle(`${title} (pages ${startPage}-${endPage})`);
          const author = srcDoc.getAuthor();    if (author) dstDoc.setAuthor(author);
          const subject = srcDoc.getSubject();  if (subject) dstDoc.setSubject(subject);
          const keywords = srcDoc.getKeywords();if (keywords) dstDoc.setKeywords(keywords);
          const producer = srcDoc.getProducer();if (producer) dstDoc.setProducer(producer);
          const creator = srcDoc.getCreator();  if (creator) dstDoc.setCreator(creator);
        } catch {
          // ignore if not present
        }
      }

      const indices: number[] = [];
      for (let p = startPage - 1; p <= endPage - 1; p++) indices.push(p);
      const copied = await dstDoc.copyPages(srcDoc, indices);
      copied.forEach((page) => dstDoc.addPage(page));

      const newBytes = await dstDoc.save();
      const outB64 = Buffer.from(newBytes).toString("base64");

      const inName = inputBin.fileName ?? "input.pdf";
      const base = inName.toLowerCase().endsWith(".pdf") ? inName.slice(0, -4) : inName;
      const outName = `${base}_sliced_p${startPage}-${endPage}.pdf`;

      const newItem: INodeExecutionData = {
        json: {
          ...item.json,
          sliceInfo: {
            from: startPage,
            to: endPage,
            totalPages,
            sourceFile: inName,
            outputFile: outName,
          },
        },
        binary: {
          ...item.binary,
          [outputPropertyName]: {
            data: outB64,
            fileName: outName,
            mimeType: "application/pdf",
          },
        },
      };

      returnData.push(newItem);
    }

    return this.prepareOutputData(returnData);
  }
}
'@
Set-Content -Path (Join-Path $PdfSlicePath "PdfSlice.node.ts") -Value $nodeTs -Encoding UTF8

# --- Build the project
Push-Location $ProjectPath
try {
  if ($BuildInDocker) {
    Write-Host "Building with Docker (node:20)..."
    docker run --rm -v "$($ProjectPath):/work" -w /work node:20 bash -lc "npm ci || npm install && npm run build"
  } else {
    Write-Host "Building with local Node.js (npm)..."
    npm --version | Out-Null
    npm install
    npm run build
  }
} finally {
  Pop-Location
}

# --- Install into running container by copying dist/
$DistPath = Join-Path $ProjectPath "dist"
if (-not (Test-Path $DistPath)) {
  throw "Build failed: 'dist' folder not found at $DistPath"
}

# Destination inside container
$DestBase = "/home/node/.n8n/custom/n8n-nodes-pdf-slice"
$DestPath = "$DestBase/dist"

Write-Host "Creating destination path inside container: $DestPath"
docker exec $ContainerName bash -lc "mkdir -p $DestPath"

Write-Host "Copying dist into container..."
docker cp "$DistPath/." "$ContainerName:$DestPath"

Write-Host "Restarting container $ContainerName ..."
docker restart $ContainerName | Out-Null

Write-Host "`n✅ Installed 'PDF Slice (Local)' node."
Write-Host "Open n8n, search for 'PDF Slice (Local)'. Input a binary PDF and set the start/end pages."

if ($PrintComposeSnippet) {
  Write-Host "`n--- Docker Compose Snippet (bind mount & env) ---`n"
  $compose = @"
services:
  n8n:
    environment:
      - N8N_CUSTOM_EXTENSIONS=/home/node/.n8n/custom
    volumes:
      - n8n_data:/home/node/.n8n
      - ${PWD}/$NodeFolderName/dist:/home/node/.n8n/custom/n8n-nodes-pdf-slice/dist:ro

volumes:
  n8n_data:
"@
  Write-Host $compose
}
