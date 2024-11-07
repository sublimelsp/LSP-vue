# LSP-vue

This is a helper package that automatically installs and updates the [Vue Language Server (formerly Volar)](https://github.com/vuejs/language-tools) for you.

## Table of Contents
  - [Installation](#installation)
  - [Configuration](#configuration)
  - [Take over mode 🤝](#enable-for-non-vue-files)
  - [Inlay hints](#inlay-hints)
  - [Vue 2 support](#vue-2-support)

### Installation

* Install [LSP](https://packagecontrol.io/packages/LSP), [Vue Syntax Highlight](https://packagecontrol.io/packages/Vue%20Syntax%20Highlight) and [LSP-vue](https://packagecontrol.io/packages/LSP-vue) from Package Control.
* Restart Sublime.

### Configuration

Open the configuration file using Command Palette with `Preferences: LSP-vue Settings` command or opening it from the Sublime menu (`Preferences > Package Settings > LSP > Servers > LSP-vue`).

### Inlay hints

Inlay hints are short textual annotations that show parameter names, type hints.

![inlay-hints](./images/inlay-hints.png)

To enable inlay hints:
1. Open the command palette and select `Preferences: LSP Settings`, then enable `show_inlay_hints`:
```js
{
    "show_inlay_hints": true
}
```

2. Modify the following settings through `Preferences: LSP-vue Settings`:

```js
{
  "settings": {
    // javascript inlay hints options.
    "javascript.inlayHints.enumMemberValues.enabled": false,
    "javascript.inlayHints.functionLikeReturnTypes.enabled": false,
    "javascript.inlayHints.parameterNames.enabled": "none",
    "javascript.inlayHints.parameterNames.suppressWhenArgumentMatchesName": false,
    "javascript.inlayHints.parameterTypes.enabled": false,
    "javascript.inlayHints.propertyDeclarationTypes.enabled": false,
    "javascript.inlayHints.variableTypes.enabled": false,
    // typescript inlay hints options.
    "typescript.inlayHints.enumMemberValues.enabled": false,
    "typescript.inlayHints.functionLikeReturnTypes.enabled": false,
    "typescript.inlayHints.parameterNames.enabled": "none",
    "typescript.inlayHints.parameterNames.suppressWhenArgumentMatchesName": false,
    "typescript.inlayHints.parameterTypes.enabled": false,
    "typescript.inlayHints.propertyDeclarationTypes.enabled": false,
    "typescript.inlayHints.variableTypes.enabled": false,
  }
}
```

> NOTE: Inlay hints require TypeScript 4.4+.
