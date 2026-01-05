(function () {
  const root = document.getElementById("root");

  let paramNames = [];
  try {
    const raw = root?.dataset?.params ?? "[]";
    paramNames = JSON.parse(raw);
  } catch (e) {
    console.error("Failed to parse data-params JSON", e);
    paramNames = [];
  }

  const checkbox = document.getElementById("specifyInputs");
  const inputsSection = document.getElementById("inputsSection");
  const paramsContainer = document.getElementById("paramsContainer");

  const contextExtraction = document.getElementById("contextExtraction");
  const terminationModel = document.getElementById("terminationModel");
  const startBtn = document.getElementById("startBtn");

  const contextOutput = document.getElementById("contextOutput");
  const analysisOutput = document.getElementById("analysisOutput");


  if (!checkbox || !inputsSection || !paramsContainer || !contextExtraction || !terminationModel || !startBtn) {
    console.error("Missing DOM elements");
    return;
  }

  function renderParams() {
    paramsContainer.innerHTML = "";

    for (const name of paramNames) {
      const row = document.createElement("div");
      row.className = "param";

      const nameEl = document.createElement("div");
      nameEl.className = "param-name";
      nameEl.textContent = name;

      const fromEl = document.createElement("input");
      fromEl.type = "number";
      fromEl.placeholder = "from";
      fromEl.step = "any";
      fromEl.dataset.param = name;
      fromEl.dataset.bound = "from";

      const toEl = document.createElement("input");
      toEl.type = "number";
      toEl.placeholder = "to";
      toEl.step = "any";
      toEl.dataset.param = name;
      toEl.dataset.bound = "to";

      row.appendChild(nameEl);
      row.appendChild(fromEl);
      row.appendChild(toEl);

      paramsContainer.appendChild(row);
    }
  }

  function collectRanges() {
    const ranges = {};
    const inputs = paramsContainer.querySelectorAll('input[type="number"]');

    for (const el of inputs) {
      const param = el.dataset.param;
      const bound = el.dataset.bound;
      if (!param || !bound) continue;

      if (!ranges[param]) ranges[param] = { from: null, to: null };

      const v = el.value.trim();
      ranges[param][bound] = v === "" ? null : Number(v);
    }

    return ranges;
  }

  checkbox.addEventListener("change", () => {
    const enabled = checkbox.checked;
    inputsSection.classList.toggle("hidden", !enabled);

    if (enabled) {
      renderParams();
    } else {
      paramsContainer.innerHTML = "";
    }
  });

  startBtn.addEventListener("click", () => {
  const settings = {
    contextExtraction: contextExtraction.value,
    terminationAnalysis: terminationModel.value,
    specifyInputs: checkbox.checked,
    ranges: checkbox.checked ? collectRanges() : null,
  };

  console.log("START clicked. Settings:", settings);

  // Temporary demo output
  contextOutput.value =
    "Context extracted using " + settings.contextExtraction + "...";

  analysisOutput.value =
    "Termination analysis performed using " +
    settings.terminationAnalysis +
    ".\n\nResult: TERMINATES (example)" + "\n\nkjaknfnk" + "\n\nkjaknfnk" + "\n\nkjaknfnk" + "\n\nkjaknfnk" + "\n\nkjaknfnk" + "\n\nkjaknfnk" + "\n\nkjaknfnk" + "\n\nkjaknfnk";
});

})();
