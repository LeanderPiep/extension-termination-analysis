# Termination Analysis

This repository contains the source code of the prototype developed as part of the master's thesis:

**Termination Analysis using Large Language Models**

The prototype is implemented as a Visual Studio Code extension and analyzes whether Python programs terminate for all possible inputs. It automatically extracts the program context relevant for the analysis and uses LLMs to predict the program's termination behavior.

## Features

- Visual Studio Code extension for Python termination analysis
- Automatic extraction of the relevant program context
- Support for local models via Ollama
- Support for OpenAI and Anthropic models

## Requirements

Before running the extension, make sure the following software is installed:

- Visual Studio Code
- Node.js 
- Python 3
- Ollama

To use cloud-based models, an API key must be stored as a system environment variable:

- `OPENAI_API_KEY` for OpenAI models
- `ANTHROPIC_API_KEY` for Anthropic models

## Installation

Clone the repository and create a Python virtual environment:

```bash
python3 -m venv env
```

Activate the virtual environment.

Install the required Python packages:

```bash
pip install -r requirements.txt
```

Install the Node.js dependencies:

```bash
npm install
```

## Ollama Setup

Install the models used by the prototype:

```bash
ollama pull qwen2.5-coder:14b
ollama pull codellama:13b
```

## Running the Extension

Press **F5** in VS Code to launch the Extension Development Host.

The extension can then be used from within the new VS Code window.
