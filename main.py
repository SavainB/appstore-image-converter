"""Convert promotional images to App Store screenshot dimensions."""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Any

from PIL import Image, ImageColor, ImageDraw, ImageEnhance, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parent
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_TARGET_SIZES = (
    (2556, 1179),
    (1179, 2556),
    (2622, 1206),
    (1206, 2622),
)


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as config_file:
        config = json.load(config_file)

    sizes = config.get("target_sizes")
    if not isinstance(sizes, list) or not sizes:
        raise ValueError("'target_sizes' doit contenir au moins une dimension.")

    normalized_sizes = []
    for size in sizes:
        try:
            width, height = int(size["width"]), int(size["height"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Chaque format doit définir une largeur et une hauteur.") from error
        if width <= 0 or height <= 0:
            raise ValueError("Les dimensions doivent être des entiers positifs.")
        if (width, height) not in ALLOWED_TARGET_SIZES:
            allowed = ", ".join(size_name(allowed_size) for allowed_size in ALLOWED_TARGET_SIZES)
            raise ValueError(
                f"Format App Store non autorisé : {width}x{height}. "
                f"Formats autorisés : {allowed}."
            )
        normalized_sizes.append((width, height))

    extension_mode = config.get("extension_mode", "gradient")
    if extension_mode not in {"gradient", "blur"}:
        raise ValueError("'extension_mode' doit valoir 'gradient' ou 'blur'.")

    output_format = str(config.get("output_format", "PNG")).upper()
    if output_format != "PNG":
        raise ValueError("Seul le format de sortie PNG est pris en charge.")

    fallback_color = config.get("fallback_color", "#20212A")
    try:
        ImageColor.getcolor(fallback_color, "RGBA")
    except (TypeError, ValueError) as error:
        raise ValueError("'fallback_color' doit être une couleur reconnue, par exemple '#20212A'.") from error

    margin = config.get("inner_margin", 0)
    if not isinstance(margin, int) or margin < 0:
        raise ValueError("'inner_margin' doit être un entier positif ou nul.")
    sharpening = config.get("sharpening", 0)
    if not isinstance(sharpening, (int, float)) or not 0 <= sharpening <= 2:
        raise ValueError("'sharpening' doit être compris entre 0 et 2.")

    config["target_sizes"] = normalized_sizes
    config["extension_mode"] = extension_mode
    config["output_format"] = output_format
    config["fallback_color"] = fallback_color
    config["inner_margin"] = margin
    config["sharpening"] = float(sharpening)
    return config


def size_name(size: tuple[int, int]) -> str:
    return f"{size[0]}x{size[1]}"


def _sample_border(image: Image.Image, x: float, y: float) -> tuple[int, int, int, int]:
    px = min(image.width - 1, max(0, round(x)))
    py = min(image.height - 1, max(0, round(y)))
    return image.getpixel((px, py))


def _gradient_background(
    image: Image.Image,
    size: tuple[int, int],
    fallback_color: str,
    blur: bool = False,
) -> Image.Image:
    """Build a smooth background from sampled edge colors, without duplicating content."""
    width, height = size
    fallback = ImageColor.getcolor(fallback_color, "RGBA")
    if image.width < 1 or image.height < 1:
        return Image.new("RGBA", size, fallback)
    image = image.convert("RGBA")

    grid_width, grid_height = 9, 9
    corners = (
        _sample_border(image, 0, 0),
        _sample_border(image, image.width - 1, 0),
        _sample_border(image, 0, image.height - 1),
        _sample_border(image, image.width - 1, image.height - 1),
    )
    grid = Image.new("RGBA", (grid_width, grid_height))
    draw = ImageDraw.Draw(grid)
    top_left, top_right, bottom_left, bottom_right = corners

    for gy in range(grid_height):
        fy = gy / (grid_height - 1)
        for gx in range(grid_width):
            fx = gx / (grid_width - 1)
            color = tuple(
                round(
                    (1 - fy) * ((1 - fx) * top_left[channel] + fx * top_right[channel])
                    + fy * ((1 - fx) * bottom_left[channel] + fx * bottom_right[channel])
                )
                for channel in range(4)
            )
            draw.point((gx, gy), fill=color)

    # Preserve the sampled colors along every edge, including non-uniform gradients.
    for index in range(grid_width):
        position = index / (grid_width - 1)
        x = position * (image.width - 1)
        y = position * (image.height - 1)
        draw.point((index, 0), fill=_sample_border(image, x, 0))
        draw.point((index, grid_height - 1), fill=_sample_border(image, x, image.height - 1))
        draw.point((0, index), fill=_sample_border(image, 0, y))
        draw.point((grid_width - 1, index), fill=_sample_border(image, image.width - 1, y))

    background = grid.resize(size, Image.Resampling.BICUBIC)
    if blur:
        background = background.filter(ImageFilter.GaussianBlur(radius=max(8, min(size) / 18)))
    return background


def fit_image(
    image: Image.Image,
    target_size: tuple[int, int],
    margin: int = 0,
) -> tuple[Image.Image, tuple[int, int], tuple[int, int]]:
    """Contain an image in a target canvas and return (canvas, resized size, offset)."""
    target_width, target_height = target_size
    available_width = target_width - 2 * margin
    available_height = target_height - 2 * margin
    if available_width <= 0 or available_height <= 0:
        raise ValueError("La marge intérieure est trop grande pour le format cible.")

    scale = min(available_width / image.width, available_height / image.height)
    resized_size = (
        min(available_width, max(1, round(image.width * scale))),
        min(available_height, max(1, round(image.height * scale))),
    )
    resized = image.resize(resized_size, Image.Resampling.LANCZOS)
    offset = (
        (target_width - resized_size[0]) // 2,
        (target_height - resized_size[1]) // 2,
    )

    has_alpha = "A" in image.getbands()
    canvas = Image.new(image.mode, target_size, 0 if has_alpha else "white")
    canvas.paste(resized, offset)
    return canvas, resized_size, offset


def convert_image(
    source: Path,
    destination: Path,
    target_size: tuple[int, int],
    config: dict[str, Any],
) -> tuple[tuple[int, int], tuple[int, int]]:
    with Image.open(source) as opened:
        original_size = opened.size
        icc_profile = opened.info.get("icc_profile")
        image = ImageOps.exif_transpose(opened)
        has_alpha = "A" in image.getbands() or "transparency" in image.info
        working_mode = "RGBA" if has_alpha else "RGB"
        image = image.convert(working_mode)

    target_width, target_height = target_size
    margin = config["inner_margin"]
    available_width = target_width - 2 * margin
    available_height = target_height - 2 * margin
    if available_width <= 0 or available_height <= 0:
        raise ValueError("La marge intérieure est trop grande pour le format cible.")

    scale = min(available_width / image.width, available_height / image.height)
    resized_size = (
        min(available_width, max(1, round(image.width * scale))),
        min(available_height, max(1, round(image.height * scale))),
    )
    resized = image.resize(resized_size, Image.Resampling.LANCZOS)
    if scale > 1 and config["sharpening"] > 0:
        resized = ImageEnhance.Sharpness(resized).enhance(1 + config["sharpening"])

    offset = ((target_width - resized_size[0]) // 2, (target_height - resized_size[1]) // 2)
    try:
        background = _gradient_background(
            resized,
            target_size,
            config["fallback_color"],
            blur=config["extension_mode"] == "blur",
        )
    except (OSError, ValueError, TypeError, IndexError) as error:
        warnings.warn(
            f"Extension du fond impossible pour {source.name}; couleur de secours utilisée : {error}",
            RuntimeWarning,
        )
        background = Image.new(
            "RGBA",
            target_size,
            ImageColor.getcolor(config["fallback_color"], "RGBA"),
        )
    if not has_alpha:
        background = background.convert("RGB")
        background.paste(resized, offset)
    else:
        background.alpha_composite(resized, dest=offset)

    destination.parent.mkdir(parents=True, exist_ok=True)
    save_options: dict[str, Any] = {"format": "PNG", "compress_level": config.get("png_compress_level", 6)}
    if icc_profile:
        save_options["icc_profile"] = icc_profile
    background.save(destination, **save_options)

    with Image.open(destination) as result:
        if result.format != "PNG" or result.size != target_size:
            raise OSError("La vérification du PNG exporté a échoué.")
        result.verify()

    return original_size, target_size


def unique_destination(directory: Path, source: Path) -> Path:
    candidate = directory / f"{source.stem}.png"
    if not candidate.exists():
        return candidate

    index = 2
    while True:
        candidate = directory / f"{source.stem}_{index}.png"
        if not candidate.exists():
            return candidate
        index += 1


def process_images(
    input_dir: Path,
    output_dir: Path,
    sizes: list[tuple[int, int]],
    config: dict[str, Any],
) -> int:
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    images = sorted(
        (
            path
            for path in input_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ),
        key=lambda path: path.name.casefold(),
    )
    if not images:
        print(f"Aucune image prise en charge dans {input_dir}.")
        return 0

    errors = 0
    for image_path in images:
        for size in sizes:
            destination_dir = output_dir / size_name(size)
            destination = unique_destination(destination_dir, image_path)
            try:
                original_size, final_size = convert_image(image_path, destination, size, config)
                print(
                    f"[OK] {image_path.name} : {original_size[0]}x{original_size[1]} "
                    f"-> {final_size[0]}x{final_size[1]} ({destination})"
                )
            except Exception as error:
                errors += 1
                print(f"[ERREUR] {image_path.name} ({size_name(size)}) : {error}", file=sys.stderr)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Convertit des images aux formats de captures App Store.")
    parser.add_argument("--size", help="Ne traiter qu'un format configuré, par exemple 1320x2868.")
    parser.add_argument("--config", type=Path, default=ROOT / "config.json", help="Chemin du fichier JSON.")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Configuration invalide : {error}", file=sys.stderr)
        return 2

    sizes = config["target_sizes"]
    if args.size:
        available = {size_name(size): size for size in sizes}
        if args.size not in available:
            parser.error(f"Format non configuré : {args.size}. Formats disponibles : {', '.join(available)}")
        sizes = [available[args.size]]

    return 1 if process_images(ROOT / "input", ROOT / "output", sizes, config) else 0


if __name__ == "__main__":
    raise SystemExit(main())
