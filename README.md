# LSP-vue

Vue support for Sublime's LSP plugin.

* Install [LSP](https://packagecontrol.io/packages/LSP), [Vue Syntax Highlight](https://packagecontrol.io/packages/Vue%20Syntax%20Highlight) and `LSP-vue` from Package Control.
* Restart Sublime.

### Configuration

Configure the vue language server by accessing `Preferences > Package Settings > LSP > Servers > LSP-vue`.
The default configuration:

```json
{
	"config": {
		"vetur": {
			"completion": {
				"autoImport": false,
				"tagCasing": "kebab",
				"useScaffoldSnippets": false
			},
			"format": {
				"defaultFormatter": {
					"js": "none",
					"ts": "none"
				},
				"defaultFormatterOptions": {},
				"scriptInitialIndent": false,
				"styleInitialIndent": false
			},
			"useWorkspaceDependencies": false,
			"validation": {
				"script": true,
				"style": true,
				"template": true
			}
		},
		"css": {},
		"emmet": {},
		"stylusSupremacy": {},
		"html": {
			"suggest": {}
		},
		"javascript": {
			"format": {}
		},
		"typescript": {
			"format": {}
		}
	}
}
```