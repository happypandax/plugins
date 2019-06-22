File Metadata
----------------------------

> This plugin extracts and applies metadata from a file accompanying a gallery folder or archive.

This plugin supports extracting metadata from files produced by:

- [eze](https://dnsev-h.github.io/eze/)
    > - only supports JSON format and file must be named `info.json`
- [HDoujin Downloader](https://doujindownloader.com/)
    > - all file versions are supported
    > - supports both JSON and TXT formats
    > - file must be named `info.json` or `info.txt`
- [E-Hentai-Downloader](https://github.com/ccloli/E-Hentai-Downloader)
    > - supports only the file named `info.txt`

## Configuration

Configure this plugin by adding `file-metadata` to the `plugin.config` namespace in your `config.yaml`:
```yaml
plugin:
    config:
        file-metadata:
            option1: True
            option2:
                - item 1
                - item 2
```

#### Available options

Name | Default | Description
--- | --- | ---
`characters_namespace` | `character` | which namespace to put the values in the CHARACTERS field in (applies to hdoujin)

# Extending

Follow these steps to add support for more kind of files:

1. Create a new enum member for your extractor in `extractors.common.DataType`
2. Add a new filetype to `extractors.common.filetypes` if necessary
3. Add your new enum member to `extractors.common.filenames`
4. Create a new `.py` file in the `extractors` folder
5. Import the `common` module and create a new `common.Extractor` subclass
6. At the end of the file, register the subclass with `common.register_extractor`
7. Import your new `.py` file in `extractors.__init__`

# Changelog

- `1.0.2`
    - Fixed a bug where not all metadata would be applied

- `1.0.1`
    - Updated the eze handler to support files produced by https://github.com/dnsev-h/ehentai-archive-info
    - Fixed the extractors still using the old api

- `1.0.0`
    - Updated to reflect new changes in HPX v0.10.0

- `0.3.0b`
    - **HDoujin**: add option `characters_namespace`
    - **HDoujin**: parse `PARODY` and `CHARACTERS` fields

- `0.2.0b`
    - require HPX `0.2.0`
    - use new api to update gallery data
    - add support for E-Hentai-Downloader
    - fix bug where `info.txt` in archive files would fail to get parsed

- `0.1.0b`
    - first version