// ADAPTED FROM: https://github.com/googlecolab/colabtools/blob/main/google/colab/resources/files.js
function startUpload(inputId, outputId) {
    (function (scope) {

        function span(text, styleAttributes = {}) {
            const element = document.createElement('span');
            element.textContent = text;
            for (const key of Object.keys(styleAttributes)) {
                element.style[key] = styleAttributes[key];
            }
            return element;
        }

        const MAX_PAYLOAD_SIZE = 100 * 1024;

        function _uploadFiles(inputId, outputId) {
            const steps = uploadFilesStep(inputId, outputId);
            const outputElement = document.getElementById(outputId);
            outputElement.steps = steps;
            return _uploadFilesContinue(outputId);
        }

        function _uploadFilesContinue(outputId) {
            const outputElement = document.getElementById(outputId);
            const steps = outputElement.steps;
            const next = steps.next(outputElement.lastPromiseValue);
            return Promise.resolve(next.value.promise).then((value) => {
                outputElement.lastPromiseValue = value;
                return next.value.response;
            });
        }

        function* uploadFilesStep(inputId, outputId) {
            const inputElement = document.getElementById(inputId);
            inputElement.disabled = false;
            const outputElement = document.getElementById(outputId);
            outputElement.innerHTML = '';
            const pickedPromise = new Promise((resolve) => {
                inputElement.addEventListener('change', (e) => {
                    resolve(e.target.files);
                });
            });

            const files = yield {
                promise: pickedPromise,
                response: {
                    action: 'starting',
                }
            };

            inputElement.disabled = true;

            if (!files) {
                return {
                    response: {
                        action: 'complete',
                    }
                };
            }

            for (const file of files) {

                const fileDataPromise = new Promise((resolve) => {
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        resolve(e.target.result);
                    };
                    reader.readAsArrayBuffer(file);
                });

                let fileData = yield {
                    promise: fileDataPromise,
                    response: {
                        action: 'continue',
                    }
                };

                let position = 0;

                do {
                    const length = Math.min(fileData.byteLength - position, MAX_PAYLOAD_SIZE);
                    const chunk = new Uint8Array(fileData, position, length);
                    position += length;
                    const base64 = btoa(String.fromCharCode.apply(null, chunk));
                    yield {
                        response: {
                            action: 'append',
                            file: file.name,
                            data: base64,
                        },
                    };

                    let percentDone = (fileData.byteLength === 0) ? 100 : Math.round((position / fileData.byteLength) * 100);
                    // UPDATE PROGRESS BAR
                    (async function() {
                        const pythonProgressBar = document.querySelector('div.progress > div.progress-bar');
                        if (pythonProgressBar) {
                            pythonProgressBar.style.width = percentDone + '%';
                        }
                    })();

                } while (position < fileData.byteLength);
            }

            yield {
                response: {
                    action: 'complete',
                }
            };
        }

        // Expose the functions to the global scope
        scope.google = scope.google || {};
        scope.google.colab = scope.google.colab || {};
        scope.google.colab._files = {
            _uploadFiles,
            _uploadFilesContinue,
        };

        // Start the file upload process
        _uploadFiles(inputId, outputId);

    })(self);
}
