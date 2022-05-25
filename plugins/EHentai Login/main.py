# main.py
import __hpx__ as hpx
from bs4 import BeautifulSoup

log = hpx.get_logger("main")

default_delay = 8

HEADERS = {'user-agent': "Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0"}

match_url_prefix = r"^(http\:\/\/|https\:\/\/)?(www\.)?"  # http:// or https:// + www.
match_url_end = r"\/?$"

url_regex = match_url_prefix + r"((exhentai|(g\.)?e-hentai)\.org)" + match_url_end

MAIN_URLS = {
    'eh': "https://e-hentai.org",
    'ex': "https://exhentai.org"
}

URLS = MAIN_URLS
URLS.update({
    'login': "https://e-hentai.org/home.php"
}
)


@hpx.subscribe("init")
def inited():
    # set default delay values if not set
    delays = hpx.get_setting("network", "delays", {})
    for u in (MAIN_URLS['ex'], MAIN_URLS['eh']):
        if u not in delays:
            log.info(f"Setting delay on {u} requests to {default_delay}")
            delays[u] = default_delay
            hpx.update_setting("network", "delays", delays)

    if 'logged_in' not in hpx.store:
        hpx.store.logged_in = False
    if 'status_text' not in hpx.store:
        hpx.store.status_text = ''
    if 'response' not in hpx.store:
        hpx.store.response = None
    if 'user' not in hpx.store:
        hpx.store.user = {}
    if 'username' not in hpx.store:
        hpx.store.username = ''

    if hpx.constants.is_main_process:
        # retrieve saved user info
        userpass = hpx.store.user
        if userpass and not hpx.constants.debug:
            r = login(userpass, {})
            if r is not None:
                log.info("Successfully re-logged in")



@hpx.subscribe("disable")
def disabled():
    pass


@hpx.subscribe("remove")
def removed():
    pass

@hpx.attach("message")
def message(msg: dict):
    t = msg.get("type")
    if t == "login":
        login(msg['data'])
    elif t == 'check-login':
        pass
    return {"logged_in": hpx.store.logged_in, "status": hpx.store.status_text}

@hpx.attach("Login.info")
def login_info():
    return hpx.command.LoginInfo(
        identifier="ehentai",
        name="EHentai",
        parser=url_regex,
        sites=("www.e-hentai.org", "www.exhentai.org"),
        description="Login to E-Hentai & ExHentai",
    )


@hpx.attach("Login.login", trigger="ehentai")
def login(userpass: dict, options=None):
    response = None
    status_text = ''
    current_user_name = ''

    ipb_member = userpass.get('ipb_member_id', "")
    ipb_pass = userpass.get('ipb_pass_hash', "")
    try:
        if not ipb_member or not ipb_pass:
            raise ValueError("Missing ipb_member_id or ipb_pass_hash")

        cookies = {}

        additional = userpass.get('additional', "")
        if additional:
            try:
                additional = {k.strip(): v.strip() for k, v in [x.strip().split('=', 1) for x in additional.split(',')]}
                cookies.update(additional)
            except:
                raise ValueError("Failed to parse additional values")

        cookies.update({
            'ipb_member_id': ipb_member,
            'ipb_pass_hash': ipb_pass,
        }
        )

        # prepare request
        req_props = hpx.command.RequestProperties(
            session=True,
            cookies=cookies,
            headers=HEADERS
        )

        req = hpx.command.SingleGETRequest()

        # check ehentai.org/home.php
        r = req.request(URLS['login'], req_props)

        if r.ok:
            bad_access, msg = check_access(r)
            status_text = msg
            if not bad_access:
                if userpass.get("exhentai", True):
                    # check exhentai
                    req_props.session = r.session
                    r = req.request(URLS['ex'], req_props)
                    if r.ok:
                        bad_access, status_text = check_access(r, ex=True)
                    else:
                        status_text = "Could not access ExHentai"

                response = r
                hpx.store.user = userpass
                current_user_name = ipb_member

        else:
            status_text = r.reason

    except ValueError as e:
        status_text = str(e)

    hpx.store.status_text = status_text
    hpx.store.response = response
    logged_in = hpx.store.logged_in = response is not None
    hpx.store.username = current_user_name
    log.debug(f"Login: {logged_in} (status: {status_text})")

    return response


@hpx.attach("Login.status", trigger="ehentai")
def status(options):
    return hpx.store.status_text


@hpx.attach("Login.logged_in", trigger="ehentai")
def logged_in(options):
    return hpx.store.logged_in


@hpx.attach("Login.response", trigger="ehentai")
def response_(options):
    return hpx.store.response


@hpx.attach("Login.current_user", trigger="ehentai")
def current_user(options):
    return hpx.store.username


def check_access(r, ex=False):
    msg = ""
    bad_access = False
    content_type = r.headers['content-type']
    text = r.text
    if 'image/gif' in content_type:
        msg = "No access to ExHentai"
    elif 'text/html' and 'Your IP address has been' in text:
        msg = text
        bad_access = True

    if not bad_access and not ex:
        soup = BeautifulSoup(text, "html.parser")
        if soup.find("div", class_="homebox"):  # we have access to home.php
            pass
        elif soup.find("form"):  # login page
            bad_access = True
            msg = "Wrong credentials!"
    if msg:
        log.info(f"MSG: {msg}")
    return bad_access, msg
