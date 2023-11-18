#!/usr/bin/env bash

# set duration, output directory, and file name; use defaults if not provided
DURATION=${1:-0.5}
OUTDIR=${2:-"."}
FILENAME=${3:-"silence.mp3"}

# create the output directory if it does not exist
mkdir -p "$OUTDIR"

# generate the specified duration of silence in the specified directory and file
ffmpeg -y -f lavfi -i anullsrc=channel_layout=mono:sample_rate=44100 -t "$DURATION" "$OUTDIR/$FILENAME"
