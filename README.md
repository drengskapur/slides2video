# slides2video
Transform PowerPoint presentations to videos with voiceovers.

The voiceover text is generated from the "Notes" section of each PowerPoint slide.

## Docker

To use the Docker image, put the PowerPoint (`.pptx`) inside the `input` folder, and run:

```bash
./run.sh
```

## Manual Execution

> [!IMPORTANT]
> You must have an [OpenAI API key](https://platform.openai.com/api-keys).

Put your OpenAI API key in the `.env` file:

`.env`
```
OPENAI_API_KEY='sk-<YOUR_OPENAI_API_KEY>'
```

Install LibreOffice and FFmpeg:

1. **LibreOffice**: Download and install from [LibreOffice Download](https://www.libreoffice.org/download/download-libreoffice/).
2. **FFmpeg**: Download and install from [FFmpeg Download](https://ffmpeg.org/download.html).

Clone the repository:

```console
git clone https://github.com/drengskapur/slides2video
```

Install pip requirements:

```console
pip install -r requirements.txt
```

## Usage

To start the pipeline, enter the command:

```console
dvc repro
```
