# main.py
import __hpx__ as hpx
import regex
import arrow
import datetime
import os
import urllib
import html

from bs4 import BeautifulSoup
from PIL import Image, ImageChops

log = hpx.get_logger("main")

MATCH_URL_PREFIX = r"^(http\:\/\/|https\:\/\/)?(www\.)?" # http:// or https:// + www.
MATCH_URL_END = r"\/?$"

DEFAULT_DELAY = 8

URLS_REGEX = {
    'eh_gallery': MATCH_URL_PREFIX + r"((?<!g\.)(e-hentai)\.org\/g\/[0-9]+\/[a-z0-9]+)" + MATCH_URL_END,
    'ex_gallery': MATCH_URL_PREFIX + r"((exhentai)\.org\/g\/[0-9]+\/[a-z0-9]+)" + MATCH_URL_END,
}

URLS = {
    'eh': 'https://e-hentai.org',
    'ex': 'https://exhentai.org',
    'api': 'https://api.e-hentai.org/api.php',
    'title_search': '{url}/?{query}&f_apply=Apply+Filter&advsearch=1&f_sname=on&f_stags=on&f_storr=on&f_srdd=2&f_sfl=on&f_sfu=on',
}

HEADERS = {'user-agent':"Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0"}

DEFAULT_CATEGORIES =  ['manga', 'doujinshi', 'non-h', 'artistcg', 'gamecg', 'western', 'imageset', 'cosplay', 'asianporn', 'misc']

PLUGIN_CONFIG = {
    'filename_search': True, # use the filename/folder-name for searching instead of gallery title
    'expunged_galleries': False, # enable expunged galleries in results
    'remove_namespaces': True, # remove superfluous namespaces like 'artist', 'language' and 'group' because they are handled specially in HPX
    'gallery_results_limit': 10, # maximum amount of galleries to return
    'blacklist_tags': [], # tags to ignore when updating tags
    'add_gallery_url': True, # add ehentai url to gallery
    'preferred_language': "english", # preferred gallery langauge (in gallery title) to extract from if multiple galleries were found, set empty string for default,
    'enabled_categories': DEFAULT_CATEGORIES, # categories that are enbaled in the search
    'search_query': "{title}", # the search query, '{title}' will be replaced with the gallery title, use double curly brackets to escape a bracket
    'search_low_power_tags': True, # enable search low power tags
    'search_torrent_name':True, # enable search torrent name
    'search_gallery_description': False, # enable search gallery description
}

@hpx.subscribe("init")
def inited():
    PLUGIN_CONFIG.update(hpx.get_plugin_config())

    # set default delay values if not set
    delays = hpx.get_setting("network", "delays", {})
    for u in (URLS['ex'], URLS['eh'], "https://api.e-hentai.org"):
        if u not in delays:
            log.info(f"Setting delay on {u} requests to {DEFAULT_DELAY}")
            delays[u] = DEFAULT_DELAY
            hpx.update_setting("network", "delays", delays)

@hpx.subscribe('config_update')
def config_update(cfg):
    PLUGIN_CONFIG.update(cfg)

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
        batch = 25,
        name = "E-Hentai",
        parser = URLS_REGEX['eh_gallery'],
        sites = ("https://e-hentai.org",),
        description = "Fetch metadata from E-Hentai",
        models = (
            hpx.command.GetDatabaseModel("Gallery"),
        )
    )

@hpx.attach("Metadata.info")
def metadata_info_ex():
    return hpx.command.MetadataInfo(
        identifier = "exhentai",
        batch = 25,
        name = "ExHentai",
        parser = URLS_REGEX['ex_gallery'],
        sites = ("https://exhentai.org",),
        description = "Fetch metadata from ExHentai",
        models = (
            hpx.command.GetDatabaseModel("Gallery"),
        )
    )

@hpx.attach("Metadata.query", trigger='ehentai')
def query_eh(itemtuple):
    log.info(f"Querying ehentai for metadata with {len(itemtuple)} items")
    return query(itemtuple)

@hpx.attach("Metadata.apply", trigger='ehentai')
def apply_eh(datatuple):
    log.info(f"Applying metadata from ehentai with {len(datatuple)} items")
    return apply(datatuple)

