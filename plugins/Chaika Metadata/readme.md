Chaika Metadata
----------------------------

> This plugin fetches metadata from Panda.Chaika

## Configuration

Configure this plugin by adding `chaika-metadata` to the `plugin.config` namespace in your `config.yaml`:
```yaml
plugin:
    config:
        chaika-metadata:
            option1: True
            option2:
                - item 1
                - item 2
```

#### Available options

Name | Default | Description
--- | --- | ---
`filename_search` | `false` | use the filename/folder-name for searching instead of gallery title
`remove_namespaces` | `true` | remove superfluous namespaces like 'artist', 'language' and 'group' because they are handled specially in HPX
`gallery_results_limit` | `10` | maximum amount of galleries to return
`blacklist_tags` | `[]` | tags to ignore when updating tags, a list of `namespace:tag` or `tag` strings
`add_gallery_url` | `true` | add chaika url to gallery
`preferred_language` | `english` | preferred gallery langauge (in gallery title) to extract from if multiple galleries were found, set empty string for default


## Things yet to be implemented

- File similarity search

# Changelog

- `1.0.0`
    - Updated to reflect new changes in HPX v0.10.0
    
- `0.1.0b`
    - first version