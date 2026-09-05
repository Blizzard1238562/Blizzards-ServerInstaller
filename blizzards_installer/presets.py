"""Deterministic plugin config presets.

Each entry is a byte-exact copy of the config.yml the plugin ships in its
jar at the time it was added here, stored base64 so arbitrary bytes are
safe. Writing the file before first boot pins the plugin to known defaults
and spares players the "configure me" first-run (the plugin won't
overwrite an existing config.yml). Refreshing a preset = bump the jar's
default config.yml into this file.
"""

from __future__ import annotations

import base64
from pathlib import Path

from .ui import ok

# plugin id -> (folder plugin.yml creates, file name, base64 of file bytes)
PRESETS: dict[str, tuple[str, str, str]] = {
    "simpletpa": (
        "SimpleTPA",
        "config.yml",
        "c2V0dGluZ3M6CiAgdHBhX2Nvb2xkb3duOiAzMCAjIENvb2xkb3duIGluIFNlY29uZHMsIGJlZm9yZSBhIFBsYXll"
        "ciBjYW4gc2VuZCBhbm90aGVyIFRQQS1SZXF1ZXN0LgogIHRwYV9yZXF1ZXN0X3RpbWVvdXQ6IDYwICMgVGltZSBp"
        "biBTZWNvbmRzLCB1bnRpbCBhIFRQQS1SZXF1ZXN0IHJ1bnMgb3V0LgogIGNoZWNrX2Zvcl91cGRhdGVzOiB0cnVl"
        "ICMgQ2hlY2tzIE1vZHJpbnRoIGV2ZXJ5IDEyIGhvdXJzIGZvciBhIG5ldyB2ZXJzaW9uLgogIG1vZHJpbnRoX3By"
        "b2plY3Rfc2x1ZzogInNpbXBsZXRwYXBsdWdpbiIgIyBNb2RyaW50aCBwcm9qZWN0IHNsdWcgdXNlZCBmb3IgdXBk"
        "YXRlIG5vdGlmaWNhdGlvbnMuIFVzdWFsbHkgdGhlcmUncyBubyBuZWVkIHRvIGNoYW5nZSB0aGlzLgogIHVzZV9w"
        "bGFjZWhvbGRlcmFwaV9mb3JtYXR0aW5nOiB0cnVlICMgRm9ybWF0cyBQbGF5ZXIgbmFtZXMgaW4gbWVzc2FnZXMg"
        "dXNpbmcgUGxhY2Vob2xkZXJBUEkuIFJlcXVpcmVzIFBsYWNlaG9sZGVyQVBJIHRvIGJlIGluc3RhbGxlZC4KICBw"
        "bGF5ZXJfZGlzcGxheV9mb3JtYXQ6ICIlcGxheWVyJSIgIyBGb3JtYXQgZm9yIFBsYXllciBuYW1lcyBpbiBtZXNz"
        "YWdlcy4gTGVnYWN5IMKnIGNvZGVzIGFuZCBNaW5pTWVzc2FnZSB0YWdzIChlLmcuIGZyb20gJWx1Y2twZXJtc19w"
        "cmVmaXglKSBhcmUgYXV0b21hdGljYWxseSB0cmFuc2xhdGVkIHNvIHRoZXkgY2FuIGJlIG1peGVkIHNhZmVseS4g"
        "RXhhbXBsZTogIiVsdWNrcGVybXNfcHJlZml4JSB8ICVwbGF5ZXIlIiByZXF1aXJlcyBQbGFjZWhvbGRlckFQSSBh"
        "bmQgTHVja1Blcm1zLCBhcyB3ZWxsIGFzIHRoZSBMdWNrUGVybXMgUGxhY2Vob2xkZXJBUEkgZXhwYW5zaW9uLCB0"
        "byBiZSBpbnN0YWxsZWQuCiAgdGVsZXBvcnRfd2FybXVwX2VuYWJsZWQ6IGZhbHNlICMgSWYgZW5hYmxlZCwgdGhl"
        "IHJlcXVlc3RlciBoYXMgdG8gc3RhbmQgc3RpbGwgZm9yIGEgY29uZmlndXJlZCBhbW91bnQgb2YgdGltZSBiZWZv"
        "cmUgYmVpbmcgdGVsZXBvcnRlZCBhZnRlciB0aGVpciBUUEEtUmVxdWVzdCBnZXRzIGFjY2VwdGVkLgogIHRlbGVw"
        "b3J0X3dhcm11cF9zZWNvbmRzOiA1ICMgVGltZSBpbiBTZWNvbmRzIHRoZSByZXF1ZXN0ZXIgaGFzIHRvIHN0YW5k"
        "IHN0aWxsIGJlZm9yZSBiZWluZyB0ZWxlcG9ydGVkLiBPbmx5IHVzZWQgaWYgdGVsZXBvcnRfd2FybXVwX2VuYWJs"
        "ZWQgaXMgdHJ1ZS4KICBhbGxvd19tdWx0aXBsZV9yZXF1ZXN0czogdHJ1ZSAjIElmIGVuYWJsZWQsIFBsYXllcnMg"
        "Y2FuIHNlbmQgVFBBLVJlcXVlc3RzIHRvIG11bHRpcGxlIGRpZmZlcmVudCBQbGF5ZXJzIGF0IHRoZSBzYW1lIHRp"
        "bWUsIGFuZCByZWNlaXZlIG11bHRpcGxlIGluY29taW5nIFJlcXVlc3RzIGF0IG9uY2UuCiAgc3VwcHJlc3NfdXNh"
        "Z2VfaGludDogdHJ1ZSAjIElmIGVuYWJsZWQsIHN1cHByZXNzZXMgdGhlIHNlcnZlcidzIGJ1aWx0LWluICIvdHBh"
        "IDxwbGF5ZXJ8dmVyc2lvbnxoZWxwPiIgdXNhZ2UgaGludCB0aGF0IHdvdWxkIG90aGVyd2lzZSBhcHBlYXIgYmVs"
        "b3cgU2ltcGxlVFBBJ3Mgb3duIGVycm9yIG1lc3NhZ2VzLgogIHRwYWhlcmVfZW5hYmxlZDogdHJ1ZSAjIElmIGVu"
        "YWJsZWQsIGFsbG93cyBQbGF5ZXJzIHRvIHVzZSAvdHBhaGVyZSB0byBhc2sgYW5vdGhlciBQbGF5ZXIgdG8gdGVs"
        "ZXBvcnQgdG8gdGhlbS4KICB0cGFoZXJlX2Nvb2xkb3duOiAzMCAjIENvb2xkb3duIGluIFNlY29uZHMsIGJlZm9y"
        "ZSBhIFBsYXllciBjYW4gc2VuZCBhbm90aGVyIFRQQS1IZXJlLVJlcXVlc3QuIFNoYXJlcyB0aGUgc2FtZSBkZWZh"
        "dWx0IGFzIHRwYV9jb29sZG93biBidXQgY2FuIGJlIGNoYW5nZWQgaW5kZXBlbmRlbnRseS4KICB0cGFoZXJlX3Jl"
        "cXVlc3RfdGltZW91dDogNjAgIyBUaW1lIGluIFNlY29uZHMsIHVudGlsIGEgVFBBLUhlcmUtUmVxdWVzdCBydW5z"
        "IG91dC4gU2hhcmVzIHRoZSBzYW1lIGRlZmF1bHQgYXMgdHBhX3JlcXVlc3RfdGltZW91dCBidXQgY2FuIGJlIGNo"
        "YW5nZWQgaW5kZXBlbmRlbnRseS4KICB0cG9fZW5hYmxlZDogdHJ1ZSAjIElmIGVuYWJsZWQsIGFsbG93cyBzdGFm"
        "ZiB0byB1c2UgL3RwbyB0byB0ZWxlcG9ydCB0byBhbiBvZmZsaW5lIFBsYXllcidzIGxhc3Qga25vd24gbG9jYXRp"
        "b24uIEFsc28gY29udHJvbHMgd2hldGhlciBsb2dvdXQgbG9jYXRpb25zIGFyZSByZWNvcmRlZCBhdCBhbGwuCnNv"
        "dW5kczoKICB0cGFfcmVxdWVzdF9zZW50OiAiZW50aXR5LmV4cGVyaWVuY2Vfb3JiLnBpY2t1cCIKICB0cGFfcmVx"
        "dWVzdF9yZWNlaXZlZDogImVudGl0eS5wbGF5ZXIubGV2ZWx1cCIKICB0cGFfYWNjZXB0OiAiZW50aXR5LmVuZGVy"
        "bWFuLnRlbGVwb3J0IgogIHRwYV9kZW55OiAiZW50aXR5LnZpbGxhZ2VyLm5vIgogIHRwYV9leHBpcmVkOiAiZW50"
        "aXR5Lml0ZW0uYnJlYWsiCiAgdHBhX3RvZ2dsZV9lbmFibGVkOiAiYmxvY2subm90ZV9ibG9jay5iYXNzIgogIHRw"
        "YV90b2dnbGVfZGlzYWJsZWQ6ICJibG9jay5ub3RlX2Jsb2NrLnBsaW5nIgogIHRwYV90ZWxlcG9ydF9jYW5jZWxs"
        "ZWQ6ICJlbnRpdHkudmlsbGFnZXIubm8iCiAgdHBhaGVyZV9yZXF1ZXN0X3NlbnQ6ICJlbnRpdHkuZXhwZXJpZW5j"
        "ZV9vcmIucGlja3VwIgogIHRwYWhlcmVfcmVxdWVzdF9yZWNlaXZlZDogImVudGl0eS5wbGF5ZXIubGV2ZWx1cCIK"
        "bWVzc2FnZXM6ICMgVXNlcyBNaW5pTWVzc2FnZSB0YWdzIChlLmcuIDxncmVlbj4sIDxncmFkaWVudDpibHVlOmFx"
        "dWE+LCA8aG92ZXI6c2hvd190ZXh0OicuLi4nPikgaW4gdGhpcyBmaWxlLiBMZWdhY3kgwqcgY29kZXMgYWxzbyB3"
        "b3JrIGFuZCBhcmUgYXV0b21hdGljYWxseSB0cmFuc2xhdGVkIGludGVybmFsbHkgaWYgeW91IHByZWZlciB0aGVt"
        "LiB1cGRhdGVfYXZhaWxhYmxlX2NvbnNvbGUgaXMgb25seSBldmVyIHByaW50ZWQgdG8gdGhlIGNvbnNvbGUgbG9n"
        "IGFuZCBkb2VzIG5vdCBzdXBwb3J0IGFueSBjb2xvcmluZy4KICB0cGFfcmVxdWVzdF9zZW50OiAiPGdyYXk+WW91"
        "IHNlbnQgYSBUUEEtUmVxdWVzdCB0byA8Z29sZD4ldGFyZ2V0JTwvZ29sZD4uIgogIHRwYV9yZXF1ZXN0X3JlY2Vp"
        "dmVkOiAiPGdvbGQ+JXBsYXllciU8L2dvbGQ+IDxncmF5PnNlbnQgeW91IGEgVFBBLVJlcXVlc3QhIDxncmVlbj4v"
        "dHBhY2NlcHQ8L2dyZWVuPiA8Z3JheT5vciA8cmVkPi90cGRlbnk8L3JlZD4iCiAgdHBhaGVyZV9yZXF1ZXN0X3Nl"
        "bnQ6ICI8Z3JheT5Zb3Ugc2VudCBhIFRQQS1SZXF1ZXN0IGFza2luZyA8Z29sZD4ldGFyZ2V0JTwvZ29sZD4gdG8g"
        "dGVsZXBvcnQgdG8geW91LiIKICB0cGFoZXJlX3JlcXVlc3RfcmVjZWl2ZWQ6ICI8Z29sZD4lcGxheWVyJTwvZ29s"
        "ZD4gPGdyYXk+c2VudCBhIFRQQS1SZXF1ZXN0IGFza2luZyB5b3UgdG8gdGVsZXBvcnQgdG8gdGhlbSEgPGdyZWVu"
        "Pi90cGFjY2VwdDwvZ3JlZW4+IDxncmF5Pm9yIDxyZWQ+L3RwZGVueTwvcmVkPiIKICB0cGFoZXJlX2Rpc2FibGVk"
        "OiAiPHJlZD5UaGUgL3RwYWhlcmUgY29tbWFuZCBpcyBjdXJyZW50bHkgZGlzYWJsZWQuIgogIHRwYV9hY2NlcHRf"
        "c3VjY2VzczogIjxncmVlbj5Zb3UgYWNjZXB0ZWQgdGhlIFRQQS1SZXF1ZXN0IGZyb20gPGdvbGQ+JXBsYXllciU8"
        "L2dvbGQ+LiIKICB0cGFfYWNjZXB0X3RlbGVwb3J0OiAiPGdyZWVuPllvdSBnb3QgdGVsZXBvcnRlZCBieSA8Z29s"
        "ZD4lcGxheWVyJTwvZ29sZD4uIgogIHRwYV90ZWxlcG9ydF93YXJtdXBfc3RhcnRlZDogIjx5ZWxsb3c+VGVsZXBv"
        "cnRpbmcgdG8gPGdvbGQ+JXBsYXllciU8L2dvbGQ+IGluIDxnb2xkPiVzZWNvbmRzJTwvZ29sZD4gc2Vjb25kcy4g"
        "PHJlZD5Eb24ndCBtb3ZlISIKICB0cGFfdGVsZXBvcnRfd2FybXVwX2NhbmNlbGxlZDogIjxyZWQ+VGVsZXBvcnRh"
        "dGlvbiB0byA8Z29sZD4lcGxheWVyJTwvZ29sZD4gd2FzIGNhbmNlbGxlZCBiZWNhdXNlIHlvdSBtb3ZlZC4iCiAg"
        "dHBhX2Rlbnlfc3VjY2VzczogIjxyZWQ+WW91IGRlbmllZCB0aGUgVFBBLVJlcXVlc3QgZnJvbSA8Z29sZD4lcGxh"
        "eWVyJTwvZ29sZD4uIgogIHRwYV9kZW55X25vdGlmeTogIjxnb2xkPiVwbGF5ZXIlPC9nb2xkPiA8cmVkPmRlbmll"
        "ZCB5b3VyIFRQQS1SZXF1ZXN0LiIKICB0cGFfbm9fcmVxdWVzdDogIjxncmF5PllvdSBkb250IGhhdmUgYW55IHBl"
        "bmRpbmcgVFBBLVJlcXVlc3RzLiIKICB0cGFfcmVxdWVzdF9leGlzdHM6ICI8Z3JheT5Zb3UgYWxyZWFkeSBoYXZl"
        "IGEgcGVuZGluZyBUUEEtUmVxdWVzdC4gV2FpdCBmb3IgaXQgdG8gYmUgYWNjZXB0ZWQsIGRlbmllZCwgb3IgdG8g"
        "ZXhwaXJlIGJlZm9yZSBzZW5kaW5nIGFub3RoZXIuIgogIHRwYV9yZXF1ZXN0X2V4aXN0c190YXJnZXQ6ICI8Z3Jh"
        "eT5Zb3UgYWxyZWFkeSBoYXZlIGEgcGVuZGluZyBUUEEtUmVxdWVzdCB0byB0aGlzIFBsYXllci4iCiAgdHBhX25v"
        "X3JlcXVlc3RfZnJvbTogIjxncmF5PllvdSBkb24ndCBoYXZlIGEgcGVuZGluZyBUUEEtUmVxdWVzdCBmcm9tIDxn"
        "b2xkPiVwbGF5ZXIlPC9nb2xkPi4iCiAgdHBhX25vX3JlcXVlc3RfdG86ICI8Z3JheT5Zb3UgZG9uJ3QgaGF2ZSBh"
        "IHBlbmRpbmcgVFBBLVJlcXVlc3QgdG8gPGdvbGQ+JXBsYXllciU8L2dvbGQ+LiIKICB0cGFfbXVsdGlwbGVfcmVx"
        "dWVzdHM6ICI8Z3JheT5Zb3UgaGF2ZSBtdWx0aXBsZSBwZW5kaW5nIFRQQS1SZXF1ZXN0czogPGdvbGQ+JXBsYXll"
        "cnMlPC9nb2xkPi4gVXNlIDxncmVlbj4vdHBhY2NlcHQ8L2dyZWVuPiBbcGxheWVyXSBvciA8cmVkPi90cGRlbnk8"
        "L3JlZD4gW3BsYXllcl0gdG8gY2hvb3NlIG9uZS4iCiAgdHBhX211bHRpcGxlX3JlcXVlc3RzX291dGdvaW5nOiAi"
        "PGdyYXk+WW91IGhhdmUgbXVsdGlwbGUgcGVuZGluZyBvdXRnb2luZyBUUEEtUmVxdWVzdHM6IDxnb2xkPiVwbGF5"
        "ZXJzJTwvZ29sZD4uIFVzZSA8eWVsbG93Pi90cGFjYW5jZWw8L3llbGxvdz4gW3BsYXllcl0gdG8gY2hvb3NlIG9u"
        "ZS4iCiAgcGxheWVyX25vdF9vbmxpbmU6ICI8cmVkPlRoaXMgUGxheWVyIGlzIGN1cnJlbnRseSBub3Qgb25saW5l"
        "LiIKICBwbGF5ZXJfb25seV9jb21tYW5kOiAiPHJlZD5UaGlzIGNvbW1hbmQgY2FuIG9ubHkgYmUgdXNlZCBieSBQ"
        "bGF5ZXJzLiIKICB0cGFfc2VsZl9yZXF1ZXN0OiAiPHJlZD5Zb3UgY2Fubm90IHNlbmQgYSBUUEEtUmVxdWVzdCB0"
        "byB5b3Vyc2VsZi4iCiAgd3JvbmdfdXNhZ2U6ICI8Z3JheT5Vc2U6IDx5ZWxsb3c+LyVjb21tYW5kJTwveWVsbG93"
        "PiBbUGxheWVyXSIKICB0cGFfY2FuY2VsX3N1Y2Nlc3M6ICI8cmVkPllvdXIgVFBBLVJlcXVlc3Qgd2FzIGNhbmNl"
        "bGxlZC4iCiAgdHBhX2NhbmNlbF9ub3RpZnk6ICI8Z29sZD4lcGxheWVyJTwvZ29sZD4gPGdyYXk+Y2FuY2VsbGVk"
        "IHRoZWlyIFRQQS1SZXF1ZXN0LiIKICB0cGFfcmVxdWVzdF9leHBpcmVkX3NlbmRlcjogIjxncmF5PllvdXIgVFBB"
        "LVJlcXVlc3QgdG8gPGdvbGQ+JXRhcmdldCU8L2dvbGQ+IHJhbiBvdXQuIgogIHRwYV9yZXF1ZXN0X2V4cGlyZWRf"
        "cmVjZWl2ZXI6ICI8Z3JheT5UaGUgVFBBLVJlcXVlc3QgYnkgPGdvbGQ+JXBsYXllciU8L2dvbGQ+IHJhbiBvdXQu"
        "IgogIHRwYWhlcmVfcmVxdWVzdF9leHBpcmVkX3NlbmRlcjogIjxncmF5PllvdXIgVFBBLVJlcXVlc3QgYXNraW5n"
        "IDxnb2xkPiV0YXJnZXQlPC9nb2xkPiB0byB0ZWxlcG9ydCB0byB5b3UgcmFuIG91dC4iCiAgdHBhaGVyZV9yZXF1"
        "ZXN0X2V4cGlyZWRfcmVjZWl2ZXI6ICI8Z3JheT5UaGUgVFBBLVJlcXVlc3QgYnkgPGdvbGQ+JXBsYXllciU8L2dv"
        "bGQ+IGFza2luZyB5b3UgdG8gdGVsZXBvcnQgdG8gdGhlbSByYW4gb3V0LiIKICB0cGFfY29vbGRvd246ICI8eWVs"
        "bG93PlBsZWFzZSB3YWl0IDxnb2xkPiVzZWNvbmRzJTwvZ29sZD4gU2Vjb25kcywgYmVmb3JlIHNlbmRpbmcgYSBu"
        "ZXcgVFBBLVJlcXVlc3QuIgogIGNvbmZpZ19yZWxvYWRlZDogIjxncmVlbj5UaGUgQ29uZmlndXJhdGlvbiBoYXMg"
        "c3VjY2VzZnVsbHkgYmVlbiByZWxvYWRlZC4iCiAgbm9fcGVybWlzc2lvbjogIjxyZWQ+WW91IGRvbnQgaGF2ZSB0"
        "aGUgcmVxdWlyZWQgUGVybWlzc2lvbnMgdG8gdXNlIHRoaXMgQ29tbWFuZC4hIgogIHRwYV90b2dnbGVfZW5hYmxl"
        "ZDogIjxyZWQ+WW91IHdpbGwgbm8gbG9uZ2VyIHJlY2VpdmUgVFBBLVJlcXVlc3RzLiIKICB0cGFfdG9nZ2xlX2Rp"
        "c2FibGVkOiAiPGdyZWVuPllvdSBjYW4gbm93IHJlY2VpdmUgVFBBLVJlcXVlc3RzIGFnYWluLiIKICB0cGFfdGFy"
        "Z2V0X25vdF9hY2NlcHRpbmc6ICI8Z29sZD4ldGFyZ2V0JTwvZ29sZD4gPHJlZD5pcyBub3QgY3VycmVudGx5IGFj"
        "Y2VwdGluZyBUUEEtUmVxdWVzdHMuIgogIHZlcnNpb25faW5mbzogIjxncmF5PlNpbXBsZVRQQSB2ZXJzaW9uIGlu"
        "Zm8gLSBDdXJyZW50OiA8Z29sZD4lY3VycmVudCU8L2dvbGQ+IHwgTGF0ZXN0OiA8Z29sZD4lbGF0ZXN0JTwvZ29s"
        "ZD4gfCA8YXF1YT4ldXJsJSIKICB1cGRhdGVfYXZhaWxhYmxlX2NvbnNvbGU6ICJBIG5ldyB2ZXJzaW9uICgldmVy"
        "c2lvbiUpIG9mIFNpbXBsZVRQQSBpcyBhdmFpbGFibGUhIERvd25sb2FkOiAldXJsJSIKICB1cGRhdGVfYXZhaWxh"
        "YmxlX3BsYXllcjogIjx5ZWxsb3c+QSBuZXcgdmVyc2lvbiAoPGdvbGQ+JXZlcnNpb24lPC9nb2xkPikgb2YgU2lt"
        "cGxlVFBBIGlzIGF2YWlsYWJsZSEgPHdoaXRlPkRvd25sb2FkOiA8YXF1YT4ldXJsJSIKICB0cGFfZGVidWdfZW5h"
        "YmxlZDogIjxncmVlbj5UUEEgZXZlbnQgZGVidWcgbG9nZ2luZyBpcyBub3cgZW5hYmxlZC48L2dyZWVuPiIKICB0"
        "cGFfZGVidWdfZGlzYWJsZWQ6ICI8Z3JheT5UUEEgZXZlbnQgZGVidWcgbG9nZ2luZyBpcyBub3cgZGlzYWJsZWQu"
        "PC9ncmF5PiIKICB0cGhlcmVfc3VjY2VzczogIjxncmVlbj5Zb3UgdGVsZXBvcnRlZCA8Z29sZD4lcGxheWVyJTwv"
        "Z29sZD4gdG8geW91LiIKICB0cGhlcmVfbW92ZWRfbm90aWZ5OiAiPHllbGxvdz5Zb3Ugd2VyZSB0ZWxlcG9ydGVk"
        "IHRvIDxnb2xkPiVwbGF5ZXIlPC9nb2xkPi4iCiAgdHBvX2Rpc2FibGVkOiAiPHJlZD5UaGUgL3RwbyBjb21tYW5k"
        "IGlzIGN1cnJlbnRseSBkaXNhYmxlZC4iCiAgdHBvX3BsYXllcl9vbmxpbmU6ICI8Z29sZD4lcGxheWVyJTwvZ29s"
        "ZD4gPHJlZD5pcyBjdXJyZW50bHkgb25saW5lLCB1c2UgL3RwYWhlcmUgb3IgL3RwYSBpbnN0ZWFkLiIKICB0cG9f"
        "bm9fZGF0YTogIjxyZWQ+Tm8gbGFzdCBrbm93biBsb2NhdGlvbiBpcyBhdmFpbGFibGUgZm9yIDxnb2xkPiVwbGF5"
        "ZXIlPC9nb2xkPi4iCiAgdHBvX3N1Y2Nlc3M6ICI8Z3JlZW4+VGVsZXBvcnRlZCB0byA8Z29sZD4lcGxheWVyJTwv"
        "Z29sZD4ncyBsYXN0IGtub3duIGxvY2F0aW9uLiIKCmNsaWNrYWJsZV9tZXNzYWdlczoKICBhY2NlcHRfdGV4dDog"
        "IlvinJQgQWNjZXB0XSIKICBhY2NlcHRfaG92ZXI6ICJDbGljayB0byBhY2NlcHQgdGhlIFRQQSEiCiAgYWNjZXB0"
        "X2NvbW1hbmQ6ICIvdHBhY2NlcHQiCiAgYWNjZXB0X2NvbG9yOiAiR1JFRU4iCgogIGRlbnlfdGV4dDogIlvinJYg"
        "RGVueV0iCiAgZGVueV9ob3ZlcjogIkNsaWNrIHRvIGRlbnkgdGhlIFRQQSEiCiAgZGVueV9jb21tYW5kOiAiL3Rw"
        "ZGVueSIKICBkZW55X2NvbG9yOiAiUkVEIgoKaGVscF9tZXNzYWdlczoKICBoZWFkZXI6ICI8Z29sZD4tLS0gU2lt"
        "cGxlVFBBIENvbW1hbmRzIC0tLSIKICB0cGE6ICI8eWVsbG93Pi90cGE8L3llbGxvdz4gPGdyYXk+W3BsYXllcl0g"
        "LSBTZW5kcyBhIFRQQS1SZXF1ZXN0IHRvIGEgUGxheWVyLiIKICB0cGFoZXJlOiAiPHllbGxvdz4vdHBhaGVyZTwv"
        "eWVsbG93PiA8Z3JheT5bcGxheWVyXSAtIEFza3MgYSBQbGF5ZXIgdG8gdGVsZXBvcnQgdG8geW91LiIKICB0cGFj"
        "Y2VwdDogIjxncmVlbj4vdHBhY2NlcHQ8L2dyZWVuPiA8Z3JheT5bcGxheWVyXSAtIEFjY2VwdHMgYSBwZW5kaW5n"
        "IFRQQS1SZXF1ZXN0LiBTcGVjaWZ5IGEgUGxheWVyIGlmIHlvdSBoYXZlIG11bHRpcGxlLiIKICB0cGRlbnk6ICI8"
        "cmVkPi90cGRlbnk8L3JlZD4gPGdyYXk+W3BsYXllcl0gLSBEZW5pZXMgYSBwZW5kaW5nIFRQQS1SZXF1ZXN0LiBT"
        "cGVjaWZ5IGEgUGxheWVyIGlmIHlvdSBoYXZlIG11bHRpcGxlLiIKICB0cGFjYW5jZWw6ICI8eWVsbG93Pi90cGFj"
        "YW5jZWw8L3llbGxvdz4gPGdyYXk+W3BsYXllcl0gLSBDYW5jZWxzIG9uZSBvZiB5b3VyIHBlbmRpbmcgb3V0Z29p"
        "bmcgVFBBLVJlcXVlc3RzLiIKICB0cGF0b2dnbGU6ICI8eWVsbG93Pi90cGF0b2dnbGU8L3llbGxvdz4gPGdyYXk+"
        "LSBUb2dnbGVzIHdoZXRoZXIgeW91IGNhbiByZWNlaXZlIFRQQS1SZXF1ZXN0cy4iCiAgdHBoZXJlOiAiPHllbGxv"
        "dz4vdHBoZXJlPC95ZWxsb3c+IDxncmF5PltwbGF5ZXJdIC0gRm9yY2UtdGVsZXBvcnRzIGEgUGxheWVyIHRvIHlv"
        "dS4gKFN0YWZmKSIKICB0cG86ICI8eWVsbG93Pi90cG88L3llbGxvdz4gPGdyYXk+W3BsYXllcl0gLSBUZWxlcG9y"
        "dHMgeW91IHRvIGFuIG9mZmxpbmUgUGxheWVyJ3MgbGFzdCBrbm93biBsb2NhdGlvbi4gKFN0YWZmKSIKICB2ZXJz"
        "aW9uOiAiPHllbGxvdz4vdHBhIHZlcnNpb248L3llbGxvdz4gPGdyYXk+LSBTaG93cyB0aGUgY3VycmVudCBwbHVn"
        "aW4gdmVyc2lvbiBhbmQgdXBkYXRlIHN0YXR1cy4iCiAgaGVscDogIjx5ZWxsb3c+L3RwYSBoZWxwPC95ZWxsb3c+"
        "IDxncmF5Pi0gU2hvd3MgdGhpcyBoZWxwIG1lc3NhZ2UuIgogIHRwcmVsb2FkOiAiPHllbGxvdz4vdHByZWxvYWQ8"
        "L3llbGxvdz4gPGdyYXk+LSBSZWxvYWRzIHRoZSBwbHVnaW4gY29uZmlndXJhdGlvbi4i",
    ),
    "simplehomes": (
        "Simplehomes",
        "config.yml",
        "bWF4LWhvbWVzOiAzICMgbWF4aW11bSBvZiBob21lcyBhIHBsYXllciBjYW4gaGF2ZQp0ZWxlcG9ydC1jb29sZG93"
        "bjogNSAgICAgICAgIyBzZWNvbmRzIGJldHdlZW4gL2hvbWUgdXNlcwp0ZWxlcG9ydC13YXJtdXA6IDMgICAgICAg"
        "ICAgIyBzZWNvbmRzIGRlbGF5IGJlZm9yZSB0ZWxlcG9ydGluZwpjYW5jZWwtb24tbW92ZTogdHJ1ZSAgICAgICAg"
        "IyBpZiB0cnVlLCBtb3ZpbmcgY2FuY2VscyB0ZWxlcG9ydApjYW5jZWwtb24tZGFtYWdlOiB0cnVlICAgICAgIyBp"
        "ZiB0cnVlLCB0YWtpbmcgZGFtYWdlIGNhbmNlbHMgdGVsZXBvcnQKCiMgSGVyZSB5b3UgY2FuIGN1c3RvbWl6ZSBh"
        "bGwgTWVzc2FnZXMKbWVzc2FnZXM6CiAgbm8tcGVybWlzc2lvbjogIiZjWW91IGRvbid0IGhhdmUgcGVybWlzc2lv"
        "biEiCiAgdXNhZ2U6CiAgICBzZXRob21lOiAiJmNVc2FnZTogL3NldGhvbWUgPG5hbWU+IgogICAgaG9tZTogIiZj"
        "VXNhZ2U6IC9ob21lIDxuYW1lPiIKICAgIGRlbGhvbWU6ICImY1VzYWdlOiAvZGVsaG9tZSA8bmFtZT4iCiAgc2V0"
        "aG9tZToKICAgIHN1Y2Nlc3M6ICImYUhvbWUgJyZmJWhvbWUlJmEnIGhhcyBiZWVuIHNldCEiCiAgICBsaW1pdC1y"
        "ZWFjaGVkOiAiJmNZb3UgcmVhY2hlZCB0aGUgbWF4IGhvbWVzICglbWF4JSkuIgogIGhvbWU6CiAgICBub3QtZXhp"
        "c3Q6ICImY1RoYXQgaG9tZSBkb2VzIG5vdCBleGlzdC4iCiAgICB3YXJtdXA6ICImYVRlbGVwb3J0aW5nIHRvICZm"
        "JWhvbWUlICZhaW4gJXRpbWUlcy4uLiBEb24ndCBtb3ZlISIKICAgIHN1Y2Nlc3M6ICImYVRlbGVwb3J0ZWQgdG8g"
        "JmYlaG9tZSUmYSEiCiAgICBjb29sZG93bjogIiZjV2FpdCAldGltZSVzIGJlZm9yZSB0ZWxlcG9ydGluZyBhZ2Fp"
        "bi4iCiAgICBjYW5jZWxsZWQtbW92ZTogIiZjVGVsZXBvcnQgY2FuY2VsbGVkIGJlY2F1c2UgeW91IG1vdmVkISIK"
        "ICAgIGNhbmNlbGxlZC1kYW1hZ2U6ICImY1RlbGVwb3J0IGNhbmNlbGxlZCBiZWNhdXNlIHlvdSB0b29rIGRhbWFn"
        "ZSEiCiAgZGVsaG9tZToKICAgIHN1Y2Nlc3M6ICImYUhvbWUgJyZmJWhvbWUlJmEnIGRlbGV0ZWQuIgogICAgbm90"
        "LWV4aXN0OiAiJmNUaGF0IGhvbWUgZG9lcyBub3QgZXhpc3QuIgogIGhvbWVzOgogICAgbm9uZTogIiZlWW91IGhh"
        "dmUgbm8gaG9tZXMuIgogICAgbGlzdDogIiZhWW91ciBob21lczogJmYlaG9tZXMlIgojIEhlcmUgeW91IGNhbiBj"
        "dXN0b21pemUgYWxsIFNvdW5kcy4gVmFsaWQgc291bmRzIGNhbiBiZSBmb3VuZCBoZXJlOiBodHRwczovL2h1Yi5z"
        "cGlnb3RtYy5vcmcvamF2YWRvY3Mvc3BpZ290L29yZy9idWtraXQvU291bmQuaHRtbApzb3VuZHM6CiAgIyBzdWNj"
        "ZXNzIHNvdW5kcwogIHNldGhvbWUtc3VjY2VzczogIkJMT0NLX05PVEVfQkxPQ0tfUExJTkc6MToxIgogIGRlbGhv"
        "bWUtc3VjY2VzczogIkVOVElUWV9JVEVNX0JSRUFLOjE6MSIKICBob21lLXdhcm11cDogIlVJX0JVVFRPTl9DTElD"
        "SzoxOjEiCiAgaG9tZS1zdWNjZXNzOiAiRU5USVRZX0VOREVSTUFOX1RFTEVQT1JUOjE6MSIKCiAgIyBjYW5jZWwg"
        "c291bmRzCiAgaG9tZS1jYW5jZWwtbW92ZTogIkVOVElUWV9WSUxMQUdFUl9OTzoxOjEiCiAgaG9tZS1jYW5jZWwt"
        "ZGFtYWdlOiAiRU5USVRZX0JMQVpFX0hVUlQ6MToxIgoKICAjIGZhaWx1cmUgc291bmRzCiAgc2V0aG9tZS1mYWls"
        "OiAiQkxPQ0tfQU5WSUxfTEFORDoxOjAuOCIKICBkZWxob21lLWZhaWw6ICJFTlRJVFlfVklMTEFHRVJfTk86MTox"
        "IgogIGhvbWUtZmFpbDogIkJMT0NLX05PVEVfQkxPQ0tfQkFTUzoxOjAuOCIKICBuby1wZXJtaXNzaW9uOiAiRU5U"
        "SVRZX1ZJTExBR0VSX05POjE6MSIKICBjb29sZG93bi1mYWlsOiAiQkxPQ0tfTk9URV9CTE9DS19CQVNTOjE6MC41"
        "Igo=",
    ),
}


def write_plugin_presets(server_dir: Path, chosen: list[dict]) -> None:
    """Write pinned config.yml presets for any chosen plugin that has one.

    Plugins without an entry here generate their own config on first boot
    and need no help."""
    for plugin in chosen:
        entry = PRESETS.get(plugin.get("id"))
        if entry is None:
            continue
        folder, filename, b64 = entry
        target = server_dir / "plugins" / folder
        target.mkdir(parents=True, exist_ok=True)
        (target / filename).write_bytes(base64.b64decode(b64))
        ok(f"Wrote plugins/{folder}/{filename} preset for {plugin['name']}")
