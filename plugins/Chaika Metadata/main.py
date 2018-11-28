# main.py
import __hpx__ as hpx
import gevent
import regex
import arrow
import datetime
import os
import urllib
import html

from bs4 import BeautifulSoup
from PIL import Image, ImageChops

log = hpx.get_logger("main")

match_url_prefix = r"^(http\:\/\/|https\:\/\/)?(www\.)?" # http:// or https:// + www.
match_url_end = r"\/?$"

default_delay = 0.5

urls_regex = {
    'gallery': match_url_prefix + r"(panda\.chaika\.moe\/(archive|gallery)\/[0-9]+)" + match_url_end,
}

urls = {
    'ch': 'https://panda.chaika.moe',
    'gallery': 'https://panda.chaika.moe/gallery/',
    'archive': 'https://panda.chaika.moe/archive/',
    'gallery_api': 'https://panda.chaika.moe/jsearch?gallery=',
    'archive_api': 'https://panda.chaika.moe/jsearch?archive=',
    'hash_api': 'https://panda.chaika.moe/jsearch?sha1=',
    'title_search': "https://panda.chaika.moe/galleries/?title={title}&tags=&category=&provider=&uploader=&rating_from=&rating_to=&filesize_from=&filesize_to=&filecount_from=&filecount_to=&sort=posted&asc_desc=desc&apply="
}

HEADERS = {'user-agent':"Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0"}

plugin_config = {
    'filename_search': False, # use the filename/folder-name for searching instead of gallery title
    'remove_namespaces': True, # remove superfluous namespaces like 'artist', 'language' and 'group' because they are handled specially in HPX
    'gallery_results_limit': 10, # maximum amount of galleries to return
    'blacklist_tags': [], # tags to ignore when updating tags
    'add_gallery_url': True, # add ehentai url to gallery
    'preferred_language': "english", # preferred gallery langauge (in gallery title) to extract from if multiple galleries were found, set empty string for default
}

@hpx.subscribe("init")
def inited():
    plugin_config.update(hpx.get_plugin_config())

    # set default delay values if not set
    delays = hpx.get_setting("network", "delays", {})
    for u in (urls['ch'],):
        if u not in delays:
            log.info(f"Setting delay on {u} requests to {default_delay}")
            delays[u] = default_delay
            hpx.update_setting("network", "delays", delays)

@hpx.subscribe("disable")
def disabled():
    pass

@hpx.subscribe("remove")
def removed():
    pass

@hpx.attach("Metadata.info")
def metadata_info_eh():
    return hpx.command.MetadataInfo(
        identifier = "chaika",
        name = "Panda.Chaika",
        parser = urls_regex['gallery'],
        sites = ("www.panda.chaika.moe",),
        description = "Fetch metadata from Panda.Chaika",
        models = (
            hpx.command.GetModelClass("Gallery"),
        )
    )

@hpx.attach("Metadata.query")
def query(item, url, options, capture="chaika"):
    log.info("Querying chaika for metadata")
    mdata = []
    gurls = [] # tuple of (title, url)
    # url was provided
    if url:
        log.info(f"url provided: {url} for {item}")
        gurls.append((url, url))
    else: # manually search for id
        log.info(f"url not provided for {item}")
        # search with title
        i_title = ""
        i_hash = ""
        if plugin_config.get("filename_search"):
            sources = item.get_sources()
            if sources:
                # get folder/file name
                i_title = os.path.split(sources[0])[1]
                # remove ext
                i_title = os.path.splitext(i_title)[0]
        else:
            if item.titles:
                i_title = item.titles[0].name # make user choice
        if i_title:
            gurls = title_search(i_title)

        # search with hash
        if not gurls:
            pass

    log.info(f"found {len(gurls)} urls for item: {item}")

    # list is sorted by date added so we reverse it
    gurls.reverse()

    log.debug(f"{gurls}")
    final_gurls = []
    pref_lang = plugin_config.get('preferred_language')
    if pref_lang:
        for t in gurls:
            if pref_lang.lower() in t[0].lower():
                final_gurls.insert(0, t)
                continue
            final_gurls.append(t)
    else:
        final_gurls = gurls

    for t, u in final_gurls:
        g_type, g_id = parse_url(u)
        if g_type and g_id:
            mdata.append(hpx.command.MetadataData(
                data={
                    'type': g_type,
                    'id': g_id,
                    'gallery_url': u,
                    'apply_url': plugin_config.get('add_gallery_url', True),
                    }))
    return tuple(mdata)

