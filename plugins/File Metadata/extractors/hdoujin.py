import __hpx__ as hpx

from . import common

log = hpx.get_logger(__name__)


class HDoujin(common.Extractor):

    def file_to_dict( self, fs ):
        """
        A subclass can choose to override or extend this method.
        Should return a dict with data from the file which will be passed to the extract method.
        If the file is not supported or should be skipped, return None.
        The parameter fs is the file in question.
        """
        d = super().file_to_dict(fs)
        if d:
            if fs.ext.lower() == '.txt':
                k = ('TITLE', 'ARTIST')
            else:
                k = ('manga_info',)
            if not all(map(lambda x: x in d, k)):  # make sure all keys are present
                d = None
            else:
                if fs.ext.lower() == '.txt':
                    new_d = { }
                    for k, v in d.items():
                        if k == "AUTHOR/CIRCLE":
                            k = "CIRCLE"
                        new_d[k.lower().replace(' ', '_')] = v
                    d = new_d
                else:
                    d = d.get('manga_info')
        return d

    def extract( self, filedata ):
        """
        A subclass must implement this method.
        Should populate a dict that looks like common_data (see common.py) and return it

        filedata parameter is the dict created in the file_to_dict method
        """
        d = { }
        if filedata:
            log.debug("Expecting hdoujin metadata file")
            mtitle = filedata.get('title')
            mtitle_jp = filedata.get('original_title')

            for t, l in ((mtitle, "english"), (mtitle_jp, "japanese")):
                if t:
                    nameparser = hpx.command.ItemTextParser(t)
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
                    nstag = { }
                    for x in mtags:
                        t = x.split(':', 1)
                        if len(t) == 2:
                            nstag.setdefault(t[0], []).append(t[1])
                    if nstag:
                        mtags = nstag

                if isinstance(mtags, dict):
                    d['tags'] = { }
                    for ns, t in mtags.items():
                        d['tags'].setdefault(common.capitalize_text(ns), t)
                else:
                    d['tags'] = { None: mtags }  # None for no namespace

            mcharacters = filedata.get("characters")
            if mcharacters:
                if isinstance(mcharacters, str):
                    mcharacters = mcharacters.split(',')
                d.setdefault('tags', { })[common.plugin_config.get('characters_namespace') or 'characters'] = mcharacters

            mparody = filedata.get("parody")
            if mparody:
                if isinstance(mparody, str):
                    mparody = mparody.split(',')
                d['parodies'] = mparody

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
