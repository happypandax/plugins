# main.py
import __hpx__ as hpx
import regex

from bs4 import BeautifulSoup

DownloadRequest = hpx.command.DownloadRequest

log = hpx.get_logger("main")

IDENTIFIER = "chaika"
HEADERS = {'user-agent':"Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0"}
DEFAULT_DELAY = 0.5

URLS = {
    'ch': 'https://panda.chaika.moe',
    'gallery_api': 'https://panda.chaika.moe/jsearch?gallery=',
}

def website_url_regex_gen(domain, path_regex=None, variable_port=False, variable_tld=False, trailing_slash=True, end=True, trailing_fragment=True):
    """
    Generates a regex suitable for a specific domain
    """
    rgx = r"^(http\:\/\/|https\:\/\/)?(www\.)?({})".format(domain)
    if variable_tld:
        rgx += r"\.[a-z]{2,5}"
    if variable_port:
        rgx += r"(:[0-9]{1,5})?"
    if trailing_slash:
        rgx += r"\/?"
    if path_regex:
        rgx += path_regex
    if trailing_slash:
        rgx += r"\/?"
    if trailing_fragment:
        rgx += r"(#\S+)?"
    if end:
        rgx += "$"
    return rgx

@hpx.subscribe("init")
def inited():
    # set default delay if not set
    delays = hpx.get_setting("network", "delays", {})
    delay_url = URLS['ch']
    if delay_url not in delays:
        log.info(f"Setting delay on {delay_url} requests to {DEFAULT_DELAY}")
        delays[delay_url] = DEFAULT_DELAY
        hpx.update_setting("network", "delays", delays)

@hpx.attach("Download.info")
def download_info():
    return hpx.command.DownloadInfo(
        identifier = IDENTIFIER,
        name = "Chaika",
        parser = website_url_regex_gen("panda.chaika.moe", path_regex=r"(gallery|archive)\/[0-9]{3,15}", trailing_slash=True, variable_tld=False, trailing_fragment=True, end=True),
        sites = ("https://panda.chaika.moe",),
        description = "Download manga and doujinshi from  panda.chaika.moe",
    )

@hpx.attach("Download.query", trigger=IDENTIFIER)
def download_query(item):
    """
    Called to query for resource URLs that should be downloaded.
    Note that HPX will handle the actual downloading part.
    The attached handler should just return all the URLs that should be downloaded in the form of .:class:`DownloadRequest` objects

    should return:
    a tuple of :class:`DownloadRequest` for all the URL resources that should be downloaded.
    Note that the download system is recursive, so if the URL resource matches a download handler (the same or a different one),
    That handler will be called upon with a new :class:`DownloadItem` for that particular URL
    (though only once, meaning, no handler will be called upon again with the exact same URL during a single session)
    """

    log.info(f"querying url: {item.url}")

    # prepare request
    req_props = hpx.command.RequestProperties(
        headers=HEADERS,
        )

    # chaika has a simple url system where every download url is in the form of https://panda.chaika.moe/archive/32870/download/
    # if the url is a gallery url, find and retrieve the archive urls

    url_type, gid = parse_url(item.url)

    download_urls = []

    if url_type == 'gallery':
        log.info(f"url was a gallery url, retrieving archive urls")
        req = hpx.command.SingleGETRequest().request(URLS['gallery_api']+str(gid), req_props)
        if req.ok:
            log.info("request was successful")

            # get all archive urls
            a_urls = req.json.get("archives")
            if a_urls:
                # we also get to set the name of this download item
                title = req.json.get('title')
                if title:
                    item.name = title

                for a in a_urls:
                    download_urls.append(URLS['ch']+a['download'])
    else:
        download_urls.append(URLS['ch']+f"/archive/{gid}/download/")


    download_requests = []

    if download_urls:
        log.debug(f"found {len(download_urls)} download urls: {download_urls}")
        for durl in download_urls:
            download_requests.append(DownloadRequest(downloaditem=item, url=durl))

    if download_requests:
        log.info(f"was able to prepare requests for {len(download_requests)} urls")
    return tuple(download_requests)

@hpx.attach("Download.done", trigger=IDENTIFIER)
def download_done(result):
    """
    Called when downloading of all :class:`DownloadRequest` for a specific :class:`DownloadItem` has finished.
    The handler should do any post-processing here (archive files, rename files or folders, delete extranous files and etc.).
    Remember to set the `status` property on the :class:`DownloadResult` object to `False` if the post-processing was a failure.
    Note that the handler should *not* import the file into HPX (if it's an item), that part will be taken care of by HPX

    should return:
    the same :class:`DownloadResult` that was provided to the handler, potentially modified on the 'path' or `status` and `reason` properties
    """
    # there's nothing special to post-process in the case of chaika downloader, so just return the result as is
    log.info(f"download of archive was successful for {result.downloaditem.name}")
    return result

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
