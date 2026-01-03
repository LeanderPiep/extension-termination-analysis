import * as vscode from "vscode";
import { execFile } from "child_process";
import * as path from "path";

function runAstProbe(extensionPath: string, filePath: string, line1Based: number): Promise<any> {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(extensionPath, "src", "backend", "ast_function_identification.py");
    const pythonExe = "python";

    execFile(
      pythonExe,
      [scriptPath, "--file", filePath, "--line", String(line1Based)],
      { maxBuffer: 10 * 1024 * 1024 },
      (err, stdout, stderr) => {
        if (err) {
          reject(new Error(`Python failed: ${err.message}\n${stderr}`));
          return;
        }
        try {
          resolve(JSON.parse(stdout));
        } catch {
          reject(new Error(`Failed to parse JSON from backend.\nstdout:\n${stdout}\nstderr:\n${stderr}`));
        }
      }
    );
  });
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/**
 * Flatten params returned from Python into a simple ordered list of param names.
 * We keep it minimal: posonly + args + (vararg) + kwonly + (kwarg)
 */
function extractParamNames(params: any): string[] {
  const out: string[] = [];
  const pushNames = (arr: any[]) => {
    for (const item of arr ?? []) {
      if (item && typeof item.name === "string") out.push(item.name);
    }
  };

  pushNames(params?.posonly);
  pushNames(params?.args);

  if (params?.vararg?.name) out.push(`*${params.vararg.name}`);

  pushNames(params?.kwonly);

  if (params?.kwarg?.name) out.push(`**${params.kwarg.name}`);

  return out;
}

function getWebviewHtml(functionName: string, paramNames: string[]): string {
  const safeFn = escapeHtml(functionName);
  const paramsJsLiteral = JSON.stringify(paramNames).replace(/</g, "\\u003c");

  return /* html */ `<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';">
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Termination Analyzer</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      padding: 16px;
      margin: 0;
      color: var(--vscode-foreground);
      background: var(--vscode-editor-background);
      box-sizing: border-box;
    }
    *, *:before, *:after { box-sizing: inherit; }

    .container {
      max-width: 720px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 14px;
    }

    h1 {
      font-size: 24px;
      margin: 6px 0 4px;
      text-align: center;
      font-weight: 700;
    }

    .fn-label {
      font-size: 14px;
      font-weight: 400;
      text-align: center;
      opacity: 0.85;
    }

    .fn-name {
      font-size: 20px;
      font-weight: 800;
      text-align: center;
      margin-top: -6px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    }

    .section { width: 100%; }

    .row {
      width: 100%;
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }

    .hint {
      width: 100%;
      text-align: center;
      font-size: 12px;
      opacity: 0.75;
      margin-top: -4px;
    }

    label {
      font-size: 14px;
      user-select: none;
    }

    .inputs {
      width: 100%;
      margin-top: 6px;
    }

    .inputs-title {
      font-size: 13px;
      font-weight: 700;
      text-align: center;
      margin: 8px 0 6px;
      opacity: 0.9;
    }

    /* ✅ Center the whole parameter block, so it doesn't stretch across the full panel */
    #paramsContainer {
      display: flex;
      flex-direction: column;
      align-items: center; 
      width: 100%;
    }

    /* ✅ Make each row content-sized and tightly spaced */
    .param {
    position: relative;

    /* ✅ This width defines the centered block (inputs only) */
    width: calc(80px + 6px + 80px); /* from + gap + to */

    display: grid;
    grid-template-columns: 80px 80px;
    column-gap: 6px;
    align-items: center;

    margin: 6px 0;
  }

    /* ✅ Bring the name closer to the first input */
    .param-name {
    position: absolute;
    right: 100%;          /* place it left of the inputs block */
    margin-right: 6px;    /* small gap to the "from" field */

    width: 90px;          /* keeps names aligned vertically */
    text-align: right;

    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }


    input[type="number"] {
      width: 80px;          /* fixed = consistent + compact */
      padding: 4px 6px;
      font-size: 12px;
      border-radius: 6px;
      border: 1px solid var(--vscode-input-border, #666);
      color: var(--vscode-input-foreground);
      background: var(--vscode-input-background);
      outline: none;
    }

    input[type="number"]:focus {
      border-color: var(--vscode-focusBorder);
    }

    .hidden { display: none; }

    /* On narrow panels, stack each param row */
    @media (max-width: 520px) {
      .param {
        width: 100%;
        grid-template-columns: 1fr;
        row-gap: 6px;
      }
      .param-name {
        position: static;
        width: auto;
        text-align: left;
        margin-right: 0;
      }
      input[type="number"] {
        width: 100%;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Termination Analyzer</h1>

    <div class="section">
      <div class="fn-label">Function to Analyze:</div>
      <div class="fn-name">${safeFn}</div>
    </div>

    <div class="section">
      <div class="row">
        <label>
          <input id="specifyInputs" type="checkbox" />
          Specify Inputs
        </label>
      </div>
      <div class="hint">If enabled, specify numeric ranges for each input parameter.</div>

      <div id="inputsSection" class="inputs hidden">
        <div class="inputs-title">Input ranges</div>
        <div id="paramsContainer"></div>
        <div class="hint">Assuming numeric inputs (int/float/double) for now.</div>
      </div>
    </div>
  </div>

  <script>
    const paramNames = ${paramsJsLiteral};

    const checkbox = document.getElementById("specifyInputs");
    const inputsSection = document.getElementById("inputsSection");
    const paramsContainer = document.getElementById("paramsContainer");

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
      if (enabled) renderParams();
    });
  </script>
</body>
</html>`;
}




export function activate(context: vscode.ExtensionContext) {
  const disposable = vscode.commands.registerCommand("termination-analysis.run", async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return;

    const doc = editor.document;
    if (doc.languageId !== "python") {
      vscode.window.showWarningMessage("Termination Analysis is only available for Python files.");
      return;
    }

    // Optional, aber hilft massiv gegen "Warum stimmt das nicht?":
    if (doc.isDirty) {
      vscode.window.showWarningMessage("Please save the file before running Termination Analysis.");
      return;
    }

    const pos = editor.selection.active;
    const filePath = doc.uri.fsPath;

    try {
      const result = await runAstProbe(context.extensionPath, filePath, pos.line + 1);

      if (!result.ok) {
        vscode.window.showErrorMessage(result.error ?? "AST probe failed.");
        return;
      }

      if (!result.function) {
        vscode.window.showWarningMessage("Cursor is not inside a Python function.");
        return;
      }

      const fnName: string = result.function.name;
      const paramNames = extractParamNames(result.function.params);

      const panel = vscode.window.createWebviewPanel(
        "terminationAnalyzer",
        "Termination Analyzer",
        vscode.ViewColumn.Beside,
        {
          enableScripts: true
        }
      );

      panel.webview.html = getWebviewHtml(fnName, paramNames);
    } catch (e: any) {
      vscode.window.showErrorMessage(e?.message ?? String(e));
    }
  });

  context.subscriptions.push(disposable);
}
