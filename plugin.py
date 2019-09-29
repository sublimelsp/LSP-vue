import shutil
import os
import sublime
import threading
import subprocess

from LSP.plugin.core.handlers import LanguageHandler
from LSP.plugin.core.settings import ClientConfig, LanguageConfig, read_client_config


package_path = os.path.dirname(__file__)
server_path = os.path.join(package_path, 'node_modules', 'vue-language-server', 'bin', 'vls')


def plugin_loaded():
    is_server_installed = os.path.isfile(server_path)
    print('LSP-vue: Server {} installed.'.format('is' if is_server_installed else 'is not' ))

    # install if not installed
    if not is_server_installed:
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


def update_to_new_configuration(settings, old_config, new_config):
    # add old config to new config
    new_config['initializationOptions']['config'] = old_config
    settings.set('client', new_config)
    # remove old config
    settings.erase('config')
    sublime.save_settings("LSP-vue.sublime-settings")

class LspVuePlugin(LanguageHandler):
    @property
    def name(self) -> str:
        return 'lsp-vue'

    @property
    def config(self) -> ClientConfig:
        settings = sublime.load_settings("LSP-vue.sublime-settings")
        # TODO: remove update_to_new_configuration after 1 November.
        old_config = settings.get('config')
        client_configuration = settings.get('client')
        if old_config:
            update_to_new_configuration(settings, old_config, client_configuration)

        default_configuration = {
            "command": [
                'node',
                server_path,
                '--stdio'
            ],
            "languages": [
                {
                    "languageId": "vue",
                    "scopes": ["text.html.vue"],
                    "syntaxes": ["Packages/Vue Syntax Highlight/Vue Component.sublime-syntax"]
                }
            ]
        }
        default_configuration.update(client_configuration)
        view = sublime.active_window().active_view()
        if view is not None:
            options = default_configuration['initializationOptions']['config']['vetur']['format']['options']
            options['tabSize'] = view.settings().get("tab_size", 4)
            options['useTabs'] = not view.settings().get("translate_tabs_to_spaces", False)

        return read_client_config('lsp-vue', default_configuration)

    def on_start(self, window) -> bool:
        if not is_node_installed():
            sublime.status_message('Please install Node.js for the Vue Language Server to work.')
            return False
        return True

    def on_initialized(self, client) -> None:
        pass   # extra initialization here.
