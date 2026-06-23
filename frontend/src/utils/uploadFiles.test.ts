import { extractRcFilesFromUploadList } from "./uploadFiles";

describe("extractRcFilesFromUploadList", () => {
  it("extracts raw RcFile objects stored directly in fileList", () => {
    const rawFile = {
      uid: "raw-1",
      name: "raw.pdf",
      size: 128,
      type: "application/pdf",
    };

    const files = extractRcFilesFromUploadList([rawFile as never]);

    expect(files).toHaveLength(1);
    expect(files[0]?.name).toBe("raw.pdf");
  });

  it("extracts originFileObj when fileList contains UploadFile wrappers", () => {
    const originFileObj = {
      uid: "wrapped-1",
      name: "wrapped.pdf",
      size: 256,
      type: "application/pdf",
    };

    const files = extractRcFilesFromUploadList([
      {
        uid: "wrapper",
        name: "wrapped.pdf",
        originFileObj: originFileObj as never,
      },
    ]);

    expect(files).toHaveLength(1);
    expect(files[0]?.name).toBe("wrapped.pdf");
  });

  it("filters out invalid items without a file name", () => {
    const files = extractRcFilesFromUploadList([
      { uid: "broken", name: "" } as never,
    ]);

    expect(files).toHaveLength(0);
  });
});
