import pytest
from app.modules.support_rag.service import SupportRAGService

def test_chunk_text():
    s=SupportRAGService()
    texto=" ".join([f"p{i}" for i in range(1200)])
    chunks=s._chunk_text(texto,500)
    assert len(chunks)==3 and len(chunks[0].split())==500

def test_chunk_empty():
    assert SupportRAGService()._chunk_text("")==[]
