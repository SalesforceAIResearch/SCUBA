from playwright.async_api import (
	BrowserContext as PlaywrightBrowserContext,
    ElementHandle,
	FrameLocator,
	Page,
)
from playwright.async_api import Page
from playwright.async_api import Error as PlaywrightError
from typing import Union, Optional, TypedDict, Any
from dataclasses import dataclass, field
import logging
import traceback
from browser_use.browser.context import BrowserContext, BrowserSession
from browser_use.utils import time_execution_async, time_execution_sync
from browser_use.dom.views import DOMElementNode, SelectorMap
from browser_use.browser.views import (
	BrowserError,
	BrowserState,
	URLNotAllowedError,
)
from browser_use.custom.dom_service_zoo import DomServiceBugFix, DomServiceBlackTransparent
import asyncio
import time
import re
logger = logging.getLogger(__name__)

@dataclass
class BrowserSessionBugFix(BrowserSession):
    context: PlaywrightBrowserContext
    cached_state: BrowserState | None
    current_page: Page

class BrowserContextBugFix(BrowserContext):
    def __init__(
        self,
        *args: Any,
        **kwargs: Any,
    ):
        if 'som_color' in kwargs:
            color = kwargs.pop('som_color')
            if color == 'black_transparent':
                self.DOM_SERVICE_CLASS = DomServiceBlackTransparent
            else:
                self.DOM_SERVICE_CLASS = DomServiceBugFix
        else:
            self.DOM_SERVICE_CLASS = DomServiceBugFix
        super().__init__(*args, **kwargs)
        self.session: BrowserSessionBugFix | None = None

    def _get_initial_state(self, page: Optional[Page] = None) -> BrowserState:
        """Get the initial state of the browser"""
        return BrowserState(
            element_tree=DOMElementNode(
                tag_name='root',
                is_visible=True,
                parent=None,
                xpath='',
                attributes={},
                children=[],
            ),
            selector_map={},
            url=page.url if page else '',
            title='',
            screenshot=None,
            tabs=[],
        )
      
    @time_execution_async('--initialize_session')
    async def _initialize_session(self) -> BrowserSessionBugFix:
        """Initialize the browser session"""
        logger.debug('Initializing browser context')

        playwright_browser = await self.browser.get_playwright_browser()
        context = await self._create_context(playwright_browser)
        self._page_event_handler = None

        # Get or create a page to use
        pages = context.pages

        active_page = None
        if self.browser.config.cdp_url:
            # If we have a saved target ID, try to find and activate it
            if self.state.target_id:
                targets = await self._get_cdp_targets()
                for target in targets:
                    if target['targetId'] == self.state.target_id:
                        # Find matching page by URL
                        for page in pages:
                            if page.url == target['url']:
                                active_page = page
                                break
                        break

        # If no target ID or couldn't find it, use existing page or create new
        if not active_page:
            if pages:
                active_page = pages[0]
                logger.info('Using existing page')
            else:
                active_page = await context.new_page()
                logger.info('Created new page')

            # Get target ID for the active page
            if self.browser.config.cdp_url:
                targets = await self._get_cdp_targets()
                for target in targets:
                    if target['url'] == active_page.url:
                        self.state.target_id = target['targetId']
                        break

        # Bring page to front
        await active_page.bring_to_front()
        await active_page.wait_for_load_state('load')
        initial_state = self._get_initial_state(active_page)
        self.session = BrowserSessionBugFix(
            context=context,
            cached_state=initial_state,
            current_page=active_page
        )

        return self.session    
    
    async def get_session(self) -> BrowserSessionBugFix:
        """Lazy initialization of the browser and related components"""
        if self.session is None:
            return await self._initialize_session()
        return self.session    
    
    async def _get_current_page(self, session: BrowserSessionBugFix) -> Page:

        # Try to find page by target ID if using CDP
        if self.browser.config.cdp_url and self.state.target_id:
            pages = session.context.pages
            targets = await self._get_cdp_targets()
            for target in targets:
                if target['targetId'] == self.state.target_id:
                    for page in pages:
                        if page.url == target['url']:
                            return page

        session = await self.get_session()
        return session.current_page if session.current_page else await session.context.new_page()    
    
    @time_execution_sync('--get_state')  # This decorator might need to be updated to handle async
    async def get_state(self) -> BrowserState:
        """Get the current state of the browser"""
        await self._wait_for_page_and_frames_load()
        session = await self.get_session()
        session.cached_state = await self._update_state()
        # Save cookies if a file is specified
        if self.config.cookies_file:
            asyncio.create_task(self.save_cookies())

        return session.cached_state

    async def _update_state(self, focus_element: int = -1) -> BrowserState:
        """Update and return state."""
        session = await self.get_session()

        # Check if current page is still valid, if not switch to another available page
        try:
            page = await self.get_current_page()
            # Test if page is still accessible
            await page.evaluate('1')
        except Exception as e:
            logger.debug(f'Current page is no longer accessible: {str(e)}')
            # Get all available pages
            pages = session.context.pages
            if pages:
                self.state.target_id = None
                page = await self._get_current_page(session)
                logger.debug(f'Switched to page: {await page.title()}')
            else:
                raise BrowserError('Browser closed: no valid pages available')

        try:
            await self.remove_highlights()
            dom_service = self.DOM_SERVICE_CLASS(page)
            content = await dom_service.get_clickable_elements(
            	focus_element=focus_element,
				viewport_expansion=self.config.viewport_expansion,
				highlight_elements=self.config.highlight_elements,
			)

            screenshot_b64 = await self.take_screenshot()
            pixels_above, pixels_below = await self.get_scroll_info(page)

            self.current_state = BrowserState(
				element_tree=content.element_tree,
				selector_map=content.selector_map,
				url=page.url,
				title=await page.title(),
				tabs=await self.get_tabs_info(),
				screenshot=screenshot_b64,
				pixels_above=pixels_above,
				pixels_below=pixels_below,
			)

            return self.current_state
        except Exception as e:
            logger.error(f'Failed to update state: {str(e)}')
			# Return last known good state if available
            if hasattr(self, 'current_state'):
                return self.current_state
            raise

    async def _wait_for_page_and_frames_load(self, timeout_overwrite: float | None = None):
        """
		Ensures page is fully loaded before continuing.
		Waits for either network to be idle or minimum WAIT_TIME, whichever is longer.
		Also checks if the loaded URL is allowed.
		"""
		# Start timing
        start_time = time.time()

		# Wait for page load
        try:
            await asyncio.sleep(self.config.wait_between_actions)
            await self._wait_for_stable_network()

			# Check if the loaded URL is allowed
            page = await self.get_current_page()
            await self._check_and_handle_navigation(page)
        except URLNotAllowedError as e:
            raise e
        except Exception:
            logger.warning('Page load failed, continuing...')
            pass

		# Calculate remaining time to meet minimum WAIT_TIME
        elapsed = time.time() - start_time
        remaining = max((timeout_overwrite or self.config.minimum_wait_page_load_time) - elapsed, 0)

        logger.debug(f'--Page loaded in {elapsed:.2f} seconds, waiting for additional {remaining:.2f} seconds')

		# Sleep remaining time if needed
        if remaining > 0:
            await asyncio.sleep(remaining)

    async def _wait_for_stable_network(self):
        page = await self.get_current_page()

        pending_requests = set()
        last_activity = asyncio.get_event_loop().time()

		# Define relevant resource types and content types
        RELEVANT_RESOURCE_TYPES = {
			'document',
			'stylesheet',
			'image',
			'font',
			'script',
			'iframe',
			'xhr'
		}

        RELEVANT_CONTENT_TYPES = {
			'text/html',
			'text/css',
			'application/javascript',
			'image/',
			'font/',
			'application/json',
		}

		# Additional patterns to filter out
        IGNORED_URL_PATTERNS = {
			# Analytics and tracking
			'analytics',
			'tracking',
			'telemetry',
			'beacon',
			'metrics',
			# Ad-related
			'doubleclick',
			'adsystem',
			'adserver',
			'advertising',
			# Social media widgets
			'facebook.com/plugins',
			'platform.twitter',
			'linkedin.com/embed',
			# Live chat and support
			'livechat',
			'zendesk',
			'intercom',
			'crisp.chat',
			'hotjar',
			# Push notifications
			'push-notifications',
			'onesignal',
			'pushwoosh',
			# Background sync/heartbeat
			'heartbeat',
			'ping',
			'alive',
			# WebRTC and streaming
			'webrtc',
			'rtmp://',
			'wss://',
			# Common CDNs for dynamic content
			'cloudfront.net',
			'fastly.net',
		}

        async def on_request(request):
			# Filter by resource type
            if request.resource_type not in RELEVANT_RESOURCE_TYPES:
                return

			# Filter out streaming, websocket, and other real-time requests
            if request.resource_type in {
				'websocket',
				'media',
				'eventsource',
				'manifest',
				'other',
			}:
                return

			# Filter out by URL patterns
            url = request.url.lower()
            if any(pattern in url for pattern in IGNORED_URL_PATTERNS):
                return

			# Filter out data URLs and blob URLs
            if url.startswith(('data:', 'blob:')):
                return

			# Filter out requests with certain headers
            headers = request.headers
            if headers.get('purpose') == 'prefetch' or headers.get('sec-fetch-dest') in [
				'video',
				'audio',
			]:
                return

            nonlocal last_activity
            pending_requests.add(request)
            last_activity = asyncio.get_event_loop().time()
			# logger.debug(f'Request started: {request.url} ({request.resource_type})')

        async def on_response(response):
            request = response.request
            if request not in pending_requests:
                return

			# Filter by content type if available
            content_type = response.headers.get('content-type', '').lower()

			# Skip if content type indicates streaming or real-time data
            if any(
				t in content_type
				for t in [
					'streaming',
					'video',
					'audio',
					'webm',
					'mp4',
					'event-stream',
					'websocket',
					'protobuf',
				]
			):
                pending_requests.remove(request)
                return

			# Only process relevant content types
            if not any(ct in content_type for ct in RELEVANT_CONTENT_TYPES):
                pending_requests.remove(request)
                return

			# Skip if response is too large (likely not essential for page load)
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > 5 * 1024 * 1024:  # 5MB
                pending_requests.remove(request)
                return

            nonlocal last_activity
            pending_requests.remove(request)
            last_activity = asyncio.get_event_loop().time()
			# logger.debug(f'Request resolved: {request.url} ({content_type})')

		# Attach event listeners
        page.on('request', on_request)
        page.on('response', on_response)

        try:
			# Wait for idle time
            start_time = asyncio.get_event_loop().time()
            while True:
                await asyncio.sleep(0.2)
                now = asyncio.get_event_loop().time()
                if len(pending_requests) == 0 and (now - last_activity) >= self.config.wait_for_network_idle_page_load_time:
                    break
                if now - start_time > self.config.maximum_wait_page_load_time:
                    logger.debug(
						f'Network timeout after {self.config.maximum_wait_page_load_time}s with {len(pending_requests)} '
						f'pending requests: {[r.url for r in pending_requests]}'
					)
                    break

        finally:
			# Clean up event listeners
            page.remove_listener('request', on_request)
            page.remove_listener('response', on_response)

        logger.debug(f'Network stabilized for {self.config.wait_for_network_idle_page_load_time} seconds')

    
    @time_execution_async('--switch_to_tab')
    async def switch_to_tab(self, page_id: int) -> None:
        """Switch to a specific tab by its page_id"""
        session = await self.get_session()
        pages = session.context.pages

        if page_id >= len(pages):
            raise BrowserError(f'No tab found with page_id: {page_id}')

        page = pages[page_id]

        # Check if the tab's URL is allowed before switching
        if not self._is_url_allowed(page.url):
            raise BrowserError(f'Cannot switch to tab with non-allowed URL: {page.url}')

        self.current_page = page
        # Update target ID if using CDP
        if self.browser.config.cdp_url:
            targets = await self._get_cdp_targets()
            for target in targets:
                if target['url'] == page.url:
                    self.state.target_id = target['targetId']
                    break
        session.current_page = page
        await page.bring_to_front()
        await page.wait_for_load_state()
      
    @time_execution_async('--create_new_tab')
    async def create_new_tab(self, url: str | None = None) -> None:
        """Create a new tab and optionally navigate to a URL"""
        if url and not self._is_url_allowed(url):
            raise BrowserError(f'Cannot create new tab with non-allowed URL: {url}')

        session = await self.get_session()
        new_page = await session.context.new_page()
        session.current_page = new_page
        await new_page.wait_for_load_state()
        

        if url:
            await new_page.goto(url)
            await self._wait_for_page_and_frames_load(timeout_overwrite=1)

        # Get target ID for new page if using CDP
        if self.browser.config.cdp_url:
            targets = await self._get_cdp_targets()
            for target in targets:
                if target['url'] == new_page.url:
                    self.state.target_id = target['targetId']
                    break
    async def reset_context(self):
        """Reset the browser session
        Call this when you don't want to kill the context but just kill the state
        """
        # close all tabs and clear cached state
        session = await self.get_session()

        pages = session.context.pages
        for page in pages:
            await page.close()

        session.cached_state = None
        self.state.target_id = None
        session.current_page = await session.context.new_page()

    @time_execution_async('--get_locate_element')
    async def get_locate_element(self, element: DOMElementNode) -> Optional[ElementHandle]:
        current_frame = await self.get_current_page()

		# Start with the target element and collect all parents
        parents: list[DOMElementNode] = []
        current = element
        while current.parent is not None:
            parent = current.parent
            parents.append(parent)
            current = parent

		# Reverse the parents list to process from top to bottom
        parents.reverse()

		# Process all iframe parents in sequence
        iframes = [item for item in parents if item.tag_name == 'iframe']
        for parent in iframes:
            css_selector = self._enhanced_css_selector_for_element(
				parent,
				include_dynamic_attributes=self.config.include_dynamic_attributes,
			)
            current_frame = current_frame.frame_locator(css_selector)

        css_selector = self._enhanced_css_selector_for_element(
			element, include_dynamic_attributes=self.config.include_dynamic_attributes
		)

        try:
            if isinstance(current_frame, FrameLocator):
                element_handle = await current_frame.locator(css_selector).element_handle()
                return element_handle
            else:
				# Try to scroll into view if hidden
                element_handle = await current_frame.query_selector(css_selector)
                if element_handle:
                    await element_handle.scroll_into_view_if_needed()
                    return element_handle
                return None
        except Exception as e:
            logger.error(f'Failed to locate element: {str(e)}')
            return None
        
    @classmethod
    @time_execution_sync('--enhanced_css_selector_for_element')
    def _enhanced_css_selector_for_element(cls, element: DOMElementNode, include_dynamic_attributes: bool = True) -> str:
        """
		Creates a CSS selector for a DOM element, handling various edge cases and special characters.

		Args:
		        element: The DOM element to create a selector for

		Returns:
		        A valid CSS selector string
		"""
        try:
			# Get base selector from XPath
            css_selector = cls._convert_simple_xpath_to_css_selector(element.xpath)

			# Handle class attributes
            if 'class' in element.attributes and element.attributes['class'] and include_dynamic_attributes:
				# Define a regex pattern for valid class names in CSS
                valid_class_name_pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_-]*$')

				# Iterate through the class attribute values
                classes = element.attributes['class'].split()
                for class_name in classes:
					# Skip empty class names
                    if not class_name.strip():
                        continue

					# Check if the class name is valid
                    if valid_class_name_pattern.match(class_name):
						# Append the valid class name to the CSS selector
                        css_selector += f'.{class_name}'
                    else:
						# Skip invalid class names
                        continue

			# Expanded set of safe attributes that are stable and useful for selection
            SAFE_ATTRIBUTES = {
				# Data attributes (if they're stable in your application)
				'id',
				# Standard HTML attributes
				'name',
				'type',
				'placeholder',
				# Accessibility attributes
				'aria-label',
				'aria-labelledby',
				'aria-describedby',
				'role',
				# Common form attributes
				'for',
				'autocomplete',
				'required',
				'readonly',
				# Media attributes
				'alt',
				'title',
				'src',
				# Custom stable attributes (add any application-specific ones)
				'href',
				'target',
			}

            if include_dynamic_attributes:
                dynamic_attributes = {
					'data-id',
					'data-qa',
					'data-cy',
					'data-testid',
					'browser_use_index'
				}
                SAFE_ATTRIBUTES.update(dynamic_attributes)

			# Handle other attributes
            for attribute, value in element.attributes.items():
                if attribute == 'class':
                    continue

				# Skip invalid attribute names
                if not attribute.strip():
                    continue

                if attribute not in SAFE_ATTRIBUTES:
                    continue

				# Escape special characters in attribute names
                safe_attribute = attribute.replace(':', r'\:')

				# Handle different value cases
                if value == '':
                    css_selector += f'[{safe_attribute}]'
                elif any(char in value for char in '"\'<>`\n\r\t'):
					# Use contains for values with special characters
					# Regex-substitute *any* whitespace with a single space, then strip.
                    collapsed_value = re.sub(r'\s+', ' ', value).strip()
					# Escape embedded double-quotes.
                    safe_value = collapsed_value.replace('"', '\\"')
                    css_selector += f'[{safe_attribute}*="{safe_value}"]'
                else:
                    css_selector += f'[{safe_attribute}="{value}"]'

            return css_selector
        
        except Exception:
			# Fallback to a more basic selector if something goes wrong
            tag_name = element.tag_name or '*'
            return f"{tag_name}[highlight_index='{element.highlight_index}']"
        
    @time_execution_async('--click_element_node')
    async def _click_element_node(self, element_node: DOMElementNode) -> Optional[str]:
        """
        Optimized method to click an element using xpath.
        """
        page = await self.get_current_page()

        try:
            # Highlight before clicking
            # if element_node.highlight_index is not None:
            # 	await self._update_state(focus_element=element_node.highlight_index)

            element_handle = await self.get_locate_element(element_node)

            if element_handle is None:
                raise Exception(f'Element: {repr(element_node)} not found')

            async def perform_click(click_func):
                """Performs the actual click, handling both download
                and navigation scenarios."""
                if self.config.save_downloads_path:
                    try:
                        # Try short-timeout expect_download to detect a file download has been been triggered
                        async with page.expect_download(timeout=5000) as download_info:
                            await click_func()
                        download = await download_info.value
                        # Determine file path
                        suggested_filename = download.suggested_filename
                        unique_filename = await self._get_unique_filename(self.config.save_downloads_path, suggested_filename)
                        download_path = os.path.join(self.config.save_downloads_path, unique_filename)
                        await download.save_as(download_path)
                        logger.debug(f'Download triggered. Saved file to: {download_path}')
                        return download_path
                    except TimeoutError:
                        # If no download is triggered, treat as normal click
                        logger.debug('No download triggered within timeout. Checking navigation...')
                        await page.wait_for_load_state()
                        await self._check_and_handle_navigation(page)
                else:
                    # Standard click logic if no download is expected
                    click_error = False
                    try:
                        await click_func()
                    except PlaywrightError as e:
                        click_error = True
                        logger.info(f'Failed to click element: {str(e)}')
                        if "has been closed" in str(e):
                            current_session = await self.get_session()
                            pages = current_session.context.pages
                            last_page = pages[-1]
                            # Update the current page to the last page since one page was closed
                            current_session.current_page = last_page
                        else:
                            raise e
                    if click_error == False:
                        await page.wait_for_load_state()
                        await self._check_and_handle_navigation(page)
                    else:
                        await last_page.wait_for_load_state()
                        await self._check_and_handle_navigation(last_page)

            try:
                return await perform_click(lambda: element_handle.click(timeout=1500))
            except URLNotAllowedError as e:
                raise e
            except Exception as e:
                logger.info(f'Failed to click element: {str(e)}')
                logger.info(traceback.format_exc())
                try:
                    logger.info("Attempting to click element using evaluate")
                    return await perform_click(lambda: page.evaluate('(el) => el.click()', element_handle))
                except URLNotAllowedError as e:
                    raise e
                except Exception as e:
                    raise Exception(f'Failed to click element: {str(e)}')

        except URLNotAllowedError as e:
            raise e
        except Exception as e:
            raise Exception(f'Failed to click element: {repr(element_node)}. Error: {str(e)}')        