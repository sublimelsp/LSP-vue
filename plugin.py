from __future__ import annotations
import re
from LSP.plugin import ClientConfig, Notification, WorkspaceFolder
from LSP.plugin.core.types import cast
from LSP.plugin.core.typing import Any, Callable, List, Mapping, Required, Tuple, TypedDict, Union
from LSP.plugin.core.protocol import Error, ExecuteCommandParams, LSPAny, Location
from LSP.plugin.locationpicker import LocationPicker
from lsp_utils import notification_handler
from lsp_utils import NpmClientHandler
from pathlib import Path
import sublime

PACKAGE_NAME = __package__
SERVER_DIRECTORY = 'server'
SERVER_NODE_MODULES = Path(SERVER_DIRECTORY) / 'node_modules'
SERVER_VUE_3_BINARY_PATH =  SERVER_NODE_MODULES / '@vue' / 'language-server' / 'bin' / 'vue-language-server.js'
SERVER_VUE_2_BINARY_PATH =  SERVER_NODE_MODULES / '@vue2' / 'language-server' / 'bin' / 'vue-language-server.js'


class TypescriptTsserverCommandParams(TypedDict):
    file: Required[str]

TsserverRequestParams = Tuple[Tuple[int, str, Union[TypescriptTsserverCommandParams, List[str]]]]


def plugin_loaded():
    LspVuePlugin.setup()


def plugin_unloaded():
    LspVuePlugin.cleanup()


class LspVuePlugin(NpmClientHandler):
    package_name = PACKAGE_NAME
    server_directory = SERVER_DIRECTORY
    server_binary_path = SERVER_VUE_3_BINARY_PATH

    @classmethod
    def required_node_version(cls) -> str:
        return '>=18'

    @classmethod
    def on_pre_start(cls, window: sublime.Window, initiating_view: sublime.View,
                     workspace_folders: list[WorkspaceFolder], configuration: ClientConfig) -> str | None:
        vue_version = configuration.settings.get('vue.version')
        version_to_use = 3
        if vue_version == 'vue3':
            version_to_use = 3
        elif vue_version == 'vue2':
            version_to_use = 2
        elif vue_version == 'auto' and workspace_folders:
            first_folder = workspace_folders[0]
            package_json = Path(first_folder.path) / 'package.json'
            if not package_json.exists():
                return
            with package_json.open(encoding="utf-8") as file:
                contents = file.read()
                json = sublime.decode_value(contents)
                vue_version_in_package_json = json.get('dependencies', {}).get('vue', '')
                major_version = re.search('[0-9]+', json.get('dependencies', {}).get('vue', '')).group()
                version_to_use = major_version
            print(f'LSP-vue: Will use the language server that supports Vue version {version_to_use}')
            # if major_version == 3: we don't need to do this
            #     configuration.command[1] = str(Path(cls.package_storage()) / SERVER_VUE_3_BINARY_PATH)
            if version_to_use == 2:
                configuration.command[1] = str(Path(cls.package_storage()) / SERVER_VUE_2_BINARY_PATH)

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
            print('[LSP-vue] LSP-typescript not found or has not loaded the Vue Plugin. Try restarting ST.')
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

    def _on_execute_command_response(self, seq: int, result: LSPAny | Error) -> None:
        session = self.weaksession()
        if not session:
            return
        body = result['body'] if isinstance(result, dict) and 'body' in result else None
        session.send_notification(Notification('tsserver/response', [[seq, body]]))
