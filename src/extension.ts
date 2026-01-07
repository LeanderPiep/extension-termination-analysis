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

function runContextOrchestrator(
  extensionPath: string,
  mode: string,
  functionName: string,
  filePath: string
): Promise<any> {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(
      extensionPath,
      "src",
      "backend",
      "context extraction",
      "orchestrator.py"
    );

    execFile(
      "python",
      [scriptPath, "--mode", mode, "--function", functionName, "--file", filePath],
      { maxBuffer: 30 * 1024 * 1024 },
      (err, stdout, stderr) => {
        if (err) {
          reject(new Error(`Context orchestrator failed: ${err.message}\n${stderr}`));
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

function extractParamNames(params: any): string[] {
  const out: string[] = [];

  const push = (arr: any[]) => {
    for (const a of arr ?? []) {
      if (a?.name) out.push(a.name);
    }
  };

  push(params?.posonly);
  push(params?.args);
  if (params?.vararg?.name) out.push(`*${params.vararg.name}`);
  push(params?.kwonly);
  if (params?.kwarg?.name) out.push(`**${params.kwarg.name}`);

  return out;
}

function getWebviewContent(
  context: vscode.ExtensionContext,
  panel: vscode.WebviewPanel,
  functionName: string,
  paramNames: string[]
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
      const paramNames = extractParamNames(result.function.params);

      const panel = vscode.window.createWebviewPanel(
        "terminationAnalyzer",
        "Termination Analyzer",
        vscode.ViewColumn.Beside,
        {
          enableScripts: true,
          localResourceRoots: [vscode.Uri.joinPath(context.extensionUri, "src", "media")],
        }
      );

      panel.webview.html = getWebviewContent(context, panel, fnName, paramNames);

      // ✅ Listen for messages from the webview (Start button, etc.)
      panel.webview.onDidReceiveMessage(async (msg) => {
        if (!msg || typeof msg.type !== "string") return;

        if (msg.type === "start") {
          const mode = String(msg.settings?.contextExtraction ?? "ast");

          try {
            // Run python orchestrator
            const ctxRes = await runContextOrchestrator(context.extensionPath, mode, fnName, filePath);

            if (!ctxRes.ok) {
              panel.webview.postMessage({
                type: "contextResult",
                ok: false,
                error: ctxRes.error ?? "Context extraction failed",
              });
              return;
            }

            panel.webview.postMessage({
              type: "contextResult",
              ok: true,
              context: ctxRes.context ?? "",
              meta: ctxRes.meta ?? {},
            });
          } catch (e: any) {
            panel.webview.postMessage({
              type: "contextResult",
              ok: false,
              error: e?.message ?? String(e),
            });
          }
        }
      });
    })
  );
}
