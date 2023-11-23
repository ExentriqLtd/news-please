import socket
import copy
import threading
import logging

import requests
import urllib3
import os
import random
from .response_decoder import decode_response

MAX_FILE_SIZE = 20000000
MIN_FILE_SIZE = 10

LOGGER = logging.getLogger(__name__)

USER_AGENT_LIST = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.71 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.71 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:94.0) Gecko/20100101 Firefox/94.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:94.0) Gecko/20100101 Firefox/94.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:91.0) Gecko/20100101 Firefox/91.0',
    'Opera/9.80 (Windows NT 6.1; WOW64) Presto/2.12.388 Version/12.18',
    'Opera/9.80 (Macintosh; Intel Mac OS X 10.15.7) Presto/2.12.388 Version/12.18',
    'Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.71 Safari/537.36 OPR/81.0.4196.61',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.71 Safari/537.36 OPR/81.0.4196.61',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.71 Safari/537.36 Edg/94.0.992.50',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.71 Safari/537.36 Edg/94.0.992.50',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.71 Safari/537.36 Vivaldi/4.2',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.71 Safari/537.36 Vivaldi/4.2',
]
ua = random.choice(USER_AGENT_LIST)
# customize headers
HEADERS = {
    'Connection': 'close',
    'User-Agent': ua,
}
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_proxy_rotation(proxys: dict, http_port: str, https_port: str, username: str, password:str, is_proxy_https = False):
    """
    Obtains the configuration for proxy rotation.

    Args:
    - proxys (dict): IPs address or URL of the proxy.
    - http_port (str): Port for HTTP connections.
    - https_port (str): Port for HTTPS connections.
    - username (str): Username for proxy authentication.
    - password (str): Password for proxy authentication.

    Returns:
    - dict: A dictionary containing details of the proxy configuration and HTTP/HTTPS ports,
            along with authentication credentials (username and password).
    """
    formatted_proxies = []
    try:
        proxies = proxys.split(',')  
        formatted_proxies = []
        protocol_http = 'http://'
        protocol_https = 'http://'
        if is_proxy_https is True: 
           protocol_https = 'https://'

        for proxy in proxies:
            formatted_proxy_http = f"{protocol_http}{username}:{password}@{proxy}:{http_port}"
            formatted_proxy_https = f"{protocol_https}{username}:{password}@{proxy}:{https_port}"
            obj = {
                "http": formatted_proxy_http,
                "https": formatted_proxy_https,
            }
            formatted_proxies.append(obj)
    except Exception as ex:
        LOGGER.error(ex)
        
    return formatted_proxies


class SimpleCrawler(object):
    _results = {}

    @staticmethod
    def fetch_url(url, timeout=None):
        """
        Crawls the html content of the parameter url and returns the html
        :param url:
        :param timeout: in seconds, if None, the urllib default is used
        :return:
        """
        return SimpleCrawler._fetch_url(url, False, timeout=timeout)

    @staticmethod
    def _fetch_url(url, is_threaded, timeout=None):
        """
        Crawls the html content of the parameter url and saves the html in _results
        :param url:
        :param is_threaded: If True, results will be stored for later processing by the fetch_urls method. Else not.
        :param timeout: in seconds, if None, the urllib default is used
        :return: html of the url
        """
        html_str = None
        # send
        PROXYS = os.getenv('PROXYS_MESH')
        PROXY_HTTP_PORT = os.getenv('PROXY_HTTP_PORT')
        PROXY_HTTPS_PORT = os.getenv('PROXY_HTTPS_PORT')
        PROXY_USERNAME = os.getenv('PROXY_USERNAME')
        PROXY_PASSWORD = os.getenv('PROXY_PASSWORD')
        # Check if all variables exist
        required_variables = [PROXYS, PROXY_USERNAME, PROXY_PASSWORD, PROXY_HTTP_PORT, PROXY_HTTPS_PORT]
        all_variables_exist = all(variable is not None for variable in required_variables)
        proxys = None
        if all_variables_exist:
            proxys_env_rotation = get_proxy_rotation(proxys=PROXYS, http_port=PROXY_HTTP_PORT, https_port=PROXY_HTTPS_PORT, username=PROXY_USERNAME, password=PROXY_PASSWORD)
            proxy_index = random.randint(0, len(proxys_env_rotation) -1)
            proxys = {"http": proxys_env_rotation[proxy_index]['http'], "https": proxys_env_rotation[proxy_index]['https']}
        else:
            LOGGER.info('start without proxymesh: Some or all of the required environment variables are missing.')
        try:
            # read by streaming chunks (stream=True, iter_content=xx)
            # so we can stop downloading as soon as MAX_FILE_SIZE is reached
            LOGGER.debug(f'start with proxymesh:  {str(proxys)}')
            response = requests.get(url, timeout=timeout, verify=False, allow_redirects=True, headers=HEADERS, proxies=proxys)
        except (requests.exceptions.MissingSchema, requests.exceptions.InvalidURL):
            LOGGER.error('malformed URL: %s', url)
        except requests.exceptions.TooManyRedirects:
            LOGGER.error('too many redirects: %s', url)
        except requests.exceptions.SSLError as err:
            LOGGER.error('SSL: %s %s', url, err)
        except (
            socket.timeout, requests.exceptions.ConnectionError,
            requests.exceptions.Timeout, socket.error, socket.gaierror
        ) as err:
            LOGGER.error('connection/timeout error: %s %s', url, err)
        else:
            # safety checks
            if response.status_code != 200:
                LOGGER.error('not a 200 response: %s', response.status_code)
            elif response.text is None or len(response.text) < MIN_FILE_SIZE:
                LOGGER.error('too small/incorrect: %s %s', url, len(response.text))
            elif len(response.text) > MAX_FILE_SIZE:
                LOGGER.error('too large: %s %s', url, len(response.text))
            else:
                html_str = decode_response(response)
        if is_threaded:
            SimpleCrawler._results[url] = html_str
        return html_str

    @staticmethod
    def fetch_urls(urls, timeout=None):
        """
        Crawls the html content of all given urls in parallel. Returns when all requests are processed.
        :param urls:
        :param timeout: in seconds, if None, the urllib default is used
        :return:
        """
        threads = [threading.Thread(target=SimpleCrawler._fetch_url, args=(url, True, timeout)) for url in urls]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        results = copy.deepcopy(SimpleCrawler._results)
        SimpleCrawler._results = {}
        return results
