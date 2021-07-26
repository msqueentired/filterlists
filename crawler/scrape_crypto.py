#!/usr/local/bin/python
from datetime import datetime
from time import perf_counter
from urllib.parse import urljoin, urlparse
import os
import re
import shutil
from bs4 import BeautifulSoup
from requests_cache import CachedSession
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

DEBUG_MODE = False

if not DEBUG_MODE:
    if os.path.exists('redirects.sqlite'):
        os.remove('redirects.sqlite')
    if os.path.exists('http_cache/'):
        shutil.rmtree('http_cache/')

session = CachedSession(backend='filesystem', namespace='my-cache')
retries = Retry(total=10,
                backoff_factor=2,
                status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))


def format_url(input_url: str) -> str:
    '''Make the URLs into the regex I need'''
    regex_string = re.compile(r'^(app|dex|docs|exchange|info|'
                              r'international|marketplace|pro|swap|'
                              r'trade|www)\.',
                              re.IGNORECASE)
    __tmp_url = urlparse(input_url).netloc
    __tmp_url = regex_string.sub('', __tmp_url)
    # __tmp_url = __tmp_url.replace('.','\.')
    # __tmp_url = ('(\.|^){}$').format(__tmp_url)
    return __tmp_url


def scrape_cmc(map_page: str, ul_class: str) -> list:
    '''Grab external links from CMC'''
    caught_domains = set()
    page_number = 1  # Shitty Pagination
    while True:
        sitemap = session.get(f'https://coinmarketcap.com'
                              f'/sitemap/{map_page}/?page={page_number}')
        if sitemap.status_code == 404:  # Catches the shitty pagination
            break
        soup_main = BeautifulSoup(sitemap.text, 'html.parser').find(
            'ul', class_='coin-list').find_all('a')
        if len(soup_main) == 0:  # Also catches the shitty pagination
            break
        print(
            f'Found {len(soup_main)} {map_page.upper()} results on page {page_number}. ')
        # [soup_main[i] for i in range(0, 3)]:
        for subpage in soup_main:
            subpage_url = urljoin('https://coinmarketcap.com',
                                  subpage.get('href'))
            temp_page = session.get(subpage_url)
            if temp_page.status_code == 429:
                print("Rate limited, backing off...")
            temp_soup = BeautifulSoup(temp_page.text,
                                      'html.parser').find('ul',
                                                          class_=ul_class)
            try:
                outbound_url = temp_soup.find('a').get('href')
                caught_domains.add(format_url(outbound_url))
            except AttributeError:  # Ignore that stupid Pepe NFT page
                pass
            print(round((soup_main.index(subpage))/len(soup_main)
                        * 100, 2), f'% complete with page {page_number}.     ', end='\r')
        page_number += 1

    print()
    print("Purging false positives...")
    # This removes known false positives from the list
    false_positives = re.compile(r'^.*(google|discord|github|'
                                r'gitlab|gitter|telegram|(^t\.me)).*')
    for item in caught_domains:
        if false_positives.match(item):
            caught_domains.discard(item)
    print("Done!")
    return list(caught_domains)


with open('../lists/crypto.txt', 'w+') as crypto_txt:
    start_time = datetime.now()
    tic = perf_counter()
    exchange_list = scrape_cmc('exchanges',
                               'cmc-details-panel-links')
    crypto_list = scrape_cmc('cryptocurrencies',
                             'content___MhX1h')
    exchange_list.sort()
    crypto_list.sort()
    toc = perf_counter()
    for url in exchange_list:
        crypto_txt.write(f'{str(url)}\n')

    for url in crypto_list:
        crypto_txt.write(f'{str(url)}\n')

    crypto_txt.close()
