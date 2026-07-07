from __future__ import annotations


def test_sector_empty_without_trade_date(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.sector.sector_snapshot.build_quality_overview",
        lambda: {"overall_status": "unknown", "top_issues": []},
    )
    from src.sector.sector_snapshot import build_sector_snapshot

    snap = build_sector_snapshot(None)
    assert snap["sectors"] == []
    assert snap["issue_summary"]


def test_rank_strong_sectors_simple_order() -> None:
    from src.sector.sector_snapshot import SectorRow, rank_strong_sectors

    rows = [
        SectorRow("A", "industry", 0.1, 0, 0.1, 1.0, 1, 0, None),
        SectorRow("B", "industry", 0.2, 0, 0.2, 1.0, 1, 0, None),
    ]
    ranked = rank_strong_sectors(rows)
    assert [r.sector_name for r in ranked] == ["B", "A"]
    assert [r.rank for r in ranked] == [1, 2]
