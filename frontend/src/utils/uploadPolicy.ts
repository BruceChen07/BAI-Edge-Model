import type { ModelInfo } from "../services/api";
import { preprocessUploadFile } from "./uploadPreprocess";

export const DOCUMENT_UPLOAD_EXTENSIONS = [
  ".pdf",
  ".doc",
  ".docx",
  ".txt",
  ".md",
  ".xlsx",
  ".pptx",
] as const;
export const IMAGE_UPLOAD_EXTENSIONS = [
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
] as const;
export const SUPPORTED_UPLOAD_EXTENSIONS = [
  ...DOCUMENT_UPLOAD_EXTENSIONS,
  ...IMAGE_UPLOAD_EXTENSIONS,
] as const;

export const MAX_UPLOAD_BYTES_IMAGE = 10 * 1024 * 1024;
export const MAX_UPLOAD_BYTES_DOCUMENT = 25 * 1024 * 1024;

export type UploadValidationCode =
  | "MODEL_UNSUPPORTED"
  | "INVALID_EXTENSION"
  | "FILE_TOO_LARGE";

export type UploadValidationResult = {
  ok: boolean;
  code?: UploadValidationCode;
  message?: string;
};

export async function prepareFileForUpload(input: {
  file: File;
  model?: ModelInfo;
}): Promise<
  | { ok: true; file: File }
  | { ok: false; code: UploadValidationCode; message: string }
> {
  const validation = validateUploadCandidate(input);
  if (!validation.ok) {
    return {
      ok: false,
      code: validation.code!,
      message: validation.message!,
    };
  }
  return {
    ok: true,
    file: await preprocessUploadFile(input.file),
  };
}

export function validateUploadCandidate(input: {
  file: File;
  model?: ModelInfo;
}): UploadValidationResult {
  if (
    input.model &&
    input.model.supports_file_upload === false
  ) {
    return {
      ok: false,
      code: "MODEL_UNSUPPORTED",
      message:
        "当前模型不支持文件上传，请切换到支持文件上传的多模态模型后重试。",
    };
  }
  const extension = getFileExtension(input.file.name);
  if (!SUPPORTED_UPLOAD_EXTENSIONS.includes(extension as (typeof SUPPORTED_UPLOAD_EXTENSIONS)[number])) {
    return {
      ok: false,
      code: "INVALID_EXTENSION",
      message:
        "不支持该文件类型：仅支持 PDF、DOC、DOCX、TXT、MD、XLSX、PPTX、PNG、JPG、JPEG、WEBP。",
    };
  }
  const limit = IMAGE_UPLOAD_EXTENSIONS.includes(
    extension as (typeof IMAGE_UPLOAD_EXTENSIONS)[number],
  )
    ? MAX_UPLOAD_BYTES_IMAGE
    : MAX_UPLOAD_BYTES_DOCUMENT;
  if (input.file.size > limit) {
    return {
      ok: false,
      code: "FILE_TOO_LARGE",
      message: `文件超过大小限制：当前文件 ${(input.file.size / 1024 / 1024).toFixed(1)} MB，允许的最大大小为 ${(limit / 1024 / 1024).toFixed(0)} MB。请压缩后重试。`,
    };
  }
  return { ok: true };
}

export function getUploadAcceptAttribute(): string {
  return SUPPORTED_UPLOAD_EXTENSIONS.join(",");
}

function getFileExtension(fileName: string): string {
  const lastDot = fileName.lastIndexOf(".");
  if (lastDot < 0) {
    return "";
  }
  return fileName.slice(lastDot).toLowerCase();
}
