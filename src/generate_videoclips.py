#!/usr/bin/env python3
import argparse
import logging
import pathlib
import shlex
import subprocess
from typing import Union

import ffmpeg
from natsort import natsorted

logging.basicConfig(level=logging.INFO, format="%(message)s")


def check_file_format(file_path: Union[pathlib.Path, str]):
    try:
        logging.info(f"Probing file format for {file_path}")
        probe = ffmpeg.probe(str(file_path))
        logging.info(f"File {file_path} format: {probe}")
    except ffmpeg.Error as e:
        logging.error(f"Error probing file {file_path}: {e}")
        raise


def resize_image(
    image_path: Union[pathlib.Path, str],
    output_dir: pathlib.Path,
    max_width: int = 1920,
) -> pathlib.Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    resized_image_path = output_dir / f"resized_{image_path.name}"
    try:
        logging.info(f"Resizing image {image_path}")
        probe = ffmpeg.probe(str(image_path))
        width = probe["streams"][0]["width"]
        height = probe["streams"][0]["height"]
        new_height = int((height * max_width) / width)
        adjusted_width = f"iw-mod(iw,2)"
        adjusted_height = f"ih-mod(ih,2)"
        ffmpeg.input(str(image_path)).filter(
            "scale", adjusted_width, adjusted_height
        ).output(str(resized_image_path)).overwrite_output().run()
        logging.info(f"Resized image saved to {resized_image_path}")
    except ffmpeg.Error as e:
        logging.error(f"Error resizing image {image_path}: {e}")
        raise

    return resized_image_path


def create_videoclip(image_path, voiceover_path, output_path, audio_bitrate="128k"):
    try:
        ffmpeg_command = [
            "ffmpeg",
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-i",
            str(voiceover_path),
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-c:a",
            "aac",
            "-b:a",
            audio_bitrate,
            "-vf",
            "scale='iw-mod(iw,2)':'ih-mod(ih,2)',format=yuv420p",
            "-shortest",
            str(output_path),
        ]
        logging.info(f"Running ffmpeg command: {' '.join(ffmpeg_command)}")
        result = subprocess.run(
            ffmpeg_command, timeout=300, capture_output=True, text=True
        )
        if result.returncode != 0:
            logging.error(f"ffmpeg command failed with error: {result.stderr}")
            return False
        else:
            logging.info(f"Video clip created at {output_path}")
            return True
    except subprocess.TimeoutExpired:
        logging.error("ffmpeg command timed out")
        return False
    except Exception as e:
        logging.error(f"Error creating video clip: {e}")
        return False


def validate_files(images_dir: pathlib.Path, voiceovers_dir: pathlib.Path):
    logging.info("Validating files")
    image_files = sorted(images_dir.glob("*.png"))
    voiceover_files = sorted(voiceovers_dir.glob("*.mp3"))
    if len(image_files) != len(voiceover_files):
        raise ValueError(
            "The number of images does not match the number of voiceover notes."
        )
    for image_file, voiceover_file in zip(image_files, voiceover_files):
        if image_file.stem.split("_")[-1] != voiceover_file.stem.split("_")[-1]:
            raise ValueError(
                f"Image {image_file} and voiceover {voiceover_file} do not match."
            )


def generate_videoclips(
    assets_dir: pathlib.Path, overwrite: bool, audio_bitrate: str = "128k"
):
    logging.info("Starting video clip generation")
    images_dir = assets_dir / "images"
    voiceovers_dir = assets_dir / "voiceovers"
    videoclips_dir = assets_dir / "videoclips"
    videoclips_dir.mkdir(parents=True, exist_ok=True)
    if not images_dir.exists() or not voiceovers_dir.exists():
        raise ValueError(
            "One or both of the specified directories (images or voiceovers) do not exist."
        )
    resized_images_dir = assets_dir / "resized"
    resized_images_dir.mkdir(parents=True, exist_ok=True)
    validate_files(images_dir, voiceovers_dir)
    image_files = natsorted(list(images_dir.glob("*.png")))
    voiceover_files = natsorted(list(voiceovers_dir.glob("*.mp3")))
    for image_file, voiceover_file in zip(image_files, voiceover_files):
        video_clip_path = (
            videoclips_dir / f"videoclip_{image_file.stem.split('_')[-1]}.mp4"
        )
        if not video_clip_path.exists() or overwrite:
            check_file_format(image_file)
            check_file_format(voiceover_file)
            resized_image = resize_image(image_file, resized_images_dir)
            create_videoclip(
                resized_image, voiceover_file, video_clip_path, audio_bitrate
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate video clips from images and voiceovers."
    )
    parser.add_argument(
        "assets_dir", type=pathlib.Path, help="Directory containing assets"
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing video clips"
    )
    parser.add_argument(
        "--audio_bitrate",
        type=str,
        default="128k",
        help="Audio bitrate for the video clips",
    )
    args = parser.parse_args()
    generate_videoclips(args.assets_dir, args.overwrite, args.audio_bitrate)
