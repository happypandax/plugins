import json
import glob
import pathlib
from urllib.parse import quote

readme = """
#### In this repository resides plugins for HappyPanda X. If you wish to write a plugin for HPX head over to [the docs](https://happypandax.github.io/plugin.html#plugins).

### How to download

I recommend these tools to download a single directory from this repo:
- https://minhaskamal.github.io/DownGit/ -- *Paste the url to the plugin folder in this repo*
- https://kinolien.github.io/gitzip/ -- *Paste the url to the plugin folder in this repo*
- [Firefox Addon](https://addons.mozilla.org/en-US/firefox/addon/gitzip/)
- [Chrome Extension](https://chrome.google.com/webstore/detail/gitzip-for-github/ffabmkklhbepgcgfonabamgnfafbdlkn)

### How to install

Please see [#Installing plugins](https://happypandax.github.io/usage.html#installing-plugins) in the documentation.

# Be careful about plugins

Read the relevant section [#Be careful about plugins](https://happypandax.github.io/usage.html#be-careful-about-plugins) in the documentation

# Plugins

{}

"""

plugins_dir = "plugins"
readme_file = "README.md"
desc_max_length = 200
repo_user = "happypandax"
repo_name = "plugins"

def main():
    print("Building...")
    plugin_readme = "Name | Version | Description\n--- | --- | ---\n"

    for p in sorted(glob.glob(f"{plugins_dir}/**/hplugin.json")):
        with open(p, 'r', encoding="utf-8") as f:
            d = json.load(f)
            plugin_dir = pathlib.Path(p).parent
            dir_name = plugin_dir.name
            plugin_dir = str(plugin_dir).replace('\\', '/')
            plugin_desc = d.get("description")
            plugin_ver = d.get("version")

            gh_url = f"https://github.com/{repo_user}/{repo_name}/tree/master/{quote(plugin_dir)}"

            if plugin_desc and plugin_ver:
                plugin_desc = plugin_desc.split('\n')[0]
                if len(plugin_desc) > desc_max_length:
                    plugin_desc = plugin_desc[:desc_max_length] + '…'
                plugin_readme += f"[**{dir_name}**]({gh_url}) | `{plugin_ver}` | *{plugin_desc}*\n"

    txt = readme.format(plugin_readme)

    with open(readme_file, 'w', encoding="utf-8") as f:
        f.write(txt)
    print("Done!")

if __name__ == '__main__':
    main()