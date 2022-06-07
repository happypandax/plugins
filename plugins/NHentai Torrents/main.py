import __hpx__ as hpx, constants, is_win  # type: ignore

from asyncio import Queue, Event, get_event_loop, get_running_loop, run, sleep
from pathlib import Path
from re import compile

from yarl import URL
from aiohttp import ClientSession
import aiofiles
from .bencode import MalformedBencodeException, decode

log = hpx.get_logger("main")

# folder with files containing links (bookmark exports, tab sessions, etc) relative to where script is ran
GREP_DIR = Path("./")
# save them here, relative to where the script is ran
SAVE_PATH = Path(constants.download_path)
UNSAFE_WIN32 = compile(r"[|\/:*?\"<>]")
# How many concurrent downloaders do you want
TOTAL_WORKERS = 1
WORKER_DELAY = 1.5
# Stored on browser, get it from cookie storage
NH_COOKIE = ""
CHECK_DELAY = 24 * 60 * 60

NH = URL("https://nhentai.net/g/")
NH_LINK = compile(r"(?=(nhentai.net/g/[^/]+))\1")
NH_INFO = compile(r"(?=_gallery = JSON\.parse\(\"([^;]+)\")")


async def search_dir(path_: Path) -> set[URL]:
    nh_ids = set()
    if not path_.exists():
        return nh_ids

    for file in path_.iterdir():
        if file.is_dir():
            await search_dir(file)

        if file.is_file():
            async with aiofiles.open(file, "r") as f:
                file_text = await f.read()

            matches = NH_LINK.findall(file_text)
            for match in matches:
                nh_ids.add(match.split("/")[-1])

    return nh_ids


async def get_magnet(queue: Queue, depleted: Event):
    id = await queue.get()
    while not depleted.is_set():
        async with ClientSession(
            headers={"user-agent": "hpx-browser-extension"},
            cookies={
                "sessionid": NH_COOKIE,
            },
        ) as session:
            async with session.request("GET", NH / id / "download") as resp:
                bytes_data = await resp.read()
                try:
                    meta_data = decode(bytes_data)
                    name_bytes = meta_data["info"]["name"]
                    name = bytes.decode(name_bytes, "UTF-8")
                    if is_win:
                        name = UNSAFE_WIN32.sub("", name)

                except MalformedBencodeException:
                    continue

                async with aiofiles.open(SAVE_PATH / f"{name}.torrent", "wb") as mag:
                    await mag.write(bytes_data)
                    queue.task_done()


async def start():
    while hpx is not None and get_event_loop.is_running():
        links = await search_dir(GREP_DIR)

        job_queue = Queue(maxsize=TOTAL_WORKERS)
        depleted = Event()
        for _ in range(TOTAL_WORKERS):
            get_running_loop().create_task(get_magnet(job_queue, depleted))

        for link in links:
            await job_queue.put(link)
            await sleep(WORKER_DELAY)

        depleted.set()
        await sleep(CHECK_DELAY)


@hpx.attach("init")
def main():
    # we don't need async necessarily but in the case of thousands of IDs, it would be beneficial
    try:
        loop = get_running_loop()
        loop.create_task(start())
    except RuntimeError:
        run(start())
