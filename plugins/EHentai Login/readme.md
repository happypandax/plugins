EHentai Login
----------------------------

> This plugin can log-in to E-Hentai & ExHentai

Set the **EXHentai** option to true through your client when logging in to also check for ExHentai access.

The user has access to both E-Hentai and ExHentai if no message is displayed on a succesful log-in.
Else the message `No access to EXHentai` will be displayed.

To find your **IPB Member ID** and **IPB Pass Hash**, follow these steps (should work on all browsers):
1. Navigate to e-hentai.org (needs to be logged in) or exhentai.org
2. Right click on page => Inpect element
3. Go on **Console** tab
4. Write: `document.cookie`
5. A line of values should appear that correspond to active cookies
6. Look for the `ipb_member_id` and `ipb_pass_hash` values

# Changelog

- `0.2.0b`
    - increase default delay limit on EH requests to `9` from `4` secs, this value can be tweaked in `network.delays` inside your`config.yaml`

- `0.1.0b`
    - first version