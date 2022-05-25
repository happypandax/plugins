import enum
import json
import typing

import __hpx__ as hpx

log = hpx.get_logger(__name__)


class IncompatibleFile(ValueError):
    pass


class DataType(enum.Flag):
    """
    The available extractors.
    Add your new extractor here
    """
    eze = enum.auto()
    hdoujin = enum.auto()
    e_hentai_downloader = enum.auto()


# The filetypes to look for, no duplicates, only add if necessary
filetypes = ('.json', '.txt')
# Which filetype belongs to which extractor, use inclusive OR '|' to combine multiple extractors
filenames = {
    "info.json": DataType.eze | DataType.hdoujin,
    "info.txt": DataType.hdoujin | DataType.e_hentai_downloader,
    }

common_data = {
    'titles': None,  # [(title, language),...]
    'artists': None,  # [(artist, (circle, circle, ..)),...]
    'parodies': None,  # [parody, ...]
    'category': None,
    'tags': None,  # [tag, tag, tag, ..] or {ns:[tag, tag, tag, ...]}
    'pub_date': None,  # DateTime object or Arrow object
    'language': None,
    'urls': None  # [url, ...]
    }

plugin_config = {
    'characters_namespace': 'character',  # hdoujin, which namespace to put the values in the CHARACTERS field in
    }

extractors = { }


def capitalize_text( text ):
    """
    better str.capitalize
    """
    return " ".join(x.capitalize() for x in text.strip().split())


def register_extractor( cls, type ):
    assert issubclass(cls, Extractor)
    assert isinstance(type, DataType)
    extractors[type] = cls()


class Extractor:
    """
    Base extractor
    """

    def file_to_dict( self, fs: hpx.command.CoreFS ) -> typing.Union[dict, None]:
        """
        A subclass can choose to override or extend this method.
        Should return a dict with data from the file which will be passed to the extract method.
        If the file is not supported or should be skipped, return None.
        The parameter fs is the file in question.

        Below is convenience code to read and convert a file into a dict.
        Supports json and txt files.
        If file is a txt, will try to parse files like this:
            Field A: value 1
            Field B: value 2
            ->
            {
                'Field A': 'value 1',
                'Field B': 'value 2',
            }
        otherwise the txt file is not supported and a ValueError will be raised.
        NotImplementedError will be raised if file is neither json or txt file.
        """
        try:
            d = { }
            log.debug(f"File ext: {fs.ext}")
            kw = { }
            if not fs.inside_archive:
                kw['encoding'] = 'utf-8'
            if fs.ext.lower() == '.json':
                with fs.open("r", **kw) as f:
                    d = json.load(f)
            elif fs.ext.lower() == '.txt':
                with fs.open("r", **kw) as f:
                    for line in f.readlines():
                        l = line.strip()
                        if isinstance(l, bytes):
                            l = l.decode(encoding="utf-8", errors="ignore")
                        k, v = l.split(':', 1)
                        if k.strip():
                            d[k.strip()] = v.strip()
            else:
                raise NotImplementedError(f"{fs.ext} filetype not supported yet")
        except Exception as e:  # Bad, I know, but too lazy
            raise IncompatibleFile(e)
        return d

    def extract( self, filedata: dict ) -> dict:
        """
        A subclass must implement this method.
        Should populate a dict that looks like common_data (see above) and return it

        filedata parameter is the dict created in the file_to_dict method
        """
        raise NotImplementedError
