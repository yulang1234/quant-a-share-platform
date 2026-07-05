"""V1.4.3 Coverage and gap repositories."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.schema_meta import DataCoverageReport, DataGapDetail
from src.repositories.meta_db import get_session


class CoverageReportRepository:
    def __init__(self, session: Session | None = None):
        self._s = session or get_session()

    def upsert(self, **kwargs) -> DataCoverageReport:
        existing = self._s.query(DataCoverageReport).filter_by(
            universe_id=kwargs.get("universe_id"),
            symbol=kwargs.get("symbol"),
            exchange=kwargs.get("exchange"),
            data_type=kwargs.get("data_type", "daily_bar"),
            adj_type=kwargs.get("adj_type"),
            start_date=kwargs.get("start_date"),
            end_date=kwargs.get("end_date"),
        ).first()
        if existing:
            for k, v in kwargs.items():
                if hasattr(existing, k) and v is not None:
                    setattr(existing, k, v)
            self._s.commit()
            return existing
        r = DataCoverageReport(**kwargs)
        self._s.add(r); self._s.commit()
        return r

    def list_all(self, limit: int = 100, adj_type: str | None = None, status: str | None = None) -> list[DataCoverageReport]:
        q = self._s.query(DataCoverageReport)
        if adj_type and adj_type != "all": q = q.filter_by(adj_type=adj_type)
        if status: q = q.filter_by(status=status)
        return q.limit(limit).all()

    def count_by_status(self) -> dict[str, int]:
        rows = self._s.query(DataCoverageReport.status, func.count()).group_by(DataCoverageReport.status).all()
        return {r[0]: r[1] for r in rows}

    def count_by_adj_type(self) -> dict[str, int]:
        rows = self._s.query(DataCoverageReport.adj_type, func.count()).group_by(DataCoverageReport.adj_type).all()
        return {r[0]: r[1] for r in rows}

    def avg_coverage_rate(self) -> float | None:
        result = self._s.query(func.avg(DataCoverageReport.coverage_rate)).filter(
            DataCoverageReport.coverage_rate.isnot(None)).scalar()
        return float(result) if result else None

    def avg_missing_days(self) -> float:
        result = self._s.query(func.avg(DataCoverageReport.missing_trade_days)).scalar()
        return float(result) if result else 0.0

    def top_missing(self, limit: int = 20) -> list[DataCoverageReport]:
        return self._s.query(DataCoverageReport).order_by(
            DataCoverageReport.missing_trade_days.desc()).limit(limit).all()


class GapDetailRepository:
    def __init__(self, session: Session | None = None):
        self._s = session or get_session()

    def clear_report_gaps(self, report_id: int) -> int:
        return self._s.query(DataGapDetail).filter_by(report_id=report_id).delete()

    def insert_batch(self, gaps: list[dict]) -> int:
        count = 0
        for g in gaps:
            self._s.add(DataGapDetail(**g))
            count += 1
        self._s.commit()
        return count

    def list_by_report(self, report_id: int) -> list[DataGapDetail]:
        return self._s.query(DataGapDetail).filter_by(report_id=report_id).all()

    def list_pending(self, limit: int = 100) -> list[DataGapDetail]:
        return self._s.query(DataGapDetail).filter_by(repair_status="pending").limit(limit).all()

    def update_repair_status(self, gap_id: int, status: str, task_id: int | None = None) -> None:
        g = self._s.query(DataGapDetail).filter_by(gap_id=gap_id).first()
        if g:
            g.repair_status = status
            if task_id: g.related_task_id = task_id
            self._s.commit()

    def list_gaps(self, limit: int = 100, adj_type: str | None = None,
                  severity: str | None = None, repair_status: str | None = None,
                  gap_type: str | None = None) -> list[DataGapDetail]:
        q = self._s.query(DataGapDetail)
        if adj_type and adj_type != "all": q = q.filter_by(adj_type=adj_type)
        if severity: q = q.filter_by(severity=severity)
        if repair_status: q = q.filter_by(repair_status=repair_status)
        if gap_type: q = q.filter_by(gap_type=gap_type)
        return q.limit(limit).all()

    def count_by_severity(self) -> dict[str, int]:
        rows = self._s.query(DataGapDetail.severity, func.count()).group_by(DataGapDetail.severity).all()
        return {r[0]: r[1] for r in rows}

    def count_by_gap_type(self) -> dict[str, int]:
        rows = self._s.query(DataGapDetail.gap_type, func.count()).group_by(DataGapDetail.gap_type).all()
        return {r[0]: r[1] for r in rows}

    def count_by_repair_status(self) -> dict[str, int]:
        rows = self._s.query(DataGapDetail.repair_status, func.count()).group_by(DataGapDetail.repair_status).all()
        return {r[0]: r[1] for r in rows}

    def total_missing_days(self) -> int:
        result = self._s.query(func.sum(DataGapDetail.missing_days)).scalar()
        return int(result) if result else 0

    def total_count(self) -> int:
        return self._s.query(DataGapDetail).count()
