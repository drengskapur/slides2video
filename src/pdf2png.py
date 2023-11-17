#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path

import pdf2image

logging.basicConfig(level=logging.INFO, format="%(message)s")


def resize_image_to_even_dimensions(image):
    width, height = image.size
    even_width = width if width % 2 == 0 else width + 1
    even_height = height if height % 2 == 0 else height + 1
    return image.resize((even_width, even_height))


def extract_images_from_pdf(pdf_path):
    output_dir = Path("assets/images")
    output_dir.mkdir(parents=True, exist_ok=True)
    images = pdf2image.convert_from_path(pdf_path, dpi=300)
    for page_num, image in enumerate(images, start=1):
        resized_image = resize_image_to_even_dimensions(image)
        output_image_path = output_dir / f"image_{page_num}.png"
        resized_image.save(output_image_path, "PNG")
        logging.info(f"Saved slide image to {output_image_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract slide images from a PDF file."
    )
    parser.add_argument("pdf", type=Path, help="Input PDF file path")
    args = parser.parse_args()
    extract_images_from_pdf(args.pdf)
