from __future__ import annotations

from LSP.plugin import LspPlugin
from LSP.plugin import Notification
from LSP.plugin import notification_handler
from LSP.plugin import OnPreStartContext
from LSP.plugin.core.protocol import Error
from LSP.protocol import ExecuteCommandParams
from LSP.protocol import LSPAny
from lsp_utils import NodeManager
from pathlib import Path
from sublime_lib import ResourcePath
from typing import final
from typing import List
from typing import Tuple
from typing import TypedDict
from typing import Union
from typing_extensions import override


class TypescriptTsserverCommandParams(TypedDict):
    file: str


TsserverRequestParams = Tuple[Tuple[int, str, Union[TypescriptTsserverCommandParams, List[str]]]]


def plugin_loaded():
    LspVuePlugin.register()


def plugin_unloaded():
    LspVuePlugin.unregister()


@final
class LspVuePlugin(LspPlugin):

    @classmethod
    @override
    def on_pre_start_async(cls, context: OnPreStartContext) -> None:
        package_name = cls.plugin_storage_path.name
        NodeManager.on_pre_start_async(
            context,
            cls.plugin_storage_path,
            ResourcePath('Packages', package_name, 'server'),
            Path('node_modules', '@vue', 'language-server', 'bin', 'vue-language-server.js'),
            node_version_requirement='>=18',
        )

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
        if session := self.weaksession():
            body = result['body'] if isinstance(result, dict) and 'body' in result else None
            session.send_notification(Notification('tsserver/response', [[seq, body]]))
