const MAX_IMAGE_LONG_EDGE = 2048;
const IMAGE_COMPRESSION_QUALITY = 0.82;

export async function preprocessUploadFile(file: File): Promise<File> {
  const normalizedName = normalizeFileName(file.name);
  if (!isImageFile(file)) {
    return rebuildFile(file, file, normalizedName, file.type || inferMimeFromName(normalizedName));
  }
  if (typeof window === "undefined" || typeof document === "undefined") {
    return rebuildFile(file, file, normalizedName, file.type || inferMimeFromName(normalizedName));
  }
  try {
    const image = await loadImageElement(file);
    const { width, height } = resizeToFit(image.width, image.height, MAX_IMAGE_LONG_EDGE);
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) {
      return rebuildFile(file, file, normalizedName, file.type || inferMimeFromName(normalizedName));
    }
    context.drawImage(image, 0, 0, width, height);
    const targetMime = inferImageOutputMime(file.type, normalizedName);
    const blob = await canvasToBlob(canvas, targetMime, IMAGE_COMPRESSION_QUALITY);
    if (!blob || blob.size >= file.size) {
      return rebuildFile(file, file, normalizedName, file.type || inferMimeFromName(normalizedName));
    }
    return new File([blob], normalizedName, {
      type: targetMime,
      lastModified: file.lastModified,
    });
  } catch {
    return rebuildFile(file, file, normalizedName, file.type || inferMimeFromName(normalizedName));
  }
}

function normalizeFileName(fileName: string): string {
  const dotIndex = fileName.lastIndexOf(".");
  if (dotIndex < 0) {
    return fileName;
  }
  return `${fileName.slice(0, dotIndex)}${fileName.slice(dotIndex).toLowerCase()}`;
}

function isImageFile(file: File): boolean {
  return file.type.startsWith("image/") || /\.(png|jpe?g|webp)$/i.test(file.name);
}

function inferMimeFromName(fileName: string): string {
  if (fileName.endsWith(".png")) {
    return "image/png";
  }
  if (fileName.endsWith(".webp")) {
    return "image/webp";
  }
  if (fileName.endsWith(".jpg") || fileName.endsWith(".jpeg")) {
    return "image/jpeg";
  }
  return "application/octet-stream";
}

function inferImageOutputMime(sourceMime: string, fileName: string): string {
  if (sourceMime === "image/png" && fileName.endsWith(".png")) {
    return "image/png";
  }
  if (sourceMime === "image/webp" || fileName.endsWith(".webp")) {
    return "image/webp";
  }
  return "image/jpeg";
}

function resizeToFit(
  width: number,
  height: number,
  maxLongEdge: number,
): { width: number; height: number } {
  const longEdge = Math.max(width, height);
  if (longEdge <= maxLongEdge) {
    return { width, height };
  }
  const scale = maxLongEdge / longEdge;
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  };
}

function canvasToBlob(
  canvas: HTMLCanvasElement,
  mimeType: string,
  quality: number,
): Promise<Blob | null> {
  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), mimeType, quality);
  });
}

function loadImageElement(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    const objectUrl = URL.createObjectURL(file);
    image.onload = () => {
      URL.revokeObjectURL(objectUrl);
      resolve(image);
    };
    image.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      reject(new Error("image decode failed"));
    };
    image.src = objectUrl;
  });
}

function rebuildFile(
  originalFile: File,
  source: Blob,
  fileName: string,
  mimeType: string,
): File {
  if (fileName === originalFile.name && mimeType === originalFile.type && source === originalFile) {
    return originalFile;
  }
  return new File([source], fileName, {
    type: mimeType,
    lastModified: originalFile.lastModified,
  });
}
