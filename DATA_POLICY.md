# Data policy

Analog Omni is used with process design kits (PDKs), whose model data is often confidential. This policy states what Omni does with your data and what stays your decision.

Omni is pre-alpha: the AI tools described below are not written yet. This policy sets the rules they will follow.

## 1. Omni sends nothing anywhere by itself

Omni runs on your machine, and so does the simulator it drives. It makes no network connections of its own: no telemetry, no uploads, no update checks.

## 2. Tool results may reach the AI service you connect

Omni's AI layer is a set of tools (an MCP tool server and an Agent Skill) that your own assistant calls. Whatever a tool returns becomes part of that assistant's conversation and goes wherever the assistant sends it. For a cloud model, that means its provider.

By default the tools return only what is in the left column:

| May go to the AI service you connect | Stays on your machine |
|---|---|
| Netlists, topology, specs | PDK model files |
| Sizes, bias points and small-signal values of a candidate | Lookup-table arrays |
| Simulation results and error tables | Raw simulator output |
| Symbolic formulas | Any path under the PDK directory |

Tools return short summaries, never raw tables. If your PDK agreement forbids cloud use, connect the same tools to an assistant that runs a local model.

## 3. You are responsible for your PDK agreement

What you send to an AI service is your decision and your responsibility, and so is following your own PDK licence or non-disclosure agreement. Omni's defaults limit what leaves your machine; they are not legal advice and do not replace reading your agreement.

## What this repository holds

This repository never holds proprietary device models, tables derived from them, or examples that reveal them. That applies to the project's own material as well as to contributions. Examples use open PDKs or generic device names (`nmos`, `pmos`). Open-PDK lookup tables are built by a script, and prebuilt tables are published only where the PDK's licence allows it. Before every commit, a guard script checks the repository against a private list of proprietary model names.
