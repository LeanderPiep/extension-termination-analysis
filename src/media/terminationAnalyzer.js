(function () {
  const root = document.getElementById("root");

  // VS Code webview API
  const vscode = acquireVsCodeApi();

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

  // ✅ Start button -> send message to extension
  startBtn.addEventListener("click", () => {
    const settings = {
      contextExtraction: contextExtraction.value,
      terminationAnalysis: terminationModel.value,
      specifyInputs: checkbox.checked,
      ranges: checkbox.checked ? collectRanges() : null,
    };

    // Optional UX: show loading state
    startBtn.disabled = true;
    startBtn.textContent = "Running...";

    if (contextOutput) contextOutput.value = "";
    if (analysisOutput) analysisOutput.value = "";

    vscode.postMessage({ type: "start", settings });
  });

  // ✅ Receive results from extension
  window.addEventListener("message", (event) => {
    const msg = event.data;
    if (!msg || typeof msg.type !== "string") return;

    if (msg.type === "contextResult") {
      // restore button
      startBtn.disabled = false;
      startBtn.textContent = "Start";

      if (!msg.ok) {
        const err = msg.error ?? "Unknown error";
        if (contextOutput) contextOutput.value = `ERROR: ${err}`;
        return;
      }

      if (contextOutput) contextOutput.value = msg.context ?? "";
    }

    // later: analysisResult, etc.
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
