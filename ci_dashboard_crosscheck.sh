#!/usr/bin/env python3
"""Build side-by-side panels comparing BMJ figures with Python redraws.

This helper uses ``pdftoppm`` to render pages 6 and 7 of the supplied BMJ PDF.
The panels are for visual checking only. They are not numerical validation.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageOps, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, default=ROOT / "sources" / "nsaid_2024_main_article_bmj_e077880.pdf")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "nsaid_2024_main_figures")
    return parser.parse_args()


def render_page(pdf: Path, page: int) -> Image.Image:
    if shutil.which("pdftoppm") is None:
        raise RuntimeError("pdftoppm is required to build PDF comparison panels")
    with tempfile.TemporaryDirectory() as tmp:
        prefix = Path(tmp) / "page"
        subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-png", "-r", "200", str(pdf), str(prefix)], check=True)
        return Image.open(f"{prefix}-{page}.png").convert("RGB")


def fit_to_box(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGB", size, "white")
    fitted = ImageOps.contain(image, size)
    x = (size[0] - fitted.width) // 2
    y = (size[1] - fitted.height) // 2
    canvas.paste(fitted, (x, y))
    return canvas


def make_panel(original: Image.Image, generated: Image.Image, output: Path, title: str) -> None:
    box = (900, 720)
    left = fit_to_box(original, box)
    right = fit_to_box(generated, box)
    panel = Image.new("RGB", (box[0] * 2, box[1] + 70), "white")
    panel.paste(left, (0, 70))
    panel.paste(right, (box[0], 70))
    draw = ImageDraw.Draw(panel)
    draw.text((20, 20), f"Published BMJ figure — {title}", fill="black")
    draw.text((box[0] + 20, 20), f"Python output — {title}", fill="black")
    output.parent.mkdir(parents=True, exist_ok=True)
    panel.save(output)


def main() -> None:
    args = parse_args()
    page6 = render_page(args.pdf, 6)
    page7 = render_page(args.pdf, 7)
    crops_dir = args.output_dir / "original_crops"
    panels_dir = args.output_dir / "comparison_panels"
    crops_dir.mkdir(parents=True, exist_ok=True)
    panels_dir.mkdir(parents=True, exist_ok=True)

    # Fixed crop boxes for the supplied BMJ PDF rendered at 200 dpi.
    figure1_crop = page6.crop((80, 150, 930, 850))
    figure2_crop = page6.crop((80, 1380, 930, 2080))
    figure3_crop = page7.crop((80, 150, 940, 970))
    figure1_crop.save(crops_dir / "original_bmj_figure1_crop.png")
    figure2_crop.save(crops_dir / "original_bmj_figure2_crop.png")
    figure3_crop.save(crops_dir / "original_bmj_figure3_crop.png")

    make_panel(figure1_crop, Image.open(args.output_dir / "figure1_expected_excess_events_workbook.png").convert("RGB"), panels_dir / "compare_bmj_figure1.png", "Figure 1")
    make_panel(figure2_crop, Image.open(args.output_dir / "figure2_total_cost_qaly_psa_workbook.png").convert("RGB"), panels_dir / "compare_bmj_figure2.png", "Figure 2")
    make_panel(figure3_crop, Image.open(args.output_dir / "figure3_exposure_duration_digitised_reconstruction.png").convert("RGB"), panels_dir / "compare_bmj_figure3.png", "Figure 3")
    print(f"Wrote comparison panels to {panels_dir}")


if __name__ == "__main__":
    main()
