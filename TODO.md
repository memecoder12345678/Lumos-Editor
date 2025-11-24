# Lumos Editor - Roadmap

This document outlines the high-priority features planned for the next development cycle of Lumos Editor. Contributions are highly welcome. If you are interested in a feature, please open an issue to start a discussion.

---

## 🚀 High-Priority Features

### 1. Integrated Language Server Protocol (LSP) Client

**Goal:** Build a native LSP client into the editor's core, providing a powerful API for plugins to register and communicate with specific language servers. This will enable advanced IDE features across multiple languages.

-   **Phase 1: Core LSP Client Implementation**
    -   [ ] **Process Manager:** Implement a robust manager within Lumos to handle the lifecycle (start, stop, monitor) of language server subprocesses.
    -   [ ] **JSON-RPC Framework:** Build the core communication layer to handle sending requests/notifications and receiving responses/diagnostics to/from a server over stdio. This must be asynchronous to prevent UI blocking.

-   **Phase 2: Core API & UI Integration**
    -   [ ] **Diagnostic API:** Create internal functions for rendering diagnostics received from the LSP. This includes:
        -   Applying styled indicators (e.g., wavy underlines for errors/warnings).
        -   Displaying diagnostic messages on hover or in a dedicated "Problems" panel.
        -   Placing markers in the editor's margin.
    -   [ ] **Editor Event Hooks:** Enable the core to trigger more granular events that the LSP client can listen to, such as:
        -   `text_changed` (with detailed change information)
        -   `file_saved`
        -   `selection_changed`
        -   `mouse_hover`
    -   [ ] **UI Feature Mapping:** Connect other LSP features (like `textDocument/completion`, `textDocument/hover`, `textDocument/definition`) to the editor's UI (e.g., completion popups, tooltips).

-   **Phase 3: Plugin Registration API**
    -   [ ] **Expose `lumos.lsp` API:** Create a new API endpoint for plugins.
    -   [ ] **Implement `lumos.lsp.register_server`:** This function will allow a plugin to register a language server by providing metadata, such as:
        -   `language_id`: e.g., `"python"`, `"javascript"`.
        -   `command`: The command and arguments to start the server, e.g., `["pylsp"]`.
        -   `file_patterns`: Glob patterns for files this server should activate for, e.g., `["*.py", "*.pyw"]`.

### 2. Standalone Linter Framework

**Goal:** Provide a direct, lightweight framework for code linting that runs external tools, as an alternative to a full LSP setup.

-   **Phase 1: Core Runner & Parser**
    -   [ ] **Asynchronous Task Runner:** Develop a central utility to execute command-line tools in a background thread and capture their output.
    -   [ ] **Extensible Output Parsers:** Create a system where plugins or configurations can define regular expressions or functions to parse the text output of various linters into a standardized diagnostic format (line, column, message, severity).

-   **Phase 2: UI & Configuration**
    -   [ ] **Diagnostic Display:** Use the same core diagnostic API built for LSP (Task 1.2) to display linting results, ensuring a consistent user experience.
    -   [ ] **"Problems" Panel:** Implement a dockable widget that aggregates and displays all diagnostics from both the LSP and standalone linters.
    -   [ ] **User Configuration:** Allow users to define and enable custom linters, their commands, and associated parsers via the `config.json` file.
