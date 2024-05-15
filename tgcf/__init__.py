"""Package tgcf.

The ultimate tool to automate custom telegram message forwarding.
https://github.com/aahnik/tgcf
"""

from importlib.metadata import version
import telethon.network.mtprotostate

__version__ = version(__package__)
telethon.network.mtprotostate.__dict__['MSG_TOO_OLD_DELTA'] = 60 * 60 * 2
