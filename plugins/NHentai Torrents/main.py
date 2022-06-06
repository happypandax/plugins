import __hpx__ as hpx, constants, is_win # type: ignore

from asyncio import Queue, Event, new_event_loop, get_running_loop, run, sleep
from pathlib import Path
from re import compile

from yarl import URL
from aiohttp import ClientSession, CookieJar
from aiofiles import open
from .bencode import MalformedBencodeException, decode

log = hpx.get_logger("main")

# folder with files containing links (bookmark exports, tab sessions, etc) relative to where script is ran
GREP_DIR = Path("./")
# save them here, relative to where the script is ran
SAVE_PATH = Path(constants.download_path)
UNSAFE_WIN32 = compile(r"[|\/:*?\"<>]")
# How many concurrent downloaders do you want
TOTAL_WORKERS = 1
# Stored on browser, get it from cookie storage
NH_COOKIE = ""
CHECK_DELAY = 24 * 60 * 60


NH_LINK = compile(r"(?=(https://nhentai.net/g/\d+)[^0-9])")
NH_INFO = compile(r"(?=_gallery = JSON\.parse\(\"([^;]+)\")")

def search_dir(path_: Path) -> set[URL]:
    found_links = set()
    if not path_.exists():
        print(f"search dir does not exists: {path_}")
        return found_links

    for file in path_.iterdir():
        if file.is_dir():
            search_dir(file)

        if file.is_file():
            file_text = file.read_text()
            matches = NH_LINK.findall(file_text)
            for match in matches:
                found_links.add(URL(match))

    return found_links


async def get_magnet(queue: Queue, depleted: Event):
    cookies = CookieJar()
    cookies.update_cookies(
        {
            "sessionid": NH_COOKIE,
        }
    )
    while not depleted.is_set():
        link: URL = await queue.get()
        if (
            torrent_file := Path(f"./save_magnets/{str(link).split('/')[-1]}.torrent")
        ).exists():
            queue.task_done()
            continue
        async with ClientSession(
            headers={"user-agent": "hpx-browser-extension"},
            cookies={
                "sessionid": NH_COOKIE,
            },
        ) as session:
            cookies = {
                "sessionid": NH_COOKIE,
            }
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/jxl,image/webp,*/*;q=0.8",
                "Host": "nhentai.net",
                "User-Agent": "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0 Waterfox/91.10.0",
                "Accept-Encoding": "gzip, deflate, br",
                "Upgrade-Insecure-Requests": 1,
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
            }

            async with session.request("GET", link / "download") as resp:
                bytes_data = await resp.read()
                try:
                    meta_data = decode(bytes_data)
                    name_bytes = meta_data["info"]["name"]
                    name = bytes.decode(name_bytes, "UTF-8")
                    if is_win:
                        name = UNSAFE_WIN32.sub('', name)

                except MalformedBencodeException:
                    continue

                async with open(SAVE_PATH / f"{name}.torrent", "wb+") as mag:
                    await mag.write(bytes_data)
                    queue.task_done()



async def get_mags(set_of_links: set[URL]):
    while hpx is not None:
        job_queue = Queue(maxsize=TOTAL_WORKERS)
        depleted = Event()
        for _ in range(TOTAL_WORKERS):
            get_running_loop().create_task(get_magnet(job_queue, depleted))

        for link in set_of_links:
            await job_queue.put(link)
            await sleep(5)

        depleted.set()
        await sleep(CHECK_DELAY)


@hpx.attach("init")
def main():
    nh_links: set[URL] = search_dir(GREP_DIR) # probably just throw a property under config.yaml:plugin:__name__:search dir
    try:
        loop = get_running_loop()
        loop.create_task(get_mags(nh_links))
    except RuntimeError:
        run(get_mags(nh_links))
