import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from infra.constructs.layers import PythonLocalBundling


class TestPythonLocalBundling:
    """PythonLocalBundlingのテスト"""

    def test_try_bundle_success_with_uv(self, tmp_path: Path):
        """uvでバンドリングが成功する場合"""
        # Arrange
        source_path = tmp_path / "source"
        source_path.mkdir()
        requirements_file = source_path / "requirements.txt"
        requirements_file.write_text("requests==2.31.0\n")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        bundling = PythonLocalBundling(str(source_path))

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            # Act
            result = bundling.try_bundle(str(output_dir), MagicMock())

            # Assert
            assert result is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "uv"
            assert call_args[1] == "pip"
            assert call_args[2] == "install"

    def test_try_bundle_fallback_to_pip_when_uv_not_found(self, tmp_path: Path):
        """uvが見つからない場合、pipにフォールバックする"""
        # Arrange
        source_path = tmp_path / "source"
        source_path.mkdir()
        requirements_file = source_path / "requirements.txt"
        requirements_file.write_text("requests==2.31.0\n")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        bundling = PythonLocalBundling(str(source_path))

        with patch("subprocess.run") as mock_run:
            # uvが見つからない → pipにフォールバック
            mock_run.side_effect = [
                FileNotFoundError("uv not found"),
                MagicMock(returncode=0),
            ]

            # Act
            result = bundling.try_bundle(str(output_dir), MagicMock())

            # Assert
            assert result is True
            assert mock_run.call_count == 2
            # 2回目の呼び出しはpip
            second_call_args = mock_run.call_args_list[1][0][0]
            assert second_call_args[0] == "pip"

    def test_try_bundle_returns_false_when_requirements_not_found(self, tmp_path: Path):
        """requirements.txtが存在しない場合、Falseを返す"""
        # Arrange
        source_path = tmp_path / "source"
        source_path.mkdir()
        # requirements.txtを作成しない

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        bundling = PythonLocalBundling(str(source_path))

        # Act
        result = bundling.try_bundle(str(output_dir), MagicMock())

        # Assert
        assert result is False

    def test_try_bundle_returns_false_when_both_fail(self, tmp_path: Path):
        """uvとpipの両方が失敗した場合、Falseを返す"""
        # Arrange
        source_path = tmp_path / "source"
        source_path.mkdir()
        requirements_file = source_path / "requirements.txt"
        requirements_file.write_text("requests==2.31.0\n")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        bundling = PythonLocalBundling(str(source_path))

        with patch("subprocess.run") as mock_run:
            # 両方とも失敗
            mock_run.side_effect = [
                FileNotFoundError("uv not found"),
                FileNotFoundError("pip not found"),
            ]

            # Act
            result = bundling.try_bundle(str(output_dir), MagicMock())

            # Assert
            assert result is False

    def test_try_bundle_returns_false_when_uv_command_fails(self, tmp_path: Path):
        """uvコマンドがエラーを返した場合、pipにフォールバックする"""
        # Arrange
        source_path = tmp_path / "source"
        source_path.mkdir()
        requirements_file = source_path / "requirements.txt"
        requirements_file.write_text("invalid-package-xyz\n")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        bundling = PythonLocalBundling(str(source_path))

        with patch("subprocess.run") as mock_run:
            # uvが失敗 → pipにフォールバック → pipも失敗
            mock_run.side_effect = [
                subprocess.CalledProcessError(1, "uv"),
                subprocess.CalledProcessError(1, "pip"),
            ]

            # Act
            result = bundling.try_bundle(str(output_dir), MagicMock())

            # Assert
            assert result is False
            assert mock_run.call_count == 2
