"""Tests for the SBV corpus crawler's offline helpers (no network)."""

from scripts.crawl_sbv_corpus import classify_slug, parse_repeal_note


def test_parse_repeal_note_full_replacement():
    note = "Bị thay thế bởi  Nghị định 01/2014/NĐ-CP Về việc nhà đầu tư nước ngoài mua cổ phần"
    assert parse_repeal_note(note) == [
        {
            "source_doc_id": "01/2014/ND-CP",
            "rel_type": "SUPERSEDES",
            "scope": "MoJ applicationNote: bị thay thế",
        }
    ]


def test_parse_repeal_note_legacy_number_and_multiple_sources():
    note = "Bị bãi bỏ bởi Quyết định 22/QĐ-NH1 và Thông tư 03/2013/TT-NHNN"
    assert [r["source_doc_id"] for r in parse_repeal_note(note)] == [
        "22/QD-NH1",
        "03/2013/TT-NHNN",
    ]


def test_parse_repeal_note_ignores_partial_and_empty():
    assert parse_repeal_note("Bị bãi bỏ một phần bởi Thông tư 13/2023/TT-NHNN") == []
    assert parse_repeal_note(None) == []
    assert parse_repeal_note("") == []


def test_classify_slug():
    assert (
        classify_slug("thong-tu-so-12-2022-tt-nhnn-quy-dinh-ve-vay-no-nuoc-ngoai") == "sbv_number"
    )
    assert classify_slug("quyet-dinh-so-22-qd-nh1-ban-hanh-the-le") == "sbv_legacy_number"
    assert classify_slug("nghi-dinh-so-52-2024-nd-cp-thanh-toan-khong-dung-tien-mat") == (
        "banking_keyword"
    )
    assert classify_slug("van-ban-hop-nhat-so-116-2026-vbhn-tt-nhnn-quy-dinh") is None
    assert classify_slug("chi-thi-so-06-ct-nhnn-ve-giai-phap") is None
    assert classify_slug("nghi-dinh-so-15-2020-nd-cp-xu-phat-buu-chinh") is None
