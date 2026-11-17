(() => {
  const sourceInputs = document.querySelectorAll('input[name="source"]');
  const dropzone = document.getElementById("dropzone");
  const textField = document.getElementById("text-field");
  const textInput = document.getElementById("text");
  const fileInput = document.getElementById("file");
  const themeInput = document.getElementById("theme");
  const submitButton = document.getElementById("submit");

  if (
    !dropzone ||
    !textField ||
    !textInput ||
    !fileInput ||
    !themeInput ||
    !submitButton
  ) {
    return;
  }

  function isTextMode() {
    const checked = document.querySelector('input[name="source"]:checked');
    return checked ? checked.value === "text" : false;
  }

  function syncSubmit() {
    const hasContent = isTextMode()
      ? Boolean(textInput.value.trim())
      : Boolean(fileInput.files.length);
    submitButton.disabled = !hasContent || !themeInput.value.trim();
  }

  function syncSource() {
    dropzone.hidden = isTextMode();
    textField.hidden = !isTextMode();
    syncSubmit();
  }

  sourceInputs.forEach((input) => input.addEventListener("change", syncSource));
  fileInput.addEventListener("change", syncSubmit);
  textInput.addEventListener("input", syncSubmit);
  themeInput.addEventListener("input", syncSubmit);
  syncSource();
})();
