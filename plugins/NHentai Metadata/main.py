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

IDENTIFIER = "nhentai"

URLS = {
    'nh': 'https://nhentai.net',
    'title_search': "https://nhentai.net/search/?q={title}"
    }

HEADERS = { 'user-agent': "Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0" }

PLUGIN_CONFIG = {
    'filename_search': False,  # use the filename/folder-name for searching instead of gallery title
    'remove_namespaces': True,  # remove superfluous namespaces like 'artists', 'languages' and 'groups' because they are handled specially in HPX
    'gallery_results_limit': 10,  # maximum amount of galleries to return
    'blacklist_tags': [],  # tags to ignore when updating tags
    'add_gallery_url': True,  # add nhentai url to gallery
    'preferred_language': "english",  # preferred gallery langauge (in gallery title) to extract from if multiple galleries were found, set empty string for default
    'search_query': "{title}",  # the search query, '{title}' will be replaced with the gallery title, use double curly brackets to escape a bracket
    }


@hpx.subscribe("init")
def inited():
    PLUGIN_CONFIG.update(hpx.get_plugin_config())

    # set default delay values if not set
    delays = hpx.get_setting("network", "delays", { })
    for u in (URLS['nh'],):
        if u not in delays:
            log.info(f"Setting delay on {u} requests to {DEFAULT_DELAY}")
            delays[u] = DEFAULT_DELAY
            hpx.update_setting("network", "delays", delays)


@hpx.subscribe('config_update')
def config_update( cfg ):
    PLUGIN_CONFIG.update(cfg)


@hpx.attach("Metadata.info")
def metadata_info():
    return hpx.command.MetadataInfo(
        identifier=IDENTIFIER,
        name="nhentai",
        parser=MATCH_URL_PREFIX + r"(nhentai\.net\/g\/[0-9]{3,10})" + MATCH_URL_END,
        sites=("https://nhentai.net",),
        description="Fetch metadata from nhentai.net",
        models=(
            hpx.command.GetDatabaseModel("Gallery"),
            )
        )


@hpx.attach("Metadata.query", trigger=IDENTIFIER)
def query( itemtuple ):
    """
    Called to query for candidates to extract metadata from.
    Note that HPX will handle choosing which candidates to extract data from.
    The attached handler should just return all the candidates found.
    """
    log.info("Querying nhentai for metadata")
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
            if PLUGIN_CONFIG.get("filename_search"):
                sources = item.get_sources()
                if sources:
                    # get folder/file name
                    i_title = os.path.split(sources[0])[1]
                    # remove ext
                    i_title = os.path.splitext(i_title)[0]
            else:
                if item.titles:
                    i_title = item.titles[0].name  # make user choice?
            if i_title:
                gurls = title_search(i_title)

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
            g_id = parse_url(u)
            if g_id:
                mdata.append(hpx.command.MetadataQuery(
                    metadataitem=mitem,
                    title=t,
                    url=u,
                    data={
                        'id': g_id,
                        'gallery_url': u,
                        }
                    )
                    )
    return tuple(mdata)


@hpx.attach("Metadata.apply", trigger=IDENTIFIER)
def apply( datatuple ):
    """
    Called to fetch and apply metadata to the given data items.
    Remember to set the `status` property on the :class:`MetadataResult` object to `True` on a successful fetch.
    """
    log.info("Applying metadata from nhentai")
    mresult = []

    for mdata in datatuple:
        applied = False
        # prepare request
        req_props = hpx.command.RequestProperties(
            headers=HEADERS,
            )

        gallery_url = mdata.data['gallery_url']

        r = hpx.command.SingleGETRequest().request(gallery_url, req_props)
        if r.ok:
            response = r.text
            if response and not '404 – Not Found' in response:
                filtered_data = format_metadata(response, mdata.item, apply_url=PLUGIN_CONFIG.get('add_gallery_url', True), gallery_url=gallery_url)
                applied = apply_metadata(filtered_data, mdata.item, mdata.options)
            elif response:
                log.debug(response)
            mresult.append(hpx.command.MetadataResult(data=mdata, status=applied))
            log.info(f"Applied: {applied}")
        else:
            log.warning(f"Request returned bad status: {r.status_code}")
    return tuple(mresult)


def title_search( title, _times=0 ):
    "Searches on nhentai for galleries with given title, returns a list of (title, matching gallery urls)"
    search_url = URLS['title_search']
    log.debug(f"searching with title: {title}")

    sq = PLUGIN_CONFIG.get("search_query")
    try:
        sq = sq.format(title=title)
    except:
        log.warning("Failed to use customized search query")
        sq = title

    log.info(f"Final search query: {sq}")

    f_url = search_url.format(
        title=urllib.parse.quote_plus(sq)
        )

    log.debug(f"final url: {f_url}")

    r = page_results(f_url)

    if not r and not _times:
        title = regex.sub(r"\(.+?\)|\[.+?\]", "", title)
        title = " ".join(title.split())
        r = title_search(title, _times=_times + 1)
    return r


