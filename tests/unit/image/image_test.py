"""Tests for image utilities — Pydantic models, tile math, error handling."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from godotllminteraction.image import (
    ImageError,
    ImageInfo,
    TileError,
    TileGrid,
    TileRegion,
    compute_tile_grid,
    compute_tile_region,
    get_image_info,
    load_image,
)

pytestmark = [pytest.mark.image]


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    """Create a 64x48 RGB PNG for testing."""
    p = tmp_path / "test.png"
    Image.new("RGB", (64, 48), color="red").save(p)
    return p


@pytest.fixture
def non_divisible_image(tmp_path: Path) -> Path:
    """Create a 65x47 image (not evenly divisible by common tile sizes)."""
    p = tmp_path / "odd.png"
    Image.new("RGB", (65, 47), color="blue").save(p)
    return p


class TestGetImageInfo:
    def test_returns_pydantic_model_with_correct_fields(self, sample_image: Path):
        result = get_image_info(sample_image)
        assert isinstance(result, ImageInfo)
        assert result.width == 64
        assert result.height == 48
        assert result.format == "PNG"
        assert result.mode == "RGB"
        assert str(sample_image) in result.path

    def test_serializes_to_json(self, sample_image: Path):
        result = get_image_info(sample_image)
        data = result.model_dump_json()
        assert '"width":64' in data
        assert '"height":48' in data

    def test_nonexistent_file_raises_image_error(self, tmp_path: Path):
        with pytest.raises(ImageError, match="File not found"):
            get_image_info(tmp_path / "nope.png")


class TestComputeTileGrid:
    def test_returns_pydantic_model_with_correct_math(self, sample_image: Path):
        result = compute_tile_grid(sample_image, tile_width=16, tile_height=12)
        assert isinstance(result, TileGrid)
        assert result.columns == 4  # 64 / 16
        assert result.rows == 4  # 48 / 12
        assert result.total_tiles == 16
        assert result.tile_width == 16
        assert result.tile_height == 12
        assert result.image_width == 64
        assert result.image_height == 48

    def test_non_divisible_dimensions_floor_division(self, non_divisible_image: Path):
        result = compute_tile_grid(non_divisible_image, tile_width=16, tile_height=16)
        assert result.columns == 4  # 65 // 16 = 4
        assert result.rows == 2  # 47 // 16 = 2
        assert result.total_tiles == 8

    def test_tile_larger_than_image_raises_tile_error(self, sample_image: Path):
        with pytest.raises(TileError, match="larger than"):
            compute_tile_grid(sample_image, tile_width=128, tile_height=128)

    def test_zero_tile_dimension_raises_tile_error(self, sample_image: Path):
        with pytest.raises(TileError, match="positive integers"):
            compute_tile_grid(sample_image, tile_width=0, tile_height=16)

    def test_negative_tile_dimension_raises_tile_error(self, sample_image: Path):
        with pytest.raises(TileError, match="positive integers"):
            compute_tile_grid(sample_image, tile_width=16, tile_height=-8)


class TestComputeTileRegion:
    def test_returns_pydantic_model_with_correct_pixel_coords(self, sample_image: Path):
        result = compute_tile_region(sample_image, 16, 12, col=2, row=3)
        assert isinstance(result, TileRegion)
        assert result.x == 32  # 2 * 16
        assert result.y == 36  # 3 * 12
        assert result.width == 16
        assert result.height == 12
        assert result.col == 2
        assert result.row == 3

    def test_godot_rect2_property_format(self, sample_image: Path):
        result = compute_tile_region(sample_image, 16, 12, col=1, row=1)
        assert result.godot_rect2 == "Rect2(16, 12, 16, 12)"

    def test_col_out_of_range_raises_tile_error(self, sample_image: Path):
        with pytest.raises(TileError, match="Column.*out of range"):
            compute_tile_region(sample_image, 16, 12, col=4, row=0)

    def test_row_out_of_range_raises_tile_error(self, sample_image: Path):
        with pytest.raises(TileError, match="Row.*out of range"):
            compute_tile_region(sample_image, 16, 12, col=0, row=4)

    def test_negative_col_raises_tile_error(self, sample_image: Path):
        with pytest.raises(TileError, match="Column.*out of range"):
            compute_tile_region(sample_image, 16, 12, col=-1, row=0)

    def test_origin_tile(self, sample_image: Path):
        result = compute_tile_region(sample_image, 16, 12, col=0, row=0)
        assert result.x == 0
        assert result.y == 0
        assert result.godot_rect2 == "Rect2(0, 0, 16, 12)"


class TestLoadImage:
    def test_returns_pil_image(self, sample_image: Path):
        img = load_image(sample_image)
        assert isinstance(img, Image.Image)
        assert img.width == 64

    def test_nonexistent_raises_image_error(self, tmp_path: Path):
        with pytest.raises(ImageError, match="File not found"):
            load_image(tmp_path / "missing.png")

    def test_corrupt_file_raises_image_error(self, tmp_path: Path):
        p = tmp_path / "corrupt.png"
        p.write_bytes(b"not a real png")
        with pytest.raises(ImageError, match="Cannot open image"):
            load_image(p)
