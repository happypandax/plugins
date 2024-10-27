NHentai Metadata
----------------------------

> This plugin fetches metadata from nhentai.net

## Configuration

Configure this plugin by adding `nhentai-metadata` to the `plugin.config` namespace in your `config.yaml`:
```yaml
plugin:
    config:
        nhentai-metadata:
            option1: True
            option2:
                - item 1
                - item 2
```

#### Available options

Name | Default | Description
--- | --- | ---
`filename_search` | `true` | use the filename/folder-name for searching instead of gallery title
`remove_namespaces` | `true` | remove superfluous namespaces like 'artists', 'languages' and 'groups' and so on because they are handled specially in HPX
`gallery_results_limit` | `10` | maximum amount of galleries to return
`blacklist_tags` | `[]` | tags to ignore when updating tags, a list of `namespace:tag` strings
`add_gallery_url` | `true` | add ehentai url to gallery
`preferred_language` | `"english"` | preferred gallery language (in gallery title) to extract from if multiple galleries were found, set empty string for default
`search_query` | `"{title}"` | the search query, '{title}' will be replaced with the gallery title, use double curly brackets to escape a curly bracket. Tip: if you want to only allow english results, you should modify this to "{title} language:english"


# Changelog
    
- `2.0.0`
    - update to support HPX v1.0.0

- `1.0.1`
    - updated to reflect site changes where titles where not geting extracted
    
- `1.0.0`
    - first version