import type { RcFile, UploadFile } from "antd/es/upload/interface";

export function extractRcFilesFromUploadList(
  fileList: UploadFile[],
): RcFile[] {
  return fileList.flatMap((file) => {
    const rawFile = file.originFileObj ?? (file as unknown as RcFile);
    if (!rawFile || typeof rawFile.name !== "string" || !rawFile.name) {
      return [];
    }
    return [rawFile];
  });
}
