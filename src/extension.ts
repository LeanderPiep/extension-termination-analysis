// The module 'vscode' contains the VS Code extensibility API
// Import the module and reference it with the alias vscode in your code below
import * as vscode from 'vscode';

// This method is called when your extension is activated
// Your extension is activated the very first time the command is executed
export function activate(context: vscode.ExtensionContext) {

	const disposable = vscode.commands.registerCommand(
    'termination-analysis.run',
    () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        return;
      }

      const document = editor.document;
      const selection = editor.selection;
      const position = selection.active;

      const wordRange = document.getWordRangeAtPosition(position);
      if (!wordRange) {
        vscode.window.showWarningMessage(
          'No function name selected.'
        );
        return;
      }

      const functionName = document.getText(wordRange);

      vscode.window.showInformationMessage(
        `Termination Analysis triggered for function: ${functionName}`
      );
    }
  );

  context.subscriptions.push(disposable);
}

// This method is called when your extension is deactivated
export function deactivate() {}
