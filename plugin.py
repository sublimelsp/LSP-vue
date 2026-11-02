from __future__ import annotations

from LSP.plugin import Error
from LSP.plugin import IsApplicableContext
from LSP.plugin import LspPlugin
from LSP.plugin import OnPreStartContext
from LSP.plugin import parse_uri
from LSP.plugin import Promise
from LSP.plugin import Request
from LSP.plugin import request_handler
from LSP.plugin import Session
from LSP.plugin import uri_from_view
from LSP.plugin.core.registry import windows
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
    def is_applicable_async(cls, context: IsApplicableContext) -> bool:
        if not super().is_applicable_async(context):
            return False
        # LSP starts the sessions of a view one after another, and checks the view again after each one. If LSP-tsgo
        # has yet to start for this view, LSP-vue starts after it. Otherwise the first request of the server fails to
        # connect to the TypeScript API and the server shows an error.
        return not cls._is_typescript_session_pending(context)

    @classmethod
    def _is_typescript_session_pending(cls, context: IsApplicableContext) -> bool:
        view = context.view
        manager = windows.lookup(view.window())
        if not manager or manager.get_session(TYPESCRIPT_SESSION_NAME, view.file_name()):
            return False
        config = manager.get_config_manager().get_config(TYPESCRIPT_SESSION_NAME)
        if not config or not config.enabled:
            return False
        scheme, _ = parse_uri(uri_from_view(view))
        return config.match_view(view, scheme, manager.window, context.workspace_folders)

    @classmethod
    @override
    def on_pre_start_async(cls, context: OnPreStartContext) -> None:
        package_name = cls.plugin_storage_path.name
        server_directory = NodeManager.on_pre_start_async(
            context,
            cls.plugin_storage_path,
            ResourcePath('Packages', package_name, 'server'),
            Path('node_modules', '@vue', 'language-server', 'bin', 'vue-language-server.js'),
            # The same as LSP-tsgo
            node_version_requirement='^20.19.0 || >=22.12.0',
        )
        contributions = cls._read_content_mapper_contributions(package_name)
        # Without a managed server there is no content mapper to report.
        if server_directory and (window := context.view.window()):
            for contribution in contributions:
                window.run_command('lsp_tsgo_set_content_mapper_location', {
                    'name': contribution['name'],
                    'location': str(server_directory / 'node_modules'),
                })
        # The content mappers for files outside any tsconfig, the same ones that LSP-tsgo registers.
        if not context.configuration.initialization_options.get('contentMappers'):
            context.configuration.initialization_options.set('contentMappers', cls._to_content_mappers(contributions))

    @classmethod
    def _read_content_mapper_contributions(cls, package_name: str) -> list[dict[str, Any]]:
        resource = ResourcePath('Packages', package_name, 'typescript-content-mappers.json')
        try:
            return cast('list[dict[str, Any]]', sublime.decode_value(resource.read_text()))
        except (OSError, ValueError):
            log(f'Failed reading "{resource}"')
            return []

    @classmethod
    def _to_content_mappers(cls, contributions: list[dict[str, Any]]) -> list[dict[str, LSPAny]]:
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
        Connects the server to the TypeScript API of the LSP-tsgo session. LSP-vue starts after LSP-tsgo, so the session
        is usually available. If not, the server shows the error and asks again on its next request.
        """
        session = self.weaksession()
        manager = session.manager() if session else None
        if not session or not manager:
            raise Error(ErrorCodes.InternalError, 'The session has ended')
        folders = session.get_workspace_folders()
        # The LSP-tsgo session that handles the workspace of this session.
        if typescript_session := manager.get_session(TYPESCRIPT_SESSION_NAME, folders[0].path if folders else None):
            return self._initialize_api_session(typescript_session)
        if manager.is_session_starting():
            # LSP starts the sessions of a view one after another, so LSP-tsgo can still be installing or starting.
            raise Error(ErrorCodes.InternalError, f'{TYPESCRIPT_SESSION_NAME} has not started yet')
        raise Error(
            ErrorCodes.InternalError,
            f'{TYPESCRIPT_SESSION_NAME} is not running. Install it and make sure that `runExternalCode` is not '
            'disabled in its settings.',
        )

    def _initialize_api_session(self, typescript_session: Session) -> Promise[TypeScriptApiConnection | None]:
        """
        Opens a session of the TypeScript API on the LSP-tsgo server. LSP-tsgo adds `packageJsonPath`, the
        `package.json` of the TypeScript installation that runs its server, to the response.
        """

        def on_result(result: dict[str, Any] | Error | None) -> Promise[TypeScriptApiConnection | None]:
            if isinstance(result, Error):
                self._log_failure(f'Failed to connect to the TypeScript API: {result}')
                return Promise.resolve(None)
            if not result or not isinstance(result.get('pipe'), str):
                self._log_failure(f'{TYPESCRIPT_SESSION_NAME} returned no TypeScript API pipe')
                return Promise.resolve(None)
            if not isinstance(result.get('packageJsonPath'), str):
                self._log_failure(
                    f'{TYPESCRIPT_SESSION_NAME} returned no TypeScript package.json. Update it or check its '
                    '`server_path` setting.'
                )
                return Promise.resolve(None)
            return Promise.resolve({'pipe': result['pipe'], 'packageJsonPath': result['packageJsonPath']})

        request = Request('custom/initializeAPISession', {})
        return typescript_session.send_request_task(request).then(on_result)

    def _log_failure(self, message: str) -> Promise[None]:
        log(message)
        # LSP only sends an error response for an `Error` that a request handler raises synchronously. When the
        # returned promise resolves, LSP sends its value as the result, and an `Error` can't be serialized. So an
        # asynchronous failure replies `null`: the server shows a generic error and asks again on its next request.
        # TODO: Resolve with the `Error` when `Session.send_response` sends it as an error response.
        return Promise.resolve(None)
