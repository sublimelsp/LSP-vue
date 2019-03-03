import shutil

import sublime
import sublime_plugin
from LSP.plugin.core.handlers import LanguageHandler
from LSP.plugin.core.settings import ClientConfig, LanguageConfig

default_name = 'vue'
server_package_name = 'vue-language-server'

default_config = ClientConfig(
    name=default_name,
    binary_args=[
        'vls'
    ],
    tcp_port=None,
    enabled=True,
    init_options=dict(),
    settings={
        "vetur": {
            "validation": {
                "template": True,
                "style": True,
                "script": True,
            },
            "completion": {
                "autoImport": False,
                "useScaffoldSnippets": False,
            },
            "format": {
                "defaultFormatter": {
                    "js": 'prettier',
                    "ts": 'prettier',
                },
                "defaultFormatterOptions": {},
                "scriptInitialIndent": False,
                "styleInitialIndent": False,
            },
        },
        "css": {},
        "html": {
            "suggest": {}
        },
        "javascript": {
            "format": {}
        },
        "typescript": {
            "format": {}
        },
        "emmet": {},
        "stylusSupremacy": {},
    },
    env=dict(),
    languages=[
        LanguageConfig(
            'vue',
            ['text.html.vue'],
            ["Packages/Vue Syntax Highlight/Vue Component.sublime-syntax"]
        )
    ]
)

# Dependencies that needs to be installed for the server to work
dependencies = ['node', 'vls']


def is_installed(dependency):
    return shutil.which(dependency) is not None


class LspVueSetupCommand(sublime_plugin.WindowCommand):
    def is_visible(self):
        if not is_installed('node') or not is_installed('vls'):
            return True
        return False

    def run(self):
        if not is_installed('node'):
            sublime.message_dialog(
                "Please install Node.js before running setup."
            )
            return

        if not is_installed('vls'):
            should_install = sublime.ok_cancel_dialog(
                "vls was not in the PATH.\nInstall {} globally now?".format(
                    server_package_name)
            )
            if should_install:
                self.window.run_command(
                    "exec", {
                        "cmd": [
                            "npm",
                            "install",
                            "--verbose",
                            "-g",
                            server_package_name
                        ]
                    })
        else:
            sublime.message_dialog(
                "{} is already installed".format(server_package_name)
            )


class LspVuePlugin(LanguageHandler):
    def __init__(self):
        self._name = default_name
        self._config = default_config

    @property
    def name(self) -> str:
        return self._name

    @property
    def config(self) -> ClientConfig:
        return self._config

    def on_start(self, window) -> bool:
        for dependency in dependencies:
            if not is_installed(dependency):
                sublime.status_message('Run: LSP: Setup Vue server')
                return False
        return True

    def on_initialized(self, client) -> None:
        pass   # extra initialization here.
