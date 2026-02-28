"""Unit tests for detect_device."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ny_feoko_shared.device import detect_device


class TestDetectDevice:
    def test_returns_requested_device(self) -> None:
        """Non-'auto' value is passed through unchanged."""
        assert detect_device("cuda") == "cuda"
        assert detect_device("mps") == "mps"
        assert detect_device("cpu") == "cpu"

    def test_auto_detects_cuda(self) -> None:
        """When requested is 'auto' and CUDA is available, returns 'cuda'."""
        with patch("ny_feoko_shared.device.torch.cuda.is_available", return_value=True):
            assert detect_device("auto") == "cuda"

    def test_auto_detects_mps(self) -> None:
        """When requested is 'auto', CUDA not available, MPS available, returns 'mps'."""
        with patch("ny_feoko_shared.device.torch.cuda.is_available", return_value=False):
            with patch(
                "ny_feoko_shared.device.torch.backends.mps.is_available",
                return_value=True,
            ):
                assert detect_device("auto") == "mps"

    def test_auto_falls_back_to_cpu(self) -> None:
        """When requested is 'auto' and neither CUDA nor MPS available, returns 'cpu'."""
        with patch("ny_feoko_shared.device.torch.cuda.is_available", return_value=False):
            with patch(
                "ny_feoko_shared.device.torch.backends.mps.is_available",
                return_value=False,
            ):
                assert detect_device("auto") == "cpu"
