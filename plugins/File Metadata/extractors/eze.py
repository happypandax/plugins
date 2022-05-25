import __hpx__ as hpx
import arrow

from . import common

log = hpx.get_logger(__name__)


class Eze(common.Extractor):

    def file_to_dict( self, fs ):
        """
        A subclass can choose to override or extend this method.
        Should return a dict with data from the file which will be passed to the extract method.
        If the file is not supported or should be skipped, return None.
        The parameter fs is the file in question.
        """
        d = super().file_to_dict(fs)
        k = ('gallery_info',)
        if d and not all(map(lambda x: x in d, k)):  # make sure all keys are present
            d = None
        k = ('image_info', 'gallery_info_full')
        if d and not any(map(lambda x: x in d, k)):  # make sure one of the keys are present
            d = None
        return d

    def extract( self, filedata ):
        """
        A subclass must implement this method.
        Should populate a dict that looks like common_data (see common.py) and return it

        filedata parameter is the dict created in the file_to_dict method
        """
        d = { }
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
                    nameparser = hpx.command.ItemTextParser(t)
                    parsed_title = nameparser.extract_title()
                    d.setdefault("titles", []).append((parsed_title[0] if parsed_title else t, l))

            mtags = filedata.get("tags")

            if mtags:
                d['tags'] = { }
                for ns, t in mtags.items():
                    d['tags'].setdefault(common.capitalize_text(ns), t)

            mlang = filedata.get("language")
            if mlang:
                d['language'] = common.capitalize_text(mlang)

            msource = filedata.get('source')
            if msource:
                d.setdefault('urls', []).append(f"https://{msource['site']}.org/g/{msource['gid']}/{msource['token']}")

            mupdate = filedata.get("upload_date")
            if mupdate:
                d['pub_date'] = arrow.get(*mupdate)

        return d


common.register_extractor(Eze, common.DataType.eze)
