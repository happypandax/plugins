import __hpx__ as hpx
from . import common

log = hpx.get_logger(__name__)

class EHentaiDownloader(common.Extractor):

    def file_to_dict(self, fs):
        """
        File is formatted weirdly so we just return {linenumber : line}
        """
        d = {}
        log.debug(f"File ext: {fs.ext}")
        kw = {}
        if not fs.inside_archive:
            kw['encoding'] = "utf-8"
        with fs.open("r", **kw) as f:
            for num, line  in enumerate(f.readlines(), 1):
                if isinstance(line, bytes):
                    line = line.decode("utf-8")
                d[num] = line

        # confirm it's the right file
        if d and not "generated by e-hentai downloader" in d[len(d)].lower():
            d = None
        return d

    def extract(self, filedata):
        d = {}
        if filedata:
            log.debug("Expecting e-hentai downloader metadata file")
            for linenum in sorted(filedata):
                line = filedata[linenum].strip()
                if not line:
                    continue

                if line.startswith("Language:"):
                    line = line.split(':', 1)[1]
                    d['language'] = common.capitalize_text(line.lower().split()[0])
                    continue

                if line.startswith("Category:"):
                    line = line.split(':', 1)[1]
                    d['category'] = common.capitalize_text(line.lower())
                    continue

                if line.startswith("> "): # tags
                    line = line[2:] # remove >
                    ns, tags = line.split(':', 1)
                    tags = tags.split(",")
                    d.setdefault("tags", {})[ns.strip()] = [t.strip() for t in tags]
                    continue

                if linenum in (1, 2, 3): # most likely a title or url, must be last because maybe it wasn't included
                    # ensure
                    if not filedata.get(3, "").startswith("http"):
                        continue

                    if linenum == 3:
                        d.setdefault('urls', []).append(line)
                    else:
                        title_lang = "english" if linenum == 1 else "japanese"
                        nameparser = hpx.command.ItemTextParser(line)
                        parsed_title = nameparser.extract_title()
                        d.setdefault("titles", []).append((parsed_title[0] if parsed_title else line, title_lang))
                    continue
        return d

common.register_extractor(EHentaiDownloader, common.DataType.e_hentai_downloader)