@hpx.attach("Metadata.query", trigger='exhentai')
def query_ex(itemtuple):
    log.info(f"Querying exhentai for metadata with {len(itemtuple)} items")
    if not hpx.command.GetLoginStatus(URLS['ex']):
        log.info("Not logged in to exhentai, aborting...")
        rtuple = []
        for i in itemtuple:
            mr = hpx.command.MetadataResult(data=hpx.command.MetadataData(metadataitem=i), status=False,
                    reason="Not logged in to exhentai, aborting...")
            rtuple.append(mr)
        return tuple(rtuple)
    return query(itemtuple, login_site=URLS['ex'])

@hpx.attach("Metadata.apply", trigger='exhentai')
def apply_ex(datatuple):
    log.info(f"Applying metadata from exhentai with {len(datatuple)} items")
    return apply(datatuple)

def query(itemtuple, login_site=URLS['eh']):
    """
    Called to query for candidates to extract metadata from.
    Note that HPX will handle choosing which candidates to extract data from.
    The attached handler should just return all the candidates found.

    Looks up on ehentai for matching items
    """
    mdata = []

    # get exhentai login session if applicable
    ex_login = hpx.command.GetLoginStatus(login_site) if "exhentai" in login_site else False
    login_session = None
    if ex_login:
        login_session = hpx.command.GetLoginSession(login_site)
    if login_site == 'exhentai':
        log.info(f"logged in to exhentai: {ex_login}")

    for mitem in itemtuple:
        gurls = [] # tuple of (title, url)

        url = mitem.url
        item = mitem.item
        options = mitem.options

        # url was provided
        if url:
            log.info(f"url provided: {url} for {item}")
            gurls.append((url, url))
        else: # manually search for id
            log.info(f"url not provided for {item}")
            if (ex_login if "exhentai" in login_site else True):
                # search with title
                i_title = ""
                i_hash = ""
                if PLUGIN_CONFIG.get("filename_search"):
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

                # TODO: search with hash
                if not gurls:
                    pass

        log.info(f"found {len(gurls)} urls for item: {item}")

        # list is sorted by date added so we reverse it
        gurls.reverse()

        log.debug(f"{gurls}")
        final_gurls = []
        # TODO: maybe prefer language of gallery first?
        pref_lang = PLUGIN_CONFIG.get('preferred_language')
        if pref_lang:
            for t in gurls:
                if pref_lang.lower() in t[0].lower():
                    final_gurls.insert(0, t)
                    continue
                final_gurls.append(t)
        else:
            final_gurls = gurls

        for t, u in final_gurls:
            g_id, g_token = parse_url(u)
            if g_id and g_token:
                mdata.append(hpx.command.MetadataData(
                    metadataitem=mitem,
                    title=t,
                    url=u,
                    data={
                        'gallery': [g_id, g_token],
                        'gallery_url': u,
                        }))
    log.info(f"Returning {len(mdata)} data items")
    return tuple(mdata)

def title_search(title, ex=True, session=None, _times=0):
    "Searches on ehentai for galleries with given title, returns a list of (title, matching gallery urls)"
    eh_url = URLS['title_search']
    log.debug(f"searching with title: {title}")
    sq = PLUGIN_CONFIG.get("search_query")

    params = {f'f_{c}': '0' for c in DEFAULT_CATEGORIES}

    try:
        sq = sq.format(title=title)
    except:
        log.warning("Failed to use customized search query")
        sq = title

    params['f_search'] = sq

    log.info(f"Final search query: {sq}")


    if PLUGIN_CONFIG.get("expunged_galleries"):
        params['f_sh'] = 'on'

    if PLUGIN_CONFIG.get("search_low_power_tags"):
        params['f_sdt1'] = 'on'

    if PLUGIN_CONFIG.get("search_gallery_description"):
        params['f_sdesc'] = 'on'

    if PLUGIN_CONFIG.get("search_torrent_name"):
        params['f_storr'] = 'on'

    for c in PLUGIN_CONFIG.get("enabled_categories"):
        params[f'f_{c.lower()}'] = '1'

    log.info(f"final params: {params}")
    param_query = urllib.parse.urlencode(params)

    f_eh_url = eh_url.format(
        url=URLS['ex'] if ex else URLS['eh'],
        query=param_query
        )
    log.info(f"final url: {f_eh_url}")
    r = eh_page_results(f_eh_url, session=session)

    if not r and not _times:

        kw = sq.split('"', 2) # if title was qouted, counts as 1 keyword
        kw_count = max(len(kw) - 1, 1)
        # this is pretty unreliable and won't detect qouted multi word tags
        kw_count += len(" ".join(kw[-1].split()).split(' ')) - 1 # some magic

        if kw_count > 8: # check if exceeds 8 keywords retry with quotes around title
            r = title_search(f'"{title}"', ex, session, _times=_times+1)

    return r