@hpx.attach("Metadata.apply")
def apply(datatuple, item, options, capture="chaika"):
    log.info("Applying metadata from chaika")
    applied = False

    for d in datatuple:
        # prepare request
        req_props = hpx.command.RequestProperties(
            headers=HEADERS,
            )
        
        api_url = urls['archive_api'] if d.data['type'] == 'archive' else urls['gallery_api']
        api_url += str(d.data['id'])

        r = hpx.command.SingleGETRequest().request(api_url, req_props)
        if r.ok:
            response = r.json
            if response and not 'result' in response:
                mdata = filter_metadata(response, item, apply_url=d.data['apply_url'], gallery_url=d.data['gallery_url'])
                applied = apply_metadata(mdata, item)
            elif response:
                log.warning(response)
    log.info(f"Applied: {applied}")
    return applied

def title_search(title, session=None, _times=0):
    "Searches on chaika for galleries with given title, returns a list of (title, matching gallery urls)"
    search_url = urls['title_search']
    log.debug(f"searching with title: {title}")
    f_url = search_url.format(
        title=urllib.parse.quote_plus(title)
        )
    log.debug(f"final url: {f_url}")
    r = page_results(f_url, session=session)
    if not r and not _times:
        title = regex.sub(r"\(.+?\)|\[.+?\]", "", title)
        title = " ".join(title.split())
        r = title_search(title, session, _times=_times+1)
    return r

def page_results(page_url, limit=None, session=None):
    "Opens chaika page, parses for results, and then returns list of (title, url)"
    found_urls = []
    if limit is None:
        limit = plugin_config.get("gallery_results_limit")

    # prepare request
    req_props = hpx.command.RequestProperties(
        headers=HEADERS,
        )
    if session:
        req_props.session = session
        log.debug(f"COOKIES: {session.cookies}")
    r = hpx.command.SingleGETRequest().request(page_url, req_props)
    soup = BeautifulSoup(r.text, "html.parser")
    results = soup.findAll("tr", class_="result-list", limit=limit)
    results = [r.findAll('td')[1] for r in results]
    # str(x.a.string)
    found_urls = [(str(x.a.string), urls['ch'] + x.a['href']) for x in results] # title, url

    if not found_urls:
        log.warning(f"No results found on url: {page_url}")
        log.debug(f"HTML: {r.text}")
    return found_urls

def parse_url(url):
    "Parses url into a tuple of gallery/archive and id"
    gallery_id = None
    stype = "gallery"

    gallery_id = regex.search('([0-9]+)', url)
    if gallery_id:
        gallery_id = gallery_id.group()
    else:
        log.warning("Error extracting id from url: {}".format(url))

    if 'archive' in url:
        stype = 'archive'

    return stype, int(gallery_id)

def capitalize_text(text):
    """
    better str.capitalize
    """
    return " ".join(x.capitalize() for x in text.strip().split())

