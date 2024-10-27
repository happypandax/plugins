EHentai Metadata
----------------------------

> This plugin fetches metadata from E-Hentai & ExHentai

**IMPORTANT:** This plugin requires the [EHentai Login](https://github.com/happypandax/plugins/tree/master/plugins/EHentai%20Login) plugin to be present

## Configuration

Configure this plugin by adding `ehentai-metadata` to the `plugin.config` namespace in your `config.yaml`:
```yaml
plugin:
    config:
        ehentai-metadata:
            option1: True
            option2:
                - item 1
                - item 2
```

#### Available options

Name | Default | Description
--- | --- | ---
`filename_search` | `true` | use the filename/folder-name for searching instead of gallery title
`expunged_galleries` | `false` | enable expunged galleries in results
`remove_namespaces` | `true` | remove superfluous namespaces like 'artist', 'language' and 'group' because they are handled specially in HPX
`gallery_results_limit` | `10` | maximum amount of galleries to return
`blacklist_tags` | `[]` | tags to ignore when updating tags, a list of `namespace:tag` strings
`add_gallery_url` | `true` | add ehentai url to gallery
`preferred_language` | `"english"` | preferred gallery language (in gallery title) to extract from if multiple galleries were found, set empty string for default
`enabled_categories` | `['manga', 'doujinshi', 'non-h', 'artistcg', 'gamecg', 'western', 'imageset', 'cosplay', 'asianporn', 'misc']` | categories that are enbaled for the search
`search_query` | `"{title}"` | the search query, '{title}' will be replaced with the gallery title, use double curly brackets to escape a curly bracket. Tip: if you want to only allow english results, you should modify this to "{title} language:english"
`search_low_power_tags` | `true` | enable search low power tags
`search_torrent_name` | `true` | enable search torrent name
`search_gallery_description` | `false` | enable search gallery description

## Things yet to be implemented

- File similarity search

# Changelog

- `2.0.0`
    - update to support HPX v1.0.0

- `1.2.1`
    - some misc. changes

- `1.2.0`
    - fixed title being qouted unconditionally
    - retry the search with qouted title if keyword count exceeds 8

- `1.1.0`
    - added several new options and fixed some errors

- `1.0.0`
    - updated to reflect new changes in HPX v0.10.0

- `0.4.0b`
    - updated to work on new EH website design changes

- `0.3.0b`
    - add a default delay on `https://api.e-hentai.org/` requests, this value can be tweaked in `network.delays` inside your`config.yaml`

- `0.2.0b`
    - added `preferred_language` option
    
- `0.1.0b`
    - first version