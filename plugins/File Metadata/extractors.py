import __hpx__ as hpx
import common

log = hpx.get_logger(__name__)

class Eze(common.Extractor):

    def file_to_dict(self, fs):
        d = super().file_to_dict(fs)
        k = ('gallery_info', 'image_info')
        if d and not all(map(lambda x: x in d, k)): # make sure all keys are present
            d = None
        return d

    def extract(self, filedata):
        d = {}
        filedata = filedata.get('gallery_info')
        if filedata:
            log.debug("Expecting eze metadata file")
            mtitle = filedata.get('title')
            mtitle_jp = filedata.get('title_original')

            mcat = filedata.get("category")
            if mcat:
                d['category'] = common.capitalize_text(mcat)

            for t, l in ((mtitle, "english"), (mtitle_jp, "japanese")):
                if t:
                    nameparser = hpx.command.NameParser(t)
                    parsed_title = nameparser.extract_title()
                    d.setdefault("titles", []).append((parsed_title[0] if parsed_title else t, l))

            mtags = filedata.get("tags")

            if mtags:
                d['tags'] = {}
                for ns, t in mtags.items():
                    d['tags'].setdefault(common.capitalize_text(ns), t)

            mlang = filedata.get("language")
            if mlang:
                d['language'] = common.capitalize_text(mlang)

            msource = filedata.get('source')
            if msource:
                d.setdefault('urls', []).append(f"https://{msource['site']}.org/g/{msource['gid']}/{msource['token']}")

        return d

common.register_extractor(Eze, common.DataType.eze)

class HDoujin(common.Extractor):

    def file_to_dict(self, fs):
        d = super().file_to_dict(fs)
        if d:
            if fs.ext.lower() == '.txt':
                k = ('TITLE', 'ARTIST')
            else:
                k = ('manga_info',)
            if not all(map(lambda x: x in d, k)): # make sure all keys are present
                d = None
            else:
                if fs.ext.lower() == '.txt':
                    new_d = {}
                    for k, v in d.items():
                        if k == "AUTHOR/CIRCLE":
                            k = "CIRCLE"
                        new_d[k.lower().replace(' ', '_')] = v
                    d = new_d
                else:
                    d = d.get('manga_info')
        return d

    def extract(self, filedata):
        d = {}
        if filedata:
            log.debug("Expecting hdoujin metadata file")
            mtitle = filedata.get('title')
            mtitle_jp = filedata.get('original_title')

            for t, l in ((mtitle, "english"), (mtitle_jp, "japanese")):
                if t:
                    nameparser = hpx.command.NameParser(t)
                    parsed_title = nameparser.extract_title()
                    d.setdefault("titles", []).append((parsed_title[0] if parsed_title else t, l))

            martists = filedata.get("artist")
            mcircles = filedata.get("circle")
            if martists:
                if isinstance(martists, str):
                    martists = martists.split(',')
                if isinstance(mcircles, str):
                    mcircles = mcircles.split(',')
                for a in martists:
                    d.setdefault("artists", []).append((a, tuple(mcircles) if mcircles else tuple()))

            mtags = filedata.get("tags")

            if mtags:
                if isinstance(mtags, str):
                    mtags = mtags.split(',')
                    nstag = {}
                    for x in mtags:
                        t = x.split(':', 1)
                        if len(t) == 2:
                            nstag.setdefault(t[0], []).append(t[1])
                    if nstag:
                        mtags = nstag

                if isinstance(mtags, dict):
                    d['tags'] = {}
                    for ns, t in mtags.items():
                        d['tags'].setdefault(common.capitalize_text(ns), t)
                else:
                    d['tags'] = mtags

            mlang = filedata.get("language")
            if mlang:
                if isinstance(mlang, list):
                    mlang = mlang[0]
                d['language'] = common.capitalize_text(mlang)

            msource = filedata.get('url')
            if msource:
                d.setdefault('urls', []).append(msource)

        return d

common.register_extractor(HDoujin, common.DataType.hdoujin)

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
                        nameparser = hpx.command.NameParser(line)
                        parsed_title = nameparser.extract_title()
                        d.setdefault("titles", []).append((parsed_title[0] if parsed_title else line, title_lang))
                    continue
        return d

common.register_extractor(EHentaiDownloader, common.DataType.e_hentai_downloader)
