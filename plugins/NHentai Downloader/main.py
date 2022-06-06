# main.py
import __hpx__ as hpx

from bs4 import BeautifulSoup

DownloadRequest = hpx.command.DownloadRequest

log = hpx.get_logger("main")

IDENTIFIER = "nhentai"
HEADERS = {'user-agent':"Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0"}
DEFAULT_DELAY = 1.5

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
    delay_url = "https://nhentai.net/g/"
    if delay_url not in delays:
        log.info(f"Setting delay on {delay_url} requests to {DEFAULT_DELAY}")
        delays[delay_url] = DEFAULT_DELAY
        hpx.update_setting("network", "delays", delays)

@hpx.attach("Download.info")
def download_info():
    return hpx.command.DownloadInfo(
        identifier = IDENTIFIER,
        name = "NHentai",
        parser = r"(?=((?:https://)?nhentai.net/g/([^/]+/)))\1",
        sites = ("https://nhentai.net",),
        description = "Download manga and doujinshi from nhentai.net",
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
    # prepare request
    req_props = hpx.command.RequestProperties(
        headers=HEADERS,
        )
    req = hpx.command.SingleGETRequest().request(item.url, req_props)

    log.info(f"querying url: {item.url}")

    download_requests = []

    if req.ok:
        log.info("request was successful")
        # parse html page
        soup = BeautifulSoup(req.text, "html.parser")

        # get gallery information
        log.info("parsing gallery info")
        info_div = soup.find("div", id="info")
        if info_div:
            title_el = soup.find("h1", class_="title")
            if title_el:
                title_name = soup.find("span", class_="pretty")
                if title_name:
                    item.name = str(title_name.string)
                    log.info(f"found name of gallery: {item.name}")
        else:
            log.warning("couldn't find gallery info div")

        # get gallery cover url
        cover_div = soup.find("div", id="cover")
        if cover_div:
            cover_img = cover_div.find("img")
            if cover_img:
                try:
                    download_requests.append(DownloadRequest(downloaditem=item, url=cover_img['data-src'], is_thumbnail=True))
                except:
                    log.warning("failed to get cover src")

        # get gallery page urls
        thumbs_div = soup.find("div", id="thumbnail-container")
        all_links = thumbs_div.findAll("a")
        if all_links:
            log.info(f"found {len(all_links)} thumbnail links")
            for l in all_links:
                # collect the urls to the page images
                # nhentai has a simple url system where thumbs are stored at
                # https://t.nhentai.net/galleries/1498842/2t.jpg
                # and the real image at
                # https://i.nhentai.net/galleries/1498842/2.jpg
                url_parts = l.img['data-src'] # img is lazy loaded so src isn't available
                if url_parts:
                    url_parts = url_parts.split('/')
                    img_id = url_parts[-2]
                    thumb_number = url_parts[-1]
                    img_number = thumb_number.replace('t', '')
                    # construct url for real image
                    img_url = "https://i.nhentai.net/galleries/{}/{}".format(img_id, img_number)
                    log.debug(f"final image url parsed to be: {img_url}")
                    # finally add the url to the list of requests for HPX downloader to take care of the rest
                    download_requests.append(DownloadRequest(downloaditem=item, url=img_url))
                else:
                    log.warning("failed to get thumbnail src")
        else:
            log.warning("couldn't find any thumbnail links")
    else:
        log.warning("request failed")

    if download_requests:
        log.info(f"was able to prepare requests for {len(download_requests)} images")
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
    # there's nothing special to post-process in the case of nhentai downloader, so just return the result as is
    log.info(f"download of images was successful for {result.downloaditem.name}")
    return result
