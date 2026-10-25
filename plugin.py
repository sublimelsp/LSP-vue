from __future__ import annotations

from LSP.plugin import Error
from LSP.plugin import LspPlugin
from LSP.plugin import OnPreStartContext
from LSP.plugin import Promise
from LSP.plugin import request_handler
from LSP.protocol import ErrorCodes
from LSP.protocol import LSPAny
from lsp_utils import NodeManager
from pathlib import Path
from sublime_lib import ResourcePath
from typing import Any
from typing import cast
from typing import final
from typing import TypedDict
from typing_extensions import override
import sublime

# The session that runs the TypeScript 7 language server, with the Vue content mapper.
TYPESCRIPT_SESSION_NAME = 'LSP-tsgo'


class TypeScriptApiConnection(TypedDict):
    pipe: str
    packageJsonPath: str


def log(message: str) -> None:
    print(f'[{__package__}] {message}')


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
        # The server runs on the API of TypeScript 5 or 6, which the `typescript` package of TypeScript 7 doesn't have.
        # The server directory installs TypeScript 6 as `typescript-6`.
        node_modules = Path(context.variables['server_path']).parents[3]
        typescript_sdk = node_modules / 'typescript-6' / 'lib'
        if not typescript_sdk.is_dir():
            typescript_sdk = node_modules / 'typescript' / 'lib'
        context.variables['typescript_sdk'] = str(typescript_sdk)
        # The content mappers for files outside any tsconfig, the same ones that LSP-tsgo registers.
        if not context.configuration.initialization_options.get('contentMappers'):
            context.configuration.initialization_options.set('contentMappers', cls._get_content_mappers(package_name))

    @classmethod
    def _get_content_mappers(cls, package_name: str) -> list[dict[str, LSPAny]]:
        resource = ResourcePath('Packages', package_name, 'typescript-content-mappers.json')
        try:
            contributions = cast('list[dict[str, Any]]', sublime.decode_value(resource.read_text()))
        except (OSError, ValueError):
            log(f'Failed reading "{resource}"')
            return []
        return [
            {
                'package': contribution['name'],
                'extensions': contribution['extensions'],
                'options': contribution.get('options', {}),
            } for contribution in contributions
        ]

    @request_handler('vue/typescriptApiConnection')
    def on_typescript_api_connection(self, _: None) -> Promise[TypeScriptApiConnection | None]:
        """
        Connects the server to the TypeScript API of the LSP-tsgo session. The server asks again after a failure, for
        example when LSP-tsgo has not started yet.
        """
        session = self.weaksession()
        manager = session.manager() if session else None
        typescript_session = manager.get_session(TYPESCRIPT_SESSION_NAME) if manager else None
        if not typescript_session:
            raise Error(ErrorCodes.InternalError, f'{TYPESCRIPT_SESSION_NAME} is not running')
        initialize_api_session = getattr(typescript_session.plugin, 'initialize_api_session', None)
        if not initialize_api_session:
            raise Error(ErrorCodes.InternalError, f'{TYPESCRIPT_SESSION_NAME} does not support the TypeScript API')

        def on_result(result: TypeScriptApiConnection | Error) -> TypeScriptApiConnection | None:
            # A request handler can't send an error response asynchronously, so the server gets no result instead.
            if isinstance(result, Error):
                log(f'Failed to connect to the TypeScript API: {result}')
                return None
            return result

        return cast('Promise[TypeScriptApiConnection | Error]', initialize_api_session()).then(on_result)
