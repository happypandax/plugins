# main.py
import datetime
import html
import os
import urllib

import __hpx__ as hpx
import arrow
import regex
from bs4 import BeautifulSoup

import happypanda.core.commands.item_cmd

log = hpx.get_logger("main")

MATCH_URL_PREFIX = r"^(http\:\/\/|https\:\/\/)?(www\.)?"  # http:// or https:// + www.
MATCH_URL_END = r"\/?$"

DEFAULT_DELAY = 1.5

URLS_REGEX = {
    'gallery': MATCH_URL_PREFIX + r"(panda\.chaika\.moe\/(archive|gallery)\/[0-9]+)" + MATCH_URL_END,
    }

URLS = {
    'ch': 'https://panda.chaika.moe',
    'gallery': 'https://panda.chaika.moe/gallery/',
    'archive': 'https://panda.chaika.moe/archive/',
    'gallery_api': 'https://panda.chaika.moe/jsearch?gallery=',
    'archive_api': 'https://panda.chaika.moe/jsearch?archive=',
    'hash_api': 'https://panda.chaika.moe/jsearch?sha1=',
    'title_search': "https://panda.chaika.moe/galleries/?title={title}&tags=&category=&provider=&uploader=&rating_from=&rating_to=&filesize_from=&filesize_to=&filecount_from=&filecount_to=&sort=posted&asc_desc=desc&apply="
    }

HEADERS = { 'user-agent': "Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0" }

PLUGIN_CONFIG = {
    'filename_search': False,  # use the filename/folder-name for searching instead of gallery title
    'remove_namespaces': True,  # remove superfluous namespaces like 'artist', 'language' and 'group' because they are handled specially in HPX
    'gallery_results_limit': 10,  # maximum amount of galleries to return
    'blacklist_tags': [],  # tags to ignore when updating tags
    'add_gallery_url': True,  # add ehentai url to gallery
    'preferred_language': "english",  # preferred gallery langauge (in gallery title) to extract from if multiple galleries were found, set empty string for default
    }


@hpx.subscribe("init")
def inited():
    PLUGIN_CONFIG.update(hpx.get_plugin_config())

    # set default delay values if not set
    delays = hpx.get_setting("network", "delays", { })
    for u in (URLS['ch'],):
        if u not in delays:
            log.info(f"Setting delay on {u} requests to {DEFAULT_DELAY}")
            delays[u] = DEFAULT_DELAY
            hpx.update_setting("network", "delays", delays)


@hpx.subscribe('config_update')
def config_update( cfg ):
    PLUGIN_CONFIG.update(cfg)


@hpx.subscribe("disable")
def disabled():
    pass


@hpx.subscribe("remove")
def removed():
    pass


@hpx.attach("Metadata.info")
def metadata_info():
    return hpx.command.MetadataInfo(
        identifier="chaika",
        name="Panda.Chaika",
        parser=URLS_REGEX['gallery'],
        sites=("https://panda.chaika.moe",),
        description="Fetch metadata from Panda.Chaika",
        models=(
            hpx.command.GetDatabaseModel("Gallery"),
            )
        )


@hpx.attach("Metadata.query", trigger="chaika")
def query( itemtuple ):
    """
    Called to query for candidates to extract metadata from.
    Note that HPX will handle choosing which candidates to extract data from.
    The attached handler should just return all the candidates found.
    """
    log.info("Querying chaika for metadata")
    mdata = []
    for mitem in itemtuple:
        item = mitem.item
        url = mitem.url
        gurls = []  # tuple of (title, url)
        # url was provided
        if url:
            log.info(f"url provided: {url} for {item}")
            gurls.append((url, url))
        else:  # manually search for id
            log.info(f"url not provided for {item}")
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
                    i_title = item.titles[0].name  # make user choice
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
            g_type, g_id = parse_url(u)
            if g_type and g_id:
                mdata.append(hpx.command.MetadataQuery(
                    metadataitem=mitem,
                    title=t,
                    url=u,
                    data={
                        'type': g_type,
                        'id': g_id,
                        'gallery_url': u,
                        }
                    )
                    )
    return tuple(mdata)


