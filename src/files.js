// ADAPTED FROM: https://github.com/googlecolab/colabtools/blob/main/google/colab/resources/files.js
(function (scope) {
    const MAX_PAYLOAD_SIZE = 100 * 1024;
    const fileReader = new FileReader();

    function span(text, styleAttributes = {}) {
        const element = document.createElement('span');
        element.textContent = text;
        Object.assign(element.style, styleAttributes);
        return element;
    }

    function updateProgressBar(percentDone) {
        const pythonProgressBar = document.querySelector('div.progress > div.progress-bar');
        if (pythonProgressBar) {
            pythonProgressBar.style.width = `${percentDone}%`;
        }
    }

    async function processFile(file) {
        return new Promise((resolve, reject) => {
            fileReader.onload = (e) => resolve(e.target.result);
            fileReader.onerror = (e) => reject(e);
            fileReader.readAsArrayBuffer(file);
        });
    }

    async function* uploadFilesStep(inputId) {
        const inputElement = document.getElementById(inputId);
        inputElement.disabled = false;
        inputElement.accept = '.pptx, application/vnd.openxmlformats-officedocument.presentationml.presentation';

        const files = await new Promise((resolve) => {
            inputElement.addEventListener('change', (e) => resolve(e.target.files));
        });

        inputElement.disabled = true;
        if (!files) return;

        for (const file of files) {
            let fileData = await processFile(file);
            let position = 0;

            do {
                const length = Math.min(fileData.byteLength - position, MAX_PAYLOAD_SIZE);
                const chunk = new Uint8Array(fileData, position, length);
                position += length;
                const base64 = btoa(String.fromCharCode.apply(null, chunk));

                yield {
                    action: 'append',
                    file: file.name,
                    data: base64,
                };

                let percentDone = fileData.byteLength === 0 ? 100 : Math.round((position / fileData.byteLength) * 100);
                updateProgressBar(percentDone);

            } while (position < fileData.byteLength);
        }
    }

    async function _uploadFiles(inputId, outputId) {
        const steps = uploadFilesStep(inputId);
        const outputElement = document.getElementById(outputId);
        let result;

        for await (let step of steps) {
            outputElement.innerHTML = JSON.stringify(step);
            result = step;
        }

        return result;
    }

    async function _uploadFilesContinue(outputId) {
        const outputElement = document.getElementById(outputId);
        const steps = outputElement.steps;
        const next = steps.next(outputElement.lastPromiseValue);
        return Promise.resolve(next.value.promise).then((value) => {
            outputElement.lastPromiseValue = value;
            return next.value.response;
        });
    }

    scope.google = scope.google || {};
    scope.google.colab = scope.google.colab || {};
    scope.google.colab._files = {
        _uploadFiles,
        _uploadFilesContinue,
    };

    _uploadFiles('INPUT_ID_PLACEHOLDER', 'OUTPUT_ID_PLACEHOLDER');

})(self);
