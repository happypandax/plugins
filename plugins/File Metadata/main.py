import __hpx__ as hpx
import os
import arrow
import datetime
import common
import extractors

log = hpx.get_logger(__name__)

options = {
}

def get_common_data(datatypes, fpath):
    assert isinstance(datatypes, tuple)
    d = {}
    fpath = hpx.command.CoreFS(fpath)

    for datatype in datatypes:
        md = {}

        ex = common.extractors.get(datatype, None)
        if ex:
            fdata = ex.file_to_dict(fpath)
            if fdata:
                md.update(ex.extract(fdata))
        if md:
            d.update(md)
            break
    return d

language_model = hpx.command.GetModelClass("Language")
title_model = hpx.command.GetModelClass("Title")
artist_model = hpx.command.GetModelClass("Artist")
circle_model = hpx.command.GetModelClass("Circle")
category_model = hpx.command.GetModelClass("Category")
artistname_model = hpx.command.GetModelClass("ArtistName")
url_model = hpx.command.GetModelClass("Url")
namespacetags_model = hpx.command.GetModelClass("NamespaceTags")

def apply_metadata(data, gallery):
    applied = False

    log.debug("data:")
    log.debug(f"{data}")

    if isinstance(data['titles'], (list, tuple)):
        for t, l in data['titles']:
            if t:
                gtitle = title_model(name=t)
                gallery.titles.append(gtitle)
            if t and l:
                gtitle.language = language_model.as_unique(name=l)
        applied = True

    if isinstance(data['artists'], (list, tuple)):
        for a, c in data['artists']:
            if a:
                gartist = artist_model.as_unique(name=a)
                if not gartist in gallery.artists:
                    gallery.artists.append(gartist)
            if a and c:
                for circlename in [x for x in c if x]:
                    gcircle = circle_model.as_unique(name=circlename)
                    if not gcircle in gartist.circles:
                        gartist.circles.append(gcircle)
        applied = True

    if data['category']:
        gcat = category_model.as_unique(name=data['category'])
        gallery.category = gcat
        applied = True
    
    if data['language']:
        glang = language_model.as_unique(name=data['language'])
        gallery.language = glang
        applied = True

    if isinstance(data['tags'], (dict, list)):
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
            if not nstag in gallery.tags:
                gallery.tags.append(nstag)
        applied = True

    if isinstance(data['pub_date'], (datetime.datetime, arrow.Arrow)):
        pub_date = data['pub_date']
        if isinstance(pub_date, datetime.datetime):
            pub_date = arrow.Arrow.fromdatetime(pub_date)
        gallery.pub_date = pub_date
        applied = True

    if isinstance(data['urls'], (list, tuple)):
        for u in data['urls']:
            gallery.urls.append(url_model(name=u))
        applied = True

    return applied
    
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