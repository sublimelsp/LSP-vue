from LSP.plugin import DottedDict
from lsp_utils import NpmClientHandler
import os
import sublime


def plugin_loaded() -> None:
    LspVuePlugin.setup()


def plugin_unloaded() -> None:
    LspVuePlugin.cleanup()


class LspVuePlugin(NpmClientHandler):
    package_name = __package__
    server_directory = 'server'
    server_binary_path = os.path.join(server_directory, 'node_modules', 'vls', 'bin', 'vls')

    def on_settings_changed(self, settings: DottedDict) -> None:
        view = sublime.active_window().active_view()
        if view:
            view_settings = view.settings()
            settings.update({
                'vetur.format.options.tabSize': view_settings.get('tab_size', 4),
                'vetur.format.options.useTabs': not view_settings.get('translate_tabs_to_spaces', False),
            })
