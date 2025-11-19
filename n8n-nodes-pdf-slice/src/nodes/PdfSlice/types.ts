export type RangeInput = {
  startPage: number; // 1-based inclusive
  endPage: number;   // 1-based inclusive
  binaryPropertyName?: string; // default: "data"
  outputPropertyName?: string; // default: "sliced"
  carryMetadata?: boolean;     // default: true
};
