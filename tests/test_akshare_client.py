"""
Tests for AkShare client -- mock the akshare API to verify column mapping,
code normalisation, and error handling.

These tests do NOT require akshare to be installed; the API is replaced
via ``AkShareClient._get_akshare_module``.
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest

from src.data_source.akshare_client import AkShareClient


# ── Fixtures ────────────────────────────────────────────────────────────

class FakeAkShare:
    """Replacement for the real ``akshare`` module used in tests."""

    @staticmethod
    def stock_zh_a_hist(symbol, period, start_date, end_date, adjust):
        return _DEFAULT_MOCK_DATA

    @staticmethod
    def stock_zh_a_daily(symbol, start_date, end_date, adjust):
        raise NotImplementedError("Not used in these tests")

    @staticmethod
    def stock_individual_info_em(symbol):
        """Mock: return sector info. Override per-test via monkeypatch."""
        return pd.DataFrame({
            "item": ["股票代码", "股票简称", "行业", "上市时间"],
            "value": ["000001", "平安银行", "银行", "19910403"],
        })


_DEFAULT_MOCK_DATA = pd.DataFrame({
    "日期": ["2024-01-02", "2024-01-03"],
    "开盘": [10.0, 10.5],
    "收盘": [10.2, 10.8],
    "最高": [10.3, 11.0],
    "最低": [9.9, 10.4],
    "成交量": [1000000, 1500000],
    "成交额": [1e7, 1.6e7],
    "振幅": [0.04, 0.06],
    "涨跌幅": [0.02, 0.0588],
    "涨跌额": [0.2, 0.6],
    "换手率": [0.005, 0.008],
    "前收盘": [10.0, 10.2],
})


@pytest.fixture
def _mock_akshare(monkeypatch) -> None:
    """Replace ``_get_akshare_module`` so tests never need real akshare."""
    monkeypatch.setattr(
        AkShareClient,
        "_get_akshare_module",
        staticmethod(lambda: FakeAkShare),
    )


@pytest.fixture
def client() -> AkShareClient:
    return AkShareClient()


@pytest.fixture
def mock_raw_data() -> pd.DataFrame:
    return pd.DataFrame({
        "日期": ["2024-01-02", "2024-01-03"],
        "开盘": [10.0, 10.5],
        "收盘": [10.2, 10.8],
        "最高": [10.3, 11.0],
        "最低": [9.9, 10.4],
        "成交量": [1000000, 1500000],
        "成交额": [1e7, 1.6e7],
        "振幅": [0.04, 0.06],
        "涨跌幅": [0.02, 0.0588],
        "涨跌额": [0.2, 0.6],
        "换手率": [0.005, 0.008],
        "前收盘": [10.0, 10.2],
    })


@pytest.fixture
def mock_qfq_data() -> pd.DataFrame:
    return pd.DataFrame({
        "日期": ["2024-01-02", "2024-01-03"],
        "开盘": [8.5, 8.9],
        "收盘": [8.7, 9.2],
        "最高": [8.8, 9.3],
        "最低": [8.4, 8.8],
        "成交量": [1000000, 1500000],
        "成交额": [8.5e6, 1.35e7],
        "振幅": [0.04, 0.06],
        "涨跌幅": [0.02, 0.0575],
        "涨跌额": [0.17, 0.5],
        "换手率": [0.005, 0.008],
    })


# =====================================================================
#  Code normalisation
# =====================================================================

class TestNormalizeCode:
    def test_int_input(self) -> None:
        assert AkShareClient.normalize_code(1) == "000001"
        assert AkShareClient.normalize_code(600519) == "600519"

    def test_str_input(self) -> None:
        assert AkShareClient.normalize_code("000001") == "000001"
        assert AkShareClient.normalize_code("600519") == "600519"

    def test_zero_padded_str(self) -> None:
        assert AkShareClient.normalize_code("1") == "000001"
        assert AkShareClient.normalize_code("00001") == "000001"

    def test_invalid_code(self) -> None:
        with pytest.raises(ValueError, match="6 digits"):
            AkShareClient.normalize_code("abcdef")
        with pytest.raises(ValueError, match="6 digits"):
            AkShareClient.normalize_code("1234567")
        with pytest.raises(ValueError, match="6 digits"):
            AkShareClient.normalize_code("")


# =====================================================================
#  _format_date
# =====================================================================

class TestFormatDate:
    def test_yyyymmdd_str(self) -> None:
        assert AkShareClient._format_date("20260703") == "20260703"

    def test_with_hyphens(self) -> None:
        assert AkShareClient._format_date("2026-07-03") == "20260703"

    def test_datetime_object(self) -> None:
        assert AkShareClient._format_date(datetime(2026, 7, 3)) == "20260703"

    def test_date_object(self) -> None:
        assert AkShareClient._format_date(date(2026, 7, 3)) == "20260703"

    def test_pandas_timestamp(self) -> None:
        ts = pd.Timestamp("2026-07-03")
        assert AkShareClient._format_date(ts) == "20260703"

    def test_invalid_str(self) -> None:
        with pytest.raises(ValueError, match="Invalid date"):
            AkShareClient._format_date("not-a-date")
        with pytest.raises(ValueError, match="Invalid date"):
            AkShareClient._format_date("2026-07")

    def test_invalid_type(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse"):
            AkShareClient._format_date(12345)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="Cannot parse"):
            AkShareClient._format_date(None)  # type: ignore[arg-type]


# =====================================================================
#  _get_akshare_module
# =====================================================================

class TestGetAkshareModule:
    def test_raises_import_error_when_not_available(self, monkeypatch):
        """If akshare import fails, _get_akshare_module must raise ImportError."""
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "akshare":
                raise ImportError("No module named 'akshare'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        with pytest.raises(ImportError, match="pip install akshare"):
            AkShareClient._get_akshare_module()


# =====================================================================
#  Data fetch with mocked akshare
# =====================================================================

class TestFetchWithMock:
    """Test fetch methods by monkey-patching the akshare call."""

    @pytest.fixture(autouse=True)
    def _auto_mock(self, _mock_akshare) -> None:
        """Apply the akshare mock fixture to all tests in this class."""
        pass

    def test_fetch_raw_column_mapping(self, client, monkeypatch, mock_raw_data):
        """Verify that Chinese column names are correctly mapped to English."""
        def mock_hist(symbol, period, start_date, end_date, adjust):
            return mock_raw_data

        # Patch at the module function level (overrides the fixture's FakeAkShare)
        monkeypatch.setattr(FakeAkShare, "stock_zh_a_hist", staticmethod(mock_hist))
        df = client.fetch_stock_daily_raw("000001", "20240101", "20240131")

        assert not df.empty
        assert "trade_date" in df.columns
        assert "stock_code" in df.columns
        assert "open" in df.columns
        assert "close" in df.columns
        assert "high" in df.columns
        assert "low" in df.columns
        assert "volume" in df.columns
        assert "amount" in df.columns
        assert "amplitude" in df.columns
        assert "pct_change" in df.columns
        assert "change_amount" in df.columns
        assert "turnover_rate" in df.columns
        assert "pre_close" in df.columns

        # Verify stock_code is 6-char string
        assert df["stock_code"].iloc[0] == "000001"

        # Verify trade_date is date type
        assert df["trade_date"].iloc[0] == date(2024, 1, 2)

        # Verify numeric columns
        assert pd.api.types.is_numeric_dtype(df["open"])

    def test_fetch_qfq_column_mapping(self, client, monkeypatch, mock_qfq_data):
        """Verify QFQ column mapping."""
        def mock_hist(symbol, period, start_date, end_date, adjust):
            return mock_qfq_data
        monkeypatch.setattr(FakeAkShare, "stock_zh_a_hist", staticmethod(mock_hist))
        df = client.fetch_stock_daily_qfq("000001", "20240101", "20240131")

        assert not df.empty
        assert "trade_date" in df.columns
        assert "stock_code" in df.columns
        assert "close" in df.columns
        assert df["stock_code"].iloc[0] == "000001"

    def test_adj_raw(self, client, monkeypatch, mock_raw_data):
        """Test fetch_stock_daily with adj='raw'."""
        def mock_hist(symbol, period, start_date, end_date, adjust):
            return mock_raw_data
        monkeypatch.setattr(FakeAkShare, "stock_zh_a_hist", staticmethod(mock_hist))
        df = client.fetch_stock_daily("000001", "20240101", "20240131", adj="raw")
        assert "pre_close" in df.columns

    def test_adj_qfq(self, client, monkeypatch, mock_qfq_data):
        """Test fetch_stock_daily with adj='qfq'."""
        def mock_hist(symbol, period, start_date, end_date, adjust):
            return mock_qfq_data
        monkeypatch.setattr(FakeAkShare, "stock_zh_a_hist", staticmethod(mock_hist))
        df = client.fetch_stock_daily("000001", "20240101", "20240131", adj="qfq")
        assert not df.empty

    def test_invalid_adj(self, client):
        """Test that an invalid adj value raises ValueError."""
        with pytest.raises(ValueError, match="adj must be"):
            client.fetch_stock_daily("000001", "20240101", "20240131", adj="invalid")

    def test_empty_response(self, client, monkeypatch):
        """Test that an empty API response returns an empty DataFrame (no crash)."""
        def mock_hist(symbol, period, start_date, end_date, adjust):
            return pd.DataFrame()
        monkeypatch.setattr(FakeAkShare, "stock_zh_a_hist", staticmethod(mock_hist))
        df = client.fetch_stock_daily_raw("000001", "20240101", "20240131")
        assert df.empty

    def test_none_response(self, client, monkeypatch):
        """Test that None response returns an empty DataFrame."""
        def mock_hist(symbol, period, start_date, end_date, adjust):
            return None
        monkeypatch.setattr(FakeAkShare, "stock_zh_a_hist", staticmethod(mock_hist))
        df = client.fetch_stock_daily_raw("000001", "20240101", "20240131")
        assert df.empty

    def test_api_exception(self, client, monkeypatch):
        """Test that an API exception propagates to the caller."""
        def mock_hist(symbol, period, start_date, end_date, adjust):
            raise ConnectionError("API timeout")
        monkeypatch.setattr(FakeAkShare, "stock_zh_a_hist", staticmethod(mock_hist))
        with pytest.raises(ConnectionError):
            client.fetch_stock_daily_raw("000001", "20240101", "20240131")

    def test_stock_code_6_digit_string(self, client, monkeypatch, mock_raw_data):
        """Verify stock_code is always a 6-digit string."""
        def mock_hist(symbol, period, start_date, end_date, adjust):
            return mock_raw_data
        monkeypatch.setattr(FakeAkShare, "stock_zh_a_hist", staticmethod(mock_hist))

        df = client.fetch_stock_daily_raw(1, "20240101", "20240131")
        assert df["stock_code"].iloc[0] == "000001"

        df = client.fetch_stock_daily_qfq("600519", "20240101", "20240131")
        assert df["stock_code"].iloc[0] == "600519"

    def test_missing_core_field_raises_value_error(self, client, monkeypatch):
        """If Akshare returns data missing a core field like ``open``, raise."""
        bad_data = pd.DataFrame({
            "日期": ["2024-01-02"],
            "收盘": [10.2],
            # missing: 开盘, 最高, 最低
        })

        def mock_hist(symbol, period, start_date, end_date, adjust):
            return bad_data
        monkeypatch.setattr(FakeAkShare, "stock_zh_a_hist", staticmethod(mock_hist))

        with pytest.raises(ValueError, match="missing core fields"):
            client.fetch_stock_daily_raw("000001", "20240101", "20240131")


# =====================================================================
#  get_stock_sector  (backward-compat wrapper)
# =====================================================================

class TestGetStockSector:
    """Test the thin backward-compat wrapper — delegates to get_stock_basic_info."""

    @pytest.fixture(autouse=True)
    def _auto_mock(self, _mock_akshare) -> None:
        pass

    def test_returns_sector_string(self, monkeypatch) -> None:
        def mock_info(symbol):
            return pd.DataFrame({
                "item": ["股票代码", "股票简称", "行业", "上市时间"],
                "value": ["000001", "平安银行", "银行", "19910403"],
            })
        monkeypatch.setattr(FakeAkShare, "stock_individual_info_em", staticmethod(mock_info))
        result = AkShareClient.get_stock_sector("000001")
        assert result == "银行"

    def test_empty_response_returns_empty_string(self, monkeypatch) -> None:
        def mock_info(symbol):
            return pd.DataFrame()
        monkeypatch.setattr(FakeAkShare, "stock_individual_info_em", staticmethod(mock_info))
        result = AkShareClient.get_stock_sector("000001")
        assert result == ""

    def test_api_exception_returns_empty_string(self, monkeypatch) -> None:
        def mock_info(symbol):
            raise ConnectionError("API timeout")
        monkeypatch.setattr(FakeAkShare, "stock_individual_info_em", staticmethod(mock_info))
        result = AkShareClient.get_stock_sector("000001")
        assert result == ""


# =====================================================================
#  get_stock_basic_info  (new unified method)
# =====================================================================

class TestGetStockBasicInfo:
    """Test the unified stock basic info fetcher."""

    @pytest.fixture(autouse=True)
    def _auto_mock(self, _mock_akshare) -> None:
        pass

    def test_returns_name_and_sector(self, monkeypatch) -> None:
        """Happy path: returns both stock_name and sector."""
        def mock_info(symbol):
            return pd.DataFrame({
                "item": ["股票代码", "股票简称", "行业"],
                "value": ["000001", "平安银行", "银行"],
            })
        monkeypatch.setattr(FakeAkShare, "stock_individual_info_em", staticmethod(mock_info))
        info = AkShareClient.get_stock_basic_info("000001")
        assert info["stock_code"] == "000001"
        assert info["stock_name"] == "平安银行"
        assert info["sector"] == "银行"

    def test_returns_name_and_sector_600519(self, monkeypatch) -> None:
        """Different stock returns different values."""
        def mock_info(symbol):
            return pd.DataFrame({
                "item": ["股票代码", "股票简称", "行业"],
                "value": ["600519", "贵州茅台", "白酒"],
            })
        monkeypatch.setattr(FakeAkShare, "stock_individual_info_em", staticmethod(mock_info))
        info = AkShareClient.get_stock_basic_info("600519")
        assert info["stock_code"] == "600519"
        assert info["stock_name"] == "贵州茅台"
        assert info["sector"] == "白酒"

    def test_int_code(self, monkeypatch) -> None:
        """Int stock code normalised to 6-digit."""
        def mock_info(symbol):
            return pd.DataFrame({
                "item": ["股票简称", "行业"],
                "value": ["平安银行", "银行"],
            })
        monkeypatch.setattr(FakeAkShare, "stock_individual_info_em", staticmethod(mock_info))
        info = AkShareClient.get_stock_basic_info(1)
        assert info["stock_code"] == "000001"

    def test_empty_response_all_fields_empty(self, monkeypatch) -> None:
        """Empty API response → all fields ''."""
        def mock_info(symbol):
            return pd.DataFrame()
        monkeypatch.setattr(FakeAkShare, "stock_individual_info_em", staticmethod(mock_info))
        info = AkShareClient.get_stock_basic_info("000001")
        assert info["stock_name"] == ""
        assert info["sector"] == ""

    def test_none_response_all_fields_empty(self, monkeypatch) -> None:
        """None response → all fields ''."""
        def mock_info(symbol):
            return None
        monkeypatch.setattr(FakeAkShare, "stock_individual_info_em", staticmethod(mock_info))
        info = AkShareClient.get_stock_basic_info("000001")
        assert info["stock_name"] == ""
        assert info["sector"] == ""

    def test_api_exception_all_fields_empty(self, monkeypatch) -> None:
        """API exception → all fields '', no crash."""
        def mock_info(symbol):
            raise RuntimeError("Connection refused")
        monkeypatch.setattr(FakeAkShare, "stock_individual_info_em", staticmethod(mock_info))
        info = AkShareClient.get_stock_basic_info("000001")
        assert info["stock_name"] == ""
        assert info["sector"] == ""

    def test_missing_both_fields_returns_empty(self, monkeypatch) -> None:
        """No name or sector rows → empty strings."""
        def mock_info(symbol):
            return pd.DataFrame({
                "item": ["股票代码", "上市时间"],
                "value": ["000001", "19910403"],
            })
        monkeypatch.setattr(FakeAkShare, "stock_individual_info_em", staticmethod(mock_info))
        info = AkShareClient.get_stock_basic_info("000001")
        assert info["stock_name"] == ""
        assert info["sector"] == ""

    def test_nan_values_skipped(self, monkeypatch) -> None:
        """'nan' string values treated as empty."""
        def mock_info(symbol):
            return pd.DataFrame({
                "item": ["股票简称", "行业"],
                "value": ["nan", "nan"],
            })
        monkeypatch.setattr(FakeAkShare, "stock_individual_info_em", staticmethod(mock_info))
        info = AkShareClient.get_stock_basic_info("000001")
        assert info["stock_name"] == ""
        assert info["sector"] == ""

    def test_wrong_column_names_returns_empty(self, monkeypatch) -> None:
        """DataFrame with non-standard columns → all fields ''."""
        def mock_info(symbol):
            return pd.DataFrame({"field": ["行业"], "data": ["银行"]})
        monkeypatch.setattr(FakeAkShare, "stock_individual_info_em", staticmethod(mock_info))
        info = AkShareClient.get_stock_basic_info("000001")
        assert info["stock_name"] == ""
        assert info["sector"] == ""

    def test_only_name_no_sector(self, monkeypatch) -> None:
        """Returns name but empty sector when only name is available."""
        def mock_info(symbol):
            return pd.DataFrame({
                "item": ["股票简称"],
                "value": ["平安银行"],
            })
        monkeypatch.setattr(FakeAkShare, "stock_individual_info_em", staticmethod(mock_info))
        info = AkShareClient.get_stock_basic_info("000001")
        assert info["stock_name"] == "平安银行"
        assert info["sector"] == ""

    def test_only_sector_no_name(self, monkeypatch) -> None:
        """Returns sector but empty name when only sector is available."""
        def mock_info(symbol):
            return pd.DataFrame({
                "item": ["行业"],
                "value": ["银行"],
            })
        monkeypatch.setattr(FakeAkShare, "stock_individual_info_em", staticmethod(mock_info))
        info = AkShareClient.get_stock_basic_info("000001")
        assert info["stock_name"] == ""
        assert info["sector"] == "银行"

    def test_alternative_name_keys(self, monkeypatch) -> None:
        """Alternative Chinese name keys are recognised."""
        for name_key in ("股票简称", "证券简称", "股票名称"):
            def make_mock(key):
                def mock_info(symbol):
                    return pd.DataFrame({"item": [key], "value": ["测试"]})
                return mock_info
            monkeypatch.setattr(FakeAkShare, "stock_individual_info_em",
                              staticmethod(make_mock(name_key)))
            info = AkShareClient.get_stock_basic_info("000001")
            assert info["stock_name"] == "测试", f"Failed for key: {name_key}"


# =====================================================================
#  resolve_sector_remote
# =====================================================================

class TestResolveSectorRemote:
    """Test the multi-API remote sector resolver."""

    @pytest.fixture(autouse=True)
    def _auto_mock(self, _mock_akshare) -> None:
        pass

    def test_em_has_priority(self, monkeypatch) -> None:
        """East Money (stock_individual_info_em) is tried first."""
        def mock_info(symbol):
            return pd.DataFrame({
                "item": ["行业"],
                "value": ["半导体"],
            })
        monkeypatch.setattr(FakeAkShare, "stock_individual_info_em", staticmethod(mock_info))
        sector, source = AkShareClient.resolve_sector_remote("000001", "")
        assert sector == "半导体"
        assert source == "akshare_em"

    def test_em_failure_falls_through(self, monkeypatch) -> None:
        """When EM fails, try CNINFO then THS then Tushare."""
        # Make EM return nothing
        def mock_info(symbol):
            return pd.DataFrame({"item": ["其他"], "value": ["x"]})
        monkeypatch.setattr(FakeAkShare, "stock_individual_info_em", staticmethod(mock_info))
        # CNINFO also fails (FakeAkShare doesn't have it → exception)
        # THS also fails (no stock_board_industry_name_ths in FakeAkShare)
        # Tushare has no token → skipped
        sector, source = AkShareClient.resolve_sector_remote("000001", "")
        assert sector == ""
        assert source == "empty"

    def test_returns_tuple(self) -> None:
        """Always returns a (str, str) tuple, never raises."""
        result = AkShareClient.resolve_sector_remote("000001", "")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)

    def test_no_crash_on_any_input(self) -> None:
        """All kinds of inputs are safe."""
        for code in ("000001", "600519", "00000", "abc", ""):
            sector, source = AkShareClient.resolve_sector_remote(code, "")
            assert isinstance(sector, str)
            assert isinstance(source, str)
