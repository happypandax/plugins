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

urls_regex = {
    'eh_gallery': match_url_prefix + r"((?<!g\.)(e-hentai)\.org\/g\/[0-9]+\/[a-z0-9]+)" + match_url_end,
    'ex_gallery': match_url_prefix + r"((exhentai)\.org\/g\/[0-9]+\/[a-z0-9]+)" + match_url_end,
}

urls = {
    'eh': 'https://e-hentai.org',
    'ex': 'https://exhentai.org',
    'api': 'https://api.e-hentai.org/api.php',
    'title_search': '{url}/?f_doujinshi=1&f_manga=1&f_artistcg=1&f_gamecg=1&f_western=1&f_non-h=1&f_imageset=1&f_cosplay=1&f_asianporn=1&f_misc=1&f_search={title}&f_apply=Apply+Filter&advsearch=1&f_sname=on&f_stags=on&f_storr=on&f_srdd=2&f_sfl=on&f_sfu=on',
    'title_search_exp': '{url}/?f_doujinshi=1&f_manga=1&f_artistcg=1&f_gamecg=1&f_western=1&f_non-h=1&f_imageset=1&f_cosplay=1&f_asianporn=1&f_misc=1&f_search={title}&f_apply=Apply+Filter&advsearch=1&f_sname=on&f_stags=on&f_storr=on&f_sh=on&f_srdd=2&f_sfl=on&f_sfu=on'
}

HEADERS = {'user-agent':"Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0"}

plugin_config = {
    'filename_search': True, # use the filename/folder-name for searching instead of gallery title
    'expunged_galleries': False, # enable expunged galleries in results
    'remove_namespaces': True, # remove superfluous namespaces like 'artist', 'language' and 'group' because they are handled specially in HPX
    'gallery_results_limit': 10, # maximum amount of galleries to return
    'blacklist_tags': [], # tags to ignore when updating tags
    'add_gallery_url': True, # add ehentai url to gallery
}

@hpx.subscribe("init")
def inited():
    plugin_config.update(hpx.get_plugin_config())

@hpx.subscribe("disable")
def disabled():
    pass

@hpx.subscribe("remove")
def removed():
    pass

@hpx.attach("Metadata.info")
def metadata_info_eh():
    return hpx.command.MetadataInfo(
        identifier = "ehentai",
        name = "EHentai",
        parser = urls_regex['eh_gallery'],
        sites = ("www.e-hentai.org",),
        description = "Fetch metadata from E-Hentai",
        models = (
            hpx.command.GetModelClass("Gallery"),
        )
    )

@hpx.attach("Metadata.info")
def metadata_info_ex():
    return hpx.command.MetadataInfo(
        identifier = "exhentai",
        name = "ExHentai",
        parser = urls_regex['ex_gallery'],
        sites = ("www.exhentai.org",),
        description = "Fetch metadata from ExHentai",
        models = (
            hpx.command.GetModelClass("Gallery"),
        )
    )

@hpx.attach("Metadata.query")
def query_eh(item, url, options, capture="ehentai"):
    log.info("Querying ehentai for metadata")
    return query(item, url, options)

@hpx.attach("Metadata.apply")
def apply_eh(datatuple, item, options, capture="ehentai"):
    log.info("Applying metadata from ehentai")
    return apply(datatuple, item, options)

@hpx.attach("Metadata.query")
def query_ex(item, url, options, capture="exhentai"):
    log.info("Querying exhentai for metadata")
    if not hpx.command.GetLoginStatus(urls['ex']):
        log.info("Not logged in to exhentai, aborting...")
        return tuple()
    return query(item, url, options, urls['ex'])

@hpx.attach("Metadata.apply")
def apply_ex(datatuple, item, options, capture="exhentai"):
    log.info("Applying metadata from exhentai")
    return apply(datatuple, item, options)

def query(item, url, options, login_site=urls['eh']):
    "Looks up on ehentai for matching item"
    mdata = []
    gurls = []
    # url was provided
    if url:
        log.info(f"url provided: {url} for {item}")
        gurls.append(url)
    else: # manually search for id
        log.info(f"url not provided for {item}")
        ex_login = hpx.command.GetLoginStatus(login_site) if "exhentai" in login_site else False
        login_session = None
        if ex_login:
            login_session = hpx.command.GetLoginSession(login_site)
        if login_site == 'exhentai':
            log.info(f"logged in to exhentai: {ex_login}")
        if (ex_login if "exhentai" in login_site else True):
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
                gurls = title_search(i_title, ex='exhentai' in login_site, session=login_session)

            # search with hash
            if not gurls:
                pass

    log.info(f"found {len(gurls)} urls for item: {item}")
    log.debug(f"{gurls}")
    for u in gurls:
        g_id, g_token = parse_url(u)
        if g_id and g_token:
            mdata.append(hpx.command.MetadataData(
                data={
                    'gallery': [g_id, g_token],
                    'gallery_url': u,
                    'apply_url': plugin_config.get('add_gallery_url', True),
                    }))
    return tuple(mdata)

