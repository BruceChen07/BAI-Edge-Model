import { describe, expect, it, vi } from "vitest";

vi.mock("./uploadPreprocess", () => ({
  preprocessUploadFile: vi.fn(async (file: File) => {
    return new File([file], file.name.toLowerCase(), {
      type: file.type,
      lastModified: file.lastModified,
    });
  }),
}));

import type { ModelInfo } from "../services/api";
import { preprocessUploadFile } from "./uploadPreprocess";
import { prepareFileForUpload, validateUploadCandidate } from "./uploadPolicy";

describe("uploadPolicy", () => {
  it("rejects upload when the current model does not support files", () => {
    const file = new File(["demo"], "sample.png", { type: "image/png" });
    const model: ModelInfo = {
      name: "gemma4:4b",
      size: 1,
      modified_at: "now",
      digest: "abc",
      supports_file_upload: false,
    };

    const result = validateUploadCandidate({ file, model });

    expect(result.ok).toBe(false);
    expect(result.code).toBe("MODEL_UNSUPPORTED");
  });

  it("rejects files outside the whitelist", () => {
    const file = new File(["demo"], "sample.exe", {
      type: "application/octet-stream",
    });

    const result = validateUploadCandidate({ file });

    expect(result.ok).toBe(false);
    expect(result.code).toBe("INVALID_EXTENSION");
  });

  it("rejects image files larger than the configured limit", () => {
    const file = new File([new Uint8Array(11 * 1024 * 1024)], "sample.png", {
      type: "image/png",
    });

    const result = validateUploadCandidate({ file });

    expect(result.ok).toBe(false);
    expect(result.code).toBe("FILE_TOO_LARGE");
  });

  it("preprocesses valid files before upload", async () => {
    const file = new File(["demo"], "Screenshot.PNG", { type: "image/png" });
    const model: ModelInfo = {
      name: "llava:7b",
      size: 1,
      modified_at: "now",
      digest: "abc",
      supports_file_upload: true,
    };

    const result = await prepareFileForUpload({ file, model });

    expect(result.ok).toBe(true);
    if (!result.ok) {
      throw new Error("expected upload preparation to succeed");
    }
    expect(result.file.name).toBe("screenshot.png");
    expect(preprocessUploadFile).toHaveBeenCalledOnce();
  });
});
