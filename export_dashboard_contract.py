#!/usr/bin/env python3
"""Extract approximate Figure 3 curve points from the BMJ PDF image.

The extraction is tied to the supplied BMJ PDF rendered at 200 dpi. It detects
blue curve pixels near expected quarter-year marker locations. The resulting CSV
is a traceable digitisation of the published chart, not a Markov-model rerun.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, default=ROOT / "sources" / "nsaid_2024_main_article_bmj_e077880.pdf")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "nsaid_2024_figure3_digitised_points.csv")
    parser.add_argument("--metadata", type=Path, default=ROOT / "data" / "nsaid_2024_figure3_digitisation_metadata.json")
    parser.add_argument("--crop-output", type=Path, default=ROOT / "outputs" / "nsaid_2024_main_figures" / "original_crops" / "original_bmj_figure3_crop.png")
    return parser.parse_args()


def render_page_7(pdf: Path) -> Image.Image:
    if shutil.which("pdftoppm") is None:
        raise RuntimeError("pdftoppm is required to rerun chart digitisation")
    with tempfile.TemporaryDirectory() as temp_dir:
        prefix = Path(temp_dir) / "page"
        subprocess.run(["pdftoppm", "-f", "7", "-l", "7", "-png", "-r", "200", str(pdf), str(prefix)], check=True)
        rendered = Path(f"{prefix}-7.png")
        return Image.open(rendered).convert("RGB")


def digitise(crop: Image.Image) -> pd.DataFrame:
    pixels = np.asarray(crop)
    red, green, blue = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
    blue_curve = (blue > 100) & (blue > red * 1.2) & (blue > green * 1.05) & (red < 100) & (green < 180)

    x_axis_left, x_axis_right = 186, 791
    cost_y_zero, cost_pixels_per_10m = 301, 60
    qaly_y_zero, qaly_pixels_per_2k = 473, 60

    rows = []
    for duration in np.arange(0.25, 10.001, 0.25):
        x = int(round(x_axis_left + (x_axis_right - x_axis_left) * duration / 10.0))
        ys, _ = np.where(blue_curve[:, max(0, x - 4): min(blue_curve.shape[1], x + 5)])
        cost_pixels = ys[(ys >= 80) & (ys <= 320)]
        qaly_pixels = ys[(ys >= 470) & (ys <= 690)]
        if len(cost_pixels) == 0 or len(qaly_pixels) == 0:
            raise RuntimeError(f"Could not detect curve marker near duration={duration}")
        cost_y = float(np.median(cost_pixels))
        qaly_y = float(np.median(qaly_pixels))
        rows.append({
            "duration_years": float(duration),
            "cost_impact_gbp_millions": (cost_y_zero - cost_y) / (cost_pixels_per_10m / 10.0),
            "qaly_impact_thousands": (qaly_y_zero - qaly_y) / (qaly_pixels_per_2k / 2.0),
        })
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    page = render_page_7(args.pdf)
    crop_box = (80, 150, 940, 970)
    crop = page.crop(crop_box)
    args.crop_output.parent.mkdir(parents=True, exist_ok=True)
    crop.save(args.crop_output)
    data = digitise(crop)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(args.output, index=False)
    metadata = {
        "source_pdf": str(args.pdf.relative_to(ROOT)),
        "source_page_1_based": 7,
        "render_dpi": 200,
        "crop_box_pixels": crop_box,
        "method": "blue-pixel detection near quarter-year marker locations",
        "scientific_scope": "digitised published-figure reconstruction; not an independent model recalculation",
    }
    args.metadata.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(data.to_string(index=False))


if __name__ == "__main__":
    main()
