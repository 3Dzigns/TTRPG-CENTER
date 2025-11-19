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
          const keywords = (srcDoc as any).getKeywords?.();
          if (keywords) {
            const arr = Array.isArray(keywords) ? keywords : [String(keywords)];
            dstDoc.setKeywords(arr);
          }
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
            outputFile: outName
          }
        },
        binary: {
          ...item.binary,
          [outputPropertyName]: {
            data: outB64,
            fileName: outName,
            mimeType: "application/pdf"
          }
        }
      };

      returnData.push(newItem);
    }

    return this.prepareOutputData(returnData);
  }
}
