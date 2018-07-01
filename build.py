import json
import glob
import pathlib

readme = """
In this repository resides plugins for HappyPanda X

# How to download

I recommend these tools to download a single directory from this repo:
- https://kinolien.github.io/gitzip/ -- *Paste the url to the plugin folder*
- https://minhaskamal.github.io/DownGit/ -- *Paste the url to the plugin folder*
- [Firefox Addon](https://addons.mozilla.org/en-US/firefox/addon/gitzip/)
- [Chrome Extension](https://chrome.google.com/webstore/detail/gitzip-for-github/ffabmkklhbepgcgfonabamgnfafbdlkn)

# How to install

Please see [#Installing plugins](https://happypandax.github.io/usage.html#installing-plugins) in the documentation.

# Be careful about plugins

Read the relevant section [#Be careful about plugins](https://happypandax.github.io/usage.html#be-careful-about-plugins) in documentation

# Plugins

{}
"""

plugins_dir = "plugins"
readme_file = "README.md"
desc_max_length = 200

def main():
    print("Building...")
    plugin_readme = ""

    for p in sorted(glob.glob(f"{plugins_dir}/**/hplugin.json")):
        with open(p, 'r', encoding="utf-8") as f:
            d = json.load(f)
            plugin_dir = pathlib.Path(p).parent
            dir_name = plugin_dir.name
            plugin_dir = str(plugin_dir).replace('\\', '/')
            plugin_desc = d.get("description")
            plugin_ver = d.get("version")

            if plugin_desc and plugin_ver:
                plugin_desc = plugin_desc.split('\n')[0]
                if len(plugin_desc) > desc_max_length:
                    plugin_desc = plugin_desc[:desc_max_length] + '…'
                plugin_readme += f"- [**{dir_name}**]({plugin_dir}) `{plugin_ver}` ᠁ *{plugin_desc}*\n"

    txt = readme.format(plugin_readme)

    with open(readme_file, 'w', encoding="utf-8") as f:
        f.write(txt)
    print("Done!")

if __name__ == '__main__':
    main()