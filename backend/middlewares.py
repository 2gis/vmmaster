import asyncio
from concurrent.futures import CancelledError
from aiohttp.errors import ClientDisconnectedError
import logging
from core.exceptions import PlatformException, SessionException
from backend.webdriver import commands, helpers
from backend.webdriver.helpers import selenium_error_response


log = logging.getLogger(__name__)


def is_selenium_request(request):
    return True if "/wd/hub" in request.path else False


def is_api_request(request):
    return True if "/api" in request.path else False


async def selenium_request_check(request):
    if request.method == "POST" and request.path == "/wd/hub/session":
        platform = await helpers.get_platform(request)
        log.debug("Platform %s check..." % platform)
        helpers.check_platform(platform)
    else:
        log.debug("Find session by id...")
        await helpers.get_vmmaster_session(request)


async def request_preprocess(request):
    if is_selenium_request(request):
        log.info("is selenium request")
        await selenium_request_check(request)
    elif is_api_request(request):
        log.debug("api request")


@asyncio.coroutine
def request_check(app, handler):
    @asyncio.coroutine
    async def middleware(request):
        try:
            await request_preprocess(request)
            ret = await handler(request)
        except (ClientDisconnectedError, CancelledError):
            log.error("Client has been disconnected for request %s" % request.path)
            await commands.service_command_send(request, 'CLIENT_DISCONNECTED')
        except PlatformException as exc:
            log.exception('%s' % exc, exc_info=False)
            platform = await helpers.get_platform(request)
            return selenium_error_response("Platform %s not found in available platforms" % platform)
        except SessionException as exc:
            log.exception('%s' % exc, exc_info=False)
            session_id = helpers.get_session_id(request.path)
            return selenium_error_response("Session %s not found in available active sessions" % session_id)
        else:
            return ret
    return middleware