def title_search(title, ex=True, session=None):
    "Searches on ehentai for galleries with given title, returns a list of matching gallery urls"
    if plugin_config.get("expunged_galleries"):
        eh_url = urls['title_search_exp']
    else:
        eh_url = urls['title_search']
    log.debug(f"searching with title: {title}")
    f_eh_url = eh_url.format(
        url=urls['ex'] if ex else urls['eh'],
        title=urllib.parse.quote_plus(title)
        )
    log.debug(f"final url: {f_eh_url}")
    return eh_page_results(f_eh_url, session=session)

def eh_page_results(eh_page_url, limit=None, session=None):
    "Opens eh page, parses for results, and then returns found urls"
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
    r = hpx.command.SingleGETRequest().request(eh_page_url, req_props)
    soup = BeautifulSoup(r.text, "html.parser")
    thumb_view = False
    dmi_div = soup.find("div", id="dmi")
    if dmi_div and dmi_div.a and "list" in str(dmi_div.a.string).lower():
        thumb_view = True
    if thumb_view:
        results = soup.findAll("div", class_="id2", limit=limit)
    else:
        results = soup.findAll("div", class_="it5", limit=limit)
    # str(x.a.string)
    found_urls = [x.a['href'] for x in results]
    if not found_urls:
        log.debug(f"HTML: {r.text}")
    return found_urls

def parse_url(url):
    "Parses url into a tuple of gallery id and token"
    gallery_id = None
    gallery_token = None

    gallery_id_token = regex.search('(?<=g/)([0-9]+)/([a-zA-Z0-9]+)', url)
    if gallery_id_token:
        gallery_id_token = gallery_id_token.group()
        gallery_id, gallery_token = gallery_id_token.split('/')
    else:
        log.warning("Error extracting g_id and g_token from url: {}".format(url))
    return int(gallery_id), gallery_token

def apply(datatuple, item, options):
    applied = False

    eh_data = {
        'method': 'gdata',
        'gidlist': [],
        'namespace': 1
    }

    urls_to_apply = []

    for d in datatuple:
        eh_data['gidlist'].append(d.data['gallery'])
        if d.data['apply_url']:
            urls_to_apply.append(d.data['gallery_url'])

    # prepare request
    req_props = hpx.command.RequestProperties(
        headers=HEADERS,
        json=eh_data
        )
    r = hpx.command.SinglePOSTRequest().request(urls['api'], req_props)
    if r.ok:
        response = r.json
        if response and not 'error' in response:
            for gdata in response['gmetadata']:
                mdata = filter_metadata(gdata, item, urls_to_apply=urls_to_apply)
                applied = apply_metadata(mdata, item)

        elif response:
            log.warning(response)
    log.info(f"Applied: {applied}")
    return applied

def capitalize_text(text):
    """
    better str.capitalize
    """
    return " ".join(x.capitalize() for x in text.strip().split())

def filter_metadata(gdata, item, urls_to_apply=None):
    mdata = {}
    replace_metadata = hpx.get_setting('metadata', 'replace_metadata')
    if replace_metadata:
        item.titles = []
        item.artists = []
        item.tags = []

    if replace_metadata:
        mdata['titles'] = []
        mdata['titles'].append((gdata['title'], 'english'))
        mdata['titles'].append((gdata['title_jpn'], 'japanese'))
    else:
        t = []
        if not item.title_by_language("english"):
            t.append((gdata['title'], 'english'))
        if not item.title_by_language("japanese"):
            t.append((gdata['title_jpn'], 'japanese'))
        if t:
            mdata['titles'] = t

    if replace_metadata:
        mdata['category'] = gdata['category']
    elif not item.category:
        mdata['category'] = gdata['category']

    if replace_metadata:
        mdata['pub_date'] = arrow.Arrow.fromtimestamp(gdata['posted'])
    elif not item.pub_date:
        mdata['pub_date'] = arrow.Arrow.fromtimestamp(gdata['posted'])

    lang = "english"
    if item.language:
        lang = item.language.name

    artists = []
    circles = []
    parodies = []

    extra_namespaces = ("artist", "parody", "group", "language")
    mdata['tags'] = {}
    for nstag in gdata['tags']:

        blacklist_tags = plugin_config.get("blacklist_tags")
        if blacklist_tags and nstag in blacklist_tags:
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

    if urls_to_apply:
        mdata['urls'] = urls_to_apply

    return mdata

language_model = hpx.command.GetModelClass("Language")
title_model = hpx.command.GetModelClass("Title")
artist_model = hpx.command.GetModelClass("Artist")
parody_model = hpx.command.GetModelClass("Parody")
circle_model = hpx.command.GetModelClass("Circle")
url_model = hpx.command.GetModelClass("Url")
namespacetags_model = hpx.command.GetModelClass("NamespaceTags")

def apply_metadata(data, gallery, replace=False):
    """
    data = {
        'titles': None, # [(title, language),...]
        'artists': None, # [(artist, (circle, circle, ..)),...]
        'parodies': None, # [parody, ...]
        'category': None,
        'tags': None, # [tag, tag, tag, ..] or {ns:[tag, tag, tag, ...]}
        'pub_date': None, # DateTime object
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