from typing import Union, Optional, TypedDict, Any
from browser_use.browser.browser import Browser
from browser_use.browser.context import BrowserContextConfig
from browser_use.custom.browser_context_zoo import BrowserContextBugFix

class BrowserBugFix(Browser):
    def __init__(
        self,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        
    async def new_context(self, config: BrowserContextConfig = BrowserContextConfig()) -> BrowserContextBugFix:
        """Create a browser context"""
        return BrowserContextBugFix(config=config, browser=self)