<!--
Markdown Guide: https://www.markdownguide.org/basic-syntax/
-->
<!--
Disable markdownlint errors:
fenced-code-language MD040
no-inline-html MD033
-->
<!-- markdownlint-disable MD040 MD033-->

# VoIPCheck

**voipcheck** - Check Cisco ATA 191 VoIP adapter status.

# SYNOPSIS

```voipcheck```

# DESCRIPTION

The **voipcheck** CLI tool checks the status of a Rath 2100-VOIP2CS (a.k.a Cisco
191 ATA) VoIP adapter and sends pings to `healthchecks.io`.

**voipcheck** also writes a log file named **voipcheck.log** to the conventional
OS-dependent log directory, `C:\Users\`*`Username`*`\AppData\Local\VoIPCheck\Logs`
on Windows.

# OPTIONS

None.

# **voipcheck** SETTINGS

Settings for **voipcheck** are configured in the `voipcheck.toml` file in the
conventional OS-dependent data directory,
`C:\Users\`*`Username`*`\AppData\Roaming\VoIPCheck` on Windows.

See [TOML: A config file format for humans](https://toml.io/en/) for the
**.toml** file format specification.

## adapter_url

Set the URL of the VoIP adapter, e.g.:

```toml
adapter_url = "http://voip.lan"
```

## service

Set the keyring service name, e.g.:

```toml
service = "2100-VOIP2CS"
```

## username

Set the VoIP adapter login user name, e.g.:

```toml
username = "admin"
```

## adapter_ping_url

Set the `healthchecks.io` URL to ping if communication with the VoIP adapter fails.

```toml
adapter_ping_url = "https://hc-ping.com/<your-check-uuid>"
```

## registration_state_ping_url

Set the `healthchecks.io` URL to ping when both Line 1 and Line 2
Registration State is *Registered*, e.g.

```toml
registration_state_ping_url = "https://hc-ping.com/<your-check-uuid>"
```

A **fail** ping is sent if either line Registration State is *Failed*.

## [line1]

Set the URL to ping if the Line 1 Hook State is *On*, e.g.:

```toml
[line1]
hook_state_ping_url = "https://hc-ping.com/<your-check-uuid>"
```

## [line2]

Set the URL to ping if the Line 2 Hook State is *On*, e.g.:

```toml
[line2]
hook_state_ping_url = "https://hc-ping.com/<your-check-uuid>"
```

# INSTALLATION

## PREREQUISITES

[Install python 3.12 or later version](https://www.python.org/downloads/).

Install [Playwright](https://playwright.dev/python/docs/intro)

Install [pipx](https://pipx.pypa.io/stable/):

```
pip install pipx
```

## INSTALL **voipcheck** FROM `.whl` package

<pre>
<code>pipx install <i>path</i>\voipcheck-<i>version</i>-py3-none-any.whl</code>
</pre>

For example:

<pre>
<code>pipx install <i>path</i>\voipcheck-0.1.5-py3-none-any.whl</code>
</pre>

## INSTALL **voipcheck** FROM `.tar.gz` package

Alternatively, install **voipcheck** from a `.tar.gz` package file:

<pre>
<code>pipx install <i>path</i>\voipcheck-<i>version</i>.tar.gz</code>
</pre>

For example:

<pre>
<code>pipx install <i>path</i>\voipcheck-0.1.5-.tar.gz</code>
</pre>

## INSTALL PLAYWRIGHT BROWSERS

```
pipx install playwright
pipx run playwright install
```

# SEE ALSO

* [Playwright for Python](https://playwright.dev/python//)<br>
* [pipx — Install and Run Python Applications in Isolated Environments](https://pipx.pypa.io/stable/)<br>
* [Healthchecks.io Documentation](https://healthchecks.io/docs/)<br>
* [TOML: A config file format for humans](https://toml.io/en/)<br>

# AUTHOR

Keith Gorlen<br>
<kgorlen@gmail.com>

# COPYRIGHT

Copyright 2025 Keith Gorlen

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the “Software”), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
