#!/usr/bin/env python3
import argparse
import logging
import shutil
import subprocess
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")


def convert_pptx_to_pdf(input_pptx: Path):
    output_pdf_dir: Path = Path("assets")
    interim_output_pdf: Path = output_pdf_dir / (input_pptx.stem + ".pdf")
    final_output_pdf: Path = output_pdf_dir / "powerpoint.pdf"

    try:
        output_pdf_dir.mkdir(parents=True, exist_ok=True)

        if shutil.which("libreoffice") is None:
            raise FileNotFoundError(
                "LibreOffice is not installed or not in the PATH. Please install LibreOffice."
            )

        cmd = [
            "libreoffice",
            "--headless",
            "--convert-to",
            "pdf",
            str(input_pptx),
            "--outdir",
            str(output_pdf_dir),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if interim_output_pdf.exists():
            interim_output_pdf.rename(final_output_pdf)
            print(f"Successfully converted {input_pptx} to {final_output_pdf}")
        else:
            raise FileNotFoundError(
                f"Conversion failed: {interim_output_pdf} was not created."
            )

    except Exception as e:
        raise RuntimeError(f"Error converting {input_pptx} to PDF: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert a PowerPoint (.pptx) file to a PDF file."
    )
    parser.add_argument("pptx", type=Path, help="Input PowerPoint (.pptx) file")
    args = parser.parse_args()
    convert_pptx_to_pdf(args.pptx)
