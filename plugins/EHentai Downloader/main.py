# main.py
import __hpx__ as hpx
import regex
import json
from bs4 import BeautifulSoup

DownloadRequest = hpx.command.DownloadRequest

log = hpx.get_logger("main")

EH_IDENTIFIER = "ehentai"
EX_IDENTIFIER = "exhentai"

HEADERS = {'user-agent':"Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0"}
DEFAULT_DELAY = 5

URLS = {
    'eh': 'https://e-hentai.org',
    'ex': 'https://exhentai.org',
    'e_api': 'https://api.e-hentai.org/api.php',
    'ex_api': 'https://exhentai.org/api.php',
    'e_archiver': 'https://e-hentai.org/archiver.php?gid={gallery_id}&token={gallery_token}&or={archiver_key}',
    'ex_archiver': 'https://exhentai.org/archiver.php?gid={gallery_id}&token={gallery_token}&or={archiver_key}',
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
    # set default delay values if not set
    delays = hpx.get_setting("network", "delays", {})
    for u in (URLS['ex'], URLS['eh'], "https://api.e-hentai.org", URLS['ex_api']):
        if u not in delays:
            log.info(f"Setting delay on {u} requests to {DEFAULT_DELAY}")
            delays[u] = DEFAULT_DELAY
            hpx.update_setting("network", "delays", delays)

@hpx.attach("Download.info")
def eh_download_info():
    return hpx.command.DownloadInfo(
        identifier = EH_IDENTIFIER,
        name = "E-Hentai",
        parser = website_url_regex_gen("e-hentai.org", path_regex=r"g\/[0-9]{3,10}\/[0-9a-zA-Z]{3,15}", trailing_slash=True, variable_tld=False, trailing_fragment=True, end=True),
        sites = ("https://e-hentai.org",),
        description = "Download manga and doujinshi from e-hentai.org",
    )

@hpx.attach("Download.info")
def ex_download_info():
    return hpx.command.DownloadInfo(
        identifier = EX_IDENTIFIER,
        name = "ExHentai",
        parser = website_url_regex_gen("exhentai.org", path_regex=r"g\/[0-9]{3,10}\/[0-9a-zA-Z]{3,15}", trailing_slash=True, variable_tld=False, trailing_fragment=True, end=True),
        sites = ("https://exhentai.org",),
        description = "Download manga and doujinshi from exhentai.org",
    )

@hpx.attach("Download.query", trigger=EH_IDENTIFIER)
def eh_download_query(item):
    return download_query(item, False)

@hpx.attach("Download.query", trigger=EX_IDENTIFIER)
def ex_download_query(item):
    return download_query(item, True)

def download_query(item, is_exhentai):
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

    gid, gtoken = parse_url(item.url)
    download_requests = []

    #===============================================================================
    # get ehentai login
    login_site = URLS['ex'] if is_exhentai else URLS['eh']
    login_status = hpx.command.GetLoginStatus(login_site)
    login_session = None
    if login_status:
        login_session = hpx.command.GetLoginSession(login_site)
    if not login_session:
        log.warning("unable to get a login sesion for querying gallery data")
        return ()
    log.info("logged in, attempting to download archive")

    #===============================================================================
    # get the gallery metadata which should have the archive key
    # https://ehwiki.org/wiki/API#Gallery_Metadata
    log.info("getting archiver key")
    eh_data = {
        'method': 'gdata',
        'gidlist': [[gid, gtoken]],
    }
    req_props = hpx.command.RequestProperties(
        headers=HEADERS,
        json=eh_data,
        session=login_session
        )
    api_url = URLS['ex_api' if is_exhentai else 'e_api']
    log.info(f"requesting with api url {api_url}")
    r = hpx.command.SinglePOSTRequest().request(api_url, req_props)
    if not r.ok:
        log.warning(f"got invalid metadata page or bad status: {r.status_code}")
        log.debug(r.text)
        return ()
    try:
        response = r.json
    except json.JSONDecodeError:
        response = None
        log.info("got empty response when trying to retrieve archiver key, this usually means that user has no access to exhentai")
        return ()
    if not response or 'error' in response:
        log.warning("response has an error of some sort, and so we have no archive key to use")
        log.debug(r.text)
        return ()

    #===============================================================================
    # Read the metadata of the gallery to fill out the download queue item
    #
    # While in theory we should only ever have a single entry in the response, best keep it more general just in case this gets retrofitted to handle multiple urls at once
    # The information we reliably get is the thumbnail url and the title of the gallery
    # We seem to also always get an archive key, but the key is not always valid, and so the archive url request can fail
    #
    # Yes, there is an expunged flag in the metadata, but it is always false when the gallery/archive is not available
    # It is also true sometimes and yet the gallery/archive is totally accessable and so is meaningless
    for gdata in response['gmetadata']:
        archive_req = False
        try:
            if 'title' in gdata:
                item.name = gdata['title']
            if 'thumb' in gdata:
                download_requests.append(
                    DownloadRequest(
                        downloaditem=item,
                        url=gdata['thumb'],
                        is_thumbnail=True,
                        properties=hpx.command.RequestProperties(method=hpx.Method.GET, headers=HEADERS, session=login_session), # we need to use the same session
                        ))
            if 'archiver_key' in gdata:
                log.info(f"found archiver key for gallery {(gid, gtoken)}")
                a_key = gdata['archiver_key']
                a_url = URLS['ex_archiver' if is_exhentai else 'e_archiver'].format(gallery_id=gid, gallery_token=gtoken, archiver_key=a_key)
                form_data = {
                    "dltype": "org", #original quality, instead of a resampled version
                    "dlcheck": "Download Original Archive"
                    }
                req_props = hpx.command.RequestProperties(
                    headers=HEADERS,
                    data=form_data,
                    session=login_session
                    )
                r = hpx.command.SinglePOSTRequest().request(a_url, req_props)
                if r.ok:
                    if "Insufficient funds" in r.text:
                        log.info("Unable to grab gallery archive due to insufficent funds (GP) on the account")
                        item.name = "(Insufficient GP) "+item.name
                    elif "Key missing, or incorrect key provided" not in r.text:
                        soup = BeautifulSoup(r.text, "html.parser")
                        dp_url = soup.find("p", id="continue")
                        if dp_url and dp_url.a: # finally
                            download_requests.append(
                                DownloadRequest(
                                    downloaditem=item,
                                    url=dp_url.a['href'] + '?start=1',
                                    properties=hpx.command.RequestProperties(method=hpx.Method.GET, headers=HEADERS, session=login_session), # we need to use the same session
                                    filename=item.name.strip()+'.zip'))
                            archive_req = True
                            log.debug(f"adding the archive url {download_requests[-1].url}")
                    if not archive_req:
                        log.info("Something went wrong and we did not actually find a URL")
                        #TODO Actually better handle the various cases of why we do not have a url
                else:
                    log.warning(f"got invalid key page or bad status: {r.status_code}")
                    if r.status_code == 404 and "This gallery is currently unavailable" in r.text:
                        #We know that there is a valid key for us to get here, so the gallery existed at some point in the past
                        #This seems like it is most of the time a copyright takedown, but I have no idea why this is not marked as expunged
                        item.name = "(Gallery Unavailable) "+item.name
            else:
                log.warning(f"didn't find archiver key for data: {eh_data}")
                item.name = "(Archive Unavailable) "+item.name
        except Exception as e:
            log.debug(f"got an error, last request content: \n\t {r.text}")
            raise

        if not archive_req:
            pass
            # TODO: download individual images instead

    if download_requests:
        log.info(f"was able to prepare {len(download_requests)} requests")
    else:
        log.info("unable to prepare any URLs to download")
    return tuple(download_requests)

@hpx.attach("Download.done", trigger=[EX_IDENTIFIER, EH_IDENTIFIER])
def download_done(result):
    """
    Called when downloading of all :class:`DownloadRequest` for a specific :class:`DownloadItem` has finished.
    The handler should do any post-processing here (archive files, rename files or folders, delete extranous files and etc.).
    Remember to set the `status` property on the :class:`DownloadResult` object to `False` if the post-processing was a failure.
    Note that the handler should *not* import the file into HPX (if it's an item), that part will be taken care of by HPX

    should return:
    the same :class:`DownloadResult` that was provided to the handler, potentially modified on the 'path' or `status` and `reason` properties
    """
    # there's nothing special to post-process in the case of e(x)hentai downloader, so just return the result as is
    log.info(f"download of archive was successful for {result.downloaditem.name}")
    #TODO Mark it as a failure if there was only a thumbnail to download
    #TODO Archive the individual images together into a cbz or something if we grabbed individual images
    return result

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
