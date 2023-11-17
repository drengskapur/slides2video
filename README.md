# pptx2video
Transform PowerPoint presentations to videos with voiceovers.

The voiceover text is generated from the "Notes" section of each PowerPoint slide.

## Requirements

> [!IMPORTANT]
> You must install LibreOffice and FFmpeg.

1. **LibreOffice**: Download and install from [LibreOffice Download](https://www.libreoffice.org/download/download-libreoffice/).
2. **FFmpeg**: Download and install from [FFmpeg Download](https://ffmpeg.org/download.html).

Clone the repository:

```console
git clone https://github.com/drengskapur/pptx2video
```

Install requirements with pip:

```console
pip install -r requirements.txt
```

## Configuration

> [!IMPORTANT]
> You must have an [OpenAI API key](https://platform.openai.com/api-keys).

Put the PowerPoint in the repository folder and set the `params.yml`.

`params.yml`
```yml
# INPUT POWERPOINT
POWERPOINT: "your_presentation.pptx"
# OUTPUT VIDEO
VIDEO_NAME: "your_video_output.mp4"
```

## Usage

To start the pipeline, enter the command:

```console
dvc repro
```
