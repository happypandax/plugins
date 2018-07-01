# main.py
import __hpx__ as hpx

log = hpx.get_logger(__name__)

@hpx.subscribe("init")
def inited():
    pass

@hpx.subscribe("disable")
def disabled():
    pass

@hpx.subscribe("remove")
def removed():
    pass