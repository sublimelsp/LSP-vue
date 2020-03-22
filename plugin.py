import os
import shutil
import sublime

from LSP.plugin.core.handlers import LanguageHandler
from LSP.plugin.core.settings import ClientConfig, read_client_config
from lsp_utils import ServerNpmResource

PACKAGE_NAME = 'LSP-vue'
SETTINGS_FILENAME = 'LSP-vue.sublime-settings'
SERVER_DIRECTORY = 'server'
SERVER_BINARY_PATH = os.path.join(SERVER_DIRECTORY, 'node_modules', 'vue-language-server', 'bin', 'vls')

server = ServerNpmResource(PACKAGE_NAME, SERVER_DIRECTORY, SERVER_BINARY_PATH)


def plugin_loaded():
    server.setup()


def plugin_unloaded():
    server.cleanup()


def is_node_installed():
    return shutil.which('node') is not None


class LspVuePlugin(LanguageHandler):
    @property
    def name(self) -> str:
        return PACKAGE_NAME.lower()

    @property
    def config(self) -> ClientConfig:
        # Calling setup() also here as this might run before `plugin_loaded`.
        # Will be a no-op if already ran.
        # See https://github.com/sublimelsp/LSP/issues/899
        server.setup()

        configuration = self.migrate_and_read_configuration()

        default_configuration = {
            'enabled': True,
            'command': ['node', server.binary_path, '--stdio'],
        }

        default_configuration.update(configuration)

        view = sublime.active_window().active_view()
        if view:
            view_settings = view.settings()
            default_configuration \
                .setdefault('initializationOptions', {}) \
                .setdefault('config', {}) \
                .setdefault('vetur', {}) \
                .setdefault('format', {}) \
                .setdefault('options', {}) \
                .update({
                    'tabSize': view_settings.get('tab_size', 4),
                    'useTabs': not view_settings.get('translate_tabs_to_spaces', False)
                })

        return read_client_config(self.name, default_configuration)

    def migrate_and_read_configuration(self) -> dict:
        settings = {}
        loaded_settings = sublime.load_settings(SETTINGS_FILENAME)

        if loaded_settings:
            if loaded_settings.has('client'):
                client = loaded_settings.get('client')
                loaded_settings.erase('client')
                # Migrate old keys
                for key in client:
                    loaded_settings.set(key, client[key])
                sublime.save_settings(SETTINGS_FILENAME)

            # Read configuration keys
            for key in ['languages', 'initializationOptions', 'settings']:
                settings[key] = loaded_settings.get(key)

        return settings

    def on_start(self, window) -> bool:
        if not is_node_installed():
            sublime.status_message('Please install Node.js for the Vue Language Server to work.')
            return False
        return server.ready

    def on_initialized(self, client) -> None:
        pass   # extra initialization here.
