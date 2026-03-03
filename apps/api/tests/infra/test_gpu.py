"""Tests for GPU monitoring utilities."""

from __future__ import annotations

from infra.telemetry.gpu import get_gpu_memory_info, format_gpu_memory


class TestGpuMemory:
    def test_get_gpu_memory_info_returns_dict(self) -> None:
        info = get_gpu_memory_info()
        assert isinstance(info, dict)
        assert "available" in info
        # If CUDA available, should have more keys
        if info["available"]:
            assert "name" in info
            assert "used_gb" in info
            assert "total_gb" in info
            assert "percent" in info

    def test_format_gpu_memory_no_gpu(self) -> None:
        info = {"available": False}
        result = format_gpu_memory(info)
        assert result == "GPU: Not available"

    def test_format_gpu_memory_with_gpu(self) -> None:
        info = {
            "available": True,
            "name": "Tesla T4",
            "used_gb": 2.5,
            "total_gb": 15.0,
            "percent": 16.7,
        }
        result = format_gpu_memory(info)
        assert "Tesla T4" in result
        assert "2.5" in result
        assert "15.0" in result
