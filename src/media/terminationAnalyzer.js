(function () {
  const root = document.getElementById("root");

  // VS Code webview API
  const vscode = acquireVsCodeApi();

  let paramSpecs = {};
  try {
    const raw = root?.dataset?.paramSpecs ?? "{}";
    paramSpecs = JSON.parse(raw);
  } catch (e) {
    console.error("Failed to parse data-param-specs JSON", e);
    paramSpecs = {};
  }

  const paramNames = Object.keys(paramSpecs); 

  const checkbox = document.getElementById("specifyInputs");
  const inputsSection = document.getElementById("inputsSection");
  const paramsContainer = document.getElementById("paramsContainer");

  const contextExtraction = document.getElementById("contextExtraction");
  const terminationModel = document.getElementById("terminationModel");
  const startBtn = document.getElementById("startBtn");

  const contextOutput = document.getElementById("contextOutput");
  const analysisOutput = document.getElementById("analysisOutput");

  if (
    !checkbox ||
    !inputsSection ||
    !paramsContainer ||
    !contextExtraction ||
    !terminationModel ||
    !startBtn
  ) {
    console.error("Missing DOM elements");
    return;
  }

  const TYPE_OPTIONS = ["Dont Specify", "Integer", "Float", "String", "Boolean"];

  function renderParams() {
  paramsContainer.innerHTML = "";

  for (const name of paramNames) {
    const row = document.createElement("div");
    row.className = "param";

    // type dropdown
    const typeSelect = document.createElement("select");
    typeSelect.className = "param-type";
    typeSelect.dataset.param = name;

    for (const opt of TYPE_OPTIONS) {
      const o = document.createElement("option");
      o.value = opt;
      o.textContent = opt;
      typeSelect.appendChild(o);
    }

    const defaultType = paramSpecs?.[name] ?? "Dont Specify";
    typeSelect.value = TYPE_OPTIONS.includes(defaultType) ? defaultType : "Dont Specify";

    const nameEl = document.createElement("div");
    nameEl.className = "param-name";
    nameEl.textContent = name;

    // container for inputs 
    const inputsEl = document.createElement("div");
    inputsEl.className = "param-inputs";
    inputsEl.dataset.param = name;

    function renderInputsForType(t) {
      inputsEl.innerHTML = "";

      if (t === "Dont Specify") {
        return;
      }

      if (t === "String") {
        const valEl = document.createElement("input");
        valEl.type = "text";
        valEl.placeholder = "value";
        valEl.dataset.param = name;
        valEl.dataset.kind = "value";
        inputsEl.appendChild(valEl);
        return;
      }

      if (t === "Boolean") {
        const boolSelect = document.createElement("select");
        boolSelect.className = "bool-select";
        boolSelect.dataset.param = name;
        boolSelect.dataset.kind = "bool";

        const optTrue = document.createElement("option");
        optTrue.value = "true";
        optTrue.textContent = "true";

        const optFalse = document.createElement("option");
        optFalse.value = "false";
        optFalse.textContent = "false";

        boolSelect.appendChild(optTrue);
        boolSelect.appendChild(optFalse);

        boolSelect.value = "true";

        inputsEl.appendChild(boolSelect);
        return;
      }


      // integer / float range
      const fromEl = document.createElement("input");
      fromEl.type = "number";
      fromEl.placeholder = "from";
      fromEl.step = t === "Integer" ? "1" : "any";
      fromEl.dataset.param = name;
      fromEl.dataset.kind = "from";

      const toEl = document.createElement("input");
      toEl.type = "number";
      toEl.placeholder = "to";
      toEl.step = t === "Integer" ? "1" : "any";
      toEl.dataset.param = name;
      toEl.dataset.kind = "to";

      inputsEl.appendChild(fromEl);
      inputsEl.appendChild(toEl);
    }

    // initial render
    renderInputsForType(typeSelect.value);

    // rerender on change
    typeSelect.addEventListener("change", () => {
      renderInputsForType(typeSelect.value);
    });

    row.appendChild(typeSelect);
    row.appendChild(nameEl);
    row.appendChild(inputsEl);

    paramsContainer.appendChild(row);
  }
}

  function collectParamTypes() {
    const out = {};
    const selects = paramsContainer.querySelectorAll("select.param-type");

    for (const sel of selects) {
      const param = sel.dataset.param;
      if (!param) continue;
      out[param] = sel.value || "Dont Specify";
    }

    return out;
  }


  function collectInputs() {
  const out = {};

  // read current types
  const selectedTypes = collectParamTypes();

  for (const [param, t] of Object.entries(selectedTypes)) {
    if (t === "Dont Specify") {
      out[param] = null;
      continue;
    }

    if (t === "String") {
      const el = paramsContainer.querySelector(`input[data-param="${param}"][data-kind="value"]`);
      const v = el ? el.value.trim() : "";
      out[param] = { type: t, value: v === "" ? null : v };
      continue;
    }

    if (t === "Boolean") {
      const el = paramsContainer.querySelector(`select[data-param="${param}"][data-kind="bool"]`);
      const v = el ? el.value : "false";
      out[param] = { type: t, value: v === "true" };
      continue;
    }

    // integer / float
    const fromEl = paramsContainer.querySelector(`input[data-param="${param}"][data-kind="from"]`);
    const toEl = paramsContainer.querySelector(`input[data-param="${param}"][data-kind="to"]`);

    const fromRaw = fromEl ? fromEl.value.trim() : "";
    const toRaw = toEl ? toEl.value.trim() : "";

    out[param] = {
      type: t,
      from: fromRaw === "" ? null : Number(fromRaw),
      to: toRaw === "" ? null : Number(toRaw),
    };
  }

  return out;
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

  // start button -> send message to extension
  startBtn.addEventListener("click", () => {
    const settings = {
      contextExtraction: contextExtraction.value,
      terminationAnalysis: terminationModel.value,
      specifyInputs: checkbox.checked,
      paramSpecs: checkbox.checked ? collectParamTypes() : null,
      inputs: checkbox.checked ? collectInputs() : null,
    };

    // show loading state
    startBtn.disabled = true;
    startBtn.textContent = "Running...";

    if (contextOutput) contextOutput.value = "";
    if (analysisOutput) analysisOutput.value = "";

    vscode.postMessage({ type: "start", settings });
  });

  // receive results from extension
  window.addEventListener("message", (event) => {
    const msg = event.data;
    if (!msg || typeof msg.type !== "string") return;

    if (msg.type === "contextResult") {
      if (!msg.ok) {
        startBtn.disabled = false;
        startBtn.textContent = "Start";
        const err = msg.error ?? "Unknown error";
        if (contextOutput) contextOutput.value = `ERROR: ${err}`;
        return;
      }
      if (contextOutput) contextOutput.value = msg.context ?? "";
    }

    if (msg.type === "analysisResult") {
      startBtn.disabled = false;
      startBtn.textContent = "Start";

      if (!msg.ok) {
        const err = msg.error ?? "Unknown error";
        if (analysisOutput) analysisOutput.value = `ERROR: ${err}`;
        return;
      }

      if (analysisOutput) analysisOutput.value = msg.analysis ?? "";
    }
  });
})();
