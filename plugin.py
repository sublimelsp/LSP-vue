import os
import sublime
from lsp_utils import NpmClientHandler


def plugin_loaded():
    LspVuePlugin.setup()


def plugin_unloaded():
    LspVuePlugin.cleanup()


class LspVuePlugin(NpmClientHandler):
    package_name = __package__
    server_directory = 'server'
    server_binary_path = os.path.join(server_directory, 'node_modules', 'vue-language-server', 'bin', 'vls')

    @classmethod
    def configuration(cls) -> sublime.Settings:
        settings = super().configuration()
        options = settings.get('initializationOptions', {})
        cls._add_formatting_options(options)
        settings.set('initializationOptions', options)
        return settings

    def on_client_configuration_ready(cls, configuration: dict):
        self._add_formatting_options(configuration)

    @classmethod
    def _add_formatting_options(cls, configuration: dict) -> None:
        view = sublime.active_window().active_view()
        if view:
            view_settings = view.settings()
            configuration \
                .setdefault('initializationOptions', {}) \
                .setdefault('config', {}) \
                .setdefault('vetur', {}) \
                .setdefault('format', {}) \
                .setdefault('options', {}) \
                .update({
                    'tabSize': view_settings.get('tab_size', 4),
                    'useTabs': not view_settings.get('translate_tabs_to_spaces', False)
                })
