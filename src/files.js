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
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = (e) => reject(e);
            reader.readAsArrayBuffer(file);
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
    
    // Store for persisting steps generators
    const stepsMap = new Map();
    
    async function _uploadFiles(inputId, outputId) {
        const steps = uploadFilesStep(inputId);
        stepsMap.set(outputId, steps);
        const outputElement = document.getElementById(outputId);
        let result;

        for await (let step of steps) {
            outputElement.innerHTML = JSON.stringify(step);
            result = step;
        }

        return result;
    }

    async function _uploadFilesContinue(outputId) {
        const steps = stepsMap.get(outputId);
        if (!steps) {
            throw new Error("Generator not found for the given outputId");
        }
        const result = await steps.next();
        if (result.done) {
            stepsMap.delete(outputId);
        }
        return result.value;
    }

    scope.google = scope.google || {};
    scope.google.colab = scope.google.colab || {};
    scope.google.colab._files = {
        _uploadFiles,
        _uploadFilesContinue,
    };

    _uploadFiles('INPUT_ID_PLACEHOLDER', 'OUTPUT_ID_PLACEHOLDER');

})(self);
