from __future__ import annotations
from LSP.plugin import ClientConfig
from LSP.plugin import Notification
from LSP.plugin import WorkspaceFolder
from LSP.plugin.core.types import cast
from LSP.plugin.core.typing import Any, Callable, List, Optional, Mapping, Required, Tuple, TypedDict, Union
from LSP.plugin.core.protocol import Error, ExecuteCommandParams, LSPAny, Location
from LSP.plugin.locationpicker import LocationPicker
from lsp_utils import notification_handler
from lsp_utils import NpmClientHandler
import os
import sublime

PACKAGE_NAME = __package__
SERVER_DIRECTORY = 'server'
SERVER_NODE_MODULES = os.path.join(SERVER_DIRECTORY, 'node_modules')
SERVER_BINARY_PATH =  os.path.join(SERVER_NODE_MODULES, '@vue', 'language-server', 'bin', 'vue-language-server.js')

TypescriptTsserverCommandParams = TypedDict('TypescriptTsserverCommandParams', {
    'file': Required[str],
}, total=False)
TsserverRequestParams = Tuple[Tuple[int, str, Union[TypescriptTsserverCommandParams, List[str]]]]
ExecuteCommandResponse = TypedDict('ExecuteCommandResponse', {
    'body': LSPAny
})


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
            return None  # don't find the `typescript.tsdk` if it was set explicitly in LSP-volar.sublime-settings
        typescript_lib_path = cls.find_typescript_lib_path(workspace_folders[0].path)
        if not typescript_lib_path:
            return 'Could not resolve location of TypeScript package'
        configuration.init_options.set('typescript.tsdk', typescript_lib_path)
        return None

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

    @notification_handler('tsserver/request')
    def on_tsserver_request(self, params: TsserverRequestParams) -> None:
        session = self.weaksession()
        if not session:
            return
        manager = session.manager()
        if not manager:
            return
        seq, command_name, command_params = params[0]
        # some commands pass an object while other pass an array.
        filepath = command_params['file'] if isinstance(command_params, dict) else command_params[0]
        session = manager.get_session('LSP-typescript', filepath)
        if not session:
            print('[LSP-vue] LSP-typescript not found')
            self._on_execute_command_response(seq, {'body': None})
            return
        execute_command_params: ExecuteCommandParams = {
            'command': 'typescript.tsserverRequest',
            'arguments': [
                command_name,
                cast(LSPAny, command_params),
                { 'isAsync': True, 'lowPriority': True },
            ]
        }
        session.execute_command(execute_command_params, progress=False) \
            .then(lambda result: self._on_execute_command_response(seq, result))

    def _on_execute_command_response(self, seq: int, result: ExecuteCommandResponse | Error) -> None:
        session = self.weaksession()
        if not session:
            return
        body = None if isinstance(result, Error) else result['body']
        session.send_notification(Notification('tsserver/response', [[seq, body]]))
