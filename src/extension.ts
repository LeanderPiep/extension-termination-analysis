import * as vscode from "vscode";
import { execFile } from "child_process";
import * as path from "path";
import * as fs from "fs";

function runAstProbe(extensionPath: string, filePath: string, line1Based: number): Promise<any> {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(extensionPath, "src", "backend", "ast_function_identification.py");

    execFile(
      "python",
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

function runOrchestrator(
  extensionPath: string,
  contextMode: string,
  analysisModel: string,
  functionName: string,
  filePath: string,
  inputs: any
): Promise<any> {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(extensionPath, "src", "backend", "orchestrator.py");

    const inputsJson = inputs ? JSON.stringify(inputs) : "null";

    execFile(
      "python",
      [
        scriptPath,
        "--mode",
        contextMode,
        "--analysis-model",
        analysisModel,
        "--function",
        functionName,
        "--file",
        filePath,
        "--inputs-json",
        inputsJson,
      ],
      { maxBuffer: 30 * 1024 * 1024 },
      (err, stdout, stderr) => {
        // Helpful for your new parameter summary log
        if (stderr && stderr.trim().length > 0) {
          console.log("[orchestrator stderr]", stderr);
        }

        if (err) {
          reject(new Error(`Orchestrator failed: ${err.message}\n${stderr}`));
          return;
        }
        try {
          resolve(JSON.parse(stdout));
        } catch {
          reject(new Error(`Failed to parse JSON from orchestrator.\nstdout:\n${stdout}\nstderr:\n${stderr}`));
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

function getWebviewContent(
  context: vscode.ExtensionContext,
  panel: vscode.WebviewPanel,
  functionName: string,
  paramNames: string[],
  paramTypes: Record<string, string>
): string {
  const webview = panel.webview;

  const htmlPath = vscode.Uri.joinPath(context.extensionUri, "src", "media", "terminationAnalyzer.html");
  let html = fs.readFileSync(htmlPath.fsPath, "utf8");

  const cssUri = webview.asWebviewUri(
    vscode.Uri.joinPath(context.extensionUri, "src", "media", "terminationAnalyzer.css")
  );

  const jsUri = webview.asWebviewUri(
    vscode.Uri.joinPath(context.extensionUri, "src", "media", "terminationAnalyzer.js")
  );

  html = html.replaceAll("{{CSP_SOURCE}}", webview.cspSource);
  html = html.replaceAll("{{CSS_URI}}", cssUri.toString());
  html = html.replaceAll("{{JS_URI}}", jsUri.toString());
  html = html.replaceAll("{{FUNCTION_NAME}}", escapeHtml(functionName));

  const paramsJson = JSON.stringify(paramNames).replace(/</g, "\\u003c");
  html = html.replaceAll("{{PARAMS_JSON}}", paramsJson);

  const paramTypesJson = JSON.stringify(paramTypes).replace(/</g, "\\u003c");
  html = html.replaceAll("{{PARAM_TYPES_JSON}}", paramTypesJson);

  return html;
}

export function activate(context: vscode.ExtensionContext) {
  context.subscriptions.push(
    vscode.commands.registerCommand("termination-analysis.run", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;

      const doc = editor.document;
      if (doc.languageId !== "python") {
        vscode.window.showWarningMessage("Termination Analysis is only available for Python files.");
        return;
      }

      if (doc.isDirty) {
        vscode.window.showWarningMessage("Please save the file first.");
        return;
      }

      const pos = editor.selection.active;
      const filePath = doc.uri.fsPath;

      const result = await runAstProbe(context.extensionPath, filePath, pos.line + 1);

      if (!result.ok || !result.function) {
        vscode.window.showWarningMessage("Cursor is not inside a Python function.");
        return;
      }

      const fnName: string = result.function.name;
      const paramTypes: Record<string, string> = result.function.params ?? {};
      const paramNames: string[] = Object.keys(paramTypes);

      const panel = vscode.window.createWebviewPanel(
        "terminationAnalyzer",
        "Termination Analyzer",
        vscode.ViewColumn.Beside,
        {
          enableScripts: true,
          localResourceRoots: [vscode.Uri.joinPath(context.extensionUri, "src", "media")],
        }
      );

      panel.webview.html = getWebviewContent(context, panel, fnName, paramNames, paramTypes);

      // ✅ Listen for messages from the webview (Start button, etc.)
      panel.webview.onDidReceiveMessage(async (msg) => {
        if (!msg || typeof msg.type !== "string") return;

        if (msg.type === "start") {
          const contextMode = String(msg.settings?.contextExtraction ?? "ast");
          const analysisModel = String(msg.settings?.terminationAnalysis ?? "gpt-5.2");
          const inputs = msg.settings?.inputs ?? null;

          try {
            const res = await runOrchestrator(context.extensionPath, contextMode, analysisModel, fnName, filePath, inputs);

            if (!res.ok) {
              panel.webview.postMessage({
                type: "contextResult",
                ok: false,
                error: res.error ?? "Run failed",
              });
              panel.webview.postMessage({
                type: "analysisResult",
                ok: false,
                error: res.error ?? "Run failed",
              });
              return;
            }

            panel.webview.postMessage({
              type: "contextResult",
              ok: true,
              context: res.context ?? "",
              meta: res.meta ?? {},
            });

            panel.webview.postMessage({
              type: "analysisResult",
              ok: true,
              analysis: res.analysis ?? "",
              meta: res.meta ?? {},
            });
          } catch (e: any) {
            panel.webview.postMessage({
              type: "contextResult",
              ok: false,
              error: e?.message ?? String(e),
            });
            panel.webview.postMessage({
              type: "analysisResult",
              ok: false,
              error: e?.message ?? String(e),
            });
          }
        }

      });
    })
  );
}
