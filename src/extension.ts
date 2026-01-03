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
        } catch (e) {
          reject(new Error(`Failed to parse JSON from backend.\nstdout:\n${stdout}\nstderr:\n${stderr}`));
        }
      }
    );
  });
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

      const fnName = result.function.name;
      const start = result.function.start_line;
      const end = result.function.end_line;

      vscode.window.showInformationMessage(
        `Function: ${fnName} (lines ${start}-${end})`
      );

    } catch (e: any) {
      vscode.window.showErrorMessage(e?.message ?? String(e));
    }
  });

  context.subscriptions.push(disposable);
}
