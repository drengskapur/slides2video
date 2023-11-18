#!/usr/bin/env bash

docker build -t slides2video .

OUTPUT_DIR="${HOME}/slides2video/output"
CONTAINER_NAME="slides2video"

echo "Checking if Docker is installed..."
if ! command -v docker &>/dev/null; then
    echo "Docker could not be found. Please install Docker."
    exit 1
fi

echo "Creating output directory..."
mkdir -p "${OUTPUT_DIR}"

chmod -R a+rwX "${OUTPUT_DIR}"

if [ "$(docker ps -aq -f name=^/${CONTAINER_NAME}$)" ]; then
    echo "Removing existing container with the same name..."
    docker rm "${CONTAINER_NAME}"
fi

echo "Creating Docker container..."
docker create --name "${CONTAINER_NAME}" slides2video
echo "Container created."

echo "Starting Docker container..."
docker start "${CONTAINER_NAME}"
echo "Container started."

echo "Waiting for Docker container to complete..."
docker wait "${CONTAINER_NAME}"
echo "Container process completed."

echo "Copying file from Docker container..."
docker cp "${CONTAINER_NAME}:/usr/src/app/output/video.mp4" "${OUTPUT_DIR}/video.mp4"

echo "Removing Docker container..."
docker rm "${CONTAINER_NAME}" || echo "Warning: Failed to remove container."

echo "Script completed."
