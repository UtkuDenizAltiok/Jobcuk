import os

import pytest
from conftest import FAKE_CV_LINES, make_docx, make_pdf

from jobcu import documents
from jobcu.documents import DocumentError, extract_text_from_bytes, tidy


def test_pdf_text_is_read():
    text = extract_text_from_bytes(make_pdf(FAKE_CV_LINES), ".pdf")
    assert "Hardware engineer with five years" in text
    assert "French (basic)" in text


def test_docx_text_is_read_including_tables():
    rows = [["2020 – 2024", "Embedded Engineer, Example GmbH"]]
    content = make_docx(FAKE_CV_LINES, table_rows=rows)
    text = extract_text_from_bytes(content, ".docx")
    assert "PCB layout" in text
    assert "Embedded Engineer, Example GmbH" in text


def test_plain_text_in_older_windows_encoding_is_read():
    content = ("Motivation letter. " * 10 + "Café engineer").encode("cp1252")
    assert "Café engineer" in extract_text_from_bytes(content, ".txt")


def test_empty_or_scanned_documents_are_refused_with_advice():
    with pytest.raises(DocumentError, match="scanned picture"):
        extract_text_from_bytes(make_pdf([" "]), ".pdf")


def test_not_really_a_pdf_is_refused():
    with pytest.raises(DocumentError, match="doesn't look like a real PDF"):
        extract_text_from_bytes(b"hello" * 100, ".pdf")


def test_very_long_documents_are_refused_not_cut():
    content = ("word " * 20_000).encode()
    with pytest.raises(DocumentError, match="much longer"):
        extract_text_from_bytes(content, ".txt")


def test_upload_is_saved_privately_and_replaces_the_old_file():
    documents.save_upload("cv", "old cv.docx", make_docx(FAKE_CV_LINES))
    info = documents.save_upload("cv", "My CV.pdf", make_pdf(FAKE_CV_LINES))
    assert info.original_name == "My CV.pdf"
    assert sorted(p.name for p in documents.documents_dir().glob("cv.*")) == ["cv.pdf"]
    assert documents.get_info("cv").extension == ".pdf"
    assert "embedded systems" in documents.read_text("cv")
    if os.name == "posix":
        assert documents.stored_path("cv", ".pdf").stat().st_mode & 0o777 == 0o600


def test_wrong_file_types_are_refused():
    with pytest.raises(DocumentError, match="PDF or DOCX"):
        documents.save_upload("cv", "cv.txt", b"text " * 50)
    with pytest.raises(DocumentError, match="PDF or DOCX or TXT"):
        documents.save_upload("cover_letter", "letter.pages", b"x" * 500)


def test_missing_document_gives_plain_message():
    with pytest.raises(DocumentError, match="upload your CV first"):
        documents.read_text("cv")


def test_delete_removes_the_file():
    documents.save_upload("cover_letter", "letter.txt", b"I want to build hardware. " * 10)
    documents.delete("cover_letter")
    assert documents.get_info("cover_letter") is None
    assert not list(documents.documents_dir().glob("cover_letter.*"))


def test_tidy_removes_extra_spacing():
    assert tidy("a  \t b\r\n\n\n\nc d ") == "a b\n\nc d"
