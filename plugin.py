from __future__ import annotations

from LSP.plugin import Error
from LSP.plugin import LspPlugin
from LSP.plugin import OnPreStartContext
from LSP.plugin import Promise
from LSP.plugin import request_handler
from LSP.plugin import Session
from LSP.protocol import ErrorCodes
from LSP.protocol import LSPAny
from lsp_utils import NodeManager
from pathlib import Path
from sublime_lib import ResourcePath
from typing import Any
from typing import Callable
from typing import cast
from typing import final
from typing import TypedDict
from typing_extensions import override
import sublime
import time

# The session that runs the TypeScript 7 language server, with the Vue content mapper.
TYPESCRIPT_SESSION_NAME = 'LSP-tsgo'
# How long to wait for that session, which can include installing its server.
SESSION_START_TIMEOUT_S = 180
SESSION_POLL_INTERVAL_MS = 250


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
        if typescript_session := self._get_typescript_session():
            return self._initialize_api_session(typescript_session)
        if not self._is_session_starting():
            raise Error(
                ErrorCodes.InternalError,
                f'{TYPESCRIPT_SESSION_NAME} is not running. Install it and make sure that `runExternalCode` is not '
                'disabled in its settings.',
            )
        # LSP starts the sessions of a view one after another, so LSP-tsgo can still be installing or starting. The
        # server waits for the response.
        return self._wait_for_typescript_session().then(
            lambda typescript_session: self._initialize_api_session(typescript_session) if typescript_session
            else self._log_failure(f'{TYPESCRIPT_SESSION_NAME} did not start')
        )

    def _get_typescript_session(self) -> Session | None:
        session = self.weaksession()
        manager = session.manager() if session else None
        return manager.get_session(TYPESCRIPT_SESSION_NAME) if manager else None

    def _is_session_starting(self) -> bool:
        session = self.weaksession()
        manager = session.manager() if session else None
        # Older LSP versions don't tell, so assume that the session is starting until the timeout.
        is_session_starting = getattr(manager, 'is_session_starting', None)
        return bool(manager) and (not is_session_starting or is_session_starting())

    def _wait_for_typescript_session(self) -> Promise[Session | None]:
        deadline = time.monotonic() + SESSION_START_TIMEOUT_S

        def poll(resolve: Callable[[Session | None], None]) -> None:
            if typescript_session := self._get_typescript_session():
                resolve(typescript_session)
            elif not self._is_session_starting() or time.monotonic() > deadline:
                resolve(None)
            else:
                sublime.set_timeout_async(lambda: poll(resolve), SESSION_POLL_INTERVAL_MS)

        return Promise(poll)

    def _initialize_api_session(self, typescript_session: Session) -> Promise[TypeScriptApiConnection | None]:
        initialize_api_session = getattr(typescript_session.plugin, 'initialize_api_session', None)
        if not initialize_api_session:
            return self._log_failure(f'{TYPESCRIPT_SESSION_NAME} does not support the TypeScript API. Update it.')

        def on_result(result: TypeScriptApiConnection | Error) -> TypeScriptApiConnection | None:
            if isinstance(result, Error):
                log(f'Failed to connect to the TypeScript API: {result}')
                return None
            return result

        return cast('Promise[TypeScriptApiConnection | Error]', initialize_api_session()).then(on_result)

    def _log_failure(self, message: str) -> Promise[None]:
        # A request handler can't send an error response asynchronously, so the server gets no result instead and
        # asks again on its next request.
        log(message)
        return Promise.resolve(None)
