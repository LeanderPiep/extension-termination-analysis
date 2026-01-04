(function () {
  const root = document.getElementById("root");

  // data-params comes from extension.ts replacing {{PARAMS_JSON}}
  let paramNames = [];
  try {
    const raw = root?.dataset?.params ?? "[]";
    paramNames = JSON.parse(raw);
  } catch (e) {
    console.error("Failed to parse data-params JSON", e);
    paramNames = [];
  }

  console.log("PARAMS:", paramNames);

  const checkbox = document.getElementById("specifyInputs");
  const inputsSection = document.getElementById("inputsSection");
  const paramsContainer = document.getElementById("paramsContainer");

  if (!checkbox || !inputsSection || !paramsContainer) {
    console.error("Missing DOM elements", {
      checkbox: !!checkbox,
      inputsSection: !!inputsSection,
      paramsContainer: !!paramsContainer,
    });
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

      const toEl = document.createElement("input");
      toEl.type = "number";
      toEl.placeholder = "to";
      toEl.step = "any";

      row.appendChild(nameEl);
      row.appendChild(fromEl);
      row.appendChild(toEl);

      paramsContainer.appendChild(row);
    }
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
})();
