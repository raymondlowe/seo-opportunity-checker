#!/usr/bin/env python3

# Uses code from https://github.com/raymondlowe/Google-analytics-and-search-console
#

import argparse
from datetime import timedelta
import requests
import requests_cache
import pandas as pd
import datetime
from progress.bar import IncrementalBar
from googleAPIget_service import get_service
from urllib.parse import urlparse
import re
from bs4 import BeautifulSoup as BS

MATCH_ALL = r'.*'


def like(string):
    """
    Return a compiled regular expression that matches the given
    string with any prefix and postfix, e.g. if string = "hello",
    the returned regex matches r".*hello.*"
    """
    string_ = string
    if not isinstance(string_, str):
        string_ = str(string_)
    regex = MATCH_ALL + re.escape(string_) + MATCH_ALL
    return re.compile(regex, flags=re.DOTALL)


def find_by_text(soup, text, tag, **kwargs):
    """
    Find the tag in soup that matches all provided kwargs, and contains the
    text.

    If no match is found, return None.
    If more than one match is found, raise ValueError.
    """
    elements = soup.find_all(tag, **kwargs)
    matches = []
    for element in elements:
        if element.find(text=like(text)):
            matches.append(element)
    return len(matches)


def checkKeywordOnPage(haystack, needle):
    print("Checking for ["+needle+"] in "+haystack)
    try:
        page = requests.get(haystack)
    except:
        print("Fail")
        return -1
    lowerpagetext = page.text.lower()
    lowerneedle = needle.lower()
    result = lowerpagetext.count(lowerneedle)
    print(result)
    return result


def checkKeywordInHTags(haystack, needle):
    print("Checking for ["+needle+"] in H tags of "+haystack)
    try:
        # will be fast as already in requests cache
        page = requests.get(haystack)
    except:
        print("Fail")
        return -1
    soup = BS(page.text.lower())
    lowerneedle = needle.lower()
    result = find_by_text(soup, needle, 'h1') + find_by_text(soup,
                                                             needle, 'h2') + find_by_text(soup, needle, 'h3')
    print(result)
    return result


requests_cache.install_cache('page_cache')


parser = argparse.ArgumentParser()


parser.add_argument(
    "period_days", help="Number of days back to check data", default=7, type=int)
parser.add_argument("-n", "--name", default='check-for-missed-keywords-report.xlsx', type=str,
                    help="File name for final output, default is check-for-missed-keywords-report + the current date. You do NOT need to add file extension")
parser.add_argument("-g", "--googleaccount", type=str, default="", help="Name of a google account; does not have to literally be the account name but becomes a token to access that particular set of secrets. Client secrets will have to be in this a file that is this string concatenated with client_secret.json.  OR if this is the name of a text file then every line in the text file is processed as one user and all results appended together into a file")

args = parser.parse_args()

period_days = args.period_days

dimensionsstring = "page,query"
dimensionsarray = dimensionsstring.split(",")
multidimention = len(dimensionsarray) > 1

dataType = "web"

name = args.name

googleaccountstring = args.googleaccount

if name == 'check-for-missed-keywords-report.xlsx':
    name = 'check-for-missed-keywords-report-' + \
        datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

scope = ['https://www.googleapis.com/auth/webmasters.readonly']

try:
    googleaccountslist = open(googleaccountstring).read().splitlines()
    # remove empty lines
    googleaccountslist = [x.strip() for x in googleaccountslist if x.strip()]
except:
    googleaccountslist = [googleaccountstring]


combinedDF = pd.DataFrame()


for thisgoogleaccount in googleaccountslist:
    print("Processing: " + thisgoogleaccount)
    # Authenticate and construct service.
    service = get_service('webmasters', 'v3', scope,
                          'client_secrets.json', thisgoogleaccount)
    profiles = service.sites().list().execute()
    # profiles is now list

    #print("Len Profiles siteEntry: " + str(len(profiles['siteEntry'])))

    bar = IncrementalBar('Processing', max=len(profiles['siteEntry']))

    bigdf = pd.DataFrame()

    end_date = datetime.datetime.now()
    start_date = end_date - timedelta(days=period_days)

    for item in profiles['siteEntry']:

        bar.next()
        if item['permissionLevel'] != 'siteUnverifiedUser':

            smalldf = pd.DataFrame()

            #print(item['id'] + ',' + start_date + ',' + end_date)
            results = service.searchanalytics().query(
                siteUrl=item['siteUrl'], body={
                    'startDate': start_date.strftime("%Y-%m-%d"),
                    'endDate': end_date.strftime("%Y-%m-%d"),
                    'dimensions': dimensionsarray,
                    'searchType': dataType,
                    'rowLimit': 5000
                }).execute()

            if len(results) == 2:
                # print(results['rows'])
                # print(smalldf)
                smalldf = smalldf.append(results['rows'])
                # print(smalldf)

                if multidimention:
                    # solves key1 reserved word problem
                    smalldf[[
                        'key-1', 'key-2']] = pd.DataFrame(smalldf['keys'].tolist(), index=smalldf.index)
                    smalldf['keys']

                rootDomain = urlparse(item['siteUrl']).hostname
                if rootDomain.find('www.') > 0:
                    rootDomain = rootDomain.replace('www.', '')

                smalldf.insert(0, 'siteUrl', item['siteUrl'])
                smalldf.insert(0, 'rootDomain', rootDomain)
                # print(smalldf)
                if len(bigdf.columns) == 0:
                    bigdf = smalldf.copy()
                else:
                    bigdf = pd.concat([bigdf, smalldf])

                # print(bigdf)
    bar.finish()

    bigdf.reset_index()
    # bigdf.to_json("output.json",orient="records")

    if len(bigdf) > 0:
        bigdf['keys'] = bigdf["keys"].str[0]

        # Got the bigdf now of all the data from this account, so add it into the combined
        combinedDF = pd.concat([combinedDF, bigdf], sort=True)

    # clean up objects used in this pass
    del bigdf
    del profiles
    del service


if len(combinedDF) > 0:
    if googleaccountstring > "":
        name = googleaccountstring + "-" + name

    combinedDF['KeywordFound'] = -1
    combinedDF['KeywordFoundinHTags'] = -1
    combinedDF['KeywordFoundinTitle'] = -1
    combinedDF.reset_index()

    lowerpagetext = ''
    lowerneedle = ''
    result = ''

    for i in range(len(combinedDF)):

        haystack = combinedDF['key-1'].values[i]
        needle = combinedDF['key-2'].values[i]

        page = None
        print("Checking for ["+needle+"] in "+haystack)
        try:
            page = requests.get(haystack)
        except:
            print("Fail")

        if page is None:
            result = -1
        else:
            lowerpagetext = page.text.lower()
            lowerneedle = needle.lower()
            result = lowerpagetext.count(lowerneedle)
        print(result)

        combinedDF['KeywordFound'].values[i] = result
        if result > 0:
            # it exists (less common case), now find out where

            print("Checking for ["+needle+"] in DOM tags of "+haystack)

            soup = BS(lowerpagetext)

            combinedDF['KeywordFoundinHTags'].values[i] = find_by_text(
                soup, needle, 'h1') + find_by_text(soup, needle, 'h2') + find_by_text(soup, needle, 'h3')

            combinedDF['KeywordFoundinTitle'].values[i] = soup.title.string.lower().count(
                lowerneedle)

    with pd.ExcelWriter(name + '.xlsx') as writer:
        combinedDF.to_excel(writer, sheet_name='data')

        print("finished and outputed to excel file")
else:
    print("nothing found")


print("--done--")
