from __future__ import annotations

from LSP.plugin import Notification
from LSP.plugin.core.protocol import Error
from LSP.plugin.locationpicker import LocationPicker
from LSP.protocol import ExecuteCommandParams
from LSP.protocol import Location
from LSP.protocol import LSPAny
from lsp_utils import notification_handler
from lsp_utils import NpmClientHandler
from pathlib import Path
from typing import Any
from typing import Callable
from typing import cast
from typing import final
from typing import List
from typing import Tuple
from typing import TypedDict
from typing import Union
from typing_extensions import override
import sublime

PACKAGE_NAME = str(__package__)
SERVER_DIRECTORY = 'server'
SERVER_NODE_MODULES = Path(SERVER_DIRECTORY) / 'node_modules'
SERVER_BINARY_PATH = SERVER_NODE_MODULES / '@vue' / 'language-server' / 'bin' / 'vue-language-server.js'


class TypescriptTsserverCommandParams(TypedDict):
    file: str


TsserverRequestParams = Tuple[Tuple[int, str, Union[TypescriptTsserverCommandParams, List[str]]]]


def plugin_loaded():
    LspVuePlugin.setup()


def plugin_unloaded():
    LspVuePlugin.cleanup()


@final
class LspVuePlugin(NpmClientHandler):
    package_name = PACKAGE_NAME
    server_directory = SERVER_DIRECTORY
    server_binary_path = str(SERVER_BINARY_PATH)

    @classmethod
    @override
    def required_node_version(cls) -> str:
        return '>=18'

    @override
    def on_pre_server_command(self, command: ExecuteCommandParams, done_callback: Callable[[], None]) -> bool:
        command_name = command['command']
        if command_name == 'editor.action.showReferences':
            _, __, references = command.get('arguments', [None, None, None])
            self._handle_show_references(cast(list[Location], references))
            done_callback()
            return True
        return False

    def _handle_show_references(self, references: list[Location]) -> None:
        session = self.weaksession()
        if not session:
            return
        view = sublime.active_window().active_view()
        if not view:
            return
        if len(references) == 1:
            window = view.window()
            if window:
                args: dict[str, Any] = {
                    'location': references[0],
                    'session_name': session.config.name,
                }
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
                command_params,
                {'isAsync': True, 'lowPriority': True},
            ]
        }
        session.execute_command(execute_command_params, progress=False).then(
            lambda result: self._on_execute_command_response(seq, result)
        )

    def _on_execute_command_response(self, seq: int, result: LSPAny | Error) -> None:
        session = self.weaksession()
        if not session:
            return
        body = result['body'] if isinstance(result, dict) and 'body' in result else None
        session.send_notification(Notification('tsserver/response', [[seq, body]]))
