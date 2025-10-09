from remote_desktop_env import RemoteDesktopEnv
import traceback
import logging
from typing import Any, Optional, Dict, Union
import time
import asyncio
import json
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright

logger = logging.getLogger("VWADesktopEnv")
class VWADesktopEnv(RemoteDesktopEnv):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def reset_remote_docker_container(self, 
                                      task_config: Optional[Union[Dict[str, Any], str]] = None, 
                                      seed=None, 
                                      options=None, 
                                      pause_after_login: int = 2) -> Union[Dict[str, Any], None]:
        logger.info(f"Reverting to snapshot to {self.snapshot_name} by directly restarting the container {self.container_name}...")
        response = self.provider.revert_to_snapshot(self.container_name, self.snapshot_name)
        logger.info("Emulator started.")
        if isinstance(task_config, str):
            with open(task_config, 'r') as f:
                task_config = json.load(f)
        self.storage_state = task_config.get("storage_state", None)
        self.start_url = task_config.get("start_url", None)
        self.geolocation = task_config.get("geolocation", None)
        self.viewport_size_from_config = {'width': task_config.get("viewport_width", self.screen_width), 
                                          'height': task_config.get("viewport_height", self.screen_height)}
        try:
            self._open_chrome_browser()
            if self.start_url:
                self._go_to_initial_page(self.start_url)
            time.sleep(pause_after_login)
            observation = self._get_obs()
            return observation
        except Exception as e:
            logger.error(f"Failed to reset remote docker container: {e}")
            logger.error(traceback.format_exc())
            raise e
        
    
    def _open_chrome_browser(self):
        # Close existing browser connection if it exists
        # if hasattr(self, 'browser') and self.browser:
        #     try:
        #         self.browser.close()
        #         logger.debug("Closed existing browser connection")
        #     except Exception as e:
        #         logger.warning(f"Error closing existing browser: {e}")
        # self.browser = None
        initial_actions = [
            # disable chrome password manager and the auto update feature
            {
                "type": "execute",
                "parameters": {
                    "command": [
                    "bash",
                    "-c",
                    "echo 'password' | sudo -S -p '' bash -c 'mkdir -p /etc/opt/chrome/policies/managed && printf %s \"{\\\"PasswordManagerEnabled\\\":false,\\\"AutofillAddressEnabled\\\":false,\\\"AutofillCreditCardEnabled\\\":false,\\\"CredentialsLeakDetectionEnabled\\\":false,\\\"BrowserSignin\\\":0,\\\"SyncDisabled\\\":true,\\\"DefaultBrowserSettingEnabled\\\":false,\\\"MetricsReportingEnabled\\\":false,\\\"PromotionalTabsEnabled\\\":false,\\\"SuppressUnsupportedOSWarning\\\":true}\" > /etc/opt/chrome/policies/managed/managed_policies.json && chmod 644 /etc/opt/chrome/policies/managed/managed_policies.json'"
                    ]
                }
            },
            {
                "type": "launch",
                "parameters": {
                    "command": [
                        "google-chrome",
                        "--remote-debugging-port=1337",
                        "--no-sandbox",
                        "--disable-web-security",
                        "--disable-site-isolation-trials",
                        "--disable-features=IsolateOrigins,site-per-process",
                        "--no-startup-window",
                        "--no-first-run", 
                        "--disable-infobars",
                        "--disable-notifications", 
                        "--disable-save-password-bubble",
                        "--disable-component-update",
                        f"--window-size={self.screen_width},{self.screen_height}",
                    ]
                }
            },
            # Set up port forwarding from 9222 to 1337
            {
                "type": "launch", 
                "parameters": {
                    "command": [
                        "socat",
                        "tcp-listen:9222,fork",
                        "tcp:localhost:1337"
                    ]
                }
            },
                # Wait a moment for Chrome to start
                {
                    "type": "sleep",
                    "parameters": {
                        "seconds": 3
                }
            }
        ]
    
        is_chrome_open = self.setup_controller.setup(config=initial_actions, use_proxy=False)
        if not is_chrome_open:
            raise Exception("Failed to open Chrome")
        remote_debugging_url = f"http://{self.vm_ip}:{self.chromium_port}"
        
        # # Close existing playwright instance if it exists to avoid conflicts
        # if hasattr(self, 'playwright') and self.playwright:
        #     try:
        #         self.playwright.stop()
        #         logger.debug("Closed existing playwright instance")
        #     except Exception as e:
        #         logger.warning(f"Error closing existing playwright instance: {e}")
        #     self.playwright = None
        
        # Keep the playwright instance alive for the browser lifecycle
        if not hasattr(self, 'playwright'):
            self.playwright = sync_playwright().start()
        
        browser = None
        for attempt in range(15):
            try:
                browser = self.playwright.chromium.connect_over_cdp(remote_debugging_url)
                break
            except Exception as e:
                if attempt < 14:
                    logger.info(f"Attempt {attempt + 1}: Failed to connect, retrying. Error: {e}")
                    time.sleep(5)
                else:
                    logger.info(f"Failed to connect after multiple attempts: {e}")
                    raise e
        if not browser:
            raise Exception("Failed to connect to browser")
        self.browser = browser
    def _go_to_initial_page(self, start_url: str):
        context = self.browser.contexts[0]
        
        # Configure the context with available settings
        self._configure_existing_context(context)
        
        start_urls = start_url.split(" |AND| ")
        for url in start_urls:
            logger.debug(f'starting new page at: {url}')
            page = context.new_page()
            
            # Apply page-level configurations
            self._configure_page(page)
            
            page.goto(url)
            
            # Apply localStorage/sessionStorage if available
            self._apply_page_storage(page)
        logger.info("bring the first page to front")
        # set the first page as the current page
        page = context.pages[0]
        page.bring_to_front()
    
    def _configure_existing_context(self, context):
        """Configure the existing context with available settings"""
        try:
            # Set geolocation if available
            if self.geolocation:
                context.set_geolocation(self.geolocation)
                # Grant geolocation permission
                context.grant_permissions(['geolocation'])
                logger.debug(f"Geolocation set: {self.geolocation}")
            
            # Handle storage state for CDP connections
            if self.storage_state:
                # For CDP connections, we need to set storage state differently
                # This might require loading cookies/localStorage manually
                self._apply_storage_state(context)
                
        except Exception as e:
            logger.warning(f"Could not configure context: {e}")
    
    def _configure_page(self, page):
        """Apply page-level configurations"""
        try:
            # Set viewport - method expects a viewport dictionary
            page.set_viewport_size(self.viewport_size_from_config)
            logger.debug(f"Viewport set: {self.viewport_size_from_config}")
            
        except Exception as e:
            logger.warning(f"Could not configure page: {e}")
    
    def _apply_storage_state(self, context):
        """Apply storage state for CDP connections"""
        try:
            if not self.storage_state:
                return
                
            if isinstance(self.storage_state, str):
                # If it's a file path, read the storage state
                import json
                import os
                if not os.path.exists(self.storage_state):
                    logger.warning(f"Storage state file not found: {self.storage_state}")
                    return
                    
                with open(self.storage_state, 'r') as f:
                    storage_data = json.load(f)
            else:
                storage_data = self.storage_state
            
            # Apply cookies if available - use sync method for sync context
            if 'cookies' in storage_data and storage_data['cookies']:
                try:
                    context.add_cookies(storage_data['cookies'])
                    logger.debug(f"Applied {len(storage_data['cookies'])} cookies from storage state")
                except Exception as cookie_error:
                    logger.warning(f"Could not apply cookies: {cookie_error}")
            
            # Note: localStorage/sessionStorage need to be set at page level after navigation
            if 'origins' in storage_data:
                self._pending_storage_origins = storage_data['origins']
                logger.debug("Storage origins data will be applied after page navigation")
                
        except Exception as e:
            logger.warning(f"Could not apply storage state: {e}")
    
    def _apply_page_storage(self, page):
        """Apply localStorage/sessionStorage to page after navigation"""
        try:
            if hasattr(self, '_pending_storage_origins') and self._pending_storage_origins:
                for origin_data in self._pending_storage_origins:
                    origin_url = origin_data.get('origin', '')
                    if page.url.startswith(origin_url) or origin_url == '*':
                        # Apply localStorage
                        if 'localStorage' in origin_data:
                            for item in origin_data['localStorage']:
                                key = item['name']
                                value = item['value']
                                logger.debug(f"Applying localStorage: {key}, {value}")
                                page.evaluate(f"localStorage.setItem('{key}', '{value}')")
                        
                        # Apply sessionStorage  
                        if 'sessionStorage' in origin_data:
                            for item in origin_data['sessionStorage']:
                                key = item['name']
                                value = item['value']
                                page.evaluate(f"sessionStorage.setItem('{key}', '{value}')")
                        
                        logger.debug(f"Applied storage data for origin: {origin_url}")
                        
        except Exception as e:
            # logger.warning(f"Could not apply page storage: {e}")
            raise ValueError(f"Could not apply page storage: {e}")
    
    def get_current_page(self, find_active=False):
        """
        Gets the current page using the sync Playwright API.
        This is useful after human interaction to get the current state.
        
        Args:
            find_active (bool): If True, attempts to find the truly active page by checking
                               which page is currently visible/focused. If False, returns
                               the first available page.
        
        Returns:
            A sync Playwright page object
        """
        if not self.browser:
            raise Exception("Browser not connected. Call _open_chrome_browser() first.")
        
        # Get the default context (same one human interacted with)
        context = self.browser.contexts[0]
        
        if not context.pages:
            # If no pages exist, create one with proper configuration
            page = context.new_page()
            self._configure_page(page)
            return page
        
        if find_active:
            logger.info("Using simple heuristic to detect active page")
            return self._detect_active_page_simple(context)
        
        # Return first page (may or may not be the truly active one)
        page = context.pages[0]
        page.bring_to_front()
        return page
    
    def _detect_active_page_simple(self, context):
        """
        Simple active page detection based on two key criteria:
        1. User activity on the page (clicks, hover, keyboard)
        2. Recent navigation to the page (links, URL bar, tab switch)
        
        NEW APPROACH: Most recent activity wins - time-based prioritization
        """
        # First, set up activity tracking on all pages
        self._setup_activity_tracking(context)
        
        best_page = None
        best_score = 0
        page_results = []
        
        # Find the most recent activity timestamp across ALL pages
        most_recent_activity_time = 0
        
        # First pass: gather all page data
        for i, page in enumerate(context.pages):
            try:
                # Evaluate page activity and navigation signals
                result = page.evaluate("""
                    () => {
                        const now = Date.now();
                        let score = 0;
                        const signals = [];
                        
                        // CRITERION 1: User Activity Detection - TIME-AWARE and PAGE-AWARE
                        
                        // Check for recent mouse clicks - but heavily penalize old clicks
                        if (window.lastClickTime) {
                            const timeSinceClick = now - window.lastClickTime;
                            if (timeSinceClick < 8000) {  // Reduced from 10 seconds
                                let points = 0;
                                
                                // Heavily time-decay click scores to prevent sticky activity
                                if (timeSinceClick < 1000) {
                                    points = 100;  // Very recent
                                } else if (timeSinceClick < 3000) {
                                    points = 60;   // Recent
                                } else if (timeSinceClick < 5000) {
                                    points = 20;   // Getting stale
                                } else {
                                    points = 5;    // Very stale
                                }
                                
                                // CRITICAL: If this page wasn't recently navigated to, 
                                // the click is probably from a previous interaction - penalize heavily
                                const navTiming = performance.getEntriesByType('navigation')[0];
                                if (navTiming) {
                                    const timeSinceLoad = now - (navTiming.navigationStart + navTiming.loadEventEnd);
                                    if (timeSinceLoad > timeSinceClick + 2000) { 
                                        // Click happened long before this page loaded - it's stale
                                        points = Math.round(points * 0.1); // 90% reduction
                                        signals.push(`Click(${Math.round(timeSinceClick/1000)}s,+${points},STALE)`);
                                    } else {
                                        signals.push(`Click(${Math.round(timeSinceClick/1000)}s,+${points})`);
                                    }
                                } else {
                                    signals.push(`Click(${Math.round(timeSinceClick/1000)}s,+${points})`);
                                }
                                score += points;
                            }
                        }
                        
                        // Check for keyboard focus/input - but check for staleness like clicks
                        const activeElement = document.activeElement;
                        const hasInputFocus = activeElement && 
                            ['INPUT', 'TEXTAREA', 'SELECT'].includes(activeElement.tagName);
                        if (hasInputFocus) {
                            let points = 80;
                            
                            // CRITICAL: Check if this input focus is stale (from before navigation)
                            const navTiming = performance.getEntriesByType('navigation')[0];
                            if (navTiming) {
                                const timeSinceLoad = now - (navTiming.navigationStart + navTiming.loadEventEnd);
                                // If page loaded recently but there's no recent typing activity, focus is stale
                                if (timeSinceLoad < 5000) {
                                    // Recent page load - input focus might be stale from previous page
                                    const lastKeyTime = window.lastKeyTime || 0;
                                    const timeSinceKey = lastKeyTime ? now - lastKeyTime : Infinity;
                                    
                                    if (timeSinceKey > timeSinceLoad + 3000) {
                                        // No recent typing but page loaded recently - focus is stale
                                        points = Math.round(points * 0.1); // 90% reduction
                                        signals.push(`InputFocus(+${points},STALE-no-typing)`);
                                    } else if (timeSinceKey < 2000) {
                                        // Recent typing - legitimate input focus
                                        signals.push(`InputFocus(+${points})`);
                                    } else {
                                        // Somewhat recent typing
                                        points = Math.round(points * 0.6); // 40% reduction
                                        signals.push(`InputFocus(+${points},old-typing)`);
                                    }
                                } else {
                                    // Page loaded long ago - input focus should be current
                                    signals.push(`InputFocus(+${points})`);
                                }
                            } else {
                                signals.push(`InputFocus(+${points})`);
                            }
                            score += points;
                        }
                        
                        // Check for mouse hover - with staleness detection
                        const hasHover = document.querySelector(':hover') !== null;
                        if (hasHover) {
                            let points = 15;
                            
                            // STALENESS CHECK: If page loaded recently, hover might be stale from previous page
                            const navTiming = performance.getEntriesByType('navigation')[0];
                            if (navTiming) {
                                const timeSinceLoad = now - (navTiming.navigationStart + navTiming.loadEventEnd);
                                if (timeSinceLoad < 3000) {
                                    // Recent page load - hover is likely stale unless there's recent mouse activity
                                    const lastMouseTime = window.lastMouseTime || 0;
                                    const timeSinceMouse = lastMouseTime ? now - lastMouseTime : Infinity;
                                    
                                    if (timeSinceMouse > timeSinceLoad + 2000) {
                                        // No recent mouse movement but page loaded recently - hover is stale
                                        points = Math.round(points * 0.2); // 80% reduction
                                        signals.push(`Hover(+${points},STALE-no-mouse)`);
                                    } else {
                                        signals.push(`Hover(+${points})`);
                                    }
                                } else {
                                    signals.push(`Hover(+${points})`);
                                }
                            } else {
                                signals.push(`Hover(+${points})`);
                            }
                            score += points;
                        }
                        
                        // REMOVED: Text selection detection - too many false positives
                        // Text selections can be stale, programmatic, or accidental
                        // We'll rely on more reliable signals like clicks and input focus
                        
                        // CRITERION 2: Recent Navigation Detection - HIGHER SCORES
                        
                        // Check for recent tab switch - with staleness detection
                        if (window.lastVisibilityChange && document.visibilityState === 'visible') {
                            const timeSinceVisible = now - window.lastVisibilityChange;
                            if (timeSinceVisible < 6000) {  // 6 seconds for freshness
                                let points = 0;
                                if (timeSinceVisible < 1000) {
                                    points = 120;  // Very recent tab switch
                                } else if (timeSinceVisible < 3000) {
                                    points = 80;   // Recent tab switch
                                } else {
                                    points = 30;   // Getting stale
                                }
                                
                                // STALENESS CHECK: If page loaded after the visibility change, it's stale
                                const navTiming = performance.getEntriesByType('navigation')[0];
                                if (navTiming) {
                                    const timeSinceLoad = now - (navTiming.navigationStart + navTiming.loadEventEnd);
                                    if (timeSinceLoad < timeSinceVisible - 1000) {
                                        // Page loaded well after tab switch - tab switch is stale
                                        points = Math.round(points * 0.1); // 90% reduction
                                        signals.push(`TabSwitch(${Math.round(timeSinceVisible/1000)}s,+${points},STALE-before-nav)`);
                                    } else {
                                        signals.push(`TabSwitch(${Math.round(timeSinceVisible/1000)}s,+${points})`);
                                    }
                                } else {
                                    signals.push(`TabSwitch(${Math.round(timeSinceVisible/1000)}s,+${points})`);
                                }
                                
                                score += points;
                            }
                        }
                        
                        // Check if page was recently loaded - MAJOR signal for new pages
                        const navTiming = performance.getEntriesByType('navigation')[0];
                        if (navTiming) {
                            const timeSinceLoad = now - (navTiming.navigationStart + navTiming.loadEventEnd);
                            
                            // DEBUG: Log navigation timing details
                            console.log(`Navigation timing: start=${navTiming.navigationStart}, end=${navTiming.loadEventEnd}, timeSince=${timeSinceLoad}`);
                            
                            if (timeSinceLoad < 15000) {  // Increased window for testing
                                let points = 0;
                                if (timeSinceLoad < 3000) {
                                    points = 150;  // Very fresh navigation - HIGHEST priority
                                } else if (timeSinceLoad < 8000) {
                                    points = 90;   // Recent navigation  
                                } else {
                                    points = 50;   // Still relatively fresh
                                }
                                score += points;
                                signals.push(`Navigation(${Math.round(timeSinceLoad/1000)}s,+${points})`);
                            } else {
                                console.log(`Navigation too old: ${Math.round(timeSinceLoad/1000)}s`);
                            }
                        } else {
                            console.log(`No navigation timing available`);
                        }
                        
                        // FALLBACK: Basic page age detection - but boost it since navigation detection might be weak
                        if (score === 0) {
                            // If we have no activity signals, check if this is a very recently modified page
                            const pageSetup = window.pageSetupTime || 0;
                            if (pageSetup > 0) {
                                const timeSinceSetup = now - pageSetup;
                                if (timeSinceSetup < 3000) {
                                    score += 100; // Boosted - recent page setup is strong signal
                                    signals.push(`RecentSetup(${Math.round(timeSinceSetup/1000)}s,+100)`);
                                } else if (timeSinceSetup < 8000) {
                                    score += 60;
                                    signals.push(`RecentSetup(${Math.round(timeSinceSetup/1000)}s,+60)`);
                                }
                            }
                        }
                        
                        // Basic browser state - REMOVED hasFocus() due to unreliability
                        const isVisible = document.visibilityState === 'visible';
                        
                        // Return activity timestamps for global comparison
                        const activityTimes = {
                            lastClick: window.lastClickTime || 0,
                            lastKey: window.lastKeyTime || 0,
                            lastMouse: window.lastMouseTime || 0,
                            lastVisibility: window.lastVisibilityChange || 0,
                            pageSetup: window.pageSetupTime || 0
                        };
                        const mostRecentActivity = Math.max(...Object.values(activityTimes));
                        
                        return {
                            score: score,
                            signals: signals,
                            url: window.location.href,
                            title: document.title,
                            isVisible: isVisible,
                            activityTimes: activityTimes,
                            mostRecentActivity: mostRecentActivity
                        };
                    }
                """)
                
                page_results.append({
                    'page': page,
                    'index': i,
                    'score': result.get('score', 0),
                    'signals': result.get('signals', []),
                    'is_visible': result.get('isVisible', False),
                    'url': page.url,
                    'most_recent_activity': result.get('mostRecentActivity', 0),
                    'activity_times': result.get('activityTimes', {})
                })
                
                # Track the most recent activity across all pages
                most_recent_activity_time = max(most_recent_activity_time, result.get('mostRecentActivity', 0))
                    
            except Exception as e:
                logger.debug(f"Page {i} evaluation failed: {e}")
                page_results.append({
                    'page': page,
                    'index': i,
                    'score': 0,
                    'signals': [],
                    'is_visible': False,
                    'url': page.url,
                    'most_recent_activity': 0,
                    'activity_times': {}
                })
        
        # REMOVED: Focus detection entirely - too unreliable in this browser environment
        # Focus API gives false positives consistently across different scenarios
        
        # GLOBAL TIME-BASED PRIORITIZATION: Apply massive penalty to non-recent activity
        logger.debug(f"Most recent activity timestamp across all pages: {most_recent_activity_time}")
        
        for result in page_results:
            if most_recent_activity_time > 0 and result['most_recent_activity'] > 0:
                time_diff = most_recent_activity_time - result['most_recent_activity']
                
                if time_diff > 1000:  # More than 1 second behind the most recent activity
                    # Apply heavy penalty to non-recent activity
                    penalty_factor = max(0.05, 1.0 - (time_diff / 10000))  # 95% penalty if very old
                    old_score = result['score']
                    result['score'] = int(result['score'] * penalty_factor)
                    
                    if old_score != result['score']:
                        result['signals'].append(f"OLD-ACTIVITY-PENALTY(-{old_score - result['score']})")
                        logger.debug(f"Page {result['index']}: Applied time penalty for {time_diff}ms lag: {old_score} -> {result['score']}")
        
        # Find the best page overall
        for result in page_results:
            logger.debug(f"Page {result['index']} ({result['url'][:50]}...): score={result['score']}")
            if result['signals']:
                logger.debug(f"  Signals: {' | '.join(result['signals'])}")
            
            if result['score'] > best_score:
                best_score = result['score']
                best_page = result['page']
        
        # Validate no ties exist (active page should clearly win)
        tied_pages = [r for r in page_results if r['score'] == best_score]
        if len(tied_pages) > 1:
            logger.warning(f"TIE DETECTED! {len(tied_pages)} pages tied with score {best_score}. This indicates scoring needs improvement.")
            for tied in tied_pages:
                logger.warning(f"  Tied page: {tied['index']} - {tied['url'][:50]}... - {tied['signals']}")
        
        if best_page:
            logger.info(f"Active page detected with score {best_score}: {best_page.url}")
            best_page.bring_to_front()
            return best_page
        else:
            logger.warning("No page scored above 0, returning first page")
            page = context.pages[0]
            page.bring_to_front()
            return page
    
    def _setup_activity_tracking(self, context):
        """
        Set up lightweight activity tracking on all pages to detect user interactions
        """
        for i, page in enumerate(context.pages):
            try:
                # Inject minimal tracking script with better error handling
                result = page.evaluate("""
                    () => {
                        try {
                            // Always re-setup to ensure it's current
                            window.activityTrackingEnabled = true;
                            
                            // Store current timestamp for navigation detection
                            if (!window.pageSetupTime) {
                                window.pageSetupTime = Date.now();
                            }
                            
                            // Track mouse clicks with more context
                            document.addEventListener('click', (e) => {
                                window.lastClickTime = Date.now();
                                window.lastMouseTime = Date.now(); // Also update mouse time for hover staleness
                                console.log(`Click tracked at ${window.lastClickTime} on ${window.location.href}`);
                                // Clear any stale text selections
                                setTimeout(() => {
                                    try {
                                        if (window.getSelection) {
                                            window.getSelection().removeAllRanges();
                                        }
                                    } catch(e) {}
                                }, 100);
                            }, true);
                            
                            // Track mouse movement for hover staleness detection
                            document.addEventListener('mousemove', () => {
                                window.lastMouseTime = Date.now();
                            }, { passive: true });
                            
                            // Track keyboard activity with timestamps
                            ['keydown', 'keypress', 'keyup', 'input'].forEach(event => {
                                document.addEventListener(event, () => {
                                    window.lastKeyTime = Date.now();
                                    console.log(`Key activity tracked at ${window.lastKeyTime} on ${window.location.href}`);
                                }, { passive: true, capture: true });
                            });
                            
                            // Track visibility changes (tab switching) 
                            document.addEventListener('visibilitychange', () => {
                                if (document.visibilityState === 'visible') {
                                    window.lastVisibilityChange = Date.now();
                                    console.log(`Visibility change tracked at ${window.lastVisibilityChange} on ${window.location.href}`);
                                }
                            });
                            
                            return { success: true, url: window.location.href };
                        } catch (e) {
                            return { success: false, error: e.toString() };
                        }
                    }
                """)
                
                if result.get('success'):
                    logger.debug(f"Activity tracking injected successfully into page {i}: {result.get('url', 'unknown')[:50]}...")
                else:
                    logger.warning(f"Activity tracking injection failed for page {i}: {result.get('error', 'unknown error')}")
                    
            except Exception as e:
                logger.warning(f"Failed to inject activity tracking into page {i} ({page.url[:50]}...): {e}")
    
    def get_page_info(self, include_page_objects=False):
        """
        Gets information about all open pages.
        Useful for debugging and understanding current browser state after human interaction.
        
        Args:
            include_page_objects (bool): If True, includes the actual page objects in the results
        
        Returns:
            List of dict with page information, optionally including page objects
        """
        if not self.browser:
            raise Exception("Browser not connected. Call _open_chrome_browser() first.")
            
        context = self.browser.contexts[0]
        pages = context.pages
        page_info = []
        
        for i, page in enumerate(pages):
            try:
                info = {
                    'index': i,
                    'url': page.url,
                    'title': page.title(),
                    'is_visible': page.evaluate("!document.hidden") if page.url != 'about:blank' else False
                }
                if include_page_objects:
                    info['page'] = page
            except Exception as e:
                info = {
                    'index': i,
                    'url': page.url if hasattr(page, 'url') else 'unknown',
                    'title': 'error getting title',
                    'is_visible': False,
                    'error': str(e)
                }
                if include_page_objects:
                    info['page'] = page
            page_info.append(info)
        
        return page_info

    
    def close(self):
        """
        Clean up Playwright resources.
        Call this when you're done with the environment to avoid resource leaks.
        """
        # Prevent multiple calls to close
        if hasattr(self, '_closed') and self._closed:
            logger.debug("Environment already closed, skipping cleanup")
            return
        
        self._closed = True
        
        # Close browser first (before stopping playwright)
        # try:
        #     if hasattr(self, 'browser') and self.browser:
        #         self.browser.close()
        #         self.browser = None
        #         logger.info("Browser closed successfully")
        # except Exception as e:
        #     logger.warning(f"Error closing browser: {e}")
        
        # # Stop playwright second (this closes the event loop)
        # try:
        #     if hasattr(self, 'playwright') and self.playwright:
        #         self.playwright.stop()
        #         self.playwright = None
        #         logger.info("Playwright stopped successfully")
        # except Exception as e:
        #     logger.warning(f"Error stopping playwright: {e}")
        # finally:
        if self.provider_name.startswith("remote_"):
            self.provider.stop_container(self.container_name)
        else:
            self.provider.stop_emulator(self.path_to_vm)

    
    def __del__(self):
        """Cleanup when object is garbage collected"""
        try:
            # Only run cleanup if not already closed
            if not hasattr(self, '_closed') or not self._closed:
                self.close()
        except:
            pass  # Ignore errors during cleanup in destructor