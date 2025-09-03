from __future__ import annotations
from LSP.plugin import ClientConfig
from LSP.plugin import WorkspaceFolder
from LSP.plugin.core.protocol import Location
from LSP.plugin.core.typing import Any, Callable, List, Optional, Mapping
from LSP.plugin.locationpicker import LocationPicker
from lsp_utils import NpmClientHandler
import os
import sublime

PACKAGE_NAME = __package__
SERVER_DIRECTORY = 'server'
SERVER_NODE_MODULES = os.path.join(SERVER_DIRECTORY, 'node_modules')
SERVER_BINARY_PATH =  os.path.join(SERVER_NODE_MODULES, '@vue', 'language-server', 'bin', 'vue-language-server.js')

def plugin_loaded():
    LspVuePlugin.setup()


def plugin_unloaded():
    LspVuePlugin.cleanup()


class LspVuePlugin(NpmClientHandler):
    package_name = PACKAGE_NAME
    server_directory = SERVER_DIRECTORY
    server_binary_path = SERVER_BINARY_PATH

    @classmethod
    def required_node_version(cls) -> str:
        return '>=18'

    @classmethod
    def is_allowed_to_start(
        cls,
        window: sublime.Window,
        initiating_view: sublime.View,
        workspace_folders: List[WorkspaceFolder],
        configuration: ClientConfig
    ) -> Optional[str]:
        if configuration.init_options.get('typescript.tsdk'):
            return  # don't find the `typescript.tsdk` if it was set explicitly in LSP-volar.sublime-settings
        typescript_lib_path = cls.find_typescript_lib_path(workspace_folders[0].path)
        if not typescript_lib_path:
            return 'Could not resolve location of TypeScript package'
        configuration.init_options.set('typescript.tsdk', typescript_lib_path)

    @classmethod
    def on_pre_start(
        cls,
        window: sublime.Window,
        initiating_view: sublime.View,
        workspace_folders: list[WorkspaceFolder],
        configuration: ClientConfig,
    ) -> str | None:
        cls._support_vue_hybrid_mode(configuration)

    @classmethod
    def _support_vue_hybrid_mode(cls, configuration: ClientConfig) -> None:
        vue_hybrid_mode = bool(configuration.init_options.get('vue.hybridMode'))
        if not vue_hybrid_mode:
            return
        configuration.disabled_capabilities.update({
            "definitionProvider": True,
            "referencesProvider": True,
            "typeDefinitionProvider": True,
        })
        configuration.priority_selector = "text.html.vue source.js, text.html.vue source.ts"

    @classmethod
    def find_typescript_lib_path(cls, workspace_folder: str) -> Optional[str]:
        module_paths = [
            'node_modules/typescript/lib/tsserverlibrary.js',
            '.vscode/pnpify/typescript/lib/tsserverlibrary.js',
            '.yarn/sdks/typescript/lib/tsserverlibrary.js'
        ]
        for module_path in module_paths:
            candidate = os.path.join(workspace_folder, module_path)
            if os.path.isfile(candidate):
                return os.path.dirname(candidate)
        server_directory_path = cls._server_directory_path()
        return os.path.join(server_directory_path, 'node_modules', 'typescript', 'lib')

    def on_pre_server_command(self, command: Mapping[str, Any], done_callback: Callable[[], None]) -> bool:
        command_name = command['command']
        if command_name == 'editor.action.showReferences':
            _, __, references = command['arguments']
            self._handle_show_references(references)
            done_callback()
            return True
        return False

    def _handle_show_references(self, references: List[Location]) -> None:
        session = self.weaksession()
        if not session:
            return
        view = sublime.active_window().active_view()
        if not view:
            return
        if len(references) == 1:
            args = {
                'location': references[0],
                'session_name': session.config.name,
            }
            window = view.window()
            if window:
                window.run_command('lsp_open_location', args)
        elif references:
            LocationPicker(view, session, references, side_by_side=False)
        else:
            sublime.status_message('No references found')
