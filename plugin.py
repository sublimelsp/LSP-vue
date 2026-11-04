from __future__ import annotations

from LSP.plugin import Error
from LSP.plugin import LspPlugin
from LSP.plugin import Notification
from LSP.plugin import notification_handler
from LSP.plugin import OnPreStartContext
from LSP.protocol import ExecuteCommandParams
from LSP.protocol import LSPAny
from lsp_utils import NodeManager
from pathlib import Path
from sublime_lib import ResourcePath
from typing import cast
from typing import final
from typing import List
from typing import Tuple
from typing import TypedDict
from typing import Union
from typing_extensions import override
import sublime


class TypescriptTsserverCommandParams(TypedDict):
    file: str


TsserverRequestParams = Tuple[Tuple[int, str, Union[TypescriptTsserverCommandParams, List[str]]]]

TYPESCRIPT_PLUGIN_NAME = '@vue/typescript-plugin'


def log(message: str) -> None:
    print(f'[{__package__}] {message}')


def find_node_modules_with(path: Path, package_name: str) -> Path | None:
    """Return the `node_modules` directory that Node.js would load `package_name` from, for a module at `path`."""
    path = path.resolve()
    for directory in path.parents:
        node_modules = directory / 'node_modules'
        if (node_modules / package_name / 'package.json').is_file():
            return node_modules
    return None


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
        cls._register_typescript_plugin(context)

    @classmethod
    def _register_typescript_plugin(cls, context: OnPreStartContext) -> None:
        # The plugin must match the version of the server, which can be a custom one set with `server_path`, so it's
        # loaded from the server's dependencies.
        if not (window := context.view.window()):
            return
        server_path = cast('str', sublime.expand_variables(context.variables['server_path'], context.variables))
        if not (location := find_node_modules_with(Path(server_path), TYPESCRIPT_PLUGIN_NAME)):
            log(f'No "{TYPESCRIPT_PLUGIN_NAME}" for the server at "{server_path}". TypeScript in Vue files won\'t work.')
            return
        window.run_command('lsp_typescript_register_plugin', {
            'name': TYPESCRIPT_PLUGIN_NAME,
            'location': str(location),
            'languages': ['vue'],
            'selector': 'text.html.vue',
        })

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