def filter_metadata(gdata, item, apply_url=False, gallery_url=None):
    mdata = {}
    replace_metadata = hpx.get_setting('metadata', 'replace_metadata')
    if replace_metadata:
        item.titles = []
        item.artists = []
        item.tags = []
        # flush is required so items are removed from the db
        hpx.command.GetSession().flush()

    if replace_metadata:
        mdata['titles'] = []
        if gdata['title']:
            mdata['titles'].append((gdata['title'], 'english'))
        if gdata['title_jpn']:
            mdata['titles'].append((gdata['title_jpn'], 'japanese'))
    else:
        t = []
        if not item.title_by_language("english") and gdata['title']:
            t.append((gdata['title'], 'english'))
        if not item.title_by_language("japanese") and gdata['title_jpn']:
            t.append((gdata['title_jpn'], 'japanese'))
        if t:
            mdata['titles'] = t

    if replace_metadata:
        mdata['category'] = gdata['category']
    elif not item.category:
        mdata['category'] = gdata['category']

    if gdata['posted']:
        if replace_metadata:
            mdata['pub_date'] = arrow.Arrow.fromtimestamp(gdata['posted'])
        elif not item.pub_date:
            mdata['pub_date'] = arrow.Arrow.fromtimestamp(gdata['posted'])

    lang = "japanese" # def lang
    if not replace_metadata and item.language:
        lang = item.language.name

    artists = []
    circles = []
    parodies = []

    extra_namespaces = ("artist", "parody", "group", "language")
    mdata['tags'] = {}
    for nstag in gdata['tags']:
        onstag = nstag
        nstag = nstag.replace('_', ' ')
        blacklist_tags = plugin_config.get("blacklist_tags")
        if blacklist_tags and (nstag in blacklist_tags or onstag in blacklist_tags):
            continue

        ns = None
        if ':' in nstag:
            ns, t = nstag.split(':', 1)
        else:
            t = nstag

        if ns == 'language' and t != 'translated':
            lang = t
        elif ns == "artist":
            artists.append(t)
        elif ns == "group":
            circles.append(t)
        elif ns == "parody":
            parodies.append(t)
        
        if not (plugin_config.get("remove_namespaces") and ns in extra_namespaces):
            mdata['tags'].setdefault(ns, []).append(t)
        else:
            log.debug(f"removing namespace {ns}")
        
    log.debug(f"tags: {mdata['tags']}")

    if replace_metadata:
        mdata['language'] = lang
    elif not item.language:
        mdata['language'] = lang
    
    if parodies:
        if replace_metadata:
            item.parodies = []
            mdata['parodies'] = parodies
        elif not item.parodies:
            mdata['parodies'] = parodies

    if artists:
        a_circles = []
        for a in artists:
            a_circles.append((a, tuple(circles)))
        if replace_metadata:
            item.artists = []
            mdata['artists'] = a_circles
        elif not item.artists:
            mdata['artists'] = a_circles

    if apply_url:
        if gdata.get('gallery', False):
            mdata['urls'] = [urls['gallery']+f"{gdata['gallery']}/"]
        elif gallery_url:
            mdata['urls'] = [gallery_url]

    return mdata

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
                gartist = artist_model.as_unique(name=capitalize_text(a))
                if not gartist in gallery.artists:
                    gallery.update("artists", gartist)
            if a and c:
                for circlename in [x for x in c if x]:
                    gcircle = circle_model.as_unique(name=capitalize_text(circlename))
                    if not gcircle in gartist.circles:
                        gartist.update("circles", gcircle)
        log.debug("applied artists")
        applied = True

    if isinstance(data.get('parodies'), (list, tuple)):
        for p in data['parodies']:
            if p:
                gparody = parody_model.as_unique(name=capitalize_text(p))
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

def is_image_greyscale(filepath):
    "Check if image is monochrome (1 channel or 3 identical channels)"
    im = Image.open(filepath).convert("RGB")
    if im.mode not in ("L", "RGB"):
        return False

    if im.mode == "RGB":
        rgb = im.split()
        if ImageChops.difference(rgb[0],rgb[1]).getextrema()[1] != 0: 
            return False
        if ImageChops.difference(rgb[0],rgb[2]).getextrema()[1] != 0: 
            return False
    return True