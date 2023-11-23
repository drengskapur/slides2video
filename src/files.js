// ADAPTED FROM: https://github.com/googlecolab/colabtools/blob/main/google/colab/resources/files.js

/**
 * @fileoverview Helpers for google.colab Python module.
 */
(function(scope) {
function span(text, styleAttributes = {}) {
  const element = document.createElement('span');
  element.textContent = text;
  for (const key of Object.keys(styleAttributes)) {
    element.style[key] = styleAttributes[key];
  }
  return element;
}

// Max number of bytes which will be uploaded at a time.
const MAX_PAYLOAD_SIZE = 100 * 1024;

function _uploadFiles(inputId, outputId) {
  const steps = uploadFilesStep(inputId, outputId);
  const outputElement = document.getElementById(outputId);
  // Cache steps on the outputElement to make it available for the next call
  // to uploadFilesContinue from Python.
  outputElement.steps = steps;

  return _uploadFilesContinue(outputId);
}

// This is roughly an async generator (not supported in the browser yet),
// where there are multiple asynchronous steps and the Python side is going
// to poll for completion of each step.
// This uses a Promise to block the python side on completion of each step,
// then passes the result of the previous step as the input to the next step.
function _uploadFilesContinue(outputId) {
  const outputElement = document.getElementById(outputId);
  const steps = outputElement.steps;

  const next = steps.next(outputElement.lastPromiseValue);
  return Promise.resolve(next.value.promise).then((value) => {
    // Cache the last promise value to make it available to the next
    // step of the generator.
    outputElement.lastPromiseValue = value;
    return next.value.response;
  });
}

/**
 * Generator function which is called between each async step of the upload
 * process.
 * @param {string} inputId Element ID of the input file picker element.
 * @param {string} outputId Element ID of the output display.
 * @return {!Iterable<!Object>} Iterable of next steps.
 */
function* uploadFilesStep(inputId, outputId) {
  const inputElement = document.getElementById(inputId);
  const outputElement = document.getElementById(outputId);
  let cancel; // Declare the cancel button variable

  // Function to show and handle the cancel button
  const handleCancelButton = () => {
    cancel = document.createElement('button');
    cancel.textContent = 'Cancel';
    cancel.onclick = () => {
      uploadCanceled = true; // Set the cancel flag
      outputElement.innerHTML = ''; // Clear the output display
      cancel.remove(); // Remove the cancel button
      inputElement.disabled = false; // Re-enable the input element
    };
    inputElement.parentElement.appendChild(cancel);
  };

  const clearCancelButton = () => {
    if (cancel && cancel.parentNode) {
      cancel.remove();
    }
  };
  
  const pickedPromise = new Promise((resolve) => {
    inputElement.addEventListener('change', (e) => {
      // Clear previous output on new file selection
      uploadCanceled = false; // Reset the cancel flag
      outputElement.innerHTML = ''; 
      resolve(e.target.files);
      // Show the cancel button when files are picked
      showCancelButton(); 
    });
  });

  // Wait for the user to pick the files.
  const files = yield {
    promise: Promise.race([pickedPromise]),
    response: {
      action: 'starting',
    }
  };

  inputElement.disabled = true; // Disable input during upload
  handleCancelButton(); // Show the cancel button

  if (!files) {
    // Remove the cancel button if no files were picked
    cancel && cancel.remove(); 
    return {
      response: {
        action: 'complete',
      }
    };
  }

  for (const file of files) {
    if (uploadCanceled) {
      clearCancelButton();
      break; // Exit the loop if upload is canceled
    }

    const li = document.createElement('li');

    // Create and append the progress bar
    const progressBar = document.createElement('progress');
    progressBar.max = file.size;
    progressBar.value = 0;
    li.appendChild(progressBar);

    // Create and append the percentage span
    const percent = span(' 0% ');
    li.appendChild(percent);
    outputElement.appendChild(li);

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

      let percentDone = fileData.byteLength === 0 ?
          100 :
          Math.round((position / fileData.byteLength) * 100);
      percent.textContent = ` ${percentDone}% `;
      progressBar.value = position;

    } while (position < fileData.byteLength);
  }

  // All done.
  yield {
    response: {
      action: 'complete',
    }
  };
  // Remove the cancel button after completion
  cancel && cancel.remove();
}


scope.google = scope.google || {};
scope.google.colab = scope.google.colab || {};
scope.google.colab._files = {
  _uploadFiles,
  _uploadFilesContinue,
};
})(self);
