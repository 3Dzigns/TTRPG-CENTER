import type { INodeTypeDescription } from "n8n-workflow";

export const PdfSliceDescription: INodeTypeDescription = {
  displayName: "PDF Slice (Local)",
  name: "pdfSliceLocal",
  group: ["transform"],
  version: 1,
  description: "Create a smaller PDF containing only pages Xâ€“Y (no external APIs).",
  defaults: { name: "PDF Slice (Local)" },
  inputs: ["main"],
  outputs: ["main"],
  icon: "fa:file-pdf",
  properties: [
    {
      displayName: "Binary Property",
      name: "binaryPropertyName",
      type: "string",
      default: "data",
      description: "Name of the incoming binary property that holds the source PDF."
    },
    {
      displayName: "Start Page",
      name: "startPage",
      type: "number",
      typeOptions: { minValue: 1 },
      default: 1,
      description: "1-based inclusive start page.",
      required: true
    },
    {
      displayName: "End Page",
      name: "endPage",
      type: "number",
      typeOptions: { minValue: 1 },
      default: 1,
      description: "1-based inclusive end page.",
      required: true
    },
    {
      displayName: "Output Binary Property",
      name: "outputPropertyName",
      type: "string",
      default: "sliced",
      description: "Name for the output binary property containing the new PDF."
    },
    {
      displayName: "Carry Over Metadata",
      name: "carryMetadata",
      type: "boolean",
      default: true,
      description: "Copy basic document metadata into the sliced PDF."
    }
  ]
};