def eh_page_results(eh_page_url, limit=None, session=None):
    "Opens eh page, parses for results, and then returns list of (title, url)"
    found_urls = []
    if limit is None:
        limit = PLUGIN_CONFIG.get("gallery_results_limit")

    # prepare request
    req_props = hpx.command.RequestProperties(
        headers=HEADERS,
        )
    if session:
        req_props.session = session
        log.debug(f"COOKIES: {session.cookies.keys()}")
    r = hpx.command.SingleGETRequest().request(eh_page_url, req_props)
    soup = BeautifulSoup(r.text, "html.parser")
    list_style = "compact"
    dmi_div = soup.find("div", id="dms")
    if dmi_div:
        list_style = dmi_div.find("option", selected=True).string.lower()
    results = []
    if list_style == "compact":
        results = soup.findAll("td", class_="gl3c glname", limit=limit)
    elif list_style == "minimal":
        results = soup.findAll("td", class_="gl3m glname", limit=limit)
    elif list_style == "extended":
        results = soup.findAll("div", class_="gl4e glname", limit=limit)
    elif list_style == "thumbnail":
        results = soup.findAll("div", class_="gl4t glname", limit=limit)
    # str(x.a.string)
    found_urls = [(str(x.a.string), x.a['href']) for x in results] # title, url

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

def apply(datatuple):
    """
    Called to fetch and apply metadata to the given data items.
    Remember to set the `status` property on the :class:`MetadataResult` object to `True` on a successful fetch.
    """
    mresults = []
    applied = False
    eh_data = {
        'method': 'gdata',
        'gidlist': [],
        'namespace': 1
    }

    mdata_map = {} # (gid,token):metadatadata and gid:metadatadata

    for d in datatuple:
        eh_data['gidlist'].append(d.data['gallery'])
        mdata_map[tuple(d.data['gallery'])] = d
        mdata_map[d.data['gallery'][0]] = d # used for when token is invalid, assumes that there's no duplicate gid's

    # prepare request
    req_props = hpx.command.RequestProperties(
        headers=HEADERS,
        json=eh_data
        )
    r = hpx.command.SinglePOSTRequest().request(URLS['api'], req_props)
    if r.ok:
        response = r.json
        if response and not 'error' in response:
            for gdata in response['gmetadata']:
                if 'error' in gdata:
                    mdata = mdata_map[gdata['gid']]
                    mresults.append(hpx.command.MetadataResult(data=mdata, status=False, reason=gdata['error']))
                else:
                    mdata = mdata_map[(gdata['gid'], gdata['token'])]
                    urls_to_apply = []
                    if PLUGIN_CONFIG.get('add_gallery_url', True):
                        urls_to_apply.append(mdata.data['gallery_url'])
                    fdata = format_metadata(gdata, mdata.metadataitem.item, urls_to_apply=urls_to_apply)
                    applied = apply_metadata(fdata, mdata.metadataitem.item, mdata.options)
                    mresults.append(hpx.command.MetadataResult(data=mdata, status=applied, reason="No data was applied" if not applied else ""))

        elif response:
            log.warning(response)
            for d in datatuple:
                mresults.append(hpx.command.MetadataResult(data=d, status=False, reason=response['error']))

    return tuple(mresults)

