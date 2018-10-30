# main.py
import __hpx__ as hpx

log = hpx.get_logger(__name__)

@hpx.subscribe("init")
def inited():
    "Called when this plugin is initialised"
    pass

@hpx.subscribe("disable")
def disabled():
    "Called when this plugin has been disiabled"
    pass

@hpx.subscribe("remove")
def removed():
    "Called when this plugin is about to be removed"
    pass