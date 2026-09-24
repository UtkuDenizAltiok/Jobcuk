"""tools/made_up_search.py never touches someone's real documents (no search is run here)."""

import importlib.util
import io
from pathlib import Path

import docx
import pytest

from jobcu import documents, paths

TOOL = Path(__file__).resolve().parent.parent / "tools" / "made_up_search.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("made_up_search", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def real_cv() -> bytes:
    document = docx.Document()
    document.add_paragraph("A real person's CV with enough text to be read by Jobcu. " * 3)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_it_refuses_a_folder_with_someones_documents():
    documents.save_upload("cv", "cv.docx", real_cv())
    with pytest.raises(SystemExit):
        load_tool().prepare_folder()
    assert "real person" in documents.read_text("cv")


def test_it_fills_an_empty_folder_with_the_made_up_person_and_can_do_so_again():
    tool = load_tool()
    tool.prepare_folder()
    assert "power electronics" in documents.read_text("cv")
    assert (paths.data_dir() / tool.MARKER).exists()
    tool.prepare_folder()  # its own folder: allowed again