def capitalize_text(text):
    """
    better str.capitalize
    """
    return " ".join(x.capitalize() for x in text.strip().split())

def format_metadata(gdata, item, urls_to_apply=None):
    """
    Formats metadata to look like this for apply_metadata:
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
    mdata = {}

    mdata['titles'] = []

    parsed_text = hpx.command.ItemTextParser(gdata['title'])
    
    parsed_title = parsed_text.extract_title()
    if parsed_title:
        parsed_title = parsed_title[0]
    mdata['titles'].append((parsed_title or gdata['title'], 'english'))

    mdata['titles'].append((gdata['title_jpn'], 'japanese'))


    mdata['category'] = gdata['category']
    mdata['pub_date'] = arrow.Arrow.fromtimestamp(gdata['posted'])

    lang = "japanese" # default language

    artists = set()
    circles = set()
    parodies = set()

    parsed_artists = parsed_text.extract_artist()
    parsed_circles = parsed_text.extract_circle()

    extranous_namespaces = ("artist", "parody", "group", "language")
    mdata['tags'] = {}
    for nstag in gdata['tags']:

        blacklist_tags = PLUGIN_CONFIG.get("blacklist_tags")
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
            for a in parsed_artists: # the artist extracted from the title likely has better capitalization, so choose that instead
                if a.lower() == t.lower():
                    artists.add(a)
                    break
            else:
                artists.add(t)
        elif ns == "group":
            for c in parsed_circles: # the circle extracted from the title likely has better capitalization, so choose that instead
                if c.lower() == t.lower():
                    circles.add(c)
                    break
            else:
                circles.add(t)
        elif ns == "parody":
            parodies.add(t)
        
        if not (PLUGIN_CONFIG.get("remove_namespaces") and ns in extranous_namespaces):
            mdata['tags'].setdefault(ns, []).append(t)
        else:
            log.debug(f"removing namespace {ns}")
        
    log.debug(f"tags: {mdata['tags']}")

    mdata['language'] = lang
    
    if parodies:
        mdata['parodies'] = parodies

    if artists:
        a_circles = []
        for a in artists:
            a_circles.append((a, tuple(circles))) # assign circles to each artist
        mdata['artists'] = a_circles

    if urls_to_apply:
        mdata['urls'] = urls_to_apply

    return mdata

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

def apply_metadata(data, gallery, options):
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
            gdata.titles = gtitles
            log.debug("applied titles")

    if isinstance(data.get('artists'), (list, tuple, set)):
        gartists = []
        for a, c in data['artists']:
            if a:
                gartist = ArtistData(names=[ArtistNameData(name=capitalize_text(a))])
                gartists.append(gartist)

                if c:
                    gcircles = []
                    for circlename in [x for x in c if x]:
                        gcircles.append(CircleData(name=capitalize_text(circlename)))
                    gartist.circles = gcircles

        if gartists:
            gdata.artists = gartists
            log.debug("applied artists")

    if isinstance(data.get('parodies'), (list, tuple, set)):
        gparodies = []
        for p in data['parodies']:
            if p:
                gparody = ParodyData(names=[ParodyNameData(name=capitalize_text(p))])
                gparodies.append(gparody)

        if gparodies:
            gdata.parodies = gparodies
            log.debug("applied parodies")

    if data.get('category'):
        gdata.category = CategoryData(name=data['category'])
        log.debug("applied category")
    
    if data.get('language'):
        gdata.language = LanguageData(name=data['language'])
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
            gdata.tags = gnstags
            log.debug("applied tags")

    if isinstance(data.get('pub_date'), (datetime.datetime, arrow.Arrow)):
        pub_date = data['pub_date']
        gdata.pub_date = pub_date
        log.debug("applied pub_date")

    if isinstance(data.get('urls'), (list, tuple)):
        gurls = []
        for u in data['urls']:
            if u:
                gurls.append(UrlData(name=u))
        if gurls:
            gdata.urls = gurls
            log.debug("applied urls")

    applied = hpx.command.UpdateItemData(gallery, gdata, options=options)

    log.debug(f"applied: {applied}")

    return applied