@hpx.attach("Metadata.apply", trigger="chaika")
def apply( datatuple ):
    """
    Called to fetch and apply metadata to the given data items.
    Remember to set the `status` property on the :class:`MetadataResult` object to `True` on a successful fetch.
    """
    log.info("Applying metadata from chaika")
    mresult = []

    for mdata in datatuple:
        applied = False
        # prepare request
        req_props = hpx.command.RequestProperties(
            headers=HEADERS,
            )

        api_url = URLS['archive_api'] if mdata.data['type'] == 'archive' else URLS['gallery_api']
        api_url += str(mdata.data['id'])

        r = hpx.command.SingleGETRequest().request(api_url, req_props)
        if r.ok:
            response = r.json
            if response and not 'result' in response:
                filtered_data = format_metadata(response, mdata.item, apply_url=PLUGIN_CONFIG.get('add_gallery_url', True), gallery_url=mdata.data['gallery_url'])
                applied = apply_metadata(filtered_data, mdata.item, mdata.options)
            elif response:
                log.warning(response)
            reason = ""
            if not applied and 'result' in response:
                reason = response['result']
            mresult.append(hpx.command.MetadataResult(data=mdata, status=applied, reason=reason))
        log.info(f"Applied: {applied}")
    return tuple(mresult)


def title_search( title, session=None, _times=0 ):
    "Searches on chaika for galleries with given title, returns a list of (title, matching gallery urls)"
    search_url = URLS['title_search']
    log.debug(f"searching with title: {title}")
    f_url = search_url.format(
        title=urllib.parse.quote_plus(title)
        )
    log.debug(f"final url: {f_url}")
    r = page_results(f_url, session=session)
    if not r and not _times:
        title = regex.sub(r"\(.+?\)|\[.+?\]", "", title)
        title = " ".join(title.split())
        r = title_search(title, session, _times=_times + 1)
    return r


def page_results( page_url, limit=None, session=None ):
    "Opens chaika page, parses for results, and then returns list of (title, url)"
    found_urls = []
    if limit is None:
        limit = PLUGIN_CONFIG.get("gallery_results_limit")

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
    found_urls = [(str(x.a.string), URLS['ch'] + x.a['href']) for x in results]  # title, url

    if not found_urls:
        log.warning(f"No results found on url: {page_url}")
        log.debug(f"HTML: {r.text}")
    return found_urls


def parse_url( url ):
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


def capitalize_text( text ):
    """
    better str.capitalize
    """
    return " ".join(x.capitalize() for x in text.strip().split())


def format_metadata( gdata, item, apply_url=False, gallery_url=None ):
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
    mdata = { }

    mdata['titles'] = []

    parsed_text = hpx.command.ItemTextParser(gdata['title'])

    parsed_title = parsed_text.extract_title()
    if parsed_title:
        parsed_title = parsed_title[0]
    mdata['titles'].append((parsed_title or gdata['title'], 'english'))

    mdata['titles'].append((gdata['title_jpn'], 'japanese'))

    mdata['category'] = gdata['category']
    if gdata['posted']:
        mdata['pub_date'] = arrow.Arrow.fromtimestamp(gdata['posted'])

    lang = "japanese"  # default language

    artists = set()
    circles = set()
    parodies = set()

    parsed_artists = parsed_text.extract_artist()
    parsed_circles = parsed_text.extract_circle()

    extranous_namespaces = ("artist", "parody", "group", "language")
    mdata['tags'] = { }

    for nstag in gdata['tags']:
        onstag = nstag
        nstag = nstag.replace('_', ' ')
        blacklist_tags = PLUGIN_CONFIG.get("blacklist_tags")
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
            for a in artists:  # the artist extracted from the title likely has better capitalization, so choose that instead
                if a.lower() == t.lower():
                    artists.add(a)
                    break
            else:
                artists.add(t)
        elif ns == "group":
            for c in circles:  # the circle extracted from the title likely has better capitalization, so choose that instead
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
            a_circles.append((a, tuple(circles)))  # assign circles to each artist
        mdata['artists'] = a_circles

    if apply_url:
        if gdata.get('gallery', False):
            mdata['urls'] = [URLS['gallery'] + f"{gdata['gallery']}/"]
        elif gallery_url:
            mdata['urls'] = [gallery_url]

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
NamespaceTagData = hpx.command.NamespaceTagData
TagData = hpx.command.TagData
NamespaceData = hpx.command.NamespaceData


def apply_metadata( data, gallery, options ):
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
            data['tags'] = { None: data['tags'] }
        gnstags = []
        for ns, tags in data['tags'].items():
            if ns is not None:
                ns = ns.strip()
            if ns and ns.lower() == 'misc':
                ns = None
            for t in tags:
                t = t.strip()
                if t:
                    kw = { 'tag': TagData(name=t) }
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

    applied = happypanda.core.commands.item_cmd.UpdateItemData(gallery, gdata, options=options)

    log.debug(f"applied: {applied}")

    return applied