def page_results( page_url, limit=None ):
    "Opens nhentai page, parses for results, and then returns list of (title, url)"
    found_urls = []  # title, url
    if limit is None:
        limit = PLUGIN_CONFIG.get("gallery_results_limit")

    # prepare request
    req_props = hpx.command.RequestProperties(
        headers=HEADERS,
        )
    r = hpx.command.SingleGETRequest().request(page_url, req_props)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    results = soup.findAll("div", class_="gallery", limit=limit)
    for x in results:
        # str(x.a.string)
        t = ""
        cap = x.find("div", class_="caption")
        if cap:
            t = str(cap.string)
        u = URLS['nh'] + x.a['href']
        found_urls.append((t or u, u))

    if not found_urls:
        log.warning(f"No results found on url: {page_url}")
        log.debug(f"HTML: {r.text}")
    return found_urls


def parse_url( url ):
    "Extracts the gallery id from url"
    gallery_id = None

    gallery_id_token = regex.search('(?<=g/)([0-9]+)', url)
    if gallery_id_token:
        gallery_id = gallery_id_token.group()
    else:
        log.warning("Error extracting gallery id from url: {}".format(url))
    return gallery_id


def capitalize_text( text ):
    """
    better str.capitalize
    """
    return " ".join(x.capitalize() for x in text.strip().split())


def format_metadata( text, item, apply_url=False, gallery_url=None ):
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

    soup = BeautifulSoup(text, "html.parser")
    info_div = soup.find("div", id="info")
    if info_div:

        mdata['titles'] = []

        parsed_text = None
        eng_title = info_div.find("h1")
        if eng_title:
            eng_title = str(eng_title.text)
            parsed_text = hpx.command.ItemTextParser(eng_title)

            parsed_title = parsed_text.extract_title()
            if parsed_title:
                parsed_title = parsed_title[0]

            mdata['titles'].append((parsed_title or eng_title, 'english'))

        jp_title = info_div.find("h2")
        if jp_title:
            mdata['titles'].append((str(jp_title.text), 'japanese'))

        parsed_artists = parsed_text.extract_artist() if parsed_text else []
        parsed_circles = parsed_text.extract_circle() if parsed_text else []

        artists = set()
        circles = set()
        parodies = set()

        lang = "japanese"  # default language

        tags_containers = info_div.find("section", id="tags")
        if tags_containers:
            extranous_namespaces = ("artists", "categories", "parodies", "groups", "languages")
            blacklist_tags = [x.lower() for x in PLUGIN_CONFIG.get("blacklist_tags")]
            for tag_container in tags_containers.findAll("div", class_="tag-container"):
                ns = list(tag_container.stripped_strings)[0]
                if not ns:
                    continue
                ns = ns[:-1]  # remove colon
                ns = ns.lower()
                tags = [list(x.stripped_strings)[0] for x in tag_container.findAll("a", class_="tag")]

                nstag = lambda t: ns + ':' + t

                if ns == "artists":
                    for t in tags:
                        if blacklist_tags and nstag(t) in blacklist_tags:
                            continue
                        for a in parsed_artists:  # the artist extracted from the title likely has better capitalization, so choose that instead
                            if a.lower() == t.lower():
                                artists.add(a)
                                break
                        else:
                            artists.add(t)
                elif ns == "groups":
                    for t in tags:
                        if blacklist_tags and nstag(t) in blacklist_tags:
                            continue
                        for a in parsed_circles:  # the circle extracted from the title likely has better capitalization, so choose that instead
                            if a.lower() == t.lower():
                                circles.add(a)
                                break
                        else:
                            circles.add(t)
                elif ns == "parodies":
                    for t in tags:
                        if blacklist_tags and nstag(t) in blacklist_tags:
                            continue
                        parodies.add(t)
                elif ns == "categories":
                    t = tags[0]  # only supports one
                    if not (blacklist_tags and nstag(t) in blacklist_tags):
                        mdata['category'] = capitalize_text(t)
                elif ns == "languages":
                    for t in tags:
                        if blacklist_tags and nstag(t) in blacklist_tags:
                            continue
                        if t in ('translated'):
                            continue
                        lang = t  # only supports one

                if PLUGIN_CONFIG.get("remove_namespaces") and ns in extranous_namespaces:
                    if ns == 'languages':  # keep other tags
                        tags = [x for x in tags if x != lang]
                    else:
                        continue

                # add rest as tags
                if tags:
                    mdata.setdefault('tags', { })
                    for t in tags:
                        if blacklist_tags and nstag(t) in blacklist_tags:
                            continue
                        if ns == 'tags':
                            mdata['tags'].setdefault(None, []).append(t)
                        else:
                            mdata['tags'].setdefault(ns, []).append(t)

        mdata['language'] = lang

        if not artists:
            artists.union(set(parsed_artists))
        if not circles:
            circles.union(set(parsed_circles))

        if parodies:
            mdata['parodies'] = parodies

        if artists:
            a_circles = []
            for a in artists:
                a_circles.append((a, tuple(circles)))  # assign circles to each artist
            mdata['artists'] = a_circles

        if apply_url:
            mdata['urls'] = [gallery_url]

    log.debug(f"formatted data: {mdata}")

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
