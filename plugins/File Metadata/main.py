import __hpx__ as hpx
import os
import arrow
import datetime
import html
import extractors
from extractors import common

log = hpx.get_logger(__name__)

options = {
}

def get_common_data(datatypes, fpath):
    assert isinstance(datatypes, common.DataType)
    d = {}
    fpath = hpx.command.CoreFS(fpath)

    for datatype in common.DataType:
        if datatype & datatypes:
            log.info(f"Attempting with {datatype}")
            md = {}

            ex = common.extractors.get(datatype, None)
            if ex:
                try:
                    fdata = ex.file_to_dict(fpath)
                except ValueError:
                    log.info(f"Skipping {datatype}")
                    continue
                if fdata:
                    md.update(ex.extract(fdata))
            if md:
                d.update(md)
                break
    return d

language_model = hpx.command.GetModelClass("Language")
title_model = hpx.command.GetModelClass("Title")
artist_model = hpx.command.GetModelClass("Artist")
parody_model = hpx.command.GetModelClass("Parody")
circle_model = hpx.command.GetModelClass("Circle")
url_model = hpx.command.GetModelClass("Url")
namespacetags_model = hpx.command.GetModelClass("NamespaceTags")

def apply_metadata(data, gallery):
    """
    data = {
        'titles': None, # [(title, language),...]
        'artists': None, # [(artist, (circle, circle, ..)),...]
        'parodies': None, # [parody, ...]
        'category': None,
        'tags': None, # [tag, tag, tag, ..] or {ns:[tag, tag, tag, ...]}
        'pub_date': None, # DateTime object or Arrow object
        'language': None,
        'urls': None # [url, ...]
    }
    """

    applied = False

    log.debug(f"data: {data}")

    if isinstance(data.get('titles'), (list, tuple)):
        for t, l in data['titles']:
            gtitle = None
            if t:
                t = html.unescape(t)
                gtitle = title_model(name=t)
            if t and l:
                gtitle.language = language_model.as_unique(name=l)
            if gtitle:
                gallery.update("titles", gtitle)
        log.debug("applied titles")
        applied = True

    if isinstance(data.get('artists'), (list, tuple)):
        for a, c in data['artists']:
            if a:
                gartist = artist_model.as_unique(name=common.capitalize_text(a))
                if not gartist in gallery.artists:
                    gallery.update("artists", gartist)
            if a and c:
                for circlename in [x for x in c if x]:
                    gcircle = circle_model.as_unique(name=common.capitalize_text(circlename))
                    if not gcircle in gartist.circles:
                        gartist.update("circles", gcircle)
        log.debug("applied artists")
        applied = True

    if isinstance(data.get('parodies'), (list, tuple)):
        for p in data['parodies']:
            if p:
                gparody = parody_model.as_unique(name=common.capitalize_text(p))
                if not gparody in gallery.parodies:
                    gallery.update("parodies", gparody)

        log.debug("applied parodies")
        applied = True

    if data.get('category'):
        gallery.update("category", name=data['category'])
        log.debug("applied category")
        applied = True
    
    if data.get('language'):
        gallery.update("language", name=data['language'])
        log.debug("applied language")
        applied = True

    if isinstance(data.get('tags'), (dict, list)):
        if isinstance(data['tags'], list):
            data['tags'] = {None: data['tags']}
        ns_tags = []
        for ns, tags in data['tags'].items():
            if ns is not None:
                ns = ns.strip()
            if ns and ns.lower() == 'misc':
                ns = None
            for t in tags:
                t = t.strip()
                ns_tags.append(namespacetags_model.as_unique(ns=ns, tag=t))
        
        for nstag in ns_tags:
            if nstag not in gallery.tags:
                gallery.tags.append(nstag)
        log.debug("applied tags")
        applied = True

    if isinstance(data.get('pub_date'), (datetime.datetime, arrow.Arrow)):
        pub_date = data['pub_date']
        gallery.update("pub_date", pub_date)
        log.debug("applied pub_date")
        applied = True

    if isinstance(data.get('urls'), (list, tuple)):
        existing_urls = [x.name.lower() for x in gallery.urls]
        urls = []
        for u in data['urls']:
            if u.lower() not in existing_urls:
                urls.append(url_model(name=u))
        gallery.update("urls", urls)
        log.debug("applied urls")
        applied = True

    return applied
    
@hpx.subscribe("init")
def inited():
    common.plugin_config.update(hpx.get_plugin_config())

@hpx.attach("GalleryFS.parse_metadata_file")
def parse(path, gallery):
    fs = hpx.command.CoreFS(path)

    contents = {x: os.path.split(x)[1].lower() for x in fs.contents(corefs=False) if x.lower().endswith(common.filetypes)}
    log.debug(f"Contents for {fs.path}:")
    log.debug(f"{tuple(contents.values())}")

    cdata = common.common_data.copy()

    for fnames, dtypes in common.filenames.items():
        for fpath, fname in contents.items():
            if fname in fnames:
                log.debug(f"path: {fpath}")
                cdata.update(get_common_data(dtypes, fpath))
                break

    return apply_metadata(cdata, gallery)