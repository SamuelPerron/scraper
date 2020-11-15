from bs4 import BeautifulSoup as bs
import requests
from urllib.parse import urlparse
import re
from datetime import datetime
from slugify import slugify
import csv


class Scrapper:
    TARGETS = (
        {
            'name': 'Pages Jaunes',
            'need_to_click': False,
            'links': {
                'home': 'https://www.pagesjaunes.ca/',
                'results': 'https://www.pagesjaunes.ca/search/si/<PAGE_NB>/<KEYWORD>/<REGION>',
                'details': 'https://www.pagesjaunes.ca/bus/'
            },
            'elements': {
                'results_list': ('div', 'class', 'resultList'),
                'results_item': ('div', 'class', 'listing'),
                'item_link': ('a', 'class', 'listing__link'),
                'details': {
                    'name': [('a', 'class', 'listing__name--link')],
                    'address': [('span', 'class', 'listing__address--full')],
                    'phone': [('li', 'class', 'mlr__submenu__item')],
                    'website': (
                        ('li', 'class', 'mlr__item--website'),
                        ('a', 'class', 'mlr__item__cta')
                    ),
                }
            }
        },
    )

    def __init__(self, target, limit, keywords, region):
        self.target = self.find_target_by_name(target)
        self.limit = limit
        self.keywords = keywords
        self.region = region
        self.findings = []


    def find_target_by_name(self, name):
        for target in self.TARGETS:
            if name == target['name']:
                return target
        raise ValueError('Target not supported.')


    def run(self):
        html = self.target['elements']
        for keyword in self.keywords:
            for page in range(self.limit):
                # Access search page
                results_url = self.construct_results_url(keyword)
                r = requests.get(results_url)
                if r.status_code == 200:
                    soup = bs(r.text, 'html.parser')

                    # Get results
                    list_element = html['results_list']
                    item_element = html['results_item']
                    list = soup.find(list_element[0], {list_element[1]: list_element[2]})
                    items = list.find_all(item_element[0], {item_element[1]: item_element[2]})

                    # Save results
                    for item in items:
                        details_url = html['item_link']
                        if self.target['need_to_click']:
                            html = requests.get(item.find(details_url[0], {details_url[1], details_url[2]}))
                            details_soup = bs(html, 'html.parser')
                        else:
                            details_soup = item

                        prospect = Prospect(
                            name=self.find_detail(details_soup, 'name'),
                            keywords=[keyword,],
                            region=self.region,
                            address=self.find_detail(details_soup, 'address'),
                            phone=self.find_detail(details_soup, 'phone'),
                            website=self.find_detail(details_soup, 'website'),
                            source=slugify(self.target['name'])
                        )
                        self.findings.append(prospect)
                        prospect.save_to_file()

                else:
                    raise RuntimeError('Request failed')


    def construct_results_url(self, keyword):
        url = self.target['links']['results'].replace('<PAGE_NB>', '1')
        url = url.replace('<KEYWORD>', keyword)
        url = url.replace('<REGION>', self.region)
        return url


    def find_detail(self, soup, detail_name):
        details = self.target['elements']['details']
        for i, level in enumerate(details[detail_name]):
            level = details[detail_name][i]
            if i == len(details[detail_name]) - 1:
                if soup is not None:
                    detail = soup.find(level[0], {level[1], level[2]})
                else:
                    detail = None
            else:
                soup = soup.find(level[0], {level[1], level[2]})

        if detail is not None:
            if detail_name == 'website':
                return self.parse_distant_url(detail['href'])
            return detail.get_text()

        return None


    def parse_distant_url(self, url):
        parsed = urlparse(f"{self.target['links']['home']}{url}")
        query = parsed.query.replace('%3A', ':')
        query = query.replace('%2F', '/')
        distant = re.findall(r"(http|ftp|https)://([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:/~+#-]*[\w@?^=%&/~+#-])?", query)
        if len(distant) > 0:
            return distant[0][1]
        else:
            return None



class Prospect:
    def __init__(self, name, keywords, region, address, phone, website, source):
        self.name = name.strip() if name else None
        self.keywords = keywords
        self.region = region.strip() if region else None
        self.address = address.strip() if address else None
        self.phone = phone.strip() if phone else None
        self.website = website
        self.source = source


    def __str__(self):
        return self.name


    def save_to_file(self):
        url = f"findings/{datetime.now().strftime('%y-%m-%d')}--{self.source}.csv"
        with open(url, 'a+') as f:
            w = csv.writer(f)
            w.writerow([self.name, self.keywords, self.region, self.address, self.phone, self.website])
