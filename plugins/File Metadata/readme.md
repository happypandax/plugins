File Metadata
----------------------------

> This plugin extracts and applies metadata from a file accompanying a gallery folder or archive.

This plugin supports extracting metadata from files produced by:

- [eze](https://dnsev-h.github.io/eze/)
    > only supports JSON format and file must be named `info.json`
- [HDoujin Downloader](https://doujindownloader.com/)
    > all file versions are supported
    > supports both JSON and TXT formats
    > file must be named `info.json` or `info.txt`

# Extending

... coming

# Changelog

- `0.2.0b`
    - require HPX `0.2.0`
    - use new api to update gallery data
    - add support for E-Hentai-Downloader
    - fix bug where `info.txt` in archive files would fail to get parsed

- `0.1.0b`
    - first version