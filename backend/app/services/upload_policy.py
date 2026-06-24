from __future__ import annotations

from pathlib import Path

MAX_UPLOAD_BYTES_IMAGE = 10 * 1024 * 1024
MAX_UPLOAD_BYTES_DOCUMENT = 25 * 1024 * 1024
MAX_UPLOAD_BYTES_HARD = 25 * 1024 * 1024

DOCUMENT_UPLOAD_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".txt",
    ".md",
    ".xlsx",
    ".pptx",
}
IMAGE_UPLOAD_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}
SUPPORTED_UPLOAD_EXTENSIONS = DOCUMENT_UPLOAD_EXTENSIONS | IMAGE_UPLOAD_EXTENSIONS
SUPPORTED_UPLOAD_TYPES = ["document", "image"]

_IMAGE_MIME_PREFIXES = ("image/",)
_DOCUMENT_MIME_ALLOWLIST = {
    "application/msword",
    "application/octet-stream",
    "application/pdf",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/markdown",
    "text/plain",
}
_MULTIMODAL_KEYWORDS = (
    "vision",
    "vl",
    "llava",
    "omni",
    "internvl",
    "minicpm-v",
    "minicpmv",
    "qvq",
)


class UploadValidationError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        error_code: str,
        repair_action: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.repair_action = repair_action


def normalize_upload_extension(file_name: str | None) -> str:
    return Path(file_name or "").suffix.lower()


def is_supported_upload_extension(file_name: str | None) -> bool:
    return normalize_upload_extension(file_name) in SUPPORTED_UPLOAD_EXTENSIONS


def is_image_upload(file_name: str | None) -> bool:
    return normalize_upload_extension(file_name) in IMAGE_UPLOAD_EXTENSIONS


def get_upload_size_limit(file_name: str | None) -> int:
    if is_image_upload(file_name):
        return MAX_UPLOAD_BYTES_IMAGE
    return MAX_UPLOAD_BYTES_DOCUMENT


def validate_file_upload_policy(
    file_name: str | None,
    content_type: str | None,
    size_bytes: int,
) -> None:
    extension = normalize_upload_extension(file_name)
    if extension not in SUPPORTED_UPLOAD_EXTENSIONS:
        raise UploadValidationError(
            "不支持该文件类型：仅支持 PDF、DOC、DOCX、TXT、MD、XLSX、PPTX、PNG、JPG、JPEG、WEBP。",
            error_code="UPLOAD_UNSUPPORTED_EXTENSION",
            repair_action="change_file",
        )
    if size_bytes <= 0:
        raise UploadValidationError(
            "文件内容为空，请重新选择有效文件后重试。",
            error_code="UPLOAD_EMPTY_FILE",
            repair_action="change_file",
        )
    limit = get_upload_size_limit(file_name)
    if size_bytes > limit or size_bytes > MAX_UPLOAD_BYTES_HARD:
        raise UploadValidationError(
            f"文件超过大小限制：当前文件 {(size_bytes / 1024 / 1024):.1f} MB，允许的最大大小为 {(limit / 1024 / 1024):.0f} MB。请压缩后重试。",
            error_code="UPLOAD_FILE_TOO_LARGE",
            repair_action="compress_file",
        )
    if not _is_content_type_allowed(extension, content_type):
        raise UploadValidationError(
            "文件类型与内容标识不匹配，请确认文件未损坏并重新上传。",
            error_code="UPLOAD_UNSUPPORTED_EXTENSION",
            repair_action="change_file",
        )


def infer_model_upload_capability(model_name: str, use_case: str | None) -> dict:
    normalized_name = model_name.lower().strip()
    normalized_use_case = (use_case or "").lower().strip()
    if normalized_use_case == "multimodal":
        supports_multimodal = True
        capability_source = "use_case"
    elif any(keyword in normalized_name for keyword in _MULTIMODAL_KEYWORDS):
        supports_multimodal = True
        capability_source = "name_inference"
    else:
        supports_multimodal = False
        capability_source = "fallback"
    return {
        "supports_multimodal": supports_multimodal,
        "supports_file_upload": supports_multimodal,
        "supported_upload_types": SUPPORTED_UPLOAD_TYPES if supports_multimodal else [],
        "capability_source": capability_source,
    }


def validate_model_upload_capability(model_name: str, use_case: str | None) -> None:
    capability = infer_model_upload_capability(model_name, use_case)
    if capability["supports_file_upload"]:
        return
    raise UploadValidationError(
        "当前模型不支持文件上传，请切换到支持文件上传的多模态模型后重试。",
        error_code="UPLOAD_MODEL_NOT_SUPPORTED",
        repair_action="switch_model",
    )


def _is_content_type_allowed(extension: str, content_type: str | None) -> bool:
    normalized_type = (content_type or "").lower().strip()
    if not normalized_type or normalized_type == "application/octet-stream":
        return True
    if extension in IMAGE_UPLOAD_EXTENSIONS:
        return normalized_type.startswith(_IMAGE_MIME_PREFIXES)
    return normalized_type in _DOCUMENT_MIME_ALLOWLIST
