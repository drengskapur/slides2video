#!/usr/bin/env python3
import argparse
import logging
import pathlib
import subprocess

logging.basicConfig(level=logging.INFO, format="%(message)s")

def create_concat_file(videoclips_dir: pathlib.Path):
    concat_file_path = videoclips_dir / "concat_list.txt"
    with open(concat_file_path, "w") as concat_file:
        for videoclip in sorted(
            videoclips_dir.glob("videoclip_*.mp4"), key=lambda x: x.stem
        ):
            concat_file.write(f"file '{videoclip.name}'\n")
    return concat_file_path

def concatenate_videos(assets_dir: pathlib.Path, output_path: pathlib.Path) -> bool:
    videoclips_dir = assets_dir / "videoclips"
    concat_file = create_concat_file(videoclips_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-r",
                "30",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "22",
                str(output_path),
            ],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        logging.error(f"Concatenation error: {e}")
        return False

    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Concatenate video clips.")
    parser.add_argument(
        "assets_dir", type=pathlib.Path, help="Directory containing assets"
    )
    parser.add_argument(
        "video_name",
        nargs='?',
        type=pathlib.Path,
        default=pathlib.Path("output/video.mp4"),
        help="The name of the output video file."
    )
    args = parser.parse_args()

    if concatenate_videos(args.assets_dir, args.video_name):
        logging.info("Video parts concatenated successfully.")
    else:
        logging.info("Failed to concatenate video parts.")
