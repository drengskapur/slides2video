// ADAPTED FROM: https://github.com/googlecolab/colabtools/blob/main/google/colab/resources/files.js
(function(scope) {

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
    return next.value.promise.then((value) => {
      outputElement.lastPromiseValue = value;
      return next.value.response;
    });
  }

  function* uploadFilesStep(inputId, outputId) {
    const inputElement = document.getElementById(inputId);
    inputElement.disabled = false;

    const outputElement = document.getElementById(outputId);
    outputElement.innerHTML = '';

    const cancel = createCancelButton(inputElement, outputElement);

    const pickedPromise = new Promise((resolve) => {
      const onChange = (e) => {
        inputElement.removeEventListener('change', onChange);
        resolve(e.target.files);
        cancel.show();
      };
      inputElement.addEventListener('change', onChange);
    });

    const files = yield {
      promise: pickedPromise,
      response: { action: 'starting' }
    };

    if (!files) {
      cancel.remove();
      return { response: { action: 'complete' } };
    }

    for (const file of files) {
      if (cancel.isCanceled()) break;

      const li = document.createElement('li');
      const progressBar = document.createElement('progress');
      progressBar.max = file.size;
      progressBar.value = 0;
      li.appendChild(progressBar);
      outputElement.appendChild(li);

      let position = 0;
      while (position < file.size) {
        if (cancel.isCanceled()) break;

        const chunkSize = Math.min(file.size - position, MAX_PAYLOAD_SIZE);
        const chunk = await readFileChunk(file, position, chunkSize);
        position += chunkSize;

        progressBar.value = position;
        const percentDone = position / file.size * 100;
        li.textContent = ` ${Math.round(percentDone)}% `;
      }
    }

    cancel.remove();
    return { response: { action: 'complete' } };
  }

  function createCancelButton(inputElement, outputElement) {
    const cancelButton = document.createElement('button');
    cancelButton.textContent = 'Cancel';
    let canceled = false;

    cancelButton.onclick = () => {
      canceled = true;
      outputElement.innerHTML = '';
      cancelButton.remove();
    };

    return {
      show: () => inputElement.parentElement.appendChild(cancelButton),
      remove: () => cancelButton.remove(),
      isCanceled: () => canceled
    };
  }

  function readFileChunk(file, start, length) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target.result);
      reader.onerror = (e) => reject(e);
      const blob = file.slice(start, start + length);
      reader.readAsArrayBuffer(blob);
    });
  }

  scope.google = scope.google || {};
  scope.google.colab = scope.google.colab || {};
  scope.google.colab._files = {
    _uploadFiles,
    _uploadFilesContinue,
  };
})(self);
