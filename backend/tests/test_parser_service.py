from __future__ import annotations

from pathlib import Path

from docx import Document

from app.services.parser_service import ParserService


def _build_docx_bytes() -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    document = Document()
    document.add_paragraph("This content came from a converted DOC file.")
    document.save(buffer)
    return buffer.getvalue()


def test_parse_doc_uses_conversion(monkeypatch) -> None:
    service = ParserService()
    monkeypatch.setattr(service, "_convert_doc_to_docx", lambda content: _build_docx_bytes())
    extracted_text, status = service.extract_text("legacy.doc", b"legacy-content", enable_ocr=True)
    assert status == "done"
    assert "converted DOC file" in extracted_text


def test_parse_pdf_prefers_mineru(monkeypatch, tmp_path: Path) -> None:
    service = ParserService()
    file_path = tmp_path / "demo.pdf"
    file_path.write_bytes(b"%PDF-1.4 demo")

    monkeypatch.setattr(service.mineru_service, "is_available", lambda: True)
    monkeypatch.setattr(service.mineru_service, "supports_file", lambda path: True)
    monkeypatch.setattr(
        service.mineru_service,
        "parse_file",
        lambda path, enable_ocr=True: "# MinerU Output\n\nStructured markdown from mineru.",
    )

    extracted_text, status = service.extract_text(
        "demo.pdf",
        b"%PDF-1.4 demo",
        enable_ocr=True,
        file_path=file_path,
    )
    assert status == "done"
    assert "Structured markdown from mineru." in extracted_text


def test_parse_scanned_pdf_uses_ocr(monkeypatch) -> None:
    fitz = __import__("fitz")
    service = ParserService()
    monkeypatch.setattr(service.mineru_service, "is_available", lambda: False)
    monkeypatch.setattr(service, "_ocr_image_bytes", lambda image_bytes: "OCR text from scanned page")

    document = fitz.open()
    page = document.new_page()
    pdf_bytes = document.tobytes()

    extracted_text, status = service.extract_text("scan.pdf", pdf_bytes, enable_ocr=True)
    assert status == "done"
    assert "OCR text from scanned page" in extracted_text
