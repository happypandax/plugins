import json
import glob
import pathlib

readme = """
In this repository resides plugins for HappyPanda X

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
            dir_name = pathlib.Path(p).parent.name
            plugin_desc = d.get("description")
            plugin_ver = d.get("version")

            if plugin_desc and plugin_ver:
                plugin_desc = plugin_desc.split('\n')[0]
                if len(plugin_desc) > desc_max_length:
                    plugin_desc = plugin_desc[:desc_max_length] + '...'
                plugin_readme += f"- **{dir_name}** `{plugin_ver}` -- *{plugin_desc}*\n"

    txt = readme.format(plugin_readme)

    with open(readme_file, 'w', encoding="utf-8") as f:
        f.write(txt)
    print("Done!")

if __name__ == '__main__':
    main()