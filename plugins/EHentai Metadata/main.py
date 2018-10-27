# main.py
from bs4 import BeautifulSoup
import __hpx__ as hpx
import gevent
import regex
import arrow
import datetime

log = hpx.get_logger("main")

match_url_prefix = r"^(http\:\/\/|https\:\/\/)?(www\.)?([^\.]?)" # http:// or https:// + www.
match_url_end = r"\/?$"

urls_regex = {
    'eh_gallery': match_url_prefix + r"((?<!g\.)(e-hentai)\.org\/g\/[0-9]+\/[a-z0-9]+)" + match_url_end,
    'ex_gallery': match_url_prefix + r"((exhentai)\.org\/g\/[0-9]+\/[a-z0-9]+)" + match_url_end,
}

urls = {
    'api': 'https://api.e-hentai.org/api.php'
}

HEADERS = {'user-agent':"Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0"}

@hpx.subscribe("init")
def inited():
    pass

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
    return query(item, url, options, 'exhentai')

@hpx.attach("Metadata.apply")
def apply_ex(datatuple, item, options, capture="exhentai"):
    log.info("Applying metadata from exhentai")
    return apply(datatuple, item, options)

def query(item, url, options, login_id='ehentai'):
    mdata = []
    # url was provided
    if url:
        log.info(f"Url provided: {url}")
        g_id, g_token = parse_url(url)
        if g_id and g_token:
            mdata.append(hpx.command.MetadataData(
                data={
                    'gallery': [g_id, g_token],
                    'apply_url': False,
                    }))
    else: # manually search for id
        if (hpx.command.GetLoginStatus(login_id) if login_id == 'exhentai' else True):
            pass
    return tuple(mdata)

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

    for d in datatuple:
        eh_data['gidlist'].append(d.data['gallery'])

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
                mdata = {}
                if hpx.get_setting('metadata', 'replace_metadata'):
                    item.titles = []
                    item.artists = []
                    item.tags = []

                mdata['titles'] = []
                mdata['titles'].append((gdata['title'], 'english'))
                mdata['titles'].append((gdata['title_jpn'], 'japanese'))
                mdata['category'] = gdata['category']
                mdata['pub_date'] = arrow.Arrow.fromtimestamp(gdata['posted'])
                mdata['language'] = "japanese"
                mdata['tags'] = {}
                for nstag in gdata['tags']:
                    ns = None
                    if ':' in nstag:
                        ns, t = nstag.split(':', 1)
                    else:
                        t = nstag
                    mdata['tags'].setdefault(ns, []).append(t)
                    if ns == 'language' and t != 'translated':
                        mdata['language'] = t
                
                applied = apply_metadata(mdata, item)

        elif response:
            log.warning(response)
    log.info(f"Applied: {applied}")
    return applied

language_model = hpx.command.GetModelClass("Language")
title_model = hpx.command.GetModelClass("Title")
artist_model = hpx.command.GetModelClass("Artist")
circle_model = hpx.command.GetModelClass("Circle")
url_model = hpx.command.GetModelClass("Url")
namespacetags_model = hpx.command.GetModelClass("NamespaceTags")

def apply_metadata(data, gallery):
    """
    data = {
        'titles': None, # [(title, language),...]
        'artists': None, # [(artist, (circle, circle, ..)),...]
        'category': None,
        'tags': None, # [tag, tag, tag, ..] or {ns:[tag, tag, tag, ...]}
        'pub_date': None, # DateTime object
        'language': None,
        'urls': None # [url, ...]
    }
    """

    applied = False

    log.debug("data:")
    log.debug(f"{data}")

    if isinstance(data.get('titles'), (list, tuple)):
        for t, l in data['titles']:
            gtitle = None
            if t:
                gtitle = title_model(name=t)
            if t and l:
                gtitle.language = language_model.as_unique(name=l)
            if gtitle:
                gallery.update("titles", gtitle)
        applied = True

    if isinstance(data.get('artists'), (list, tuple)):
        for a, c in data['artists']:
            if a:
                gartist = artist_model.as_unique(name=a)
                if not gartist in gallery.artists:
                    gallery.update("artists", gartist)
            if a and c:
                for circlename in [x for x in c if x]:
                    gcircle = circle_model.as_unique(name=circlename)
                    if not gcircle in gartist.circles:
                        gartist.update("circles", gcircle)
        applied = True

    if data.get('category'):
        gallery.update("category", name=data['category'])
        applied = True
    
    if data.get('language'):
        gallery.update("language", name=data['language'])
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
        applied = True

    if isinstance(data.get('pub_date'), (datetime.datetime, arrow.Arrow)):
        pub_date = data['pub_date']
        gallery.update("pub_date", pub_date)
        applied = True

    if isinstance(data.get('urls'), (list, tuple)):
        urls = []
        for u in data['urls']:
            urls.append(url_model(name=u))
        gallery.update("urls", urls)
        applied = True

    return applied