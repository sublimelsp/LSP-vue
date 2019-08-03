import shutil
import os
import sublime
import threading
import subprocess

from LSP.plugin.core.handlers import LanguageHandler
from LSP.plugin.core.settings import ClientConfig, LanguageConfig


package_path = os.path.dirname(__file__)
server_path = os.path.join(package_path, 'node_modules', 'vue-language-server', 'bin', 'vls')


def plugin_loaded():
    print('LSP-vue: Server {} installed.'.format('is' if os.path.isfile(server_path) else 'is not' ))

    # install the node_modules if not installed
    if not os.path.isdir(os.path.join(package_path, 'node_modules')):
        # this will be called only when the plugin gets:
        # - installed for the first time,
        # - or when updated on package control
        logAndShowMessage('LSP-vue: Installing server.')

        runCommand(
            onCommandDone,
            ["npm", "install", "--verbose", "--prefix", package_path, package_path]
        )


def onCommandDone():
    logAndShowMessage('LSP-vue: Server installed.')


def runCommand(onExit, popenArgs):
    """
    Runs the given args in a subprocess.Popen, and then calls the function
    onExit when the subprocess completes.
    onExit is a callable object, and popenArgs is a list/tuple of args that
    would give to subprocess.Popen.
    """
    def runInThread(onExit, popenArgs):
        try:
            if sublime.platform() == 'windows':
                subprocess.check_call(popenArgs, shell=True)
            else:
                subprocess.check_call(popenArgs)
            onExit()
        except subprocess.CalledProcessError as error:
            logAndShowMessage('LSP-vue: Error while installing the server.', error)
        return
    thread = threading.Thread(target=runInThread, args=(onExit, popenArgs))
    thread.start()
    # returns immediately after the thread starts
    return thread


def is_node_installed():
    return shutil.which('node') is not None


def logAndShowMessage(msg, additional_logs=None):
    print(msg, '\n', additional_logs) if additional_logs else print(msg)
    sublime.active_window().status_message(msg)


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
