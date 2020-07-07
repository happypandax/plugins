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
                    log.info(f"{datatype} matched!")
                    md.update(ex.extract(fdata))
                else:
                    log.info(f"{datatype} didn't match")
            if md:
                d.update(md)
                break
    return d

SetValue = hpx.command.Set
GalleryData = hpx.command.GalleryData
LanguageData = hpx.command.LanguageData
TitleData = hpx.command.TitleData
ArtistData = hpx.command.ArtistData
ArtistNameData = hpx.command.ArtistNameData
ParodyData = hpx.command.ParodyData
ParodyNameData = hpx.command.ParodyNameData
CircleData = hpx.command.CircleData
CategoryData = hpx.command.CategoryData
UrlData = hpx.command.UrlData
NamespaceTagData= hpx.command.NamespaceTagData
TagData= hpx.command.TagData
NamespaceData = hpx.command.NamespaceData

def apply_metadata(data, gallery, options={}):
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

    log.debug(f"data: {data}")

    gdata = GalleryData()

    if isinstance(data.get('titles'), (list, tuple, set)):
        gtitles = []
        for t, l in data['titles']:
            gtitle = None
            if t:
                t = html.unescape(t)
                gtitle = TitleData(name=t)
            if t and l:
                gtitle.language = LanguageData(name=l)
            if gtitle:
                gtitles.append(gtitle)

        if gtitles:
            gdata.titles = SetValue(gtitles)
            log.debug("applied titles")

    if isinstance(data.get('artists'), (list, tuple, set)):
        gartists = []
        for a, c in data['artists']:
            if a:
                gartist = ArtistData(names=[ArtistNameData(name=common.capitalize_text(a))])
                gartists.append(gartist)

                if c:
                    gcircles = []
                    for circlename in [x for x in c if x]:
                        gcircles.append(CircleData(name=common.capitalize_text(circlename)))
                    gartist.circles = gcircles

        if gartists:
            gdata.artists = SetValue(gartists)
            log.debug("applied artists")

    if isinstance(data.get('parodies'), (list, tuple, set)):
        gparodies = []
        for p in data['parodies']:
            if p:
                gparody = ParodyData(names=[ParodyNameData(name=common.capitalize_text(p))])
                gparodies.append(gparody)

        if gparodies:
            gdata.parodies = SetValue(gparodies)
            log.debug("applied parodies")

    if data.get('category'):
        gdata.category = SetValue(CategoryData(name=data['category']))
        log.debug("applied category")
    
    if data.get('language'):
        gdata.language = SetValue(LanguageData(name=data['language']))
        log.debug("applied language")

    if isinstance(data.get('tags'), (dict, list)):
        if isinstance(data['tags'], list):
            data['tags'] = {None: data['tags']}
        gnstags = []
        for ns, tags in data['tags'].items():
            if ns is not None:
                ns = ns.strip()
            if ns and ns.lower() == 'misc':
                ns = None
            for t in tags:
                t = t.strip()
                if t:
                    kw = {'tag': TagData(name=t)}
                    if ns:
                        kw['namespace'] = NamespaceData(name=ns)
                    gnstags.append(NamespaceTagData(**kw))

        if gnstags:
            gdata.tags = SetValue(gnstags)
            log.debug("applied tags")

    if isinstance(data.get('pub_date'), (datetime.datetime, arrow.Arrow)):
        pub_date = data['pub_date']
        gdata.pub_date = SetValue(pub_date)
        log.debug("applied pub_date")

    if isinstance(data.get('urls'), (list, tuple)):
        gurls = []
        for u in data['urls']:
            if u:
                gurls.append(UrlData(name=u))
        if gurls:
            gdata.urls = SetValue(gurls)
            log.debug("applied urls")

    if data.get('times_read'):
        gdata.times_read = SetValue(data['times_read'])
        log.debug("applied times_read")

        if data['times_read'] > 0:
            gallery_id = gallery.id
            page_id = gallery.last_page.id

            GalleryProgress.update_progress(gallery_id, page_id)

    applied = hpx.command.UpdateItemData(gallery, gdata, options=options)

    log.debug(f"applied: {applied}")

    return applied
    
@hpx.subscribe("init")
def inited():
    common.plugin_config.update(hpx.get_plugin_config())

@hpx.subscribe('config_update')
def config_update(cfg):
    common.plugin_config.update(cfg)

def has_file_metadata(path):
    fs = hpx.command.CoreFS(path)

    contents = {x: os.path.split(x)[1].lower() for x in fs.contents(corefs=False) if x.lower().endswith(common.filetypes)}
    log.debug(f"Contents for {fs.path}:")
    log.debug(f"{tuple(contents.values())}")

    found_files = []
    for fnames, dtypes in common.filenames.items():
        for fpath, fname in contents.items():
            if fname in fnames:
                found_files.append((dtypes, fpath))
                break

    return found_files

def apply_file_metadata(gallery, found_files):
    applied = False
    cdata = common.common_data.copy()
    for dtypes, fpath in found_files:
        log.debug(f"path: {fpath}")
        d = get_common_data(dtypes, fpath)
        if d:
            applied = True
            cdata.update(d)

    if applied:
        apply_metadata(cdata, gallery)

    return applied

@hpx.attach("GalleryFS.parse_metadata_file")
def parse(path, gallery):
    f = has_file_metadata(path)
    return apply_file_metadata(gallery, f)

##### --- 

@hpx.attach("Metadata.info")
def metadata_info():
    return hpx.command.MetadataInfo(
        identifier = "filemetadata",
        name = "File Metadata",
        description = "Extracts and applies metadata from a file accompanying a gallery",
        sites= ("eze", "E-Hentai-Downloader", "HDoujinDownloader"),
        models = (
            hpx.command.GetDatabaseModel("Gallery"),
        )
    )

@hpx.attach("Metadata.query", trigger='filemetadata')
def query(itemtuple):
    "Looks up files for matching items"
    mdata = []

    for mitem in itemtuple:
        item = mitem.item
        options = mitem.options

        found_files = []
        for s in item.get_sources():
            found_files.extend(has_file_metadata(s))

        log.info(f"found {len(found_files)} metadata files for item: {item}")

        if found_files:
            log.debug(f"{found_files}")

            mdata.append(hpx.command.MetadataData(
                metadataitem=mitem,
                title=item.preferred_title.name if item.preferred_title else '',
                data={
                    'found':found_files,
                }))

    log.info(f"Returning {len(mdata)} data items")
    return tuple(mdata)

@hpx.attach("Metadata.apply", trigger='filemetadata')
def apply(datatuple):
    mresults = []
    applied = False

    for d in datatuple:
        applied = apply_file_metadata(d.item, d.data['found'])
        if applied:
            mresults.append(hpx.command.MetadataResult(data=d, status=True))
        else:
            mresults.append(hpx.command.MetadataResult(data=d, status=False, reason="failed to apply data from file"))

    return tuple(mresults)