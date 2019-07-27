import shutil
import os
import sublime

from LSP.plugin.core.handlers import LanguageHandler
from LSP.plugin.core.settings import ClientConfig, LanguageConfig


package_path = os.path.dirname(__file__)
server_path = os.path.join(package_path, 'node_modules', 'vue-language-server', 'bin', 'vls')


def plugin_loaded():
    print('LSP-vue: Server {} installed.'.format('is' if os.path.isfile(server_path) else 'is not' ))

    if not os.path.isdir(os.path.join(package_path, 'node_modules')):
        # install server if no node_modules
        print('LSP-vue: Installing server.')
        sublime.active_window().run_command(
            "exec", {
                "cmd": [
                    "npm",
                    "install",
                    "--verbose",
                    "--prefix",
                    package_path
                ]
            }
        )
        sublime.message_dialog('LSP-vue\n\nRestart sublime after the server has been installed successfully.')


def is_node_installed():
    return shutil.which('node') is not None


class LspVuePlugin(LanguageHandler):
    @property
    def name(self) -> str:
        return 'lsp-vue'

    @property
    def config(self) -> ClientConfig:
        settings = sublime.load_settings("LSP-vue.sublime-settings")            
        return ClientConfig(
            name='lsp-vue',
            binary_args=[
                'node',
                server_path
            ],
            tcp_port=None,
            enabled=True,
            init_options={
                "config": settings.get('config')
            },
            settings=dict(),
            env=dict(),
            languages=[
                LanguageConfig(
                    'vue',
                    ['text.html.vue'],
                    ["Packages/Vue Syntax Highlight/Vue Component.sublime-syntax"]
                )
            ]
        )

    def on_start(self, window) -> bool:
        if not is_node_installed():
            sublime.status_message('Please install Node.js for the Vue Language Server to work.')
            return False
        return True

    def on_initialized(self, client) -> None:
        pass   # extra initialization here.